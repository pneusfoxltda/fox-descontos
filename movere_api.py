"""
movere_api.py · Vendas pela API OFICIAL do Movere (na hora, sem esperar o Analytics da madrugada)
================================================================================================
Usado pelos robôs da "venda concluída" (conferir_vendas_movere.py, descontos) e das Ligações (ligacoes_lojas.py).
Lê as notas fiscais emitidas (NotasFiscaisEmitidas) de todas as lojas num período e devolve, só das VENDAS
(sem transferência, remessa nem carcaça; devolução de venda fica de fora):
  · por telefone  → {últimos 8 dígitos: [(dia, valor), ...]}  (mesmo formato do Analytics)
  · por orçamento → {nº do orçamento: (dia, valor)}            (para achar o desconto pelo número)
Login com Ambiente + Usuário + Senha (segredos MOVERE_API_AMBIENTE / _USUARIO / _SENHA). Cada login gera um token
novo e NÃO derruba o token de outra integração que usa o mesmo usuário (testado em 25/11/2026).
Nunca imprime telefone, nome nem valor: só contagens.
"""
import os, re
from datetime import date, datetime, timedelta, timezone

import httpx

BASE = "https://api.moveresoftware.com"
POR_PAGINA = 100
DIAS_API = 10          # os robôs buscam pela API só os últimos 10 dias (o Analytics cobre os mais antigos; 45 dias passava de 15 min)


def configurada() -> bool:
    return all(os.environ.get(n, "").strip() for n in ("MOVERE_API_AMBIENTE", "MOVERE_API_USUARIO", "MOVERE_API_SENHA"))


def login(cli: httpx.Client) -> str:
    r = cli.post(f"{BASE}/api/LoginComAmbiente", json={"ambiente": os.environ["MOVERE_API_AMBIENTE"].strip(),
                 "usuario": os.environ["MOVERE_API_USUARIO"].strip(), "senha": os.environ["MOVERE_API_SENHA"].strip()})
    r.raise_for_status()
    tok = (r.json() or {}).get("token")
    if not tok:
        raise RuntimeError("a API do Movere não devolveu o token")
    return tok


