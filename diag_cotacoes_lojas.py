"""Teste SÓ DE LEITURA (não grava nada): quantas cotações das LOJAS (vendedores) apareceriam nas Ligações.
Compara o relatório 782403 com o filtro do televendas (dashboard 782276) e sem o filtro.
No registro público só contagens; nomes de operadores e valores saem trancados (trancar)."""
import os, statistics
from datetime import date, timedelta
import httpx
import conferir_vendas_movere as cv
import ligacoes_lojas as ll
from varejo_teste import trancar

with httpx.Client(timeout=180) as cli:
    tt = cv.login_analytics(cli, os.environ["ANALYTICS_LOGIN"], os.environ["ANALYTICS_SENHA"])
    print("login ok")
    hoje = date(2026, 11, 25)
    dias = [hoje - timedelta(days=i) for i in (4, 3, 2, 1)]   # 21 a 24/11
    uris = {d: u for d in dias if (u := cv.elemento_dia(cli, tt, d))}
    filtro = ll.filtro_dias(list(uris.values()))
    tv = ll.cotacoes(cv.relatorio(cli, tt, ll.REL_COT, ll.DASH_COT, filtro))
    todas_l = cv.relatorio(cli, tt, ll.REL_COT, None, filtro)
    todas = ll.cotacoes(todas_l)
    print("cabeçalho:", todas_l[0] if todas_l else None)
    ops_tv = {c["operador"] for c in tv}
    cot_tv = {c["cotacao"] for c in tv}
    print(f"dias no Analytics: {[d.strftime('%d/%m') for d in uris]}")
    print(f"COM filtro televendas: {len(tv)} cotações · operadores {len(ops_tv)}")
    print(f"SEM filtro: {len(todas)} cotações · operadores {len({c['operador'] for c in todas})}")
    lojas = [c for c in todas if c["cotacao"] not in cot_tv and c["operador"] not in ops_tv]
    print(f"Cotações das LOJAS (não televendas): {len(lojas)}")
    por = {}
    for c in lojas:
        k = (c["data"].strftime("%d/%m"), c["loja"])
        p = por.setdefault(k, [0, 0, 0, set()])
        p[0] += 1; p[1] += 1 if c.get("medida") else 0; p[2] += 1 if c["telefone"] and len("".join(ch for ch in c["telefone"] if ch.isdigit())) >= 8 else 0
        p[3].add(c["operador"])
    print("dia | loja | cotações | com medida de pneu | com telefone | vendedores")
    for k in sorted(por):
        p = por[k]; print(f"{k[0]} | {k[1]} | {p[0]} | {p[1]} | {p[2]} | {len(p[3])}")
    seg = {}
    for c in lojas:
        seg.setdefault(c["loja"], {}).setdefault(c["operador"], [0, []])
        s = seg[c["loja"]][c["operador"]]; s[0] += 1; s[1].append(c["valor"])
    det = {l: {o: [v[0], round(statistics.median(v[1]), 2)] for o, v in ops.items()} for l, ops in seg.items()}
    vals = [c["valor"] for c in lojas]
    # coluna "Vendedor" (r[6]) das cotações das lojas
    vend = {}
    for r in todas_l[1:]:
        if len(r) < 9 or r[0].strip() in cot_tv or r[5].strip() in ops_tv: continue
        vend.setdefault(r[4].strip(), {}).setdefault(r[6].strip(), set()).add(r[0].strip())
    print("loja | vendedores distintos (coluna Vendedor) | cotações com vendedor 'Não informado'/vazio")
    for l, v in sorted(vend.items()):
        sem = sum(len(c) for k, c in v.items() if not k or k.lower().startswith("n"+"ão inf"))
        print(f"{l} | {len(v)} | {sem}")
    # na mesma cotação, mais de um vendedor?
    multi = {}
    for r in todas_l[1:]:
        if len(r) >= 9: multi.setdefault(r[0].strip(), set()).add(r[6].strip())
    print("cotações com mais de 1 vendedor:", sum(1 for v in multi.values() if len(v) > 1))
    print("Z TRANCADO:", trancar({l: {k: len(c) for k, c in v.items()} for l, v in vend.items()}))
    print("Z2 TRANCADO_IGNORAR:", trancar({"operadores_por_loja": det, "ops_tv": sorted(ops_tv),
          "valor_mediana": statistics.median(vals) if vals else 0, "acima_500": sum(v >= 500 for v in vals),
          "acima_1000": sum(v >= 1000 for v in vals)}))
