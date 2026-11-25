"""Teste (não grava): quais famílias têm itens com MEDIDA no nome (pneus), sem filtro de tabela/família. Resultado trancado."""
import os, re, sys
from datetime import datetime, timedelta, timezone
import httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_vendas_movere as cv
from varejo_teste import trancar
from analytics_varejo_diag import executar, df, q
MEDIDA = re.compile(r"(?<!\d)\d{3}\s*/\s*\d{2}\s*[A-Z]{0,2}\s*R\s*-?\s*\d{2}|(?<!\d)\d{2}\s*[xX]\s*\d{1,2}[.,]\d{1,2}\s*R\s*\d{2}|(?<!\d)\d{1,2}[.,]?\d{0,2}\s*R\s*\d{2}(?:[.,]5)?\b|(?<!\d)\d{3,4}\s*[xX]\s*\d{2}")
hoje = datetime.now(timezone(timedelta(hours=-4))).date(); ontem = hoje - timedelta(days=1)
with httpx.Client(timeout=180) as cli:
    tt = cv.login_analytics(cli, os.environ["ANALYTICS_LOGIN"], os.environ["ANALYTICS_SENHA"])
    rep = q(cli, tt, f"/gdc/md/{cv.PID}/obj/1111480")["report"]
    base = q(cli, tt, rep["content"]["definitions"][-1])["reportDefinition"]["content"]
    dias = [u for u in (cv.elemento_dia(cli, tt, hoje.replace(day=1) + timedelta(days=i)) for i in range(ontem.day)) if u]
    fdia = f"[/gdc/md/{cv.PID}/obj/{cv.ATTR_DIA}] IN ({', '.join('[' + u + ']' for u in dias)})"
    F, I = df(cli, tt, f"/gdc/md/{cv.PID}/obj/1637"), df(cli, tt, f"/gdc/md/{cv.PID}/obj/1609")
    r = executar(cli, tt, base, [F, I], [f"/gdc/md/{cv.PID}/obj/2161"], ("obj/1637]", "obj/3800]", "obj/1583]", "obj/1539]"), (fdia,))
    print("linhas:", len(r) if isinstance(r, list) else r)
    fam = {}
    for f, nome, qt in (l[:3] for l in (r[1:] if isinstance(r, list) else []) if len(l) >= 3):
        try: qt = float(qt)
        except ValueError: continue
        x = fam.setdefault(f, {"com_medida": 0.0, "sem_medida": 0.0, "ex_com": [], "ex_sem": []})
        if MEDIDA.search(nome.upper()):
            x["com_medida"] += qt; len(x["ex_com"]) < 4 and x["ex_com"].append(nome)
        else:
            x["sem_medida"] += qt; len(x["ex_sem"]) < 6 and x["ex_sem"].append(nome)
b = trancar(fam)
for i in range(0, len(b), 900): print("TRANCADO:" + b[i:i + 900])
