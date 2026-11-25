"""Teste da API do Movere (só leitura) com o dia de ONTEM inteiro, todas as lojas:
  · vendas (NotasFiscaisEmitidas): notas, total, saídas × entradas (devoluções), vendedor, nº do orçamento, celular, pneus
  · cotações (ConsultaOrcamentos): quantidade, status, operador, canal, celular, quantas viraram orçamento/nota
  · comparação com o faturamento do Analytics por loja (todas as tabelas, sem filtro)
Registro público: só a estrutura (nomes de campos) e contagens gerais. Valores por loja saem TRANCADOS."""
import os, re, sys, json, datetime, collections
import httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from varejo_teste import trancar

BASE = "https://api.moveresoftware.com"
TZ = datetime.timezone(datetime.timedelta(hours=-4))
ONTEM = (datetime.datetime.now(TZ) - datetime.timedelta(days=1)).date()
MEDIDA = re.compile(r"(?<!\d)\d{3}\s*/\s*\d{2}\s*[A-Z]{0,2}\s*R\s*-?\s*\d{2}|(?<!\d)\d{2}\s*[xX]\s*\d{1,2}[.,]\d{1,2}\s*R\s*\d{2}")
cli = httpx.Client(timeout=120)
r = cli.post(BASE + "/api/LoginComAmbiente", json={"ambiente": os.environ["MOVERE_API_AMBIENTE"].strip(),
             "usuario": os.environ["MOVERE_API_USUARIO"].strip(), "senha": os.environ["MOVERE_API_SENHA"].strip()})
TOK = r.json()["token"]; H = {"Authorization": f"Bearer {TOK}", "Accept": "application/json"}
print(f"Login: HTTP {r.status_code} · dia testado: {ONTEM:%d/%m/%Y}")

def lista(j):
    """A resposta pode ser uma lista ou um objeto com a lista dentro."""
    if isinstance(j, list): return j
    if isinstance(j, dict):
        for k, v in j.items():
            if isinstance(v, list): return v
    return []

def paginas(rota, params, max_pag=60):
    out, estrutura = [], None
    for p in range(1, max_pag + 1):
        rr = cli.get(BASE + rota, headers=H, params=dict(params, pagina=p))
        if rr.status_code != 200:
            return out, f"HTTP {rr.status_code} na página {p}: {rr.text[:120]}", estrutura
        j = rr.json()
        if estrutura is None: estrutura = sorted(j.keys()) if isinstance(j, dict) else "lista"
        l = lista(j)
        out += l
        if len(l) < 100: break
    return out, None, estrutura

est = cli.get(BASE + "/api/Estabelecimentos", headers=H).json()
e0 = est[0] if est else {}
print("Estabelecimentos: campos →", sorted(e0.keys())[:12])
cod_k = next((k for k in e0 if re.fullmatch(r"(id)?(estab\w*|codigo\w*)", k, re.I) and isinstance(e0[k], int)), None)
nome_k = next((k for k in e0 if re.search(r"nome|fantasia|razao", k, re.I)), None)
lojas = [(x[cod_k], str(x.get(nome_k) or x[cod_k])) for x in est] if cod_k else []
print(f"Lojas: {len(lojas)} (campo do código: {cod_k})")

