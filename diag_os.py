"""SÓ LEITURA: campos da ConsultaOrcamentos (cotação → O.S.) na API do Movere. Só nomes e tipos (e datas/status)."""
import httpx, movere_api as ma
from datetime import date, timedelta
with httpx.Client(timeout=120) as cli:
    tok = ma.login(cli)
    lojas = ma.lojas(cli, tok)
    for st in (2, 1, 3, None):
        p = {"codigoLoja": lojas[0], "emissaoInicial": (date.today() - timedelta(days=5)).isoformat(), "emissaoFinal": date.today().isoformat(), "pagina": 1}
        if st is not None: p["status"] = st
        l = ma._lista(ma._get(cli, tok, "/api/ConsultaOrcamentos", p))
        print(f"status={st}: {len(l)} itens")
        if l:
            x = l[0]; o = x.get("orcamento") or x
            print("   chaves do item:", sorted(x.keys()))
            print("   chaves de 'orcamento':", sorted((o or {}).keys()) if isinstance(o, dict) else type(o))
            for k, v in (o.items() if isinstance(o, dict) else []):
                if any(t in k.lower() for t in ("data", "dt", "status", "valor", "total", "situ", "tipo", "id")):
                    print(f"     {k} = {str(v)[:40] if ('data' in k.lower() or 'dt' in k.lower() or 'status' in k.lower() or 'situ' in k.lower() or 'tipo' in k.lower()) else type(v).__name__}")
    # contagem de status distintos num período maior (sem filtro de status)
    cont = {}
    for loja in lojas[:3]:
        for pg in range(1, 6):
            l = ma._lista(ma._get(cli, tok, "/api/ConsultaOrcamentos", {"codigoLoja": loja, "emissaoInicial": (date.today() - timedelta(days=10)).isoformat(), "emissaoFinal": date.today().isoformat(), "pagina": pg}))
            for x in l:
                o = x.get("orcamento") or x
                k = str(o.get("status") or o.get("idstatus") or o.get("situacao"))
                cont[k] = cont.get(k, 0) + 1
            if len(l) < 100: break
    print("status encontrados (3 lojas, 10 dias):", cont)
