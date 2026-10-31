"""
teste_movere.py
===============
Roda um ÚNICO teste: login + preenchimento do formulário 553 para UMA data
e UM operador, tirando screenshots em cada passo.

Uso no GitHub Actions:
  python3 teste_movere.py

Gera (na pasta atual):
  screenshot_01_login.png
  screenshot_02_form_antes.png
  screenshot_03_form_preenchido.png
  screenshot_04_resultado.png
  html_capturado.html        (se o relatório foi gerado)
"""

import asyncio, os, sys
from datetime import datetime
from playwright.async_api import async_playwright

MOVERE_USER = os.environ.get("MOVERE_USER", "")
MOVERE_PASS = os.environ.get("MOVERE_PASS", "")
MOVERE_BASE   = "https://foxpneus.moveresoftware.com"
RELATORIO_URL = f"{MOVERE_BASE}/foxpneus/rotinas/005/rotina553.aspx"

# ── CONFIGURAÇÃO DO TESTE ──────────────────────────────────────────────────────
# Muda aqui para testar outro dia ou operador
DATA_TESTE   = "27/10/2026"   # formato dd/mm/aaaa
OPERADOR     = {"codigo": "294862", "nome": "Graziele Garcia"}
# ──────────────────────────────────────────────────────────────────────────────

