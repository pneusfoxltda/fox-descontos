"""
conferir_vendas_movere.py
=========================
Marca como "Venda concluída (Movere)" os descontos cujo cliente COMPROU.

Como funciona (mesma lógica do Apps Script das planilhas de ligações):
  1. Pega no Supabase os descontos PENDENTES DE LIBERAÇÃO (os já liberados pela
     equipe ficam de fora), ainda não marcados e com telefone do cliente.
  2. Entra no Analytics do Movere e baixa o relatório de vendas dos dias
     desde o desconto mais antigo até hoje.
  3. Compara pelos ÚLTIMOS 8 DÍGITOS do telefone (celular ou comercial).
  4. Se o cliente comprou no MESMO DIA do cadastro do desconto ou DEPOIS,
     marca a venda (vale mesmo se o desconto já estiver vencido).

Segredos (GitHub → Settings → Secrets → Actions):
  ANALYTICS_LOGIN        e-mail de login do Analytics Movere
  ANALYTICS_SENHA        senha do Analytics Movere
  SUPABASE_SERVICE_KEY   chave service_role do Supabase

Opcional: DRY_RUN=1 mostra o que faria, sem gravar nada.

⚠️ O repositório é público e o registro do GitHub Actions também:
   este script NUNCA escreve telefone nem nome de cliente no registro.
"""

import csv
import io
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

import httpx

# ── Configuração ──────────────────────────────────────────────────────────────
SUPABASE_URL = "https://dxwkiaxpygibzmwzvcuz.supabase.co"
GD = "https://analytics.moveresoftware.com"
PID = "uljodb77ez5d22jaim5mks2y36n5xvr4"
REL_VENDAS = 742591        # "Faturamento Clientes validação do televendas"
DASH_VENDAS = 744813       # dashboard do relatório (filtros salvos)
ATTR_DIA = 1266            # atributo "dtaemissao" (dia)
DF_DIA = 1303              # formato dd/mm/yyyy desse atributo
JANELA_DIAS = 45           # confere descontos cadastrados nos últimos N dias
# Os filtros do dashboard restringem às operadoras do televendas. Para conferir
# vendas de TODAS as lojas, eles ficam desligados (USAR_FILTRO_DASH=1 liga).
USAR_FILTRO_DASH = os.environ.get("USAR_FILTRO_DASH", "0") == "1"

TZ_LOJA = timezone(timedelta(hours=-4))   # Porto Velho
ROBO = "conferir_vendas_movere"
GUARDAR_DIAS = 90          # rodadas mais antigas que isso são apagadas

# Resumo da rodada (vai para a tabela robo_execucoes; nunca tem dados de cliente)
RESUMO = {"conferidos": None, "encontrados": None, "inicio": None}


# ── Utilidades ────────────────────────────────────────────────────────────────
def chave_tel(v) -> str:
    """Últimos 8 dígitos do telefone (igual ao Apps Script). Vazio se curto."""
    d = re.sub(r"\D", "", str(v or ""))
    return d[-8:] if len(d) >= 8 else ""


def chaves_tel(texto) -> set:
    """Um campo pode ter mais de um telefone separado por , ; / ou 'e'."""
    partes = re.split(r"[,;/]|\se\s", str(texto or ""))
    return {k for k in (chave_tel(p) for p in partes) if k}


def data_br(s):
    """'21/11/2026' → date. None se não for uma data."""
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(s or ""))
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def numero_br(s) -> float:
    s = str(s or "").strip()
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(re.sub(r"[^\d.\-]", "", s) or 0)
    except ValueError:
        return 0.0


def data_local(iso: str):
    """criado_em do Supabase (timestamptz) → dia em Porto Velho."""
    if not iso:
        return None
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_LOJA).date()


# ── Cruzamento (a regra de negócio) ───────────────────────────────────────────
def vendas_por_telefone(linhas: list) -> dict:
    """
    linhas = CSV do Analytics (1ª linha = cabeçalho).
    Devolve {chave_tel: [(data, valor), ...]}.
    """
    if not linhas:
        return {}
    cab = [c.strip() for c in linhas[0]]
    i_tel = [i for i, c in enumerate(cab) if c.lower().startswith("telefone")]
    i_val = next((i for i, c in enumerate(cab) if "valor" in c.lower()), None)
    i_dat = next((i for i, c in enumerate(cab) if "data" in c.lower() or "emiss" in c.lower()), 0)
    if not i_tel:
        raise RuntimeError("o relatório de vendas não tem coluna de telefone")

    vendas = {}
    for r in linhas[1:]:
        if len(r) <= 1:
            continue
        d = data_br(r[i_dat]) if i_dat < len(r) else None
        if d is None:
            d = next((x for x in (data_br(c) for c in r) if x), None)
        if d is None:
            continue
        valor = numero_br(r[i_val]) if i_val is not None and i_val < len(r) else 0.0
        for i in i_tel:
            if i < len(r):
                for k in chaves_tel(r[i]):
                    vendas.setdefault(k, []).append((d, valor))
    return vendas


