"""Teste: campos que as rotas da API do Movere devolvem (documentação PÚBLICA do Swagger). Sem login, nada gravado."""
import httpx
ALVO = {"/api/NotasFiscaisEmitidas", "/api/NotasFiscaisEmitidasPorEstruturaDeItens", "/api/ConsultaOrcamentos", "/api/Vendedores",
        "/api/Documentos", "/api/Clientes", "/api/Leads"}
for doc in ("movere-api", "movere-inteligente"):
    j = httpx.get(f"https://api.moveresoftware.com/swagger/docs/{doc}", timeout=60).json()
    defs = j.get("definitions") or {}
    def campos(ref, nivel=0, vistos=()):
        nome = ref.split("/")[-1]
        if nome in vistos or nivel > 3: return
        d = defs.get(nome) or {}
        for k, v in (d.get("properties") or {}).items():
            tipo = v.get("type") or (v.get("$ref") or "").split("/")[-1] or ((v.get("items") or {}).get("$ref") or "").split("/")[-1]
            desc = (v.get("description") or "").replace("\n", " ")[:90]
            print("   " + "  " * nivel + f"- {k}: {tipo} {desc}")
            sub = v.get("$ref") or (v.get("items") or {}).get("$ref")
            if sub: campos(sub, nivel + 1, vistos + (nome,))
    for path, ops in (j.get("paths") or {}).items():
        if path not in ALVO: continue
        for verbo, op in ops.items():
            print(f"\n##### {verbo.upper()} {path} · {op.get('summary')}")
            print("   descrição:", (op.get("description") or "").replace("\n", " ")[:400])
            for p in op.get("parameters") or []:
                print(f"   param {p.get('name')} ({p.get('in')}, {p.get('type') or ''}) {(p.get('description') or '')[:120]}")
            for cod, resp in (op.get("responses") or {}).items():
                sch = resp.get("schema") or {}
                ref = sch.get("$ref") or (sch.get("items") or {}).get("$ref")
                print(f"   resposta {cod}: {resp.get('description','')[:80]} {ref or ''}")
                if ref and cod.startswith("2"): campos(ref)
