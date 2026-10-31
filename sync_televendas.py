"""
sync_televendas.py
==================
Busca as vendas do dia dos 4 operadores de televendas no Movere ERP
e salva no Supabase para o televendas.html exibir em tempo real.

Credenciais via variáveis de ambiente:
  MOVERE_USER  — login do Movere
  MOVERE_PASS  — senha do Movere
"""

import asyncio
import os
import sys
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import httpx

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

# ─── Classes CSS do relatório HTML do Movere ──────────────────────────────────
LABEL_CLS = [
    'a5119','a5128','a5137','a5146','a5155','a5164','a5173','a5182',
    'a5191','a5200','a5209','a5218','a5227','a5236','a5245','a5261'
]
VALUE_CLS = [
    'a5123','a5132','a5141','a5150','a5159','a5168','a5177','a5186',
    'a5195','a5204','a5213','a5222','a5231','a5240','a5249','a5265'
]

# ─── Parser do HTML do relatório ──────────────────────────────────────────────

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

# ─── Salvar no Supabase ────────────────────────────────────────────────────────

async def salvar_supabase(operador: dict, data_ref: str, dados: dict):
    VALOR_KEY = 'Valor Venda Líquida (Venda - Devolução)'
    valor = parse_br_number(dados.get(VALOR_KEY, '0'))

    qtd_cli_str = dados.get('Quantidade Clientes Atendidos', '0').replace('.', '')
    qtd_ite_str = dados.get('Quantidade Itens Atendidos', '0').replace('.', '')
    qtd_clientes = int(qtd_cli_str) if qtd_cli_str.isdigit() else 0
    qtd_itens    = int(qtd_ite_str) if qtd_ite_str.isdigit() else 0

    payload = {
        'data_ref':        data_ref,
        'operador_codigo': operador['codigo'],
        'operador_nome':   operador['nome'],
        'valor_venda':     valor,
        'qtd_clientes':    qtd_clientes,
        'qtd_itens':       qtd_itens,
        'atualizado_em':   datetime.now().isoformat(),
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

# ─── Automação do Movere ───────────────────────────────────────────────────────

async def login(page):
    print("  Abrindo Movere...")
    await page.goto(f"{MOVERE_BASE}/foxpneus/default.aspx", wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(2000)

    for sel in ['#txtLogin', 'input[name="txtLogin"]', 'input[type="text"]:visible']:
        try:
            if await page.locator(sel).count() > 0:
                await page.fill(sel, MOVERE_USER)
                break
        except Exception:
            pass

    for sel in ['#txtSenha', 'input[name="txtSenha"]', 'input[type="password"]:visible']:
        try:
            if await page.locator(sel).count() > 0:
                await page.fill(sel, MOVERE_PASS)
                break
        except Exception:
            pass

    for sel in ['#btnEntrar', 'input[value="Entrar"]', 'button:has-text("Entrar")', 'input[type="submit"]:visible']:
        try:
            if await page.locator(sel).count() > 0:
                await page.click(sel)
                break
        except Exception:
            pass

    await page.wait_for_load_state('networkidle', timeout=20000)
    print("  Login OK!")


async def preencher_formulario(page, operador: dict, data_fmt: str):
    """
    Preenche todos os campos do relatório 553 via JavaScript + Playwright.
    Garante: Visão Empresarial=REDE FOX PNEUS, datas, operador,
             Listar somente resumo, Agrupamento=Vendedor,
             Filtrar somente base de venda, Formato=HTML.
    """

    await page.goto(RELATORIO_URL, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(2000)

    # ── 1. Visão Empresarial = "1" (REDE FOX PNEUS) ──────────────────────────
    # Busca o campo pelo texto do label na mesma linha
    await page.evaluate("""() => {
        const tds = [...document.querySelectorAll('td, div')];
        for (const td of tds) {
            if (td.childElementCount === 0 && td.innerText &&
                td.innerText.trim() === 'Visão Empresarial') {
                const row = td.closest('tr');
                if (row) {
                    const input = row.querySelector('input[type="text"]');
                    if (input && (!input.value || input.value.trim() === '')) {
                        input.value = '1';
                        input.dispatchEvent(new Event('change', {bubbles:true}));
                        input.dispatchEvent(new Event('blur',   {bubbles:true}));
                    }
                }
                break;
            }
        }
    }""")
    await page.wait_for_timeout(1200)

    # ── 2. Data Inicial ───────────────────────────────────────────────────────
    data_preenchida = False
    for sel in ['#dtaini', 'input[name="dtaini"]', 'input[id*="dtaini"]',
                'input[id*="DataIni"]', 'input[id*="dataini"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.triple_click()
                await el.fill(data_fmt)
                await el.press('Tab')
                data_preenchida = True
                break
        except Exception:
            pass

    if not data_preenchida:
        # Fallback via JS: primeiro input de data (rosa/obrigatório)
        await page.evaluate(f"""() => {{
            const inputs = [...document.querySelectorAll('input[type="text"]')];
            for (const inp of inputs) {{
                const style = window.getComputedStyle(inp);
                if (style.backgroundColor && style.backgroundColor.includes('255')) {{
                    inp.value = '{data_fmt}';
                    inp.dispatchEvent(new Event('change', {{bubbles:true}}));
                    inp.dispatchEvent(new Event('blur',   {{bubbles:true}}));
                    break;
                }}
            }}
        }}""")
    await page.wait_for_timeout(500)

    # ── 3. Data Final ─────────────────────────────────────────────────────────
    for sel in ['#dtafim', 'input[name="dtafim"]', 'input[id*="dtafim"]',
                'input[id*="DataFim"]', 'input[id*="datafim"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.triple_click()
                await el.fill(data_fmt)
                await el.press('Tab')
                break
        except Exception:
            pass
    await page.wait_for_timeout(500)

    # ── 4. Operador ───────────────────────────────────────────────────────────
    for sel in ['input[id*="operador"]', 'input[id*="Operador"]',
                'input[id*="cliforOperador"]', 'input[name*="operador"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.clear()
                await el.type(operador['codigo'], delay=80)
                await page.wait_for_timeout(1200)
                # Fecha autocomplete se aparecer
                for drop_sel in ['li.autocomplete-result', '.dropdown-item',
                                  '[class*="suggest"]', 'li[class*="auto"]']:
                    try:
                        item = page.locator(drop_sel).first
                        if await item.count() > 0:
                            await item.click()
                            break
                    except Exception:
                        pass
                await el.press('Tab')
                await page.wait_for_timeout(800)
                break
        except Exception:
            pass

    # ── 5. Checkboxes e radio via JavaScript ──────────────────────────────────
    await page.evaluate("""() => {
        // --- Função auxiliar ---
        function checkInputNearText(texto, tipo='checkbox', valor=true) {
            const todos = [...document.querySelectorAll('td, label, span, div')];
            for (const el of todos) {
                if (el.childElementCount === 0 && el.innerText &&
                    el.innerText.trim().replace(/[?]/g,'').includes(texto)) {

                    // Verifica a própria célula
                    let inp = el.querySelector('input[type="' + tipo + '"]');
                    if (!inp) {
                        // Verifica a linha / pai
                        const row = el.closest('tr') || el.parentElement;
                        if (row) inp = row.querySelector('input[type="' + tipo + '"]');
                    }
                    if (!inp) {
                        // Verifica o próximo td irmão
                        const next = el.nextElementSibling;
                        if (next) inp = next.querySelector('input[type="' + tipo + '"]');
                    }
                    if (inp) {
                        inp.checked = valor;
                        inp.dispatchEvent(new Event('change', {bubbles:true}));
                        inp.dispatchEvent(new Event('click',  {bubbles:true}));
                        return true;
                    }
                }
            }
            return false;
        }

        // Listar somente resumo?
        checkInputNearText('Listar somente resumo', 'checkbox', true);

        // Filtrar somente base de venda?
        checkInputNearText('Filtrar somente base de venda', 'checkbox', true);

        // Agrupamento = Vendedor (radio)
        const radios = [...document.querySelectorAll('input[type="radio"]')];
        for (const r of radios) {
            // Texto do label ou do elemento irmão
            const parent = r.parentElement;
            const rowEl  = r.closest('td') || r.parentElement;
            const txt = (parent ? parent.innerText : '') + ' ' + (rowEl ? rowEl.innerText : '');
            if (txt.trim() === 'Vendedor' || txt.includes('Vendedor')) {
                // Confirma que é o radio de Agrupamento verificando a linha
                const tr = r.closest('tr');
                if (tr && tr.innerText.includes('Agrupamento')) {
                    r.checked = true;
                    r.dispatchEvent(new Event('change', {bubbles:true}));
                    break;
                }
                // Se não encontrou via linha, usa o primeiro "Vendedor" encontrado
                r.checked = true;
                r.dispatchEvent(new Event('change', {bubbles:true}));
                break;
            }
        }
    }""")
    await page.wait_for_timeout(500)

    # ── 6. Formato = Visualização HTML ────────────────────────────────────────
    try:
        selects = await page.query_selector_all('select')
        for sel_el in selects:
            opts = await sel_el.query_selector_all('option')
            for opt in opts:
                txt = await opt.inner_text()
                if 'HTML' in txt or 'Visualiza' in txt:
                    val = await opt.get_attribute('value')
                    await sel_el.select_option(value=val)
                    break
    except Exception:
        pass
    await page.wait_for_timeout(300)


async def buscar_operador(page, operador: dict, data_hoje: str) -> str | None:
    html_capturado = []
    data_fmt = datetime.strptime(data_hoje, '%Y-%m-%d').strftime('%d/%m/%Y')

    async def on_response(response):
        if 'ImpressaoRelatorio' in response.url and response.status == 200:
            ct = response.headers.get('content-type', '')
            if 'html' in ct.lower():
                try:
                    body = await response.text()
                    if 'a5119' in body or 'Valor Venda' in body:
                        html_capturado.append(body)
                except Exception:
                    pass

    page.on('response', on_response)

    # Preenche o formulário com todos os campos obrigatórios
    await preencher_formulario(page, operador, data_fmt)

    # Clica em Executar
    executar_clicado = False
    for sel in [
        'input[value="Executar"]', '#btnExecutar',
        'button:has-text("Executar")', 'input[id*="Executar"]',
        'a:has-text("Executar")',
    ]:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click()
                executar_clicado = True
                break
        except Exception:
            pass

    if not executar_clicado:
        # Fallback: botão vermelho "Executar"
        try:
            btn = await page.query_selector('input[type="submit"]')
            if btn:
                await btn.click()
                executar_clicado = True
        except Exception:
            pass

    if not executar_clicado:
        print(f"  ⚠️  Botão 'Executar' não encontrado para {operador['nome']}")

    # Aguarda o relatório (até 20 s)
    for _ in range(40):
        if html_capturado:
            break
        await page.wait_for_timeout(500)

    page.remove_listener('response', on_response)
    return html_capturado[0] if html_capturado else None

# ─── Main ──────────────────────────────────────────────────────────────────────

async def main():
    if not MOVERE_USER or not MOVERE_PASS:
        print("❌  Variáveis MOVERE_USER e MOVERE_PASS não definidas!")
        sys.exit(1)

    # Usa horário de Brasília para data de referência
    from datetime import timezone, timedelta
    tz_sp = timezone(timedelta(hours=-3))
    agora_sp = datetime.now(tz_sp)
    data_hoje = agora_sp.strftime('%Y-%m-%d')

    print(f"\n🔄  Sincronizando televendas — {agora_sp.strftime('%d/%m/%Y %H:%M')} (Brasília)\n")

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

        resultados = []

        for op in OPERADORES:
            print(f"  → {op['nome']} ({op['codigo']})…")
            try:
                html = await buscar_operador(page, op, data_hoje)
                if html:
                    dados = parse_report_html(html)
                    print(f"     Campos capturados: {list(dados.keys())[:4]}")
                    status, valor = await salvar_supabase(op, data_hoje, dados)
                    emoji = "✅" if status in (200, 201) else "⚠️"
                    print(f"     {emoji} R$ {valor:,.2f}  (Supabase {status})")
                    resultados.append({'nome': op['nome'], 'valor': valor})
                else:
                    print(f"     ⚠️  HTML não capturado — verifique os campos do formulário")
            except Exception as e:
                print(f"     ❌  Erro: {e}")

        await browser.close()

    print(f"\n{'─'*40}")
    print("RESUMO:")
    total = 0
    for r in sorted(resultados, key=lambda x: x['valor'], reverse=True):
        print(f"  {r['nome']:<20} R$ {r['valor']:>10,.2f}")
        total += r['valor']
    print(f"  {'TOTAL':<20} R$ {total:>10,.2f}")
    print(f"{'─'*40}\n")

if __name__ == '__main__':
    asyncio.run(main())