async def main():
    if not MOVERE_USER or not MOVERE_PASS:
        print("❌  Defina MOVERE_USER e MOVERE_PASS nas variáveis de ambiente!")
        sys.exit(1)

    print(f"\n🔬  Teste Movere — {DATA_TESTE} / {OPERADOR['nome']}\n")

    html_cap = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale='pt-BR', timezone_id='America/Sao_Paulo')
        page = await ctx.new_page()

        # ── 1. Login ───────────────────────────────────────────────────────────
        print("  1. Abrindo página de login…")
        await page.goto(f"{MOVERE_BASE}/foxpneus/default.aspx",
                        wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path="screenshot_01_login.png")
        print("     → screenshot_01_login.png salvo")

        # Campos de login
        for sel in ['#txtLogin','input[name="txtLogin"]','input[type="text"]:visible']:
            try:
                if await page.locator(sel).count() > 0:
                    await page.fill(sel, MOVERE_USER)
                    print(f"     Usuário preenchido via {sel}")
                    break
            except Exception:
                pass

        for sel in ['#txtSenha','input[name="txtSenha"]','input[type="password"]:visible']:
            try:
                if await page.locator(sel).count() > 0:
                    await page.fill(sel, MOVERE_PASS)
                    print("     Senha preenchida")
                    break
            except Exception:
                pass

        for sel in ['#btnEntrar','input[value="Entrar"]',
                    'button:has-text("Entrar")','input[type="submit"]:visible']:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel)
                    print(f"     Botão Entrar clicado via {sel}")
                    break
            except Exception:
                pass

        await page.wait_for_load_state('networkidle', timeout=20000)
        print(f"     URL após login: {page.url}")

        if 'default.aspx' in page.url.lower() or 'login' in page.url.lower():
            print("  ❌  Parece que o login FALHOU — URL ainda é a de login!")
        else:
            print("  ✅  Login OK!")

        # ── 2. Formulário ─────────────────────────────────────────────────────
        print(f"\n  2. Abrindo rotina 553…")
        await page.goto(RELATORIO_URL, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(1500)
        await page.screenshot(path="screenshot_02_form_antes.png")
        print("     → screenshot_02_form_antes.png salvo")

        # Visão Empresarial
        ve_antes = await page.evaluate("""() => {
            for (const td of document.querySelectorAll('td,div')) {
                if (td.childElementCount===0 && td.innerText &&
                    td.innerText.trim()==='Visão Empresarial') {
                    const row = td.closest('tr');
                    if (row) {
                        const inp = row.querySelector('input[type="text"]');
                        return inp ? inp.value : 'campo não encontrado';
                    }
                }
            }
            return 'label não encontrado';
        }""")
        print(f"     Visão Empresarial ANTES: '{ve_antes}'")

        await page.evaluate("""() => {
            for (const td of document.querySelectorAll('td,div')) {
                if (td.childElementCount===0 && td.innerText &&
                    td.innerText.trim()==='Visão Empresarial') {
                    const row = td.closest('tr');
                    if (row) {
                        const inp = row.querySelector('input[type="text"]');
                        if (inp && (!inp.value || inp.value.trim()==='')) {
                            inp.value='1';
                            inp.dispatchEvent(new Event('change',{bubbles:true}));
                            inp.dispatchEvent(new Event('blur',{bubbles:true}));
                        }
                    }
                    break;
                }
            }
        }""")
        await page.wait_for_timeout(900)

        ve_depois = await page.evaluate("""() => {
            for (const td of document.querySelectorAll('td,div')) {
                if (td.childElementCount===0 && td.innerText &&
                    td.innerText.trim()==='Visão Empresarial') {
                    const row = td.closest('tr');
                    if (row) {
                        const inp = row.querySelector('input[type="text"]');
                        return inp ? inp.value : 'campo não encontrado';
                    }
                }
            }
            return 'label não encontrado';
        }""")
        print(f"     Visão Empresarial DEPOIS: '{ve_depois}'")

        # Data Inicial
        data_setada = False
        for sel in ['#dtaini','input[name="dtaini"]','input[id*="dtaini"]','input[id*="DataIni"]']:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.triple_click()
                    await el.fill(DATA_TESTE)
                    await el.press('Tab')
                    val = await el.input_value()
                    print(f"     Data Inicial via {sel} → valor: '{val}'")
                    data_setada = True
                    break
            except Exception as e:
                print(f"     Data Inicial {sel} falhou: {e}")

        if not data_setada:
            print("     ⚠️  Data Inicial: nenhum seletor funcionou!")

        await page.wait_for_timeout(400)

        # Data Final
        for sel in ['#dtafim','input[name="dtafim"]','input[id*="dtafim"]','input[id*="DataFim"]']:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.triple_click()
                    await el.fill(DATA_TESTE)
                    await el.press('Tab')
                    val = await el.input_value()
                    print(f"     Data Final   via {sel} → valor: '{val}'")
                    break
            except Exception as e:
                print(f"     Data Final {sel} falhou: {e}")

        await page.wait_for_timeout(400)

        # Operador
        op_setado = False
        for sel in ['input[id*="operador"]','input[id*="Operador"]',
                    'input[id*="cliforOperador"]','input[name*="operador"]']:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.clear()
                    await el.type(OPERADOR['codigo'], delay=80)
                    await page.wait_for_timeout(1200)
                    # Tenta clicar no autocomplete
                    for drop in ['li.autocomplete-result','.dropdown-item','[class*="suggest"]']:
                        try:
                            item = page.locator(drop).first
                            if await item.count() > 0:
                                txt = await item.inner_text()
                                print(f"     Autocomplete operador: '{txt.strip()[:50]}'")
                                await item.click()
                                break
                        except Exception:
                            pass
                    await el.press('Tab')
                    val = await el.input_value()
                    print(f"     Operador via {sel} → valor: '{val}'")
                    op_setado = True
                    break
            except Exception as e:
                print(f"     Operador {sel} falhou: {e}")

        if not op_setado:
            print("     ⚠️  Operador: nenhum seletor funcionou!")

        # Checkboxes e rádio
        await page.evaluate("""() => {
            function check(texto, tipo, valor) {
                for (const el of document.querySelectorAll('td,label,span,div')) {
                    if (el.childElementCount===0 && el.innerText &&
                        el.innerText.trim().replace(/[?]/g,'').includes(texto)) {
                        let inp = el.querySelector('input[type="'+tipo+'"]')
                               || (() => { const row=el.closest('tr')||el.parentElement;
                                           return row&&row.querySelector('input[type="'+tipo+'"]'); })()
                               || (() => { const n=el.nextElementSibling;
                                           return n&&n.querySelector('input[type="'+tipo+'"]'); })();
                        if (inp) { inp.checked=valor;
                                   inp.dispatchEvent(new Event('change',{bubbles:true})); return true; }
                    }
                }
                return false;
            }
            const r1 = check('Listar somente resumo',       'checkbox', true);
            const r2 = check('Filtrar somente base de venda','checkbox', true);
            window.__checkboxResults = {resumo:r1, filtrar:r2};

            for (const r of document.querySelectorAll('input[type="radio"]')) {
                const tr = r.closest('tr');
                if (tr && tr.innerText.includes('Agrupamento')) {
                    const p = r.parentElement;
                    if (p && p.innerText.trim()==='Vendedor') {
                        r.checked=true;
                        r.dispatchEvent(new Event('change',{bubbles:true}));
                        break;
                    }
                }
            }
        }""")

        results = await page.evaluate("() => window.__checkboxResults || {}")
        print(f"     Checkbox 'Listar resumo': {results.get('resumo')}")
        print(f"     Checkbox 'Filtrar base':  {results.get('filtrar')}")

        # Formato HTML
        try:
            for sel_el in await page.query_selector_all('select'):
                for opt in await sel_el.query_selector_all('option'):
                    txt = await opt.inner_text()
                    if 'HTML' in txt or 'Visualiza' in txt:
                        await sel_el.select_option(value=await opt.get_attribute('value'))
                        print(f"     Formato selecionado: '{txt.strip()}'")
                        break
        except Exception as e:
            print(f"     Formato: erro — {e}")

        await page.wait_for_timeout(300)
        await page.screenshot(path="screenshot_03_form_preenchido.png")
        print("     → screenshot_03_form_preenchido.png salvo")

        # ── 3. Executar ───────────────────────────────────────────────────────
        print(f"\n  3. Clicando Executar…")

        async def on_resp(response):
            if 'ImpressaoRelatorio' in response.url and response.status == 200:
                ct = response.headers.get('content-type', '')
                if 'html' in ct.lower():
                    try:
                        body = await response.text()
                        print(f"     📥  Resposta capturada: {len(body)} bytes")
                        print(f"          Contém 'a5119': {'a5119' in body}")
                        print(f"          Contém 'Valor Venda': {'Valor Venda' in body}")
                        html_cap.append(body)
                    except Exception as e:
                        print(f"     Erro ao ler resposta: {e}")

        page.on('response', on_resp)

        clicou = False
        for sel in ['input[value="Executar"]','#btnExecutar',
                    'button:has-text("Executar")','input[type="submit"]']:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click()
                    print(f"     Clicado via {sel}")
                    clicou = True
                    break
            except Exception as e:
                print(f"     Executar {sel} falhou: {e}")

        if not clicou:
            print("     ⚠️  Botão Executar não encontrado!")

        # Aguarda resposta
        for i in range(40):
            if html_cap: break
            await page.wait_for_timeout(500)

        page.remove_listener('response', on_resp)
        await page.screenshot(path="screenshot_04_resultado.png")
        print("     → screenshot_04_resultado.png salvo")

        await browser.close()

    # ── Resultado ─────────────────────────────────────────────────────────────
    print("\n" + "═"*50)
    if html_cap:
        html = html_cap[0]
        print(f"  ✅  HTML capturado! ({len(html)} bytes)")
        with open("html_capturado.html", "w") as f:
            f.write(html)
        print("     → html_capturado.html salvo")

        # Tenta parsear
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            LABEL_CLS = ['a5119','a5128','a5137','a5146','a5155','a5164','a5173','a5182',
                         'a5191','a5200','a5209','a5218','a5227','a5236','a5245','a5261']
            VALUE_CLS = ['a5123','a5132','a5141','a5150','a5159','a5168','a5177','a5186',
                         'a5195','a5204','a5213','a5222','a5231','a5240','a5249','a5265']
            data = {}
            label = None
            for div in soup.find_all('div'):
                cls_list = div.get('class', [])
                cls = cls_list[0] if cls_list else ''
                text = div.get_text(strip=True)
                if not text: continue
                if cls in LABEL_CLS: label = text
                elif cls in VALUE_CLS and label:
                    data[label] = text
                    label = None
            print("\n  Campos extraídos do relatório:")
            for k, v in data.items():
                print(f"    {k}: {v}")
        except Exception as e:
            print(f"  Erro ao parsear: {e}")
    else:
        print("  ❌  HTML NÃO capturado — o relatório não foi gerado!")
        print("     Veja os screenshots para entender o que aconteceu.")
    print("═"*50 + "\n")

if __name__ == '__main__':
    asyncio.run(main())
