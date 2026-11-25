"""Teste (só leitura): os exemplos do TI batem com a API? cotação 954745 → O.S. 35613 · cotação 954709 → O.S. 127171.
Mostra só se achou e em qual campo (nada de cliente nem valor)."""
import os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import httpx, movere_api as ma
EX = [("954745", "35613"), ("954709", "127171")]
hoje = (datetime.datetime.utcnow() - datetime.timedelta(hours=4)).date()
desde = hoje - datetime.timedelta(days=20)
with httpx.Client(timeout=120) as cli:
    tok = ma.login(cli)
    achados = {}
    for loja in ma.lojas(cli, tok):
        for st in (None, 2):
            for p in range(1, 400):
                prm = {"codigoLoja": loja, "emissaoInicial": desde.isoformat(), "emissaoFinal": hoje.isoformat(), "pagina": p}
                if st is not None: prm["status"] = st
                l = ma._lista(ma._get(cli, tok, "/api/ConsultaOrcamentos", prm))
                for x in l:
                    o = x.get("orcamento") or x
                    vals = {k: str(v) for k, v in o.items() if isinstance(v, (int, str)) and str(v).isdigit()}
                    for cot, os_ in EX:
                        for k, v in vals.items():
                            if v in (cot, os_):
                                achados.setdefault((cot, os_), set()).add(f"loja {loja} · status={st} · campo {k}={'cotação' if v == cot else 'O.S.'} · idcotacao={'igual' if str(o.get('idcotacao')) == cot else o.get('idcotacao') and 'outro'} · idorcamento={'= O.S.' if str(o.get('idorcamento')) == os_ else ('vazio' if not o.get('idorcamento') else 'OUTRO número')}")
                if len(l) < 100: break
    for ex in EX:
        print(f"Exemplo cotação {ex[0]} / O.S. {ex[1]}:")
        for a in sorted(achados.get(ex, [])) or ["   não achei em ConsultaOrcamentos (últimos 20 dias)"]:
            print("   ", a)
    # nas notas: a O.S. aparece como idorcamento?
    ns = ma.notas(cli, tok, desde, hoje, log=lambda *a: None)
    for cot, os_ in EX:
        hit = [n for n in ns if str(n["orcamento"]) == os_]
        print(f"Nota com idorcamento = O.S. {os_}: {'SIM (' + hit[0]['tipo'] + ', loja ' + str(hit[0]['loja']) + ')' if hit else 'não'}"
              f" · com idorcamento = cotação {cot}: {'SIM' if any(str(n['orcamento']) == cot for n in ns) else 'não'}")
