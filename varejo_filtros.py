"""
Filtros do dashboard do VAREJO na rotina 553 do Movere (decisão do TI, 24/11/2026).
Usado pelo robô do Varejo e pelo diagnóstico. As listas do Movere (Estabelecimentos, Famílias de Itens,
Tabela de Preço) são "digita e escolhe" (select2): o robô digita cada nome e clica na opção, como uma pessoa.
"""
import unicodedata

LOJAS_VAREJO = {  # código do estabelecimento no Movere → nome
    "1": "MATRIZ", "5": "JI-PARANA", "6": "CACOAL", "8": "C.AUTO PVH",
    "9": "C.AUTO VLH", "11": "ARIQUEMES", "101": "XAPURI", "201": "PARINTINS",
}
FAMILIAS_VAREJO = [
    "DUNLOP", "FAMÍLIA PASSEIO PIRELLI", "LUBRIFICANTES REPOSIÇÃO", "MERCADORIAS EM GERAL FDL",
    "MERCADORIAS EM GERAL REPOSIÇÃO", "MULTIMARCAS CAR", "PASSEIO BRIDGESTONE", "PECAS FDL",
    "PECAS REPOSICAO", "PNEUS IMPORTADOS CAR", "SERVICOS PRESTADOS",
]
# Coluna "Pneus" do Resultado Varejo (pedido do TI, 24/11/2026): só as famílias de PNEU (as outras são peças,
# lubrificantes, mercadorias e serviços).
FAMILIAS_PNEUS = ["DUNLOP", "FAMÍLIA PASSEIO PIRELLI", "MULTIMARCAS CAR", "PASSEIO BRIDGESTONE", "PNEUS IMPORTADOS CAR"]
TABELAS_VAREJO = [
    "COLABORADORES", "CP 1", "CP 2", "CP 3", "CP 4", "CP 5", "CP SEM DEFINIÇÃO", "CTR",
    "FROTAS LEVE", "FROTAS TICKET LOG", "Não Atribuído", "RECAPAGEM DIFERENCIADA", "VAREJO",
]
# Na 553 não existe a opção "Não Atribuído" (venda SEM tabela de preço). Para incluí-la:
# Varejo = (sem filtro de tabela) − (tabelas que NÃO são do varejo). Lista ativa na 553 em 24/11/2026: 16 tabelas.
TABELAS_FORA_VAREJO = ["AMAGGI", "ATACADO", "ATACADO PREMIUM", "GK FROTAS/ZANELATTO/PINGO"]
# Segmento de vendas (GERAL / LICITACAO / PAGAMENTO FLEXIVEL / REVENDA): o TI quer tirar REVENDA, mas esse filtro
# NÃO existe na 553 (procurado nas 21 listas do formulário em 24/11/2026). Guardado para o futuro.
SEGMENTOS_VENDA_VAREJO = ["(vazio)", "GERAL", "LICITACAO", "PAGAMENTO FLEXIVEL"]   # fora: REVENDA

