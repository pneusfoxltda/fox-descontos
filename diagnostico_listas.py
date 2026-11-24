"""
diagnostico_listas.py · procura o "Segmento de vendas" (GERAL / LICITACAO / PAGAMENTO FLEXIVEL / REVENDA)
nas listas "digita e escolhe" da rotina 553. Só lê os NOMES das listas e das opções; não gera relatório.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_televendas import login, RELATORIO_URL

JS = r"""() => [...document.querySelectorAll('select.caixaTextoPesquisaDeMultiplaSelecao')].map((s, i) => {
  let w = s.parentElement, rot = '';
  for (let k = 0; k < 6 && w && !rot; k++) {
    const t = [...w.parentElement.children].filter(c => c !== w && !c.contains(s)).map(c => (c.innerText || '').trim()).filter(Boolean)[0];
    if (t && t.length < 60) rot = t; w = w.parentElement;
  }
  const c = s.nextElementSibling && s.nextElementSibling.classList.contains('select2') ? s.nextElementSibling : s.parentElement.querySelector('.select2-container');
  if (c && !c.id) c.id = 'fxl-' + i;
  const comp = (s.closest('[id$="_divGrupo"]') || {}).id || '';
  return {i, rot, comp, tabela: s.getAttribute('tabela'), campo: s.getAttribute('nomedocampoquerepresentanomeoudescricaodoregistro'),
          cont: c ? c.id : ''};
})"""


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        page = await (await b.new_context(locale="pt-BR", viewport={"width": 1400, "height": 2400})).new_page()
        await login(page)
        await page.goto(RELATORIO_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(2500)
        listas = await page.evaluate(JS)
        print(f"\n📋 {len(listas)} listas 'digita e escolhe' na 553:")
        for l in listas:
            print(f"   #{l['i']:>2} rótulo='{l['rot']}' componente='{l['comp']}' tabela='{l['tabela']}' campo='{l['campo']}'")
        print("\n🔎 Opções de cada lista (buscando 'a' e 'e'):")
        for l in listas:
            if not l["cont"]:
                continue
            vistos = set()
            for termo in ("a", "e", "r"):
                try:
                    await page.click(f"#{l['cont']} .select2-selection", timeout=3000)
                    campo = page.locator(f"#{l['cont']} .select2-search__field")
                    await campo.fill(""); await campo.type(termo, delay=30)
                    for _ in range(16):
                        await page.wait_for_timeout(250)
                        it = await page.evaluate("() => [...document.querySelectorAll('.select2-results__option')].map(e => (e.innerText || '').trim())")
                        it = [x for x in it if x and 'Procurando' not in x]
                        if it:
                            break
                    vistos.update(it[:25])
                    await page.keyboard.press("Escape")
                except Exception as e:
                    vistos.add(f"(erro {type(e).__name__})")
            achou = [x for x in vistos if any(k in x.upper() for k in ("REVENDA", "LICITA", "FLEXIVEL", "GERAL"))]
            print(f"   #{l['i']:>2} {l['comp'] or l['tabela']}: {sorted(vistos)[:14]}{'  ⭐ SEGMENTO?' if achou else ''}")
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