def cruzar(descontos: list, vendas: dict, por_orcamento: dict = None) -> list:
    """
    Para cada desconto, procura a venda no dia do cadastro ou depois:
      1º pelo NÚMERO do orçamento/O.S. (API do Movere: a nota traz o nº do orçamento) · mais certeiro;
      2º pela PRIMEIRA venda do mesmo telefone (últimos 8 dígitos; Analytics e API).
    Devolve a lista de marcações a gravar.
    """
    marcar = []
    por_orcamento = por_orcamento or {}
    for d in descontos:
        base = data_local(d.get("criado_em"))
        if base is None:
            continue
        num = re.sub(r"\D", "", str(d.get("numero") or "")).lstrip("0")
        if num and num in por_orcamento and por_orcamento[num][0] >= base:
            dia, valor = por_orcamento[num]
            marcar.append({"id": d["id"], "numero": d.get("numero"), "venda_movere_em": dia.isoformat(),
                           "venda_movere_valor": valor, "por": "orçamento"})
            continue
        achou = []
        for k in chaves_tel(d.get("telefone_cliente")):
            achou += [v for v in vendas.get(k, []) if v[0] >= base]
        if not achou:
            continue
        dia = min(v[0] for v in achou)
        valor = round(sum(v[1] for v in achou if v[0] == dia), 2)
        marcar.append({
            "id": d["id"], "numero": d.get("numero"),
            "venda_movere_em": dia.isoformat(), "venda_movere_valor": valor, "por": "telefone",
        })
    return marcar


# ── Supabase ──────────────────────────────────────────────────────────────────
def _sb_headers(chave: str, extras: dict = None) -> dict:
    h = {"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json"}
    h.update(extras or {})
    return h


def registrar_rodada(ok: bool, mensagem: str = None, teste: bool = False):
    """Grava o resumo da rodada no Supabase. Nunca derruba o robô se falhar."""
    chave = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not chave:
        return
    agora = datetime.now(timezone.utc)
    corpo = {
        "robo": ROBO, "ok": ok, "teste": teste,
        "inicio": (RESUMO["inicio"] or agora).isoformat(), "fim": agora.isoformat(),
        "conferidos": RESUMO["conferidos"], "encontrados": RESUMO["encontrados"],
        "mensagem": (mensagem or "")[:300] or None,
    }
    try:
        with httpx.Client(timeout=20) as cli:
            cli.post(f"{SUPABASE_URL}/rest/v1/robo_execucoes",
                     headers=_sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo)
            limite = (agora - timedelta(days=GUARDAR_DIAS)).isoformat()
            cli.delete(f"{SUPABASE_URL}/rest/v1/robo_execucoes?robo=eq.{ROBO}&inicio=lt.{limite}",
                       headers=_sb_headers(chave))
    except Exception as e:  # o registro é só informativo
        print(f"⚠️ Não consegui registrar a rodada: {type(e).__name__}")


def buscar_pendentes(cli: httpx.Client, chave: str, desde: date) -> list:
    url = (f"{SUPABASE_URL}/rest/v1/descontos"
           f"?select=id,numero,tipo,telefone_cliente,criado_em"
           f"&venda_movere=is.false&liberado=not.is.true&tipo=neq.conc&telefone_cliente=not.is.null"
           f"&criado_em=gte.{desde.isoformat()}&order=criado_em.asc&limit=5000")
    r = cli.get(url, headers=_sb_headers(chave))
    if r.status_code == 400 and "venda_movere" in r.text:
        raise RuntimeError("falta rodar o SQL 09_venda_movere.sql no Supabase")
    r.raise_for_status()
    return [d for d in r.json() if chaves_tel(d.get("telefone_cliente"))]


def gravar(cli: httpx.Client, chave: str, m: dict, agora: str):
    corpo = {
        "venda_movere": True,
        "venda_movere_em": m["venda_movere_em"],
        "venda_movere_valor": m["venda_movere_valor"],
        "venda_movere_por": m.get("por", "telefone"),
        "venda_movere_conferido_em": agora,
    }
    r = cli.patch(f"{SUPABASE_URL}/rest/v1/descontos?id=eq.{m['id']}",
                  headers=_sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo)
    r.raise_for_status()


