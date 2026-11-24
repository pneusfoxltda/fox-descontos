"""
diagnostico_pneus.py · Qual jeito conta os PNEUS certo? (teste; nada é gravado; resultado TRANCADO no registro público)
  A) Analytics, item por item: só itens cujo NOME tem uma medida (ex.: 175/75R14, 185/65R15, 205/60R17) · ideia do TI
  B) Analytics: itens das famílias de pneu
  C) Rotina 553 com todos os ARO marcados (só itens com aro)
  D) Rotina 553 com as famílias de pneu
Período: do dia 1 até ontem (o Analytics vai até ontem).
"""
import asyncio, os, re, sys
from datetime import datetime, timedelta, timezone
import httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_vendas_movere as cv
from varejo_teste import trancar

MEDIDA = re.compile(r"(?<!\d)\d{3}\s*/\s*\d{2}\s*[A-Z]{0,2}\s*R\s*-?\s*\d{2}|(?<!\d)\d{2}\s*[xX]\s*\d{1,2}[.,]\d{1,2}\s*R\s*\d{2}")


def analytics(hoje):
    from analytics_varejo_diag import executar, df, q
    ontem = hoje - timedelta(days=1)
    out = {}
    with httpx.Client(timeout=180) as cli:
        tt = cv.login_analytics(cli, os.environ["ANALYTICS_LOGIN"], os.environ["ANALYTICS_SENHA"])
        rep = q(cli, tt, f"/gdc/md/{cv.PID}/obj/1111480")["report"]
        base = q(cli, tt, rep["content"]["definitions"][-1])["reportDefinition"]["content"]
        dias = [u for u in (cv.elemento_dia(cli, tt, hoje.replace(day=1) + timedelta(days=i)) for i in range(ontem.day)) if u]
        fdia = f"[/gdc/md/{cv.PID}/obj/{cv.ATTR_DIA}] IN ({', '.join('[' + u + ']' for u in dias)})"
        at = q(cli, tt, f"/gdc/md/{cv.PID}/query/attributes")["query"]["entries"]
        cand = [(e["title"], e["link"]) for e in at if re.search(r"item|produto", e["title"], re.I)]
        print("🏷️ atributos de item:", [(t, l.split("/")[-1]) for t, l in cand][:40])
        item = next((l for t, l in cand if re.fullmatch(r"(nome|descri[cç][aã]o)\s*(do\s*)?item", t.strip(), re.I)), None) \
            or next((l for t, l in cand if t.strip().lower() in ("item", "itens", "produto")), None)
        print("   usando:", item)
        if not item:
            return {"erro": "sem atributo de item"}
        E, F, I = df(cli, tt, f"/gdc/md/{cv.PID}/obj/1583"), df(cli, tt, f"/gdc/md/{cv.PID}/obj/1637"), df(cli, tt, item)
        r = executar(cli, tt, base, [E, F, I], [f"/gdc/md/{cv.PID}/obj/2161"], (), (fdia,))
        if not isinstance(r, list):
            return {"erro": str(r)}
        print(f"   linhas: {len(r) - 1}")
        from varejo_filtros import FAMILIAS_PNEUS, norm
        fp = {norm(x) for x in FAMILIAS_PNEUS}
        lojas = {}
        fam_sem_medida, medida_fora_fam = {}, {}
        for loja, fam, nome, qt in (l[:4] for l in r[1:] if len(l) >= 4):
            try:
                qt = float(qt)
            except ValueError:
                continue
            x = lojas.setdefault(loja, {"medida": 0.0, "familia": 0.0})
            tem, ehfam = bool(MEDIDA.search(nome.upper())), norm(fam) in fp
            if tem: x["medida"] += qt
            if ehfam: x["familia"] += qt
            if ehfam and not tem: fam_sem_medida[nome] = fam_sem_medida.get(nome, 0) + qt
            if tem and not ehfam: medida_fora_fam[f"{nome} ({fam})"] = medida_fora_fam.get(f"{nome} ({fam})", 0) + qt
        out["por_loja"] = lojas
        out["familia_pneu_sem_medida"] = sorted(fam_sem_medida.items(), key=lambda x: -x[1])[:40]
        out["medida_fora_da_familia"] = sorted(medida_fora_fam.items(), key=lambda x: -x[1])[:40]
    return out


async def rotina553(hoje):
    from playwright.async_api import async_playwright
    from sync_televendas import login
    from varejo_teste import gerar
    from varejo_filtros import TABELAS_VAREJO, FAMILIAS_VAREJO, FAMILIAS_PNEUS
    os.environ["FRETE"] = "1"
    ini, fim = hoje.replace(day=1).strftime("%d/%m/%Y"), (hoje - timedelta(days=1)).strftime("%d/%m/%Y")
    out = {}
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        page = await (await b.new_context(locale="pt-BR", viewport={"width": 1400, "height": 2400})).new_page()
        await login(page)
        for nome, fam, aros in (("C_aros", FAMILIAS_VAREJO, True), ("D_familias", FAMILIAS_PNEUS, False)):
            print("▶", nome)
            r = await gerar(page, ini, fim, TABELAS_VAREJO, fam, None, aros)
            out[nome] = {"lojas": {e["nome"]: {"itens": e["itens"], "vendas": e["vendas"]} for e in r.get("estabelecimentos") or []},
                         "erro": r.get("erro")}
            print("   lojas:", len(out[nome]["lojas"]))
        await b.close()
    return out


if __name__ == "__main__":
    hoje = datetime.now(timezone(timedelta(hours=-4))).date()
    res = {"analytics": analytics(hoje)}
    res["553"] = asyncio.run(rotina553(hoje))
    b = trancar(res)
    for i in range(0, len(b), 900):
        print("TRANCADO:" + b[i:i + 900])
