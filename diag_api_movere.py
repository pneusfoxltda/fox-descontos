"""Teste da API do Movere (só leitura): quais segredos existem e se o TOKEN funciona numa consulta simples.
NÃO faz login (não gera token novo, não derruba outra integração que usa o mesmo usuário). Não imprime nenhum valor."""
import os, httpx
BASE = "https://api.moveresoftware.com"
for n in ("MOVERE_API_AMBIENTE", "MOVERE_API_USUARIO", "MOVERE_API_SENHA", "MOVERE_API_TOKEN"):
    print(f"{n}: {'existe' if os.environ.get(n, '').strip() else 'NÃO existe (ou vazio)'}")
tok = os.environ.get("MOVERE_API_TOKEN", "").strip()
if tok.lower().startswith("bearer "):
    tok = tok[7:].strip()
if not tok:
    print("Sem token: nada a testar."); raise SystemExit(0)
H = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
for rota in ("/api/Versao", "/api/Estabelecimentos"):
    try:
        r = httpx.get(BASE + rota, headers=H, timeout=60)
        corpo = r.text or ""
        tipo = "lista" if corpo.strip().startswith("[") else "objeto" if corpo.strip().startswith("{") else "texto"
        qtd = ""
        if tipo == "lista":
            try: qtd = f" · {len(r.json())} registros"
            except Exception: pass
        print(f"{rota}: HTTP {r.status_code} · resposta {tipo}{qtd}")
        if r.status_code in (401, 403):
            print("   → token recusado (vencido ou sem permissão)")
    except Exception as e:
        print(f"{rota}: erro {type(e).__name__}")
# Validade do token (só a data, lida do próprio token; nada do conteúdo é impresso)
try:
    import base64, json, datetime
    p = tok.split(".")[1]; p += "=" * (-len(p) % 4)
    d = json.loads(base64.urlsafe_b64decode(p))
    for k in ("exp", "nbf", "iat"):
        if k in d:
            print(f"token {k}: {datetime.datetime.utcfromtimestamp(d[k]).strftime('%d/%m/%Y %H:%M')} (UTC)")
except Exception:
    print("token sem data de validade legível")