# ── Analytics Movere (GoodData) — igual ao Apps Script ────────────────────────
def _md() -> str:
    return f"/gdc/md/{PID}"


def _abs(u: str) -> str:
    return u if u.startswith("http") else GD + u


def login_analytics(cli: httpx.Client, login: str, senha: str) -> str:
    r = cli.post(f"{GD}/gdc/account/login",
                 headers={"Accept": "application/json"},
                 json={"postUserLogin": {"login": login.strip(), "password": senha,
                                         "remember": 1, "verify_level": 2}})
    if r.status_code != 200:
        raise RuntimeError(f"login no Analytics recusado ({r.status_code}): confira ANALYTICS_LOGIN e ANALYTICS_SENHA")
    sst = r.headers.get("X-GDC-AuthSST") or (r.json().get("userLogin") or {}).get("token")
    if not sst:
        raise RuntimeError("o Analytics não devolveu o token de sessão")
    t = cli.get(f"{GD}/gdc/account/token", headers={"Accept": "application/json", "X-GDC-AuthSST": sst})
    tt = t.headers.get("X-GDC-AuthTT") or (t.json().get("userToken") or {}).get("token")
    if not tt:
        raise RuntimeError(f"não consegui o token temporário do Analytics ({t.status_code})")
    return tt


def _gd_json(cli: httpx.Client, tt: str, uri: str) -> dict:
    r = cli.get(_abs(uri), headers={"Accept": "application/json", "X-GDC-AuthTT": tt})
    if r.status_code >= 300:
        raise RuntimeError(f"Analytics respondeu {r.status_code} em {uri}")
    return r.json()


def elemento_dia(cli, tt, d: date):
    titulo = d.strftime("%d/%m/%Y")
    j = _gd_json(cli, tt, f"{_md()}/obj/{DF_DIA}/elements?filter={titulo}")
    for e in (j.get("attributeElements") or {}).get("elements") or []:
        if e.get("title") == titulo:
            return e.get("uri")
    return None


def _filtros_dash(cli, tt, dash_id: int) -> list:
    pd = _gd_json(cli, tt, f"{_md()}/obj/{dash_id}")["projectDashboard"]
    filtros = []
    for f in pd["content"].get("filters") or []:
        c = f.get("filterItemContent") or {}
        els = (c.get("default") or {}).get("elements") or []
        if c.get("type") == "list" and els:
            attr = els[0].split("/elements")[0]
            filtros.append({"expression": f"[{attr}] IN ({', '.join('[' + e + ']' for e in els)})"})
    return filtros


def relatorio(cli, tt, rel_id: int, dash_id, filtro_data: str) -> list:
    rep = _gd_json(cli, tt, f"{_md()}/obj/{rel_id}")["report"]
    def_uri = rep["content"]["definitions"][-1]
    c = _gd_json(cli, tt, def_uri)["reportDefinition"]["content"]
    extras = _filtros_dash(cli, tt, dash_id) if dash_id else []
    c["filters"] = (c.get("filters") or []) + extras + [{"expression": filtro_data}]

    r = cli.post(f"{GD}/gdc/app/projects/{PID}/execute/raw",
                 headers={"Accept": "application/json", "X-GDC-AuthTT": tt},
                 json={"report_req": {"definitionContent": {
                     "content": {"reportDefinition": {"content": c, "meta": {"title": "auto"}}},
                     "projectMetadata": _md()}}})
    if r.status_code >= 300:
        raise RuntimeError(f"Analytics recusou o relatório {rel_id} ({r.status_code})")
    uri = r.json()["uri"]

    for _ in range(150):
        g = cli.get(_abs(uri), headers={"X-GDC-AuthTT": tt}, follow_redirects=False)
        if 300 <= g.status_code < 400:
            loc = _abs(g.headers.get("Location", ""))
            g = cli.get(loc, headers={"X-GDC-AuthTT": tt} if loc.startswith(GD) else {})
        if g.status_code == 200:
            return list(csv.reader(io.StringIO(g.content.decode("utf-8-sig"))))
        if g.status_code == 204:
            return []
        if g.status_code >= 400:
            raise RuntimeError(f"erro {g.status_code} ao baixar o relatório {rel_id}")
        time.sleep(2)
    raise RuntimeError(f"o Analytics demorou demais para gerar o relatório {rel_id}")