def _get(cli, tok, rota, params=None):
    r = cli.get(f"{BASE}{rota}", headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"}, params=params or {})
    r.raise_for_status()
    return r.json()


def _lista(j):
    if isinstance(j, list):
        return j
    if isinstance(j, dict):
        return next((v for v in j.values() if isinstance(v, list)), [])
    return []


def lojas(cli, tok) -> list:
    return [x["codigoEstabelecimento"] for x in _lista(_get(cli, tok, "/api/Estabelecimentos"))
            if x.get("codigoEstabelecimento") is not None and x.get("ativo") is not False]


def _dia(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(s or "")) or re.match(r"(\d{2})/(\d{2})/(\d{4})", str(s or ""))
    if not m:
        return None
    a, b, c = m.groups()
    return date(int(a), int(b), int(c)) if len(a) == 4 else date(int(c), int(b), int(a))


def tipo_nota(nf: dict) -> str:
    """'venda', 'devolucao' ou 'outra' (transferência, remessa, carcaça…), pela descrição de entrada/saída."""
    d = str(nf.get("descricaoentradaesaida") or "").upper()
    if "DEVOLU" in d and "VENDA" in d:
        return "devolucao"
    if "VENDA" in d:
        return "venda"
    return "outra"


def simplificar(item: dict, loja) -> dict:
    """Uma nota da API → só o que os robôs usam."""
    nf = item.get("NF") or item.get("nf") or item
    cm, cl = nf.get("Comercial") or nf.get("comercial") or {}, nf.get("Cliente") or nf.get("cliente") or {}
    tels = {re.sub(r"\D", "", str(cl.get(k) or "")) for k in ("fonecelular", "fonecom")}
    return {"dia": _dia(nf.get("dtaemissao")), "valor": float(nf.get("valortotalnota") or 0), "tipo": tipo_nota(nf),
            "orcamento": cm.get("idorcamento"), "tels": {t[-8:] for t in tels if len(t) >= 8}, "loja": loja}


def notas(cli, tok, desde: date, ate: date, log=print) -> list:
    """Todas as notas de todas as lojas no período (paginado de 100 em 100)."""
    out = []
    for loja in lojas(cli, tok):
        for p in range(1, 400):
            l = _lista(_get(cli, tok, "/api/NotasFiscaisEmitidas",
                            {"codigoLoja": loja, "emissaoInicial": desde.isoformat(), "emissaoFinal": ate.isoformat(), "pagina": p}))
            out += [simplificar(x, loja) for x in l]
            if len(l) < POR_PAGINA:
                break
    log(f"🛰️ API do Movere: {len(out)} notas de {desde:%d/%m} a {ate:%d/%m} · vendas: {sum(1 for n in out if n['tipo'] == 'venda')}")
    return out


def vendas_por_telefone(ns: list) -> dict:
    v = {}
    for n in ns:
        if n["tipo"] != "venda" or not n["dia"]:
            continue
        for t in n["tels"]:
            v.setdefault(t, []).append((n["dia"], n["valor"]))
    return v


def vendas_por_orcamento(ns: list) -> dict:
    v = {}
    for n in ns:
        if n["tipo"] != "venda" or not n["dia"] or not n["orcamento"]:
            continue
        k = str(n["orcamento"])
        dia, val = v.get(k, (n["dia"], 0.0))
        v[k] = (min(dia, n["dia"]), round(val + n["valor"], 2))
    return v


def cotacoes_para_os(cli, tok, desde: date, ate: date, log=print) -> dict:
    """{nº da cotação: nº da O.S.} das O.S. que viraram nota no período (ConsultaOrcamentos com status 2 = Nota gerada).
    Nos descontos, "Orçamento" = nº da COTAÇÃO e "O.S." = nº da ordem de serviço (a nota traz o nº da O.S.)."""
    out = {}
    for loja in lojas(cli, tok):
        for p in range(1, 400):
            l = _lista(_get(cli, tok, "/api/ConsultaOrcamentos",
                            {"codigoLoja": loja, "emissaoInicial": desde.isoformat(), "emissaoFinal": ate.isoformat(),
                             "status": 2, "pagina": p}))
            for x in l:
                o = x.get("orcamento") or x
                if o.get("idcotacao") and o.get("idorcamento"):
                    out[str(o["idcotacao"])] = str(o["idorcamento"])
            if len(l) < POR_PAGINA:
                break
    log(f"🛰️ API do Movere: {len(out)} cotações que viraram O.S. com nota")
    return out


def por_numero(vendas_os: dict, cot_os: dict) -> dict:
    """{('os', nº): (dia, valor), ('cotacao', nº): (dia, valor)} para achar o desconto pelo número certo do seu tipo."""
    out = {("os", k): v for k, v in vendas_os.items()}
    for cot, os_ in cot_os.items():
        if os_ in vendas_os:
            out[("cotacao", cot)] = vendas_os[os_]
    return out


def juntar(a: dict, b: dict) -> dict:
    """Junta dois {telefone: [(dia, valor)]} sem repetir a mesma venda."""
    out = {k: list(v) for k, v in a.items()}
    for k, l in b.items():
        atual = out.setdefault(k, [])
        for x in l:
            if x not in atual:
                atual.append(x)
    return out


def buscar(desde: date, ate: date, log=print):
    """(por_telefone, por_numero) da API, ou ({}, {}) se a API não estiver configurada ou falhar.
    por_numero = {('os', nº da O.S.) ou ('cotacao', nº da cotação): (dia, valor)}."""
    if not configurada():
        log("ℹ️ API do Movere não configurada (segredos MOVERE_API_*): segue só com o Analytics")
        return {}, {}
    try:
        with httpx.Client(timeout=120) as cli:
            tok = login(cli)
            ns = notas(cli, tok, desde, ate, log)
            try:
                cot_os = cotacoes_para_os(cli, tok, desde, ate, log)
            except Exception as e:   # sem a ligação cotação → O.S., ainda acha pela O.S. e pelo telefone
                log(f"⚠️ Cotações da API falharam ({type(e).__name__}): segue pela O.S. e pelo telefone")
                cot_os = {}
        return vendas_por_telefone(ns), por_numero(vendas_por_orcamento(ns), cot_os)
    except Exception as e:
        log(f"⚠️ API do Movere falhou ({type(e).__name__}): segue só com o Analytics")
        return {}, {}
