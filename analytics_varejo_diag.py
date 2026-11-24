"""
analytics_varejo_diag.py · Varejo pelo Analytics (relatório "Jonathan - Faturamento Varejo", que gera a planilha do TI).
Mostra só METADADOS (nomes de relatórios, atributos, métricas e a montagem dos filtros). Os VALORES saem trancados.
"""
import json, os, re, sys
from datetime import date, timedelta
import httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_vendas_movere as cv
from varejo_teste import trancar

GD, PID = cv.GD, cv.PID
MD = f"/gdc/md/{PID}"


def q(cli, tt, uri):
    return cv._gd_json(cli, tt, uri)


def main():
    out = {}
    with httpx.Client(timeout=120) as cli:
        tt = cv.login_analytics(cli, os.environ["ANALYTICS_LOGIN"], os.environ["ANALYTICS_SENHA"])
        print("✅ login no Analytics")
        reps = q(cli, tt, f"{MD}/query/reports")["query"]["entries"]
        alvo = [e for e in reps if "faturamento varejo" in e["title"].lower()]
        print(f"📄 relatórios com 'Faturamento Varejo': {[(e['title'], e['link'].split('/')[-1]) for e in alvo]}")
        rep = q(cli, tt, alvo[0]["link"])["report"]
        rid = alvo[0]["link"].split("/")[-1]
        c = q(cli, tt, rep["content"]["definitions"][-1])["reportDefinition"]["content"]
        print("🧩 grade:", json.dumps(c.get("grid"), ensure_ascii=False)[:1500])
        print("🔎 filtros:")
        attrs = {}
        for f in c.get("filters") or []:
            ex = f.get("expression", "")
            uris = sorted(set(re.findall(r"\[(/gdc/md/[^\]]+)\]", ex)))
            a = [u for u in uris if "/elements" not in u]
            nomes = []
            for u in a:
                try:
                    o = q(cli, tt, u); k = next(iter(o)); nomes.append(f"{o[k]['meta']['title']} ({u.split('/')[-1]})")
                    attrs[o[k]["meta"]["title"]] = u
                except Exception:
                    nomes.append(u)
            print(f"   - {nomes} · {len([u for u in uris if '/elements' in u])} valores · {ex[:160]}")
        # atributos e métricas que podem servir (loja, vendedor, dia, quantidades)
        at = q(cli, tt, f"{MD}/query/attributes")["query"]["entries"]
        me = q(cli, tt, f"{MD}/query/metrics")["query"]["entries"]
        print("🏷️ atributos úteis:", [(e["title"], e["link"].split("/")[-1]) for e in at if re.search(r"estabelec|vendedor|dtaemiss|segmento|cliente$|nota|documento", e["title"], re.I)][:40])
        print("📏 métricas úteis:", [(e["title"], e["link"].split("/")[-1]) for e in me if re.search(r"fatur|quant|qtd|cliente|item|venda|ticket|devol", e["title"], re.I)][:60])

        # Execução de teste: 01 a 21/11/2026, linhas = loja
        estab_attr = next((u for t, u in attrs.items() if "estabelec" in t.lower()), None)
        dfs = q(cli, tt, estab_attr)["attribute"]["content"]["displayForms"]
        estab_df = dfs[0]["meta"]["uri"]
        dias = [cv.elemento_dia(cli, tt, date(2026, 11, 1) + timedelta(days=i)) for i in range(21)]
        filtro_dia = f"[{MD}/obj/{cv.ATTR_DIA}] IN ({', '.join('[' + u + ']' for u in dias if u)})"
        c2 = json.loads(json.dumps(c))
        c2["grid"]["rows"] = [{"attribute": {"alias": "", "totals": [], "uri": estab_df}}]
        c2["grid"]["columns"] = ["metricGroup"]
        c2["grid"]["sort"] = {"columns": [], "rows": []}
        c2["grid"]["columnWidths"] = []
        c2["filters"] = (c2.get("filters") or []) + [{"expression": filtro_dia}]
        r = cli.post(f"{GD}/gdc/app/projects/{PID}/execute/raw", headers={"Accept": "application/json", "X-GDC-AuthTT": tt},
                     json={"report_req": {"definitionContent": {"content": {"reportDefinition": {"content": c2, "meta": {"title": "auto"}}}, "projectMetadata": MD}}})
        print("▶ execução por loja:", r.status_code, r.text[:200] if r.status_code >= 300 else "")
        linhas = []
        if r.status_code < 300:
            import csv, io, time
            uri = r.json()["uri"]
            for _ in range(90):
                g = cli.get(cv._abs(uri), headers={"X-GDC-AuthTT": tt}, follow_redirects=True)
                if g.status_code == 200:
                    linhas = list(csv.reader(io.StringIO(g.content.decode("utf-8-sig")))); break
                if g.status_code >= 400:
                    print("   erro", g.status_code); break
                time.sleep(2)
        print(f"   linhas: {len(linhas)} · cabeçalho: {linhas[0] if linhas else None}")
        out = {"relatorio": rid, "por_loja_01_21": linhas}
    print("\n===== RESULTADO TRANCADO (início) =====")
    b = trancar(out)
    for i in range(0, len(b), 900):
        print("TRANCADO:" + b[i:i + 900])
    print("===== RESULTADO TRANCADO (fim) =====")


if __name__ == "__main__":
    main()
