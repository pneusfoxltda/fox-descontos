"""Diagnóstico (só leitura): NOMES dos campos que a API do Movere devolve na O.S. e na nota (sem valores, sem cliente).
Para saber se dá para separar Varejo/Atacado (tabela de preço) e o vendedor direto pela API."""
import os, sys
from datetime import datetime, timedelta
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import movere_api as m


def chaves(o, pre="", out=None, nivel=0):
    out = out if out is not None else set()
    if isinstance(o, dict) and nivel < 4:
        for k, v in o.items():
            out.add(pre + k + (" {}" if isinstance(v, dict) else " []" if isinstance(v, list) else ""))
            if isinstance(v, dict):
                chaves(v, pre + k + ".", out, nivel + 1)
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                chaves(v[0], pre + k + "[].", out, nivel + 1)
    return out


hoje = datetime.utcnow().date()
desde = hoje - timedelta(days=3)
with httpx.Client(timeout=120) as cli:
    tok = m.login(cli)
    loja = "1"
    for status in (2, 1):
        l = m._lista(m._get(cli, tok, "/api/ConsultaOrcamentos", {"codigoLoja": loja, "emissaoInicial": desde.isoformat(),
                     "emissaoFinal": hoje.isoformat(), "status": status, "pagina": 1}))
        print(f"\n== ConsultaOrcamentos status {status}: {len(l)} registros · campos:")
        ks = set()
        for x in l[:20]:
            chaves(x, out=ks)
        for k in sorted(ks):
            if any(p in k.lower() for p in ("vend", "tabela", "preco", "preço", "func", "operador", "usuario", "estab", "loja", "total", "valor", "tipo", "status", "data")):
                print("  *", k)
        print("  (todos):", ", ".join(sorted(k.split(" ")[0] for k in ks))[:3000])
    ns = m._lista(m._get(cli, tok, "/api/NotasFiscaisEmitidas", {"codigoLoja": loja, "emissaoInicial": desde.isoformat(),
                  "emissaoFinal": hoje.isoformat(), "pagina": 1}))
    print(f"\n== NotasFiscaisEmitidas: {len(ns)} registros · campos:")
    ks = set()
    for x in ns[:20]:
        chaves(x, out=ks)
    print("  (todos):", ", ".join(sorted(k.split(" ")[0] for k in ks))[:3000])
