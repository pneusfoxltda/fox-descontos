"""SÓ LEITURA: medidas em que a Fox não conseguiu cobrir a oferta. Por medida: negociações, fechou (liberado ou venda
no Movere), não fechou (vencida/perdida), concorrente mais barato que o nosso valor com desconto (e quanto), concorrentes
mais citados, e os registros só de concorrência (tipo conc). Registro público só com totais; o resto sai trancado."""
import os, re
from datetime import date, datetime
import httpx
import conferir_vendas_movere as cv
from varejo_teste import trancar

chave = os.environ["SUPABASE_SERVICE_KEY"]
hoje = datetime.now(cv.TZ_LOJA).date()
def conc_obs(obs):
    obs = obs or ""; i = obs.find("CONCORRENTES:")
    if i < 0: return []
    out = []
    for l in obs[i:].split("\n"):
        l = l.strip()
        if not l.startswith("•"): continue
        s = l.lstrip("• ").strip(); ci = s.find(":")
        if ci < 0: continue
        m = re.search(r"R\$\s*([\d.,]+)", s[ci:])
        v = float(m.group(1).replace(".", "").replace(",", ".")) if m else 0.0
        out.append((s[:ci].strip(), v))
    return out
def norm_med(m):
    return re.sub(r"\s+", "", str(m or "").upper().replace("-", "/")) or "(sem medida)"
with httpx.Client(timeout=120) as cli:
    q = []
    for ini in range(0, 20000, 1000):
        r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/descontos?select=id,tipo,medida,segmento,loja,valor,obs,liberado,perdida,motivo_perda,validade,criado_em,venda_movere,erro_interno&order=id",
                    headers=cv._sb_headers(chave, {"Range": f"{ini}-{ini + 999}"}))
        r.raise_for_status(); p = r.json(); q += p
        if len(p) < 1000: break
q = [x for x in q if not x.get("erro_interno")]
med, conc_emp, motivos = {}, {}, {}
for x in q:
    k = norm_med(x.get("medida")); d = med.setdefault(k, {"neg": 0, "fechou": 0, "nao_fechou": 0, "pend": 0, "so_conc": 0,
        "com_conc": 0, "conc_mais_barato": 0, "gap_soma": 0.0, "nao_fechou_conc_barato": 0, "segmento": {}, "empresas": {}})
    concs = [c for c in conc_obs(x.get("obs")) if c[1] > 0]
    for e, v in concs:
        d["empresas"][e] = d["empresas"].get(e, 0) + 1; conc_emp[e] = conc_emp.get(e, 0) + 1
    if x.get("tipo") == "conc":
        d["so_conc"] += 1; continue
    d["neg"] += 1; seg = x.get("segmento") or "?"; d["segmento"][seg] = d["segmento"].get(seg, 0) + 1
    fechou = bool(x.get("liberado") or x.get("venda_movere"))
    try: vencida = bool(x.get("validade")) and date.fromisoformat(x["validade"][:10]) < hoje
    except ValueError: vencida = False   # validade digitada errada (ex.: ano com 5 números)
    if fechou: d["fechou"] += 1
    elif vencida or x.get("perdida"): d["nao_fechou"] += 1
    else: d["pend"] += 1
    if x.get("perdida") and not str(x.get("motivo_perda") or "").startswith("Validade expirada"):
        motivos[x["motivo_perda"]] = motivos.get(x["motivo_perda"], 0) + 1
    try: nosso = float(x.get("valor") or 0)
    except ValueError: nosso = 0
    if concs:
        d["com_conc"] += 1
        menor = min(v for _, v in concs)
        if nosso and menor < nosso:
            d["conc_mais_barato"] += 1; d["gap_soma"] += nosso - menor
            if not fechou: d["nao_fechou_conc_barato"] += 1
print("registros:", len(q), "· medidas:", len(med), "· com concorrência citada:", sum(d["com_conc"] for d in med.values()),
      "· só concorrência (tipo conc):", sum(d["so_conc"] for d in med.values()))
print("Z TRANCADO:", trancar({"med": med, "conc_emp": conc_emp, "motivos": motivos}))
