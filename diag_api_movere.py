"""Teste da API do Movere (só leitura): um login novo derruba o token anterior do mesmo usuário?
Faz 2 logins (token A e token B) e testa o A de novo. Também conta as vendas e cotações de hoje de uma loja.
Não imprime senha, token, nem dado de cliente: só códigos HTTP, contagens e datas."""
import os, time, base64, json, datetime
import httpx
BASE = "https://api.moveresoftware.com"
cred = {"ambiente": os.environ["MOVERE_API_AMBIENTE"].strip(), "usuario": os.environ["MOVERE_API_USUARIO"].strip(),
        "senha": os.environ["MOVERE_API_SENHA"].strip()}
cli = httpx.Client(timeout=90)

def validade(tok):
    try:
        p = tok.split(".")[1]; p += "=" * (-len(p) % 4); d = json.loads(base64.urlsafe_b64decode(p))
        if "exp" in d:
            return datetime.datetime.fromtimestamp(d["exp"], datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    except Exception:
        pass
    return "sem data"

def login(n):
    r = cli.post(BASE + "/api/LoginComAmbiente", json=cred)
    tok = ""
    try: tok = (r.json() or {}).get("token") or ""
    except Exception: pass
    print(f"Login {n}: HTTP {r.status_code} · token {'recebido' if tok else 'NÃO veio'} · vale até {validade(tok) if tok else '-'}")
    if not tok: print("   resposta:", r.text[:160].replace(cred['senha'], '***'))
    return tok

def testa(nome, tok, rota="/api/Estabelecimentos", params=None):
    r = cli.get(BASE + rota, headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"}, params=params or {})
    info = ""
    try:
        j = r.json()
        info = f"{len(j)} registros" if isinstance(j, list) else "objeto"
    except Exception:
        info = "texto: " + r.text[:120]
    print(f"{nome}: {rota} → HTTP {r.status_code} · {info}")
    return r

A = login(1)
if A:
    testa("Token A (logo depois do login 1)", A)
    time.sleep(5)
    B = login(2)
    if B:
        print("Tokens A e B são iguais?", "SIM (o Movere devolve o mesmo token)" if A == B else "não")
        time.sleep(3)
        ra = testa("Token A DEPOIS do login 2", A)
        testa("Token B", B)
        print("\n>>> RESULTADO:", "o login novo NÃO derruba o token anterior ✅" if ra.status_code == 200
              else "o login novo DERRUBA o token anterior ⚠️ (ou o token A falhou por outro motivo)")
        # Contagens de hoje (só números): vendas e cotações da loja 1 (MATRIZ)
        hoje = (datetime.datetime.utcnow() - datetime.timedelta(hours=4)).strftime("%Y-%m-%d")
        rv = testa("Vendas de hoje (notas emitidas, loja 1)", B, "/api/NotasFiscaisEmitidas", {"codigoLoja": 1, "emissaoInicial": hoje, "emissaoFinal": hoje, "pagina": 1})
        rc = testa("Cotações/orçamentos de hoje (loja 1)", B, "/api/ConsultaOrcamentos", {"codigoLoja": 1, "emissaoInicial": hoje, "emissaoFinal": hoje, "pagina": 1})
        for nome, r in (("vendas", rv), ("cotações", rc)):
            try:
                j = r.json()
                if isinstance(j, list) and j:
                    print(f"   {nome}: campos do 1º registro → {sorted(list(j[0].keys()))[:15]}")
            except Exception:
                pass
