"""
teste_movere.py  v2
===================
Diagnóstico completo: login + formulário 553 para UMA data / UM operador.
Tira screenshots em cada etapa. Corrigido: usa click(click_count=3) no lugar
de triple_click() que não existe nessa versão do Playwright.

Uso: python3 teste_movere.py
Gera: screenshot_01..04.png  e  html_capturado.html (se o relatório saiu)
"""

import asyncio, os, sys
from playwright.async_api import async_playwright

MOVERE_USER = os.environ.get("MOVERE_USER", "")
MOVERE_PASS = os.environ.get("MOVERE_PASS", "")
MOVERE_BASE   = "https://foxpneus.moveresoftware.com"
RELATORIO_URL = f"{MOVERE_BASE}/foxpneus/rotinas/005/rotina553.aspx"

# ── CONFIGURAÇÃO DO TESTE ──────────────────────────────────────────────────────
DATA_TESTE = "27/10/2026"          # formato dd/mm/aaaa
OPERADOR   = {"codigo": "294862", "nome": "Graziele Garcia"}
# ──────────────────────────────────────────────────────────────────────────────

async def main():
    if not MOVERE_USER or not MOVERE_PASS:
        print("❌  Defina MOVERE_USER e MOVERE_PASS!"); sys.exit(1)

    print(f"\n🔬  Teste Movere v2 — {DATA_TESTE} / {OPERADOR['nome']}\n")
    html_cap = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale='pt-BR', timezone_id='America/Sao_Paulo')
        page = await ctx.new_page()

        # ── 1. Login ──────────────────────────────────────────────────────────
        print("  1. Login…")
        await page.goto(f"{MOVERE_BASE}/foxpneus/default.aspx",
                        wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path="screenshot_01_login.png")

        for sel in ['#txtLogin','input[name="txtLogin"]','input[type="text"]:visible']:
            try:
                if await page.locator(sel).count() > 0:
                    await page.fill(sel, MOVERE_USER); print(f"     user via {sel}"); break
            except Exception: pass

        for sel in ['#txtSenha','input[name="txtSenha"]','input[type="password"]:visible']:
            try:
                if await page.locator(sel).count() > 0:
                    await page.fill(sel, MOVERE_PASS); print("     senha OK"); break
            except Exception: pass

        for sel in ['#btnEntrar','input[value="Entrar"]',
                    'button:has-text("Entrar")','input[type="submit"]:visible']:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel); print(f"     entrar via {sel}"); break
            except Exception: pass

        await page.wait_for_load_state('networkidle', timeout=20000)
        print(f"     URL pós-login: {page.url}")

        # ── 2. Abre formulário ────────────────────────────────────────────────
        print(f"\n  2. Rotina 553…")
        await page.goto(RELATORIO_URL, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(1500)
        await page.screenshot(path="screenshot_02_form_antes.png")
        print("     screenshot_02_form_antes.png")

        # DEBUG: lista todos os inputs de texto para ver o que existe na página
        all_inputs = await page.evaluate("""() => {
            const r = [];
            for (const inp of document.querySelectorAll('input[type="text"],input:not([type])')) {
                const row = inp.closest('tr') || inp.parentElement;
                const near = row ? row.innerText.replace(/\\s+/g,' ').trim().slice(0,80) : '';
                r.push({ id: inp.id||'', name: inp.name||'', value: inp.value||'', near });
            }
            return r;
        }""")
        print(f"     Inputs de texto na página ({len(all_inputs)}):")
        for x in all_inputs:
            print(f"       id='{x['id']}' name='{x['name']}' val='{x['value']}' → '{x['near'][:60]}'")

        # VE = 1
        ve = await page.evaluate("""() => {
            function set1(inp) {
                inp.value = '1';
                ['input','change','blur'].forEach(e =>
                    inp.dispatchEvent(new Event(e, {bubbles:true})));
                return 'setado: ' + (inp.id||inp.name||'?');
            }
            for (const el of document.querySelectorAll('td,th,div,label,span')) {
                const t = (el.innerText||'').trim();
                if (t.includes('Empresarial')) {
                    const row = el.closest('tr') || el.parentElement;
                    const inp = row && row.querySelector('input[type="text"],input:not([type])');
                    if (inp) return set1(inp);
                }
            }
            for (const inp of document.querySelectorAll('input[type="text"],input:not([type])')) {
                const id = (inp.id + inp.name).toLowerCase();
                if (id.includes('empresa') || id.includes('visao')) return set1(inp);
            }
            return 'nao encontrado';
        }""")
        print(f"     Visão Empresarial: {ve}")
        await page.wait_for_timeout(900)

        # Data Inicial  ← FIX: click(click_count=3) no lugar de triple_click()
        data_ok = False
        for sel in ['#dtaini','input[name="dtaini"]','input[id*="dtaini"]',
                    'input[id*="DataIni"]','input[id*="dataini"]']:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click(click_count=3)
                    await el.fill(DATA_TESTE)
                    await el.press('Tab')
                    val = await el.input_value()
                    print(f"     Data Ini via {sel} → '{val}'")
                    data_ok = True; break
            except Exception as e:
                print(f"     Data Ini {sel} erro: {e}")

        if not data_ok:
            # Fallback via JavaScript
            r = await page.evaluate(f"""() => {{
                const sels = ['#dtaini','[name="dtaini"]','[id*="dtaini"]','[id*="DataIni"]'];
                for (const s of sels) {{
                    const el = document.querySelector(s);
                    if (el) {{
                        el.value = '{DATA_TESTE}';
                        el.dispatchEvent(new Event('change',{{bubbles:true}}));
                        return 'JS ok: ' + s;
                    }}
                }}
                return 'nao encontrado';
            }}""")
            print(f"     Data Ini (JS fallback): {r}")
        await page.wait_for_timeout(400)

        # Data Final
        data_fim_ok = False
        for sel in ['#dtafim','input[name="dtafim"]','input[id*="dtafim"]',
                    'input[id*="DataFim"]','input[id*="datafim"]']:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click(click_count=3)
                    await el.fill(DATA_TESTE)
                    await el.press('Tab')
                    val = await el.input_value()
                    print(f"     Data Fim via {sel} → '{val}'")
                    data_fim_ok = True; break
            except Exception as e:
                print(f"     Data Fim {sel} erro: {e}")

        if not data_fim_ok:
            r = await page.evaluate(f"""() => {{
                const sels = ['#dtafim','[name="dtafim"]','[id*="dtafim"]','[id*="DataFim"]'];
                for (const s of sels) {{
                    const el = document.querySelector(s);
                    if (el) {{
                        el.value = '{DATA_TESTE}';
                        el.dispatchEvent(new Event('change',{{bubbles:true}}));
                        return 'JS ok: ' + s;
                    }}
                }}
                return 'nao encontrado';
            }}""")
            print(f"     Data Fim (JS fallback): {r}")
        await page.wait_for_timeout(400)

        # Operador
        for sel in ['input[id*="operador"]','input[id*="Operador"]',
                    'input[id*="cliforOperador"]','input[name*="operador"]']:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.clear()
                    await el.type(OPERADOR['codigo'], delay=80)
                    await page.wait_for_timeout(1500)
                    for drop in ['li.autocomplete-result','.dropdown-item',
                                 '[class*="suggest"]','[class*="autocomplete"] li']:
                        try:
                            item = page.locator(drop).first
                            if await item.count() > 0:
                                txt = await item.inner_text()
                                print(f"     Autocomplete op: '{txt.strip()[:50]}'")
                                await item.click(); break
                        except Exception: pass
                    await el.press('Tab')
                    await page.wait_for_timeout(600)
                    val = await el.input_value()
                    print(f"     Operador via {sel} → '{val}'")
                    break
            except Exception as e:
                print(f"     Operador {sel} erro: {e}")

        # Checkboxes e rádio
        r = await page.evaluate("""() => {
            function check(texto, tipo, valor) {
                for (const el of document.querySelectorAll('td,label,span,div,th')) {
                    if ((el.innerText||'').trim().replace(/[?]/g,'').includes(texto)) {
                        let inp = el.querySelector('input[type="'+tipo+'"]')
                               || (() => { const p=el.closest('tr')||el.parentElement;
                                           return p&&p.querySelector('input[type="'+tipo+'"]'); })()
                               || (() => { const n=el.nextElementSibling;
                                           return n&&n.querySelector('input[type="'+tipo+'"]'); })();
                        if (inp) { inp.checked=valor;
                                   inp.dispatchEvent(new Event('change',{bubbles:true})); return true; }
                    }
                }
                return false;
            }
            const r1 = check('Listar somente resumo','checkbox',true);
            const r2 = check('Filtrar somente base de venda','checkbox',true);
            for (const r of document.querySelectorAll('input[type="radio"]')) {
                const tr = r.closest('tr');
                if (tr && tr.innerText.includes('Agrupamento')) {
                    const p = r.parentElement;
                    if (p && p.innerText.trim()==='Vendedor') {
                        r.checked=true; r.dispatchEvent(new Event('change',{bubbles:true})); break;
                    }
                }
            }
            return {resumo:r1, filtrar:r2};
        }""")
        print(f"     Checkboxes resumo={r.get('resumo')} filtrar={r.get('filtrar')}")

        # Formato HTML
        try:
            for sel_el in await page.query_selector_all('select'):
                for opt in await sel_el.query_selector_all('option'):
                    txt = await opt.inner_text()
                    if 'HTML' in txt or 'Visualiza' in txt:
                        await sel_el.select_option(value=await opt.get_attribute('value'))
                        print(f"     Formato: '{txt.strip()}'"); break
        except Exception as e:
            print(f"     Formato erro: {e}")

        await page.wait_for_timeout(300)
        await page.screenshot(path="screenshot_03_form_preenchido.png")
        print("     screenshot_03_form_preenchido.png")

        # ── 3. Executar ───────────────────────────────────────────────────────
        print(f"\n  3. Executar…")

        async def on_resp(response):
            if 'ImpressaoRelatorio' in response.url and response.status == 200:
                ct = response.headers.get('content-type', '')
                if 'html' in ct.lower():
                    try:
                        body = await response.text()
                        print(f"     📥  {len(body)} bytes | a5119={'a5119' in body} | 'Valor Venda'={'Valor Venda' in body}")
                        html_cap.append(body)
                    except Exception as e:
                        print(f"     Erro leitura: {e}")

        page.on('response', on_resp)
        for sel in ['input[value="Executar"]','#btnExecutar',
                    'button:has-text("Executar")','input[type="submit"]']:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click(); print(f"     clicado via {sel}"); break
            except Exception: pass

        for _ in range(40):
            if html_cap: break
            await page.wait_for_timeout(500)

        page.remove_listener('response', on_resp)
        await page.screenshot(path="screenshot_04_resultado.png")
        print("     screenshot_04_resultado.png")
        await browser.close()

    # ── Resultado ─────────────────────────────────────────────────────────────
    print("\n" + "═"*52)
    if html_cap:
        print(f"  ✅  HTML capturado! ({len(html_cap[0])} bytes)")
        with open("html_capturado.html","w") as f: f.write(html_cap[0])
        print("     html_capturado.html salvo")
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_cap[0], 'html.parser')
            LCLS = ['a5119','a5128','a5137','a5146','a5155','a5164','a5173','a5182',
                    'a5191','a5200','a5209','a5218','a5227','a5236','a5245','a5261']
            VCLS = ['a5123','a5132','a5141','a5150','a5159','a5168','a5177','a5186',
                    'a5195','a5204','a5213','a5222','a5231','a5240','a5249','a5265']
            data, label = {}, None
            for div in soup.find_all('div'):
                cls = (div.get('class') or [''])[0]
                t = div.get_text(strip=True)
                if not t: continue
                if cls in LCLS: label = t
                elif cls in VCLS and label: data[label]=t; label=None
            print("\n  Campos:")
            for k,v in data.items(): print(f"    {k}: {v}")
        except Exception as e:
            print(f"  Erro parse: {e}")
    else:
        print("  ❌  HTML NÃO capturado — veja os screenshots!")
    print("═"*52 + "\n")

if __name__=='__main__':
    asyncio.run(main())
