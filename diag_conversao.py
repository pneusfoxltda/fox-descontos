"""SÓ LEITURA: conversão real por vendedor nos descontos (negociadas, vendidas de verdade no Movere, perdidas, vencidas,
pendentes). Registro público só com totais; por vendedor sai trancado."""
import os
from datetime import date, datetime, timedelta
import httpx
import conferir_vendas_movere as cv
import movere_api
from varejo_teste import trancar

chave = os.environ["SUPABASE_SERVICE_KEY"]
hoje = datetime.now(cv.TZ_LOJA).date()
with httpx.Client(timeout=120) as cli:
    q = []
    for ini in range(0, 20000, 1000):
        r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/descontos?select=id,numero,tipo,vendedor,liberado,perdida,motivo_perda,validade,"
                    f"criado_em,telefone_cliente,venda_movere,venda_movere_em,erro_interno&order=id",
                    headers=cv._sb_headers(chave, {"Range": f"{ini}-{ini + 999}"}))
        r.raise_for_status(); p = r.json(); q += p
        if len(p) < 1000: break
    q = [x for x in q if not x.get("erro_interno") and x.get("tipo") != "conc"]
    print("descontos (sem erro interno, sem concorrência):", len(q))
    inicio = min(cv.data_local(x["criado_em"]) for x in q)
    print("primeiro cadastro:", inicio)
    tt = cv.login_analytics(cli, os.environ["ANALYTICS_LOGIN"], os.environ["ANALYTICS_SENHA"])
    dias = [inicio + timedelta(days=i) for i in range((hoje - inicio).days + 1)]
    els = [u for u in (cv.elemento_dia(cli, tt, d) for d in dias) if u]
    filtro = f"[{cv._md()}/obj/{cv.ATTR_DIA}] IN ({', '.join('[' + u + ']' for u in els)})"
    vendas = cv.vendas_por_telefone(cv.relatorio(cli, tt, cv.REL_VENDAS, None, filtro))
api_tel, api_orc = movere_api.buscar(hoje - timedelta(days=movere_api.DIAS_API), hoje)
vendas = movere_api.juntar(vendas, api_tel)
com_tel = [x for x in q if x.get("telefone_cliente")]
vend_ids = {m["id"] for m in cv.cruzar(com_tel, vendas, api_orc)} | {x["id"] for x in q if x.get("venda_movere")}

def isexp(v):
    return bool(v) and date.fromisoformat(v[:10]) < hoje

por = {}
for x in q:
    v = (x.get("vendedor") or "(sem vendedor)").strip()
    d = por.setdefault(v, {"neg": 0, "vendido": 0, "liberado": 0, "lib_e_vendido": 0, "perdido": 0, "vencido": 0, "pendente": 0, "sem_tel": 0})
    d["neg"] += 1
    if not x.get("telefone_cliente"): d["sem_tel"] += 1
    if x.get("liberado"): d["liberado"] += 1
    if x["id"] in vend_ids:
        d["vendido"] += 1
        if x.get("liberado"): d["lib_e_vendido"] += 1
    elif x.get("perdida") and (x.get("motivo_perda") or "").startswith("Validade expirada"):
        d["vencido"] += 1
    elif x.get("perdida"):
        d["perdido"] += 1
    elif isexp(x.get("validade")):
        d["vencido"] += 1
    else:
        d["pendente"] += 1
tot = {k: sum(d[k] for d in por.values()) for k in next(iter(por.values()))}
print("TOTAL:", tot)
print("Z TRANCADO:", trancar({"por": por, "tot": tot, "inicio": inicio.isoformat()}))
