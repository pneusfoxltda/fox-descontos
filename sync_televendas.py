"""
sync_televendas.py - v3
========================
Sincroniza TODOS os dias úteis do mês atual para os 4 operadores.

Lógica:
  1. Calcula dias úteis (seg-sáb) do mês até hoje
  2. Consulta Supabase para ver quais (data, operador) já existem
  3. Executa no Movere apenas os que faltam + sempre atualiza hoje
  4. Salva R$0 quando não há vendas no dia (evita re-consulta)

Credenciais via variáveis de ambiente:
  MOVERE_USER  — login do Movere
  MOVERE_PASS  — senha do Movere
"""

import asyncio
import os
import sys
from datetime import datetime, date, timedelta, timezone
from calendar import monthrange
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import httpx

# ─── Timezone Brasília ─────────────────────────────────────────────────────────
TZ_SP = timezone(timedelta(hours=-3))

# ─── Configurações ─────────────────────────────────────────────────────────────
MOVERE_USER = os.environ.get("MOVERE_USER", "")
MOVERE_PASS = os.environ.get("MOVERE_PASS", "")

SUPABASE_URL = "https://dxwkiaxpygibzmwzvcuz.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR4d2tpYXhweWdpYnptd3p2Y3V6Iiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3NzczMTE3NzcsImV4cCI6MjA5Mjg4Nzc3N30"
    ".mVbUlLaRCI5OMf539Ehjt-XpfAY-wjr7_WCzPsgVvp0"
)

OPERADORES = [
    {"codigo": "294862", "nome": "Graziele Garcia"},
    {"codigo": "299497", "nome": "Kessya Marques"},
    {"codigo": "286240", "nome": "Sabrina Rocha"},
    {"codigo": "298172", "nome": "Ana Clara"},
]

MOVERE_BASE   = "https://foxpneus.moveresoftware.com"
RELATORIO_URL = f"{MOVERE_BASE}/foxpneus/rotinas/005/rotina553.aspx"

