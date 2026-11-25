"""Teste: lista as rotas da documentação PÚBLICA (Swagger) da API do Movere. Sem login, sem senha, nada gravado."""
import json, httpx
for doc in ("movere-api", "movere-inteligente", "v1"):
    url = f"https://api.moveresoftware.com/swagger/docs/{doc}"
    try:
        r = httpx.get(url, timeout=60, follow_redirects=True)
        print(f"\n===== {doc}: HTTP {r.status_code} · {len(r.content)} bytes")
        if r.status_code != 200:
            print(r.text[:300]); continue
        j = r.json()
        for path, ops in sorted((j.get("paths") or {}).items()):
            for verbo, op in ops.items():
                if not isinstance(op, dict): continue
                params = [p.get("name") for p in op.get("parameters") or [] if isinstance(p, dict)]
                print(f"{verbo.upper():6} {path}  [{', '.join(op.get('tags') or [])}]  {op.get('summary') or ''}  params={params[:12]}")
    except Exception as e:
        print(doc, "erro:", type(e).__name__, str(e)[:200])
