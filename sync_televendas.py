"""
sync_televendas.py - v4
========================
Sincroniza todos os dias úteis do mês. Protege dados reais — nunca
sobrescreve um valor positivo com R$0 de captura falha.

Lógica:
  1. Busca Supabase: quais (data, operador) existem e com qual valor
  2. Fila = sem dados + dias com R$0 (possível falha anterior) + hoje
  3. Movere: se capturou HTML → salva o valor real
             se não capturou → PULA o dia (não sobrescreve nada)
             se é hoje e não capturou → salva R$0 (sem vendas ainda)
"""

import asyncio
import os
import sys
from datetime import datetime, date, timedelta, timezone
from calendar import monthrange
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import httpx

TZ_SP = timezone(timedelta(hours=-3))

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
    total = monthrange(ano, mes)[1]
    dias = []
    for d in range(1, total + 1):
        dt = date(ano, mes, d)
        if dt > ate_hoje:
            break
        if dt.weekday() <= 5:
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

async def buscar_existentes(mes_ini: str, mes_fim: str) -> dict:
    """
    Retorna dict {(data_ref, operador_codigo): valor_venda} para o mês.
    Inclui tanto registros com valor positivo quanto R$0.
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/vendas_televendas"
        f"?select=data_ref,operador_codigo,valor_venda"
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
                result = {}
                for row in r.json():
                    chave = (row['data_ref'], str(row['operador_codigo']))
                    result[chave] = float(row.get('valor_venda') or 0)
                return result
    except Exception as e:
        print(f"  ⚠️  Erro ao consultar Supabase: {e}")
    return {}

async def salvar_supabase(operador: dict, data_ref: str, dados: dict, force_zero: bool = False):
    VALOR_KEY = 'Valor Total das Notas Emitidas'
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
    await page.goto(RELATORIO_URL, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(1500)

    # IDs exatos descobertos pelo diagnóstico no GitHub Actions:
    # VE  → id contém "idvisaoempresarial"  (já vem com value='1' por padrão)
    # INI → id contém "cdtaini"
    # FIM → id contém "cdtafim"
    # OP  → id contém "idcliforoperador"

    # 1. Visão Empresarial = 1 (garante mesmo se vier vazio)
    await page.evaluate("""() => {
        const inp = document.querySelector('[id*="idvisaoempresarial"]');
        if (inp && (!inp.value || inp.value.trim() === '')) {
            inp.value = '1';
            ['input','change','blur'].forEach(e =>
                inp.dispatchEvent(new Event(e, {bubbles:true})));
        }
    }""")
    await page.wait_for_timeout(600)

    # 2. Data Inicial
    for sel in ['[id*="cdtaini"]','[name*="cdtaini"]',
                'input[id*="dtaini"]','input[id*="DataIni"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click(click_count=3)
                await el.fill(data_fmt)
                await el.press('Tab')
                break
        except Exception:
            pass
    await page.wait_for_timeout(400)

    # 3. Data Final
    for sel in ['[id*="cdtafim"]','[name*="cdtafim"]',
                'input[id*="dtafim"]','input[id*="DataFim"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click(click_count=3)
                await el.fill(data_fmt)
                await el.press('Tab')
                break
        except Exception:
            pass
    await page.wait_for_timeout(400)

    # 4. Operador
    for sel in ['[id*="idcliforoperador"]','input[id*="operador"]',
                'input[id*="Operador"]','input[name*="operador"]']:
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

    # 5. Checkboxes e rádio
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

    # 6. Formato HTML
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

    # Preenche formulário PRIMEIRO (inclui page.goto que pode disparar
    # ImpressaoRelatorio com parâmetros da sessão anterior — queremos ignorar).
    await preencher_formulario(page, operador, data_fmt)

    # Aguarda a rede estabilizar para garantir que qualquer ImpressaoRelatorio
    # disparado pelo carregamento inicial já completou antes do listener subir.
    try:
        await page.wait_for_load_state('networkidle', timeout=8000)
    except Exception:
        pass

    # Listener ativado DEPOIS do carregamento inicial, para capturar
    # apenas a resposta real gerada pelo clique em Executar.
    page.on('response', on_resp)

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

    todos_dias = dias_uteis_mes(ano, mes, hoje)
    print(f"  Dias úteis até hoje : {len(todos_dias)}  ({todos_dias[0]} → {todos_dias[-1]})")

    # Busca existentes COM valores (não apenas se existe)
    existentes = await buscar_existentes(mes_ini, mes_fim)
    print(f"  Registros Supabase  : {len(existentes)}")

    # Fila:
    #   - dias sem registro algum → precisa capturar
    #   - dias com R$0  → pode ser falha anterior, retenta
    #   - hoje          → sempre atualiza
    fila = []
    for dia in todos_dias:
        for op in OPERADORES:
            chave = (dia, op['codigo'])
            valor_existente = existentes.get(chave)
            eh_hoje = (dia == data_hoje)

            if valor_existente is None:       # nunca capturado
                fila.append((dia, op))
            elif valor_existente == 0.0:      # pode ser falha → retenta
                fila.append((dia, op))
            elif eh_hoje:                     # hoje → refresh sempre
                fila.append((dia, op))
            # else: tem valor > 0 e não é hoje → mantém como está

    print(f"  Queries a executar  : {len(fila)}\n")

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
        qtd_skip = 0

        for i, (dia, op) in enumerate(fila):
            data_br  = datetime.strptime(dia, '%Y-%m-%d').strftime('%d/%m/%Y')
            eh_hoje  = (dia == data_hoje)
            chave    = (dia, op['codigo'])
            valor_anterior = existentes.get(chave, None)

            print(f"  [{i+1:>3}/{len(fila)}] {data_br}  {op['nome']}…")
            try:
                html = await buscar_relatorio(page, op, dia)

                if html:
                    # HTML capturado → salva o valor real
                    dados = parse_report_html(html)
                    st, v = await salvar_supabase(op, dia, dados)
                    emoji = "✅" if st in (200, 201) else "⚠️"
                    print(f"    {emoji}  R$ {v:>12,.2f}  (Supabase {st})")
                    if eh_hoje:
                        total_hoje += v
                    qtd_ok += 1

                elif eh_hoje:
                    # Hoje sem vendas ainda → salva R$0
                    st, _ = await salvar_supabase(op, dia, {}, force_zero=True)
                    print(f"    —   R$ 0,00  (sem vendas hoje — Supabase {st})")

                else:
                    # Dia passado sem HTML → NÃO sobrescreve dado existente
                    if valor_anterior and valor_anterior > 0:
                        print(f"    🔒  Sem HTML — mantendo R$ {valor_anterior:,.2f} existente")
                    else:
                        print(f"    ⚠️  Sem HTML — pulando (sem dado real para proteger)")
                    qtd_skip += 1

            except Exception as e:
                print(f"    ❌  Erro: {e}")
                qtd_skip += 1

            # Re-login a cada 25 queries
            if (i + 1) % 25 == 0 and (i + 1) < len(fila):
                print("\n  🔁  Re-login para manter sessão…\n")
                try:
                    await login(page)
                except Exception:
                    pass

        await browser.close()

    print(f"\n{'─'*45}")
    print(f"  Capturados : {qtd_ok}/{len(fila)}")
    print(f"  Pulados    : {qtd_skip}/{len(fila)}")
    if total_hoje > 0:
        print(f"  Total hoje : R$ {total_hoje:,.2f}")
    print(f"{'─'*45}\n")

if __name__ == '__main__':
    asyncio.run(main())