# Classes CSS do relatório Movere
LABEL_CLS = [
    'a5119','a5128','a5137','a5146','a5155','a5164','a5173','a5182',
    'a5191','a5200','a5209','a5218','a5227','a5236','a5245','a5261'
]
VALUE_CLS = [
    'a5123','a5132','a5141','a5150','a5159','a5168','a5177','a5186',
    'a5195','a5204','a5213','a5222','a5231','a5240','a5249','a5265'
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def dias_uteis_mes(ano: int, mes: int, ate_hoje: date) -> list:
    """Dias úteis (seg-sáb) do mês até ate_hoje, como strings 'YYYY-MM-DD'."""
    total = monthrange(ano, mes)[1]
    dias = []
    for d in range(1, total + 1):
        dt = date(ano, mes, d)
        if dt > ate_hoje:
            break
        if dt.weekday() <= 5:   # 0=seg … 5=sáb; 6=dom fica de fora
            dias.append(dt.strftime('%Y-%m-%d'))
    return dias

def parse_report_html(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    data = {}
    label = None
    for div in soup.find_all('div'):
        cls_list = div.get('class', [])
        cls = cls_list[0] if cls_list else ''
        text = div.get_text(strip=True)
        if not text:
            continue
        if cls in LABEL_CLS:
            label = text
        elif cls in VALUE_CLS and label:
            data[label] = text
            label = None
    return data

def parse_br_number(s: str) -> float:
    try:
        return float(s.replace('.', '').replace(',', '.'))
    except Exception:
        return 0.0

# ─── Supabase ─────────────────────────────────────────────────────────────────

async def buscar_existentes(mes_ini: str, mes_fim: str) -> set:
    """Retorna set de (data_ref, operador_codigo) que já existem no Supabase."""
    url = (
        f"{SUPABASE_URL}/rest/v1/vendas_televendas"
        f"?select=data_ref,operador_codigo"
        f"&data_ref=gte.{mes_ini}&data_ref=lte.{mes_fim}"
    )
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                return {(row['data_ref'], row['operador_codigo']) for row in r.json()}
    except Exception as e:
        print(f"  ⚠️  Erro ao consultar Supabase: {e}")
    return set()

async def salvar_supabase(operador: dict, data_ref: str, dados: dict, force_zero: bool = False):
    VALOR_KEY = 'Valor Venda Líquida (Venda - Devolução)'
    valor = 0.0 if force_zero else parse_br_number(dados.get(VALOR_KEY, '0'))

    qtd_clientes = 0
    qtd_itens    = 0
    if not force_zero:
        qtd_cli = dados.get('Quantidade Clientes Atendidos', '0').replace('.', '')
        qtd_ite = dados.get('Quantidade Itens Atendidos',   '0').replace('.', '')
        qtd_clientes = int(qtd_cli) if qtd_cli.isdigit() else 0
        qtd_itens    = int(qtd_ite) if qtd_ite.isdigit() else 0

    payload = {
        'data_ref':        data_ref,
        'operador_codigo': operador['codigo'],
        'operador_nome':   operador['nome'],
        'valor_venda':     valor,
        'qtd_clientes':    qtd_clientes,
        'qtd_itens':       qtd_itens,
        'atualizado_em':   datetime.now(TZ_SP).isoformat(),
    }
    headers = {
        'apikey':        SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type':  'application/json',
        'Prefer':        'resolution=merge-duplicates,return=minimal',
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/vendas_televendas",
            headers=headers,
            json=payload,
        )
        return r.status_code, valor

# ─── Login ────────────────────────────────────────────────────────────────────

async def login(page):
    print("  🔑  Login no Movere…")
    await page.goto(f"{MOVERE_BASE}/foxpneus/default.aspx",
                    wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(2000)

    for sel in ['#txtLogin', 'input[name="txtLogin"]', 'input[type="text"]:visible']:
        try:
            if await page.locator(sel).count() > 0:
                await page.fill(sel, MOVERE_USER); break
        except Exception:
            pass

    for sel in ['#txtSenha', 'input[name="txtSenha"]', 'input[type="password"]:visible']:
        try:
            if await page.locator(sel).count() > 0:
                await page.fill(sel, MOVERE_PASS); break
        except Exception:
            pass

    for sel in ['#btnEntrar', 'input[value="Entrar"]',
                'button:has-text("Entrar")', 'input[type="submit"]:visible']:
        try:
            if await page.locator(sel).count() > 0:
                await page.click(sel); break
        except Exception:
            pass

    await page.wait_for_load_state('networkidle', timeout=20000)
    print("  ✅  Login OK!")

# ─── Preencher formulário ─────────────────────────────────────────────────────

async def preencher_formulario(page, operador: dict, data_fmt: str):
    """Preenche TODOS os campos obrigatórios do relatório 553."""
    await page.goto(RELATORIO_URL, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(1500)

    # 1. Visão Empresarial = 1 (REDE FOX PNEUS)
    await page.evaluate("""() => {
        for (const td of document.querySelectorAll('td, div')) {
            if (td.childElementCount === 0 && td.innerText &&
                td.innerText.trim() === 'Visão Empresarial') {
                const row = td.closest('tr');
                if (row) {
                    const inp = row.querySelector('input[type="text"]');
                    if (inp && (!inp.value || inp.value.trim() === '')) {
                        inp.value = '1';
                        inp.dispatchEvent(new Event('change', {bubbles:true}));
                        inp.dispatchEvent(new Event('blur',   {bubbles:true}));
                    }
                }
                break;
            }
        }
    }""")
    await page.wait_for_timeout(900)

    # 2. Data Inicial
    for sel in ['#dtaini','input[name="dtaini"]','input[id*="dtaini"]','input[id*="DataIni"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.triple_click(); await el.fill(data_fmt); await el.press('Tab')
                break
        except Exception:
            pass
    await page.wait_for_timeout(400)

    # 3. Data Final
    for sel in ['#dtafim','input[name="dtafim"]','input[id*="dtafim"]','input[id*="DataFim"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.triple_click(); await el.fill(data_fmt); await el.press('Tab')
                break
        except Exception:
            pass
    await page.wait_for_timeout(400)

    # 4. Operador
    for sel in ['input[id*="operador"]','input[id*="Operador"]',
                'input[id*="cliforOperador"]','input[name*="operador"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.clear()
                await el.type(operador['codigo'], delay=80)
                await page.wait_for_timeout(1200)
                for drop in ['li.autocomplete-result','.dropdown-item','[class*="suggest"]']:
                    try:
                        item = page.locator(drop).first
                        if await item.count() > 0:
                            await item.click(); break
                    except Exception:
                        pass
                await el.press('Tab')
                await page.wait_for_timeout(600)
                break
        except Exception:
            pass

    # 5. Checkboxes e rádio (Listar resumo, Vendedor, Filtrar base)
    await page.evaluate("""() => {
        function check(texto, tipo, valor) {
            for (const el of document.querySelectorAll('td,label,span,div')) {
                if (el.childElementCount === 0 && el.innerText &&
                    el.innerText.trim().replace(/[?]/g,'').includes(texto)) {
                    let inp = el.querySelector('input[type="'+tipo+'"]')
                           || (() => { const row = el.closest('tr')||el.parentElement;
                                       return row && row.querySelector('input[type="'+tipo+'"]'); })()
                           || (() => { const n = el.nextElementSibling;
                                       return n && n.querySelector('input[type="'+tipo+'"]'); })();
                    if (inp) { inp.checked = valor;
                               inp.dispatchEvent(new Event('change',{bubbles:true})); return true; }
                }
            }
            return false;
        }
        check('Listar somente resumo',       'checkbox', true);
        check('Filtrar somente base de venda','checkbox', true);

        // Radio Agrupamento = Vendedor
        for (const r of document.querySelectorAll('input[type="radio"]')) {
            const tr = r.closest('tr');
            if (tr && tr.innerText.includes('Agrupamento')) {
                const p = r.parentElement;
                if (p && p.innerText.trim() === 'Vendedor') {
                    r.checked = true;
                    r.dispatchEvent(new Event('change',{bubbles:true}));
                    break;
                }
            }
        }
    }""")
    await page.wait_for_timeout(400)

    # 6. Formato = Visualização HTML
    try:
        for sel_el in await page.query_selector_all('select'):
            for opt in await sel_el.query_selector_all('option'):
                txt = await opt.inner_text()
                if 'HTML' in txt or 'Visualiza' in txt:
                    await sel_el.select_option(value=await opt.get_attribute('value'))
                    break
    except Exception:
        pass
    await page.wait_for_timeout(300)

# ─── Capturar relatório ───────────────────────────────────────────────────────

async def buscar_relatorio(page, operador: dict, data_iso: str) -> str | None:
    html_cap = []
    data_fmt = datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')

    async def on_resp(response):
        if 'ImpressaoRelatorio' in response.url and response.status == 200:
            ct = response.headers.get('content-type', '')
            if 'html' in ct.lower():
                try:
                    body = await response.text()
                    if 'a5119' in body or 'Valor Venda' in body:
                        html_cap.append(body)
                except Exception:
                    pass

    page.on('response', on_resp)
    await preencher_formulario(page, operador, data_fmt)

    for sel in ['input[value="Executar"]','#btnExecutar',
                'button:has-text("Executar")','input[type="submit"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click(); break
        except Exception:
            pass

    for _ in range(40):
        if html_cap: break
        await page.wait_for_timeout(500)

    page.remove_listener('response', on_resp)
    return html_cap[0] if html_cap else None

# ─── Main ──────────────────────────────────────────────────────────────────────

async def main():
    if not MOVERE_USER or not MOVERE_PASS:
        print("❌  MOVERE_USER / MOVERE_PASS não definidos!")
        sys.exit(1)

    agora_sp  = datetime.now(TZ_SP)
    hoje      = agora_sp.date()
    ano, mes  = hoje.year, hoje.month
    data_hoje = hoje.strftime('%Y-%m-%d')
    mes_ini   = f"{ano}-{mes:02d}-01"
    mes_fim   = f"{ano}-{mes:02d}-31"

    print(f"\n🔄  Sync Televendas — {agora_sp.strftime('%d/%m/%Y %H:%M')} (Brasília)\n")

    # Dias úteis do mês até hoje
    todos_dias = dias_uteis_mes(ano, mes, hoje)
    print(f"  Dias úteis até hoje: {len(todos_dias)}  ({todos_dias[0]} → {todos_dias[-1]})")

    # Registros já existentes no Supabase
    existentes = await buscar_existentes(mes_ini, mes_fim)
    print(f"  Registros no Supabase: {len(existentes)}\n")

    # Fila: dias faltantes + sempre atualiza hoje
    fila = []
    for dia in todos_dias:
        for op in OPERADORES:
            if (dia, op['codigo']) not in existentes or dia == data_hoje:
                fila.append((dia, op))

    print(f"  Queries a executar: {len(fila)}\n")

    if not fila:
        print("  ✅  Tudo já atualizado.\n")
        return

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
        )
        page = await context.new_page()

        try:
            await login(page)
        except Exception as e:
            print(f"❌  Erro no login: {e}")
            await browser.close()
            return

        total_hoje = 0
        qtd_ok = 0

        for i, (dia, op) in enumerate(fila):
            data_br = datetime.strptime(dia, '%Y-%m-%d').strftime('%d/%m/%Y')
            print(f"  [{i+1:>3}/{len(fila)}] {data_br}  {op['nome']}…")
            try:
                html = await buscar_relatorio(page, op, dia)
                if html:
                    dados  = parse_report_html(html)
                    st, v  = await salvar_supabase(op, dia, dados)
                    emoji  = "✅" if st in (200, 201) else "⚠️"
                    print(f"    {emoji}  R$ {v:>12,.2f}  (Supabase {st})")
                    if dia == data_hoje:
                        total_hoje += v
                    qtd_ok += 1
                else:
                    # Sem vendas neste dia → salva R$ 0 para não re-consultar
                    st, _  = await salvar_supabase(op, dia, {}, force_zero=True)
                    print(f"    —   R$ 0,00  (sem dados — Supabase {st})")
            except Exception as e:
                print(f"    ❌  Erro: {e}")

            # Re-login a cada 25 queries para manter sessão ativa
            if (i + 1) % 25 == 0 and (i + 1) < len(fila):
                print("\n  🔁  Re-login para manter sessão…\n")
                try:
                    await login(page)
                except Exception:
                    pass

        await browser.close()

    print(f"\n{'─'*45}")
    print(f"  Registros salvos : {qtd_ok}/{len(fila)}")
    if total_hoje > 0:
        print(f"  Total hoje       : R$ {total_hoje:,.2f}")
    print(f"{'─'*45}\n")

if __name__ == '__main__':
    asyncio.run(main())