dia = ONTEM.isoformat()
res = {"dia": dia, "lojas": {}}
ger = collections.Counter()
for cod, nome in lojas:
    notas, erro_n, est_n = paginas("/api/NotasFiscaisEmitidas", {"codigoLoja": cod, "emissaoInicial": dia, "emissaoFinal": dia})
    cots, erro_c, est_c = paginas("/api/ConsultaOrcamentos", {"codigoLoja": cod, "emissaoInicial": dia, "emissaoFinal": dia})
    if ger["estrutura_impressa"] == 0 and notas:
        n0 = notas[0].get("nf", notas[0])
        print("Estrutura da resposta de vendas:", est_n, "· campos da nota:", sorted(n0.keys()))
        print("   comercial:", sorted((n0.get("comercial") or {}).keys()))
        print("   produto:", sorted(((n0.get("produtos") or [{}])[0]).keys()))
        ger["estrutura_impressa"] = 1
    if ger["estrutura_cot"] == 0 and cots:
        c0 = cots[0].get("orcamento", cots[0])
        print("Estrutura da resposta de cotações:", est_c, "· campos:", sorted(c0.keys()))
        print("   comercial:", sorted((c0.get("comercial") or {}).keys()))
        ger["estrutura_cot"] = 1
    L = {"nome": nome, "erro_vendas": erro_n, "erro_cotacoes": erro_c}
    tipos = collections.Counter(); saida = entrada = 0.0; com_orc = com_cel = 0; vend = set(); pneus = 0; n_saida = 0
    for n in notas:
        nf = n.get("nf", n)
        v = float(nf.get("valortotalnota") or 0)
        t = f"{nf.get('identradasaida')}:{nf.get('descricaoentradaesaida')}"
        tipos[t] += 1
        es = str(nf.get("descricaoentradaesaida") or "").upper()
        if nf.get("identradasaida") == 1 or "ENTRADA" in es or "DEVOL" in es: entrada += v
        else: saida += v; n_saida += 1
        com_orc += 1 if (nf.get("comercial") or {}).get("idorcamento") else 0
        com_cel += 1 if (nf.get("cliente") or {}).get("fonecelular") else 0
        vend.add((nf.get("comercial") or {}).get("idvendedor"))
        for p in nf.get("produtos") or []:
            if MEDIDA.search(str(p.get("descricao") or "").upper()): pneus += float(p.get("quantidade") or 0)
    L.update({"notas": len(notas), "notas_saida": n_saida, "valor_saida": round(saida, 2), "valor_entrada": round(entrada, 2),
              "tipos": dict(tipos), "com_orcamento": com_orc, "com_celular": com_cel, "vendedores": len(vend - {None}), "pneus": pneus})
    st = collections.Counter(); com_oper = com_cel_c = virou = 0; canais = collections.Counter()
    for c in cots:
        o = c.get("orcamento", c); cm = o.get("comercial") or {}
        st[str(o.get("emissor", {}).get("status") or o.get("status") or ("orçamento" if o.get("idorcamento") else "cotação"))] += 1
        com_oper += 1 if cm.get("idoperador") else 0
        com_cel_c += 1 if (o.get("cliente") or {}).get("fonecelular") else 0
        virou += 1 if o.get("dataemissaonf") else 0
        canais[str(cm.get("nomecanaldevendas") or "")] += 1
    L.update({"cotacoes": len(cots), "cot_status": dict(st), "cot_com_operador": com_oper, "cot_com_celular": com_cel_c,
              "cot_viraram_nota": virou, "cot_canais": dict(canais.most_common(6))})
    res["lojas"][str(cod)] = L
    ger["notas"] += len(notas); ger["cotacoes"] += len(cots); ger["erros"] += (1 if erro_n else 0) + (1 if erro_c else 0)
print(f"\nTOTAL do dia (todas as lojas): {ger['notas']} notas · {ger['cotacoes']} cotações · {ger['erros']} erro(s)")

# Analytics: faturamento do dia por loja, sem filtro de tabela/família/segmento (para comparar)
try:
    import conferir_vendas_movere as cv
    from analytics_varejo_diag import executar, df, q
    with httpx.Client(timeout=180) as c2:
        tt = cv.login_analytics(c2, os.environ["ANALYTICS_LOGIN"], os.environ["ANALYTICS_SENHA"])
        rep = q(c2, tt, f"/gdc/md/{cv.PID}/obj/1111480")["report"]
        base = q(c2, tt, rep["content"]["definitions"][-1])["reportDefinition"]["content"]
        u = cv.elemento_dia(c2, tt, ONTEM)
        fd = f"[/gdc/md/{cv.PID}/obj/{cv.ATTR_DIA}] IN ([{u}])"
        a = executar(c2, tt, base, [df(c2, tt, f"/gdc/md/{cv.PID}/obj/1583")], [f"/gdc/md/{cv.PID}/obj/2160", f"/gdc/md/{cv.PID}/obj/3983"],
                     ("obj/1637]", "obj/3800]", "obj/1583]", "obj/1539]"), (fd,))
        res["analytics"] = a if isinstance(a, list) else str(a)
        print("Analytics do dia: lido", "(" + str(len(a) - 1) + " lojas)" if isinstance(a, list) else str(a)[:80])
except Exception as e:
    print("Analytics não lido:", type(e).__name__)

b = trancar(res)
for i in range(0, len(b), 900):
    print("TRANCADO:" + b[i:i + 900])