# ── Principal ─────────────────────────────────────────────────────────────────
def main() -> int:
    chave = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    login = os.environ.get("ANALYTICS_LOGIN", "").strip()
    senha = os.environ.get("ANALYTICS_SENHA", "")
    dry = os.environ.get("DRY_RUN", "") == "1"
    faltam = [n for n, v in (("SUPABASE_SERVICE_KEY", chave), ("ANALYTICS_LOGIN", login),
                             ("ANALYTICS_SENHA", senha)) if not v]
    if faltam:
        print("❌ Faltam os segredos no GitHub: " + ", ".join(faltam))
        return 1

    hoje = datetime.now(TZ_LOJA).date()
    desde = hoje - timedelta(days=JANELA_DIAS)
    RESUMO["inicio"] = datetime.now(timezone.utc)

    with httpx.Client(timeout=60) as cli:
        pendentes = buscar_pendentes(cli, chave, desde)
        print(f"🔎 Descontos pendentes de liberação, com telefone e sem venda (últimos {JANELA_DIAS} dias): {len(pendentes)}")
        RESUMO["conferidos"] = len(pendentes)
        if not pendentes:
            RESUMO["encontrados"] = 0
            print("✅ Nada para conferir.")
            registrar_rodada(True, teste=dry)
            return 0

        inicio = min(data_local(d["criado_em"]) for d in pendentes)
        dias = [inicio + timedelta(days=i) for i in range((hoje - inicio).days + 1)]

        # 1) API oficial do Movere: vendas NA HORA, com telefone e nº do orçamento
        import movere_api
        # só os últimos dias pela API (rápido); os mais antigos o Analytics já tem
        api_tel, api_orc = movere_api.buscar(max(inicio, hoje - timedelta(days=movere_api.DIAS_API)), hoje)
        RESUMO["api_telefones"], RESUMO["api_orcamentos"] = len(api_tel), len(api_orc)

        # 2) Analytics (reserva: atualiza de madrugada). Se falhar e a API respondeu, segue só com a API.
        vendas = {}
        try:
            tt = login_analytics(cli, login, senha)
            print("🔐 Login no Analytics OK")
            els = [u for u in (elemento_dia(cli, tt, d) for d in dias) if u]
            print(f"📅 Dias com dados no Analytics: {len(els)} de {len(dias)} "
                  f"({inicio.strftime('%d/%m')} a {hoje.strftime('%d/%m')})")
            if els:
                filtro = f"[{_md()}/obj/{ATTR_DIA}] IN ({', '.join('[' + u + ']' for u in els)})"
                linhas = relatorio(cli, tt, REL_VENDAS, DASH_VENDAS if USAR_FILTRO_DASH else None, filtro)
                vendas = vendas_por_telefone(linhas)
                print(f"🧾 Analytics: {max(len(linhas) - 1, 0)} linhas de venda · telefones distintos: {len(vendas)}")
        except Exception as e:
            if not api_tel:
                raise
            print(f"⚠️ Analytics falhou ({type(e).__name__}): segue só com a API")
        vendas = movere_api.juntar(vendas, api_tel)

        marcar = cruzar(pendentes, vendas, api_orc)
        n_orc = sum(1 for m in marcar if m.get("por") == "orçamento")
        print(f"🎯 Descontos que viraram venda: {len(marcar)} (pelo nº do orçamento: {n_orc} · pelo telefone: {len(marcar) - n_orc})")
        RESUMO["por_orcamento"] = n_orc
        RESUMO["encontrados"] = len(marcar)
        agora = datetime.now(timezone.utc).isoformat()
        for m in marcar:
            print(f"   • #{m['numero']} → venda em {date.fromisoformat(m['venda_movere_em']).strftime('%d/%m/%Y')} (pelo {m.get('por', 'telefone')})"
                  + (" (teste, não gravado)" if dry else ""))
            if not dry:
                gravar(cli, chave, m, agora)
    registrar_rodada(True, teste=dry)
    print("✅ Fim.")
    return 0


def rodar() -> int:
    try:
        codigo = main()
        if codigo != 0:
            registrar_rodada(False, "faltam segredos no GitHub (ANALYTICS_LOGIN / ANALYTICS_SENHA)")
        return codigo
    except Exception as e:  # mensagem curta e sem dados de clientes
        print(f"❌ Erro: {e}")
        registrar_rodada(False, str(e), teste=os.environ.get("DRY_RUN", "") == "1")
        return 1


if __name__ == "__main__":
    sys.exit(rodar())
