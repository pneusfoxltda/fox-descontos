"""Diagnóstico (só leitura, sem valores em reais no registro): a nota da API traz tipopreco e vendedor?
Conta as notas de VENDA de hoje por loja e por tipopreco, e compara (em %) com o "hoje" da 553 gravado no banco."""
import os, sys
from collections import Counter, defaultdict
from datetime import datetime
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import movere_api as m
import conferir_vendas_movere as cv
from varejo_filtros import LOJAS_VAREJO, TABELAS_VAREJO
from resultados_atacado import da_equipe

from datetime import timedelta
agora = datetime.now(cv.TZ_LOJA).date()
fim = agora - timedelta(days=1)          # ontem (fechado)
ini = fim.replace(day=1)
chave = os.environ.get("SUPABASE_SERVICE_KEY", "")
with httpx.Client(timeout=120) as cli:
    r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/varejo_lojas?select=loja,venda,clientes,dia,periodo&periodo=eq.mes&mes=eq.{ini.isoformat()}",
                headers=cv._sb_headers(chave))
    banco = {x["loja"]: x for x in (r.json() if r.status_code == 200 else [])}
    print(f"553 'mês' no banco: {len(banco)} lojas · retrato do dia {sorted({x['dia'] for x in banco.values()})} · API de {ini:%d/%m} a {fim:%d/%m}")
    tok = m.login(cli)
    tipos = Counter()
    soma = defaultdict(lambda: defaultdict(float))
    qtd = defaultdict(lambda: defaultdict(int))
    com_vend = 0
    total = 0
    for cod, loja in LOJAS_VAREJO.items():
        for p in range(1, 400):
            l = m._lista(m._get(cli, tok, "/api/NotasFiscaisEmitidas", {"codigoLoja": cod, "emissaoInicial": ini.isoformat(),
                         "emissaoFinal": fim.isoformat(), "pagina": p}))
            for x in l:
                nf = x.get("NF") or x
                desc = str(nf.get("descricaoentradaesaida") or "").upper()
                if (nf.get("Cancelamento") or {}).get("dtacancelamento"):
                    continue
                co = nf.get("Comercial") or {}
                tp = "ATACADO_EQUIPE" if da_equipe(co.get("nomevendedor") or "") else "OUTROS"
                tipos[(tp, desc[:30])] += 1
                total += 1
                com_vend += 1 if co.get("nomevendedor") else 0
                sinal = -1 if "DEVOLU" in desc else 1 if "VENDA" in desc else 0
                if sinal:
                    soma[loja][tp] += sinal * float(nf.get("valortotalnota") or 0)
                    qtd[loja][tp] += sinal
            if len(l) < m.POR_PAGINA:
                break
    print(f"Notas no período: {total} · com vendedor: {com_vend}")
    print("tipopreco × operação (contagem):")
    for (tp, d), n in tipos.most_common(40):
        print(f"   {tp!r:40} {d:30} {n}")
    print("Tabelas do Varejo (553):", TABELAS_VAREJO)
    print("Comparação com a 553 (só %, sem reais): loja · API varejo ÷ 553")
    for loja in LOJAS_VAREJO.values():
        b = banco.get(loja)
        api_var = soma[loja].get("OUTROS", 0.0)
        api_tudo = sum(soma[loja].values())
        if b and b.get("venda"):
            print(f"   {loja:12} sem a equipe do Atacado {api_var / b['venda'] * 100:6.1f}% · tudo {api_tudo / b['venda'] * 100:6.1f}% · vendas API {qtd[loja].get('OUTROS', 0)} × 553 {b.get('clientes')}")
        else:
            print(f"   {loja:12} (sem 553 de hoje no banco)")
