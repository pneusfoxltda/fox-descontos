"""SÓ LEITURA: conversão por vendedor igual às abas do Consultar (Todos, Liberados, Venda concluída, Vencidas, Válidos),
no mês, no ano e no total. Registro público só com totais; por vendedor sai trancado."""
import os
from datetime import date, datetime
import httpx
import conferir_vendas_movere as cv
from varejo_teste import trancar

chave = os.environ["SUPABASE_SERVICE_KEY"]
hoje = datetime.now(cv.TZ_LOJA).date()
with httpx.Client(timeout=120) as cli:
    q = []
    for ini in range(0, 20000, 1000):
        r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/descontos?select=id,tipo,vendedor,liberado,perdida,validade,criado_em,venda_movere,erro_interno&order=id",
                    headers=cv._sb_headers(chave, {"Range": f"{ini}-{ini + 999}"}))
        r.raise_for_status(); p = r.json(); q += p
        if len(p) < 1000: break
print("registros:", len(q), "· erro interno:", sum(1 for x in q if x.get("erro_interno")), "· concorrência:", sum(1 for x in q if x.get("tipo") == "conc"))
exp = lambda v: bool(v) and date.fromisoformat(v[:10]) < hoje
def classe(x):
    if x.get("liberado"): return "liberado"
    if x.get("venda_movere"): return "venda_movere"
    if exp(x.get("validade")): return "vencida"
    if x.get("perdida"): return "perdida_no_prazo"
    return "valido"
out = {}
for nome, f in (("mes", lambda d: d.year == hoje.year and d.month == hoje.month), ("ano", lambda d: d.year == hoje.year), ("total", lambda d: True)):
    por = {}
    for x in q:
        if x.get("erro_interno") or not f(cv.data_local(x["criado_em"])): continue
        v = (x.get("vendedor") or "(sem vendedor)").strip()
        d = por.setdefault(v, {"neg": 0, "liberado": 0, "venda_movere": 0, "vencida": 0, "perdida_no_prazo": 0, "valido": 0})
        d["neg"] += 1; d[classe(x)] += 1
    out[nome] = por
    print(nome, {k: sum(d[k] for d in por.values()) for k in ("neg", "liberado", "venda_movere", "vencida", "perdida_no_prazo", "valido")})
print("Z TRANCADO:", trancar(out))