CAMPOS = {  # componente do Movere (id) → o que marcar
    "cEstabelecimentos": list(LOJAS_VAREJO.values()),
    "cFamiliaItens": FAMILIAS_VAREJO,
    "cTabelaPreco": TABELAS_VAREJO,
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().upper()
    return " ".join(s.replace(":", " ").split())


# O Movere lembra os últimos filtros usados com o mesmo login (ex.: "Nome do item começando por: FLEXIVEL"):
# antes de marcar os do Varejo, limpa TODOS os campos de texto e listas, menos datas, visão e grupo empresarial.
JS_LIMPAR = r"""() => {
  const manter = /cdtaini|cdtafim|idvisaoempresarial|idgrupoempresarial/i;
  let n = 0;
  for (const el of document.querySelectorAll('input[type=text],input:not([type]),textarea')) {
    if (manter.test(el.id || '') || !el.value) continue;
    el.value = ''; ['input', 'change'].forEach(e => el.dispatchEvent(new Event(e, {bubbles: true}))); n++;
  }
  for (const h of document.querySelectorAll('[id$="_hiddenFieldRegistrosSelecionados"]')) { if (h.value) { h.value = ''; n++; } }
  for (const s of document.querySelectorAll('select.caixaTextoPesquisaDeMultiplaSelecao')) {
    if (window.jQuery) { try { window.jQuery(s).val(null).trigger('change'); } catch (e) {} }
    else { [...s.options].forEach(o => o.selected = false); s.dispatchEvent(new Event('change', {bubbles: true})); }
  }
  for (const c of document.querySelectorAll('[id*="cArosPermitidos"]')) if (c.checked) { c.checked = false; n++; }
  return n;
}"""


# Acha a caixa "digita e escolhe" de um componente pelo campo escondido dele
JS_CAIXA = r"""(comp) => {
  const h = document.querySelector('[id$="' + comp + '_hiddenFieldRegistrosSelecionados"]');
  if (!h) return null;
  let w = h.parentElement;
  for (let i = 0; i < 6 && w && !w.querySelector('select.caixaTextoPesquisaDeMultiplaSelecao'); i++) w = w.parentElement;
  if (!w) return null;
  const sel = w.querySelector('select.caixaTextoPesquisaDeMultiplaSelecao');
  const cont = w.querySelector('.select2-container');
  if (cont && !cont.id) cont.id = 'fx-' + comp;
  return {hidden: h.value, escolhidos: [...w.querySelectorAll('.select2-selection__choice')].map(c => c.title || c.innerText.replace('×', '').trim()),
          opcoes: [...sel.options].map(o => o.value + '=' + o.text.trim()).slice(0, 40), html: w.outerHTML.slice(0, 1500)};
}"""


async def marcar_lista(page, comp: str, nomes: list, log=print) -> dict:
    """Marca cada nome na lista "digita e escolhe" do componente. Devolve {'ok': [...], 'faltou': [...], 'hidden': '...'}."""
    info = await page.evaluate(JS_CAIXA, comp)
    if not info:
        return {"ok": [], "faltou": list(nomes), "hidden": "", "erro": "componente não encontrado"}
    ja = {norm(x).split(" ", 1)[-1] if norm(x)[:1].isdigit() else norm(x) for x in info["escolhidos"]}
    ok, faltou = [], []
    for nome in nomes:
        alvo = norm(nome)
        if any(alvo == j or alvo in j for j in ja):
            ok.append(nome); continue
        await page.click(f"#fx-{comp} .select2-selection")
        campo = page.locator(f"#fx-{comp} .select2-search__field")
        await campo.fill("")
        await campo.type(nome.split()[0] if len(nome) > 14 else nome, delay=40)
        achou = False
        for _ in range(24):  # até ~6 s esperando a lista do Movere
            await page.wait_for_timeout(250)
            itens = await page.evaluate("""() => [...document.querySelectorAll('.select2-results__option')]
                .map((e, i) => ({i, t: (e.innerText || '').trim()}))""")
            cand = [x for x in itens if x["t"] and "Procurando" not in x["t"] and "Nenhum" not in x["t"]]
            if not cand:
                continue
            esc = next((x for x in cand if norm(x["t"]) == alvo or norm(x["t"]).endswith(" " + alvo) or norm(x["t"]).split(" ", 1)[-1] == alvo), None)
            if esc is None:
                esc = next((x for x in cand if alvo in norm(x["t"])), None)
            if esc is not None:
                await page.locator(".select2-results__option").nth(esc["i"]).click()
                achou = True
                log(f"     ✔ {nome}  ← '{esc['t']}'")
            else:
                log(f"     ✖ {nome}: opções vistas = {[x['t'] for x in cand][:8]}")
            break
        if not achou and nome != nome.split()[-1]:
            # 2ª tentativa: busca pela última palavra sem acento (ex.: "Não Atribuído" → "Atribuido")
            await page.keyboard.press("Escape")
            await page.click(f"#fx-{comp} .select2-selection")
            campo = page.locator(f"#fx-{comp} .select2-search__field")
            await campo.fill(""); await campo.type(norm(nome).split()[-1][:6], delay=40)
            for _ in range(24):
                await page.wait_for_timeout(250)
                itens = await page.evaluate("""() => [...document.querySelectorAll('.select2-results__option')].map((e, i) => ({i, t: (e.innerText || '').trim()}))""")
                cand = [x for x in itens if x["t"] and "Procurando" not in x["t"] and "Nenhum" not in x["t"]]
                if not cand:
                    continue
                esc = next((x for x in cand if alvo in norm(x["t"])), None)
                if esc is not None:
                    await page.locator(".select2-results__option").nth(esc["i"]).click(); achou = True
                    log(f"     ✔ {nome}  ← '{esc['t']}' (2ª busca)")
                else:
                    log(f"     ✖ {nome}: opções vistas = {[x['t'] for x in cand][:8]}")
                break
        if not achou:
            faltou.append(nome)
            await page.keyboard.press("Escape")
        else:
            ok.append(nome)
        await page.wait_for_timeout(200)
    info2 = await page.evaluate(JS_CAIXA, comp)
    return {"ok": ok, "faltou": faltou, "hidden": info2["hidden"] if info2 else "", "escolhidos": info2["escolhidos"] if info2 else []}


# ── Leitura do relatório (só os quadros de resumo; nada de cliente) ──────────────
COLUNAS = ["peso", "quant", "qtd_mont", "preco_tabela", "vlr_venda", "vlr_c_rep", "vlr_lucro", "pct_lucro",
           "pct_marg", "pct_desc", "qtd_vendas", "ticket"]


def _num(s: str):
    s = str(s).strip().replace("R$", "").replace(" ", "")
    if s in ("NaN", "Infinity", "-Infinity"):
        return 0.0
    if not s or not any(ch.isdigit() for ch in s):
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def ler_resumos(html: str) -> dict:
    """Lê do HTML (SSRS) da 553 os quadros "Resumo por Vendedor" e "Resumo por Estabelecimento" e os totais.
    Guarda só: venda líquida (vlr_venda), itens (quant), vendas (qtd_vendas) e ticket. Nada de cliente, lucro ou margem."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    seq = []
    for d in soup.find_all("div"):
        if d.find("div"):
            continue  # só as caixas de texto finais
        t = " ".join(d.get_text(" ", strip=True).split())
        if t:
            seq.append(t)

    def quadro(titulo):
        try:
            i = seq.index(titulo)
        except ValueError:
            return [], None
        try:
            i = seq.index("Ticket Médio", i) + 1
        except ValueError:
            return [], None
        linhas, total = [], None
        while i < len(seq):
            t = seq[i]
            # o quadro pode continuar na página seguinte, com o MESMO título repetido: só para em outro quadro
            if (t.startswith("Resumo por") and t != titulo) or t.startswith("Valor Total"):
                break
            if t == "Total Geral:":
                nums = [x for x in (_num(v) for v in seq[i + 1:i + 16]) if x is not None]
                total = nums
                break
            if t.lstrip("-").isdigit() and i + 1 < len(seq) and _num(seq[i + 1]) is None:
                vals = [_num(v) for v in seq[i + 2:i + 2 + len(COLUNAS)]]
                if all(v is not None for v in vals):
                    r = dict(zip(COLUNAS, vals))
                    if any(x["cod"] == t for x in linhas):   # cabeçalho/linha repetida na quebra de página
                        i += 2 + len(COLUNAS)
                        continue
                    linhas.append({"cod": t, "nome": seq[i + 1], "venda": r["vlr_venda"], "itens": r["quant"],
                                   "vendas": int(r["qtd_vendas"]), "ticket": r["ticket"]})
                    i += 2 + len(COLUNAS)
                    continue
            i += 1
        return linhas, total

    vend, vend_tot = quadro("Resumo por Vendedor")
    estab, estab_tot = quadro("Resumo por Estabelecimento")
    totais = {}
    for rot in ["Valor Total das Notas Emitidas", "Valor Total Devoluções", "Valor Venda Líquida (Venda - Devolução)",
                "Quantidade Clientes Atendidos", "Quantidade Itens Atendidos"]:
        if rot in seq:
            j = seq.index(rot)
            v = next((_num(x) for x in seq[j + 1:j + 4] if _num(x) is not None), None)
            totais[rot] = v
    return {"vendedores": vend, "estabelecimentos": estab, "totais": totais}


def ler_quadro_familia(html: str) -> list:
    """Quadro "Resumo por Família de Itens" da 553: [{'cod','nome','venda','itens'}] (12 colunas, sem vendas/ticket)."""
    from bs4 import BeautifulSoup
    seq = []
    for d in BeautifulSoup(html, "html.parser").find_all(["div", "td"]):
        if d.find(["div", "td"]):
            continue
        t = " ".join(d.get_text(" ", strip=True).split())
        if t:
            seq.append(t)
    try:
        i = seq.index("Resumo por Família de Itens")
        i = seq.index("% Desc. Cond. Pag.", i) + 1
    except ValueError:
        return []
    out = []
    while i < len(seq) and not seq[i].startswith("Resumo por") and seq[i] != "Total Geral:":
        t = seq[i]
        if t.lstrip("-").isdigit() and i + 1 < len(seq) and _num(seq[i + 1]) is None:
            vals = [_num(v) for v in seq[i + 2:i + 12]]
            if all(v is not None for v in vals):
                out.append({"cod": t, "nome": seq[i + 1], "itens": vals[1], "venda": vals[4]})
                i += 12
                continue
        i += 1
    return out
