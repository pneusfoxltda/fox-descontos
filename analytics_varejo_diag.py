"""
analytics_varejo_diag.py · por que o Analytics ("Jonathan - Faturamento Varejo") e a rotina 553 dão números diferentes?
Quebra o faturamento de 01 a 21/11/2026 por loja × tabela de preço, por loja × segmento de venda (com e sem o filtro)
e com/sem devolução. Só metadados no registro público; os VALORES saem trancados.
"""
import csv, io, json, os, re, sys, time
from datetime import date, timedelta
import httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_vendas_movere as cv
from varejo_teste import trancar

GD, PID = cv.GD, cv.PID
MD = f"/gdc/md/{PID}"
REL = 1111480
M_FAT, M_FAT_SEM_DEV, M_DEV = f"{MD}/obj/2160", f"{MD}/obj/3982", f"{MD}/obj/3983"
A_ESTAB, A_TABELA, A_SEGMENTO, A_FAMILIA = f"{MD}/obj/1583", f"{MD}/obj/3800", f"{MD}/obj/1539", f"{MD}/obj/1637"


def q(cli, tt, uri):
    return cv._gd_json(cli, tt, uri)


def df(cli, tt, attr):
    return q(cli, tt, attr)["attribute"]["content"]["displayForms"][0]["meta"]["uri"]


def executar(cli, tt, base, linhas, metricas, tirar=(), extra=()):
    c = json.loads(json.dumps(base))
    c["grid"] = {"rows": [{"attribute": {"alias": "", "totals": [], "uri": u}} for u in linhas], "columns": ["metricGroup"],
                 "sort": {"columns": [], "rows": []}, "columnWidths": [],
                 "metrics": [{"uri": m, "alias": ""} for m in metricas]}
    c["filters"] = [f for f in (c.get("filters") or []) if not any(t in f.get("expression", "") for t in tirar)] + [{"expression": e} for e in extra]
    r = cli.post(f"{GD}/gdc/app/projects/{PID}/execute/raw", headers={"Accept": "application/json", "X-GDC-AuthTT": tt},
                 json={"report_req": {"definitionContent": {"content": {"reportDefinition": {"content": c, "meta": {"title": "auto"}}}, "projectMetadata": MD}}})
    if r.status_code >= 300:
        return {"erro": f"{r.status_code} {r.text[:200]}"}
    uri = r.json()["uri"]
    for _ in range(90):
        g = cli.get(cv._abs(uri), headers={"X-GDC-AuthTT": tt}, follow_redirects=True)
        if g.status_code == 200:
            return list(csv.reader(io.StringIO(g.content.decode("utf-8-sig"))))
        if g.status_code == 204:
            return []
        if g.status_code >= 400:
            return {"erro": g.status_code}
        time.sleep(2)
    return {"erro": "demorou"}


def main():
    out = {}
    with httpx.Client(timeout=180) as cli:
        tt = cv.login_analytics(cli, os.environ["ANALYTICS_LOGIN"], os.environ["ANALYTICS_SENHA"])
        rep = q(cli, tt, f"{MD}/obj/{REL}")["report"]
        base = q(cli, tt, rep["content"]["definitions"][-1])["reportDefinition"]["content"]
        dias = [cv.elemento_dia(cli, tt, date(2026, 11, 1) + timedelta(days=i)) for i in range(21)]
        fdia = f"[{MD}/obj/{cv.ATTR_DIA}] IN ({', '.join('[' + u + ']' for u in dias if u)})"
        E, T, S, F = df(cli, tt, A_ESTAB), df(cli, tt, A_TABELA), df(cli, tt, A_SEGMENTO), df(cli, tt, A_FAMILIA)
        at = q(cli, tt, f"{MD}/query/attributes")["query"]["entries"]
        cand = [(e["title"], e["link"]) for e in at if re.search(r"vendedor", e["title"], re.I)]
        print("🏷️ atributos de vendedor:", [(t, l.split("/")[-1]) for t, l in cand])
        vend = next((l for t, l in cand if re.fullmatch(r"(nome )?vendedor( 1)?", t.strip(), re.I)), None) or next((l for t, l in cand if "nome" in t.lower() and "vendedor" in t.lower()), None)
        print("   usando:", vend)
        if os.environ.get("CLIENTES_REVENDA"):   # pedido do TI: código do cliente das vendas de REVENDA
            cc = [(e["title"], e["link"]) for e in at if re.search(r"cliente|nota|documento", e["title"], re.I)]
            print("🏷️ atributos de cliente/nota:", [(t, l.split("/")[-1]) for t, l in cc])
            esc = [l for t, l in cc if re.fullmatch(r"(c[oó]d(igo)?\.?|id|nome)?\s*(do\s+)?cliente", t.strip(), re.I)][:3]
            esc += [l for t, l in cc if re.search(r"n[uú]mero.*(nota|documento)|^(nota|documento)", t.strip(), re.I)][:1]
            print("   usando:", [l.split("/")[-1] for l in esc])
            linhas = ([E, df(cli, tt, vend), S] if vend else [E, S]) + [df(cli, tt, f"{MD}/obj/{cv.ATTR_DIA}")]
            dfs = []
            for l in esc:
                for d in q(cli, tt, l)["attribute"]["content"]["displayForms"]:
                    dfs.append(d["meta"]["uri"])
            r = executar(cli, tt, base, linhas + dfs, [M_FAT], ("obj/1539]",), (fdia,))
            if isinstance(r, list) and r:
                out["8_revenda_clientes"] = [r[0]] + [x for x in r[1:] if any("REVENDA" in str(c).upper() for c in x)]
            else:
                out["8_revenda_clientes"] = r
            print("▶ 8_revenda_clientes:", len(out["8_revenda_clientes"]) if isinstance(out["8_revenda_clientes"], list) else out["8_revenda_clientes"], "linhas")
        testes = {} if os.environ.get("CLIENTES_REVENDA") else {"7_loja_x_vendedor_x_segmento": ([E, df(cli, tt, vend), S], [M_FAT], ("obj/1539]",), ())} if vend else {}
        _antigos = {
            "1_loja_com_e_sem_devolucao": ([E], [M_FAT, M_FAT_SEM_DEV, M_DEV], (), ()),
            "2_loja_x_tabela": ([E, T], [M_FAT], (), ()),
            "3_loja_x_segmento_SEM_filtro_segmento": ([E, S], [M_FAT], ("obj/1539]",), ()),
            "4_tabelas_do_filtro": ([T], [M_FAT], (), ()),
            "5_loja_x_tabela_SEM_filtro_tabela": ([E, T], [M_FAT], ("obj/3800]",), ()),
        }
        for nome, (linhas, mets, tirar, extra) in testes.items():
            out[nome] = executar(cli, tt, base, linhas, mets, tirar, (fdia,) + extra)
            n = len(out[nome]) if isinstance(out[nome], list) else out[nome]
            print(f"▶ {nome}: {n} linhas" + (f" · cabeçalho {out[nome][0]}" if isinstance(out[nome], list) and out[nome] else ""))
    print("\n===== RESULTADO TRANCADO (início) =====")
    b = trancar(out)
    for i in range(0, len(b), 900):
        print("TRANCADO:" + b[i:i + 900])
    print("===== RESULTADO TRANCADO (fim) =====")


if __name__ == "__main__":
    main()
