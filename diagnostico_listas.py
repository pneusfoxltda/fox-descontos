"""
diagnostico_listas.py · como aparece o "Não Atribuído" na lista Tabela de Preço da 553 (só lê nomes de opções).
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_televendas import login, RELATORIO_URL
from varejo_filtros import JS_CAIXA


async def opcoes(page, comp, termo):
    await page.click(f"#fx-{comp} .select2-selection")
    campo = page.locator(f"#fx-{comp} .select2-search__field")
    await campo.fill("")
    if termo:
        await campo.type(termo, delay=40)
    vistos = []
    for _ in range(20):
        await page.wait_for_timeout(300)
        it = await page.evaluate("() => [...document.querySelectorAll('.select2-results__option')].map(e => ((e.innerText || '').trim() + ' {id=' + (e.id || '') + ' aria=' + (e.getAttribute('aria-selected') || '') + '}'))")
        if it and not all('Procurando' in x for x in it):
            vistos = it; break
    # rola a lista para carregar mais
    for _ in range(6):
        await page.evaluate("() => { const r = document.querySelector('.select2-results__options'); if (r) r.scrollTop = r.scrollHeight; }")
        await page.wait_for_timeout(600)
    vistos2 = await page.evaluate("() => [...document.querySelectorAll('.select2-results__option')].map(e => (e.innerText || '').trim())")
    await page.keyboard.press("Escape")
    return vistos, vistos2


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        page = await (await b.new_context(locale="pt-BR", viewport={"width": 1400, "height": 2400})).new_page()
        await login(page)
        await page.goto(RELATORIO_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(2500)
        await page.evaluate(JS_CAIXA, "cTabelaPreco")
        for termo in ["", "N", "Não", "NAO", "Atrib", "0", "-1", "empty"]:
            a, todos = await opcoes(page, "cTabelaPreco", termo)
            print(f"\n🔎 busca '{termo}': {a[:6]}")
            print(f"   lista completa ({len(todos)}): {todos}")
        sel = await page.evaluate("""() => { const h = document.querySelector('[id$="cTabelaPreco_hiddenFieldRegistrosSelecionados"]');
            let w = h.parentElement; for (let i = 0; i < 6 && !w.querySelector('select'); i++) w = w.parentElement;
            const s = w.querySelector('select'); return [...s.attributes].map(a => a.name + '=' + a.value.slice(0, 120)); }""")
        print("\n⚙️ atributos da lista:", sel)
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())
