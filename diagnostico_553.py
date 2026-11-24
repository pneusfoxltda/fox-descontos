"""
diagnostico_553.py · Etapa 1 do dashboard do VAREJO
====================================================
Só ABRE o formulário da rotina 553 do Movere e lista os campos (nome, tipo, opções).
NÃO gera relatório e NÃO lê nenhuma venda: o registro do GitHub é público.

Rodar: GitHub → Actions → "Teste Movere (Debug)" → Run workflow (na branch varejo-553).
Gera também form_553.png e form_553.html (artefato "debug-movere") para conferir.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_televendas import login, RELATORIO_URL  # mesmo login do robô do televendas

# Campos que interessam ao Varejo (procurados pelo texto da linha do formulário)
PROCURAR = ["Estab", "Tabela de Pre", "Famíl", "Famil", "Vendedor", "Operador", "Listar", "resumo",
            "Grupo Empresarial", "Visão", "Visao", "Dta", "Data", "Agrup", "base de venda", "Formato", "Saída", "Saida"]

JS_CAMPOS = r"""() => {
  const vis = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const rotulo = el => {
    const tr = el.closest('tr');
    if (tr) { const t = (tr.querySelector('td,th') || tr).innerText || ''; if (t.trim()) return t.trim().split('\n')[0].slice(0, 60); }
    const lb = el.id && document.querySelector('label[for="' + el.id + '"]');
    if (lb) return lb.innerText.trim().slice(0, 60);
    const p = el.parentElement; return p ? (p.innerText || '').trim().split('\n')[0].slice(0, 60) : '';
  };
  const out = [];
  for (const el of document.querySelectorAll('input,select,textarea')) {
    if (el.type === 'hidden' && !/estab|tabela|famil|preco|preço/i.test((el.id || '') + (el.name || ''))) continue;
    const o = {rotulo: rotulo(el), tag: el.tagName.toLowerCase(), tipo: el.type || '', id: el.id || '', name: el.name || '',
               multiplo: !!el.multiple, visivel: vis(el), valor: (el.type === 'password') ? '***' : String(el.value || '').slice(0, 80),
               marcado: (el.type === 'checkbox' || el.type === 'radio') ? el.checked : undefined,
               classes: (el.className || '').toString().slice(0, 80)};
    if (el.tagName === 'SELECT') o.opcoes = [...el.options].slice(0, 120).map(op => (op.selected ? '[x] ' : '[ ] ') + op.value + ' = ' + op.text.trim());
    out.push(o);
  }
  // Componentes de lista com caixinhas (select2 / chosen / multiselect / sumoselect)
  const widgets = [...document.querySelectorAll('.select2,.select2-container,.chosen-container,.ms-parent,.SumoSelect,.multiselect,.dropdown-check-list,[class*="multiselect"],[class*="select2"]')]
    .slice(0, 40).map(w => ({classes: (w.className || '').toString().slice(0, 80), rotulo: rotulo(w), id: w.id || ''}));
  return {campos: out, widgets, frames: [...document.querySelectorAll('iframe')].map(f => f.src)};
}"""


async def main():
    if not os.environ.get("MOVERE_USER") or not os.environ.get("MOVERE_PASS"):
        print("❌ Faltam os segredos MOVERE_USER / MOVERE_PASS"); sys.exit(1)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await (await browser.new_context(locale='pt-BR', timezone_id='America/Sao_Paulo', viewport={"width": 1400, "height": 2400})).new_page()
        await login(page)
        await page.goto(RELATORIO_URL, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="screenshot_form_553.png", full_page=True)
        with open("html_capturado.html", "w", encoding="utf-8") as f:
            f.write(await page.content())
        dados = await page.evaluate(JS_CAMPOS)
        for fr in page.frames[1:]:
            try:
                d2 = await fr.evaluate(JS_CAMPOS)
                if d2["campos"]:
                    print(f"\n🪟 Frame {fr.url}: {len(d2['campos'])} campos")
                    dados["campos"] += d2["campos"]; dados["widgets"] += d2["widgets"]
            except Exception:
                pass
        print(f"\n📋 Formulário da 553: {len(dados['campos'])} campos · {len(dados['widgets'])} listas com caixinhas · iframes: {dados['frames']}\n")
        for c in dados["campos"]:
            imp = any(p.lower() in (c["rotulo"] + c["id"] + c["name"]).lower() for p in PROCURAR)
            marca = "⭐" if imp else "  "
            print(f"{marca} [{c['tag']}/{c['tipo']}{'/multi' if c['multiplo'] else ''}{'' if c['visivel'] else '/oculto'}] "
                  f"rótulo='{c['rotulo']}' id='{c['id']}' name='{c['name']}' valor='{c['valor']}'"
                  + (f" marcado={c['marcado']}" if c.get('marcado') is not None else "") + (f" classes='{c['classes']}'" if c['classes'] else ""))
            if c.get("opcoes") and imp:
                for op in c["opcoes"]:
                    print(f"       {op}")
            elif c.get("opcoes"):
                print(f"       ({len(c['opcoes'])} opções)")
        print("\n🧩 Listas com caixinhas:")
        for w in dados["widgets"]:
            print(f"   rótulo='{w['rotulo']}' id='{w['id']}' classes='{w['classes']}'")
        await browser.close()
    print("\n✅ Diagnóstico pronto (nenhuma venda foi lida).")


if __name__ == "__main__":
    asyncio.run(main())
