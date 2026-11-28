"""
funil_televendas.py · Robô do "Funil do televendas" (painel no fim de /televendas.html)
=======================================================================================
Junta, por lead do Kommo (Funil Principal, sem as etapas de disparo), as datas de cada etapa:
  · entrou     = criação do lead
  · cotou      = marcação "2 - Fez cotação" ou "3 - Cotação criada pela IA" (dia em que foi marcada, pelo histórico
                 do Kommo); se não tiver, a 1ª cotação do televendas no Movere (relatório 782403) pelo telefone
  · negociou   = "4 - Negociação realizada"
  · agendou    = "6 - Agendamento IA" ou "7 - Agendamento" (+ "Data da visita", quando tiver)
  · comprou    = nota fiscal no Movere pelo telefone (vendas 742591 + API), no dia da entrada ou depois;
                 ou a COTAÇÃO do cliente virou O.S. (API ConsultaOrcamentos; TI, 27/11/2026: "cotação que virou O.S. é venda",
                 vale mesmo com outro telefone na nota); se não achar, a coluna "VENDA GANHA" do Kommo (= foi à loja) ou o
                 campo "1ª Venda" do cartão. compra_fonte guarda de onde veio (os · movere · venda_ganha · 1a_venda; SQL 34)
  · perdido    = etapa "venda perdida" (motivo do Kommo ou o campo "Motivo de perda")
Guarda uma linha por lead em funil_leads (sem nome; o telefone só como código HMAC) e grava as contas prontas
(funil_calculo.montar) em funil_resumo e funil_abertos (SQL 33).
Carga aos poucos (TI, 27/11/2026): a 1ª rodada lê os últimos 4 meses; cada rodada seguinte lê só o que mudou no Kommo
(leads atualizados e marcações novas) + as vendas/cotações recentes do Movere, e volta mais MESES_POR_RODADA meses no
histórico até INICIO_HIST (01/2025).
Entrou = lead com "1 - Contato Inicial", ou que avançou para alguma etapa, ou que está aberto/ganho (o lead de anúncio
que nunca conversou e foi perdido não entra).
Decisões do TI (27/11/2026): a coluna DISPARO fica de fora; "Outros produtos" = produto que a Fox não trabalha.
Registro público: só contagens. Segredos: KOMMO_TOKEN, ANALYTICS_LOGIN, ANALYTICS_SENHA, SUPABASE_SERVICE_KEY,
MOVERE_API_*. Rodar sem gravar: DRY_RUN=1.
"""
import hashlib, hmac, os, sys, time
from datetime import date, datetime, timedelta, timezone

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_vendas_movere as cv
import ligacoes_lojas as ll
import funil_calculo as fc

ROBO = "funil_televendas"
DRY = os.environ.get("DRY_RUN") == "1"
DISPARO = {108557363, 89179007}                       # "9 - DISPARO" e "8 - Disparo Noturno": fora (TI, 27/11/2026)
PERDIDA, GANHA = 143, 142                        # "venda perdida" e "VENDA GANHA" (foi à loja e comprou; TI, 27/11/2026)
CAMPOS = {"cotou": (586966, 798926), "negociou": (822817,), "agendou": (586976, 822865)}
C_VISITA, C_1VENDA, C_MOTIVO, C_LOJA = 774304, 813604, 783662, 776466
C_CONTATO = 586964                                    # "1 - Contato Inicial"
MESES_INICIAIS = 4                                    # 1ª rodada: os últimos 4 meses
MESES_POR_RODADA = 2                                  # depois, volta 2 meses por rodada no histórico
INICIO_HIST = date(2025, 1, 1)
DIAS_MARCACAO = 90                                    # marcações de um lead acontecem até 90 dias depois da entrada
DETALHES = {}


# ── Kommo ─────────────────────────────────────────────────────────────────────
class Kommo:
    def __init__(self, cli, token):
        self.cli, self.h = cli, {"Authorization": "Bearer " + token.strip()}

    def get(self, rota):
        for t in range(5):
            try:
                r = self.cli.get(ll.KOMMO + rota, headers=self.h)
            except httpx.TransportError:
                time.sleep(3 * (t + 1)); continue
            if r.status_code == 429:
                time.sleep(2 * (t + 1)); continue
            if r.status_code == 204:
                return None
            if r.status_code == 401:
                raise RuntimeError("token do Kommo expirado ou inválido (401)")
            r.raise_for_status()
            return r.json()
        raise RuntimeError("Kommo não respondeu depois de 5 tentativas")

    def todas(self, rota, chave):
        out, pg = [], 1
        sep = "&" if "?" in rota else "?"
        while True:
            d = self.get(f"{rota}{sep}limit=250&page={pg}")
            if not d:
                break
            out += (d.get("_embedded") or {}).get(chave) or []
            if not (d.get("_links") or {}).get("next"):
                break
            pg += 1
        return out


def _ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=cv.TZ_LOJA).timestamp())


def _dia(ts):
    return datetime.fromtimestamp(int(ts), cv.TZ_LOJA).date() if ts else None


def _valor_campo(lead, fid):
    for f in lead.get("custom_fields_values") or []:
        if f.get("field_id") == fid:
            v = (f.get("values") or [{}])[0]
            return v.get("value")
    return None


def _origem(lead):
    for f in lead.get("custom_fields_values") or []:
        if f.get("field_name") == "utm_source":
            return str((f.get("values") or [{}])[0].get("value") or "").strip().lower() or None
    for f in lead.get("custom_fields_values") or []:
        if f.get("field_name") == "Meta Ads fonte":
            return "facebook"
    return None


def datas_marcacoes(k: Kommo, desde: date, ate: date = None) -> dict:
    """{lead_id: {etapa: 1º dia em que a marcação foi ligada}} pelo histórico de eventos do Kommo."""
    out = {}
    filtro_ate = f"&filter%5Bcreated_at%5D%5Bto%5D={_ts(ate + timedelta(days=1)) - 1}" if ate else ""
    for etapa, fids in CAMPOS.items():
        for fid in fids:
            for ev in k.todas(f"/events?filter%5Btype%5D=custom_field_{fid}_value_changed&filter%5Bcreated_at%5D%5Bfrom%5D={_ts(desde)}{filtro_ate}", "events"):
                va = ev.get("value_after") or []
                ligado = any(str((x.get("custom_field_value") or {}).get("text")) in ("1", "true") for x in va)
                if not ligado:
                    continue
                d = _dia(ev.get("created_at"))
                atual = out.setdefault(ev["entity_id"], {}).get(etapa)
                if d and (atual is None or d < atual):
                    out[ev["entity_id"]][etapa] = d
    return out


def ler_leads(k: Kommo, filtro: str):
    return [l for l in k.todas(f"/leads?{filtro}&filter%5Bpipeline_id%5D={ll.FUNIL}&with=contacts,loss_reason", "leads")
            if l.get("pipeline_id") == ll.FUNIL and l.get("status_id") not in DISPARO]


def telefones(k: Kommo, leads):
    """{contato: {últimos 8 dígitos}} (só para cruzar com o Movere; o número não vai para o banco)."""
    cids = sorted({c["id"] for l in leads for c in (l.get("_embedded") or {}).get("contacts") or []})
    tel = {}
    for i in range(0, len(cids), 40):
        d = k.get("/contacts?" + "&".join(f"filter%5Bid%5D%5B%5D={x}" for x in cids[i:i + 40]) + "&limit=250")
        for c in (d or {}).get("_embedded", {}).get("contacts", []):
            for f in c.get("custom_fields_values") or []:
                if f.get("field_code") == "PHONE":
                    tel[c["id"]] = {kk for v in f.get("values") or [] for kk in cv.chaves_tel(v.get("value"))}
    return tel


def codigo_tel(k8: str, sal: bytes) -> str:
    """Telefone → código (HMAC-SHA256 com a chave do robô). Serve para cruzar com o Movere; não dá para voltar ao número."""
    return hmac.new(sal, k8.encode(), hashlib.sha256).hexdigest()[:24]


def campos_do_lead(lead) -> list:
    """Campos do Trackeamento que estão 'Sim' AGORA no cartão: '1' Contato Inicial … '7' Agendamento (SQL 35).
    Pelo nome "N - ..." (o 5 - Recuperação Inicial não tem id fixo no código)."""
    out = set()
    for f in lead.get("custom_fields_values") or []:
        nome = str(f.get("field_name") or "").strip()
        if len(nome) > 4 and nome[0] in "1234567" and nome[1:4] == " - ":
            v = (f.get("values") or [{}])[0].get("value")
            if v is True or str(v).lower() in ("1", "true", "sim"):
                out.add(nome[0])
    return sorted(out)


def etapa_do_lead(lead) -> str:
    st = lead.get("status_id")
    return "ganha" if st == GANHA else "perdida" if st == PERDIDA else "aberto"


def entrou_de_verdade(lead, m) -> bool:
    """Conversou de verdade: "1 - Contato Inicial", alguma etapa, ou ainda aberto/ganho."""
    return bool(_valor_campo(lead, C_CONTATO) or m or lead.get("status_id") != PERDIDA)


def linha_do_lead(l, users, m, tels_lead, cot_tel, vendas):
    """Uma linha por lead com as datas de cada etapa (veja as regras no começo do arquivo)."""
    entrou = _dia(l.get("created_at"))
    cots = sorted((c for kk in tels_lead for c in cot_tel.get(kk, []) if c["data"] >= entrou - timedelta(days=1)), key=lambda c: c["data"])
    d_cot = m.get("cotou") or (cots[0]["data"] if cots else None)
    comp = sorted((dv, val) for kk in tels_lead for dv, val in vendas.get(kk, []) if dv >= entrou)
    d_comp, val, fonte = (comp[0][0], round(sum(v for dv, v in comp if dv == comp[0][0]), 2), "movere") if comp else (None, None, None)
    if not d_comp and l.get("status_id") == GANHA and l.get("closed_at"):
        d_comp, fonte = _dia(l["closed_at"]), "venda_ganha"   # a equipe moveu para VENDA GANHA (compareceu na loja)
    if not d_comp:
        v1 = _valor_campo(l, C_1VENDA)
        if v1:
            d1 = _dia(v1) if str(v1).isdigit() else date.fromisoformat(str(v1)[:10])
            if d1 and d1 >= entrou:
                d_comp, fonte = d1, "1a_venda"
    perdido = l.get("status_id") == PERDIDA
    lr = ((l.get("_embedded") or {}).get("loss_reason") or [{}])
    motivo = (lr[0].get("name") if lr and isinstance(lr[0], dict) else None) or _valor_campo(l, C_MOTIVO)
    vis = _valor_campo(l, C_VISITA)
    return {"id": l["id"], "operadora": users.get(l.get("responsible_user_id")), "origem": _origem(l),
            "loja": _valor_campo(l, C_LOJA), "perdido": perdido and not d_comp, "motivo": motivo if perdido else None,
            "d_entrou": entrou, "d_cotou": d_cot, "d_negociou": m.get("negociou"), "d_agendou": m.get("agendou"),
            "d_visita": _dia(vis) if vis and str(vis).isdigit() else None,
            "d_comprou": d_comp, "valor_compra": val, "valor_cotacao": cots[0]["valor"] if cots else None, "compra_fonte": fonte,
            "cotacoes": sorted({str(c["cotacao"]) for c in cots if c.get("cotacao")}) or None}


def juntar(antiga, nova):
    """Junta a linha nova com a que já estava no banco: as datas ficam com a mais antiga (a 1ª vez que aconteceu)."""
    if not antiga:
        return nova
    out = dict(antiga, **{k: v for k, v in nova.items() if v is not None and not k.startswith("d_")})
    cs = set(antiga.get("cotacoes") or []) | set(nova.get("cotacoes") or [])
    out["cotacoes"] = sorted(cs) or None
    for k in ("d_cotou", "d_negociou", "d_agendou", "d_visita", "d_comprou"):
        a, b = antiga.get(k), nova.get(k)
        out[k] = min(x for x in (a, b) if x) if (a or b) else None
    if out.get("d_comprou") and out["d_comprou"] == antiga.get("d_comprou"):
        if antiga.get("valor_compra") is not None:
            out["valor_compra"] = antiga["valor_compra"]
        out["compra_fonte"] = antiga.get("compra_fonte") or nova.get("compra_fonte")
    out["perdido"] = nova.get("perdido", antiga.get("perdido")) and not out.get("d_comprou")
    out["motivo"] = nova.get("motivo") if out["perdido"] else None
    return out


def movere(cli, seg, ini: date, fim: date):
    """Cotações do televendas e vendas (Analytics) entre ini e fim → (cotações por telefone, vendas por telefone)."""
    tt = cv.login_analytics(cli, seg["ANALYTICS_LOGIN"], seg["ANALYTICS_SENHA"])
    dias_ = [ini + timedelta(days=i) for i in range((fim - ini).days + 1)]
    els = [u for u in (cv.elemento_dia(cli, tt, d) for d in dias_) if u]
    if not els:
        return {}, {}
    cots = ll.cotacoes(cv.relatorio(cli, tt, ll.REL_COT, ll.DASH_COT, ll.filtro_dias(els)))
    tt = cv.login_analytics(cli, seg["ANALYTICS_LOGIN"], seg["ANALYTICS_SENHA"])   # o token do Analytics vence rápido
    vendas = cv.vendas_por_telefone(cv.relatorio(cli, tt, cv.REL_VENDAS, None, ll.filtro_dias(els)))
    cot_tel = {}
    for c in cots:
        for kk in cv.chaves_tel(c["telefone"]):
            cot_tel.setdefault(kk, []).append(c)
    return cot_tel, vendas


def os_das_cotacoes(desde: date, ate: date) -> dict:
    """{nº da cotação: (dia, valor, 'nota'|'os')} das cotações que viraram O.S. (API do Movere). Falhou → {} (segue sem)."""
    import movere_api
    if not movere_api.configurada():
        print("ℹ️ API do Movere não configurada: sem a regra cotação → O.S.")
        return {}
    try:
        with httpx.Client(timeout=120) as c:
            out = movere_api.cotacoes_que_viraram_os(c, movere_api.login(c), desde, ate, log=lambda *_: None)
        print(f"🧾 Cotações que viraram O.S. ({desde:%d/%m/%Y} a {ate:%d/%m/%Y}): {len(out)}")
        DETALHES["cotacoes_os"] = DETALHES.get("cotacoes_os", 0) + len(out)
        return out
    except Exception as e:
        print(f"⚠️ API do Movere (cotação → O.S.) falhou ({type(e).__name__}): segue sem")
        DETALHES["cotacoes_os_erro"] = type(e).__name__
        return {}


def preencher_cotacoes(cli, seg, sal, banco, ini: date, fim: date) -> list:
    """Uma vez só (SQL 34): guarda os números das cotações do Movere nos leads que já estavam no banco."""
    cot_tel, _ = movere(cli, seg, ini, fim)
    ch = {}
    for kk, cs in cot_tel.items():
        ch.setdefault(codigo_tel(kk, sal), []).extend(cs)
    mudou = []
    for l in banco.values():
        cs = {str(c["cotacao"]) for h in l.get("tel_hash") or [] for c in ch.get(h, [])
              if c.get("cotacao") and c["data"] >= l["d_entrou"] - timedelta(days=1)}
        if cs - set(l.get("cotacoes") or []):
            nova = dict(l, cotacoes=sorted(cs | set(l.get("cotacoes") or [])))
            banco[l["id"]] = nova
            mudou.append(nova)
    print(f"🧾 Cotações guardadas em {len(mudou)} leads que já estavam no banco")
    return mudou


def aplicar_os(banco: dict, os_map: dict) -> list:
    """Lead com cotação que virou O.S. (no dia da entrada ou depois) = comprou. Fica a data mais antiga."""
    mudou = []
    if not os_map:
        return mudou
    for l in banco.values():
        achou = sorted(os_map[c][:2] for c in (l.get("cotacoes") or []) if c in os_map and os_map[c][0] >= l["d_entrou"])
        if not achou:
            continue
        dia, valor = achou[0]
        if l.get("d_comprou") and l["d_comprou"] <= dia:
            continue
        nova = dict(l, d_comprou=dia, valor_compra=round(sum(v for d, v in achou if d == dia), 2), compra_fonte="os",
                    perdido=False, motivo=None)
        banco[l["id"]] = nova
        mudou.append(nova)
    return mudou


# ── Supabase ──────────────────────────────────────────────────────────────────
def sb_todas(cli, chave, tabela, select="*"):
    out, ini = [], 0
    while True:
        r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/{tabela}?select={select}&order=id",
                    headers=cv._sb_headers(chave, {"Range": f"{ini}-{ini + 999}"}))
        r.raise_for_status()
        p = r.json(); out += p
        if len(p) < 1000:
            return out
        ini += 1000


def ler_estado(cli, chave):
    r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/funil_estado?select=chave,valor", headers=cv._sb_headers(chave))
    r.raise_for_status()
    return {x["chave"]: x["valor"] for x in r.json()}


def _linha_banco(l):
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in l.items() if not k.startswith("_")}


def _linha_do_banco(x):
    out = dict(x)
    for k in ("d_entrou", "d_cotou", "d_negociou", "d_agendou", "d_visita", "d_comprou"):
        out[k] = date.fromisoformat(x[k]) if x.get(k) else None
    return out


def gravar(cli, chave, linhas_mudadas, estado, resumos, abertos):
    H = cv._sb_headers(chave, {"Prefer": "resolution=merge-duplicates,return=minimal"})
    url, agora = f"{cv.SUPABASE_URL}/rest/v1", datetime.now(timezone.utc).isoformat()
    unicas = {l["id"]: l for l in linhas_mudadas}          # o mesmo lead não pode ir 2 vezes no mesmo envio
    L = [dict(_linha_banco(l), atualizado_em=agora) for l in unicas.values()]
    chaves = {k for x in L for k in x}
    L = [{k: x.get(k) for k in chaves} for x in L]
    novas = ("campos", "etapa", "entrou")                  # SQL 35: sem ele, grava sem essas colunas (e sem os "adicionados")
    sem35 = False
    for i in range(0, len(L), 500):
        r = cli.post(f"{url}/funil_leads?on_conflict=id", headers=H, json=L[i:i + 500])
        if r.status_code == 400 and any(c in r.text for c in novas):
            print("⚠️ Falta rodar o SQL 35: gravando sem os campos do Trackeamento")
            sem35 = True
            L = [{k: v for k, v in x.items() if k not in novas} for x in L if x.get("entrou") is not False]
            for j in range(0, len(L), 500):
                cli.post(f"{url}/funil_leads?on_conflict=id", headers=H, json=L[j:j + 500]).raise_for_status()
            break
        r.raise_for_status()
    if sem35:
        estado = {k: v for k, v in estado.items() if k != "campos_desde"}   # a leitura dos campos fica para depois do SQL 35
    cli.post(f"{url}/funil_estado?on_conflict=chave", headers=H,
             json=[{"chave": k, "valor": v, "atualizado_em": agora} for k, v in estado.items()]).raise_for_status()
    cli.post(f"{url}/funil_resumo?on_conflict=periodo", headers=H,
             json=[{"periodo": p, "dados": d, "atualizado_em": agora} for p, d in resumos.items()]).raise_for_status()
    cli.delete(f"{url}/funil_abertos?lead_id=gt.0", headers=cv._sb_headers(chave)).raise_for_status()
    for i in range(0, len(abertos), 500):
        cli.post(f"{url}/funil_abertos?on_conflict=lead_id", headers=H,
                 json=[dict(a, atualizado_em=agora) for a in abertos[i:i + 500]]).raise_for_status()


def registrar(chave, ok, msg, inicio):
    if not chave or DRY:
        return
    corpo = {"robo": ROBO, "ok": ok, "teste": False, "inicio": inicio.isoformat(), "fim": datetime.now(timezone.utc).isoformat(),
             "mensagem": (msg or "")[:300] or None, "detalhes": DETALHES}
    try:
        with httpx.Client(timeout=20) as c:
            c.post(f"{cv.SUPABASE_URL}/rest/v1/robo_execucoes", headers=cv._sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo)
    except Exception as e:
        print(f"⚠️ Não consegui registrar a rodada: {type(e).__name__}")


def mes_anterior(d: date, n=1) -> date:
    d = d.replace(day=1)
    for _ in range(n):
        d = (d - timedelta(days=1)).replace(day=1)
    return d


def linha_minima(l, users) -> dict:
    """Lead que NÃO conta como 'entrou' (adicionado sem Contato Inicial): só o necessário para o quadro 'Pelo Kommo'."""
    return {"id": l["id"], "operadora": users.get(l.get("responsible_user_id")), "origem": _origem(l), "loja": _valor_campo(l, C_LOJA),
            "d_entrou": _dia(l.get("created_at")), "entrou": False, "campos": campos_do_lead(l), "etapa": etapa_do_lead(l),
            "perdido": l.get("status_id") == PERDIDA}


def atualizar_campos(banco, leads, users) -> list:
    """Uma vez só (SQL 35): campos do Trackeamento e etapa dos leads que já estavam no banco + os 'adicionados' que faltavam."""
    mudou = []
    for l in leads:
        x = banco.get(l["id"])
        if x is None:
            x = linha_minima(l, users)
        else:
            x = dict(x, campos=campos_do_lead(l), etapa=etapa_do_lead(l), entrou=x.get("entrou", True) is not False)
        banco[l["id"]] = x
        mudou.append(x)
    return mudou


def processar(k, cli, seg, sal, leads, marc, ini_mov, fim_mov, banco, hoje):
    """Leads do Kommo + Movere → linhas juntas com o banco. Devolve as linhas que mudaram."""
    tel = telefones(k, leads)
    cot_tel, vendas = movere(cli, seg, ini_mov, fim_mov)
    mudou, fora = [], 0
    for l in leads:
        m = marc.get(l["id"], {})
        ok = entrou_de_verdade(l, m) or bool((banco.get(l["id"]) or {}).get("entrou", l["id"] in banco))
        if not ok:
            fora += 1                       # "adicionado" (sem Contato Inicial nem etapa): só para o quadro "Pelo Kommo"
            nova = linha_minima(l, seg["_users"])
            banco[l["id"]] = dict(banco.get(l["id"]) or {}, **nova)
            mudou.append(banco[l["id"]])
            continue
        tl = set().union(*[tel.get(c["id"], set()) for c in (l.get("_embedded") or {}).get("contacts") or []] or [set()])
        nova = linha_do_lead(l, seg["_users"], m, tl, cot_tel, vendas)
        nova["tel_hash"] = sorted(codigo_tel(x, sal) for x in tl) or None
        nova["entrou"], nova["campos"], nova["etapa"] = True, campos_do_lead(l), etapa_do_lead(l)
        j = juntar(banco.get(l["id"]), nova)
        banco[l["id"]] = j
        mudou.append(j)
    return mudou, fora


def compras_recentes(cli, seg, sal, banco, hoje, dias=10):
    """Vendas e cotações recentes do Movere (Analytics + API) para os leads que já estão no banco (pelo código do telefone)."""
    import movere_api
    cot_tel, vendas = movere(cli, seg, hoje - timedelta(days=dias), hoje)
    api_tel, _ = movere_api.buscar(hoje - timedelta(days=movere_api.DIAS_API), hoje)
    vendas = movere_api.juntar(vendas, api_tel)
    vh = {codigo_tel(kk, sal): v for kk, v in vendas.items()}
    ch = {codigo_tel(kk, sal): v for kk, v in cot_tel.items()}
    mudou = []
    for l in banco.values():
        hs = l.get("tel_hash") or []
        nova = dict(l)
        if not l.get("d_comprou"):
            comp = sorted((dv, val) for h in hs for dv, val in vh.get(h, []) if dv >= l["d_entrou"])
            if comp:
                nova["d_comprou"] = comp[0][0]
                nova["valor_compra"] = round(sum(v for dv, v in comp if dv == comp[0][0]), 2)
                nova["perdido"], nova["motivo"], nova["compra_fonte"] = False, None, "movere"
        if not l.get("d_cotou"):
            cots = sorted((c for h in hs for c in ch.get(h, []) if c["data"] >= l["d_entrou"] - timedelta(days=1)), key=lambda c: c["data"])
            if cots:
                nova["d_cotou"], nova["valor_cotacao"] = cots[0]["data"], cots[0]["valor"]
        cots_novas = {str(c["cotacao"]) for h in hs for c in ch.get(h, []) if c.get("cotacao") and c["data"] >= l["d_entrou"] - timedelta(days=1)}
        if cots_novas - set(l.get("cotacoes") or []):
            nova["cotacoes"] = sorted(cots_novas | set(l.get("cotacoes") or []))
        if nova != l:
            banco[l["id"]] = nova
            mudou.append(nova)
    return mudou


def main() -> int:
    inicio = datetime.now(timezone.utc)
    hoje = datetime.now(cv.TZ_LOJA).date()
    seg = {n: os.environ.get(n, "") for n in ("KOMMO_TOKEN", "ANALYTICS_LOGIN", "ANALYTICS_SENHA", "SUPABASE_SERVICE_KEY")}
    faltam = [n for n, v in seg.items() if not v]
    if faltam:
        print("❌ Faltam segredos:", ", ".join(faltam)); return 1
    chave = seg["SUPABASE_SERVICE_KEY"]
    sal = hashlib.sha256(("funil-televendas:" + chave).encode()).digest()
    try:
        with httpx.Client(timeout=120) as cli:
            try:
                estado = ler_estado(cli, chave)
                banco = {x["id"]: _linha_do_banco(x) for x in sb_todas(cli, chave, "funil_leads")}
            except httpx.HTTPStatusError as e:
                if not DRY:
                    raise RuntimeError(f"falta rodar o passo 33 no Supabase ({e.response.status_code})")
                estado, banco = {}, {}          # teste antes do SQL 33: começa do zero, sem gravar
            k = Kommo(cli, seg["KOMMO_TOKEN"])
            seg["_users"] = {u["id"]: u["name"] for u in k.todas("/users", "users")}
            mudaram, fora = [], 0
            carga = date.fromisoformat(estado["carga_desde"]) if estado.get("carga_desde") else None
            ultima = datetime.fromisoformat(estado["ultima_rodada"]) if estado.get("ultima_rodada") else None
            if carga is None:
                # 1ª rodada: os últimos meses inteiros
                carga = mes_anterior(hoje, MESES_INICIAIS - 1)
                print(f"📥 1ª carga: leads desde {carga:%d/%m/%Y}")
                leads = ler_leads(k, f"filter%5Bcreated_at%5D%5Bfrom%5D={_ts(carga)}")
                marc = datas_marcacoes(k, carga)
                m, f = processar(k, cli, seg, sal, leads, marc, carga - timedelta(days=1), hoje, banco, hoje)
                mudaram += m; fora += f
                mudaram += aplicar_os(banco, os_das_cotacoes(carga - timedelta(days=1), hoje))
            else:
                # rodada do dia: leads que mudaram desde a última rodada (com 1 dia de folga)
                desde = (ultima - timedelta(days=1)) if ultima else datetime.combine(hoje - timedelta(days=2), datetime.min.time(), cv.TZ_LOJA)
                leads = ler_leads(k, f"filter%5Bupdated_at%5D%5Bfrom%5D={int(desde.timestamp())}")
                marc = datas_marcacoes(k, desde.date())
                m, f = processar(k, cli, seg, sal, leads, marc, hoje - timedelta(days=10), hoje, banco, hoje)
                mudaram += m; fora += f
                print(f"🔄 Mudaram desde {desde:%d/%m %H:%M}: {len(leads)} leads")
                mudaram += compras_recentes(cli, seg, sal, banco, hoje)
                mudaram += aplicar_os(banco, os_das_cotacoes(hoje - timedelta(days=10), hoje))
                if not estado.get("campos_desde"):
                    # 1ª rodada com o SQL 35: relê os cartões já carregados só para os campos do Trackeamento (sem Movere)
                    leads = ler_leads(k, f"filter%5Bcreated_at%5D%5Bfrom%5D={_ts(carga)}")
                    m = atualizar_campos(banco, leads, seg["_users"])
                    print(f"🏷️ Campos do Trackeamento lidos em {len(m)} cartões")
                    mudaram += m
                if not estado.get("cotacao_os_desde"):
                    # 1ª rodada com o SQL 34: os leads que já estavam no banco ganham as cotações e a regra cotação → O.S.
                    mudaram += preencher_cotacoes(cli, seg, sal, banco, carga - timedelta(days=1), hoje)
                    mudaram += aplicar_os(banco, os_das_cotacoes(carga - timedelta(days=1), hoje))
                # histórico: mais MESES_POR_RODADA meses para trás, até INICIO_HIST
                if carga > INICIO_HIST:
                    novo = max(INICIO_HIST, mes_anterior(carga, MESES_POR_RODADA))
                    fim = carga - timedelta(days=1)
                    print(f"📚 Histórico: leads de {novo:%m/%Y} a {fim:%m/%Y}")
                    leads = ler_leads(k, f"filter%5Bcreated_at%5D%5Bfrom%5D={_ts(novo)}&filter%5Bcreated_at%5D%5Bto%5D={_ts(carga) - 1}")
                    marc = datas_marcacoes(k, novo, min(hoje, fim + timedelta(days=DIAS_MARCACAO)))
                    m, f = processar(k, cli, seg, sal, leads, marc, novo - timedelta(days=1), min(hoje, fim + timedelta(days=DIAS_MARCACAO)), banco, hoje)
                    mudaram += m; fora += f
                    mudaram += aplicar_os(banco, os_das_cotacoes(novo - timedelta(days=1), min(hoje, fim + timedelta(days=DIAS_MARCACAO))))
                    carga = novo
            linhas = list(banco.values())
            resumos, abertos = fc.montar(linhas, hoje, carga)
            r = resumos["mes"]
            DETALHES.update(leads_no_banco=len(linhas), mudaram=len(mudaram), fora_sem_conversa=fora, carga_desde=carga.isoformat(),
                            abertos=len(abertos), alertas=len(r["alertas"]))
            print(f"📊 No banco: {len(linhas)} leads (histórico desde {carga:%m/%Y}) · mudaram {len(mudaram)} · sem conversa (fora) {fora}")
            print(f"📊 Mês: entrou {r['funil']['etapas']['entrou']} · cotou {r['funil']['etapas']['cotou']} · agendou "
                  f"{r['funil']['etapas']['agendou']} · comprou {r['funil']['etapas']['comprou']} · em aberto {len(abertos)}")
            K = r.get("kommo")
            if K:
                print(f"📋 Pelo Kommo (mês): alguma forma {K['alguma_forma']} · Contato Inicial {K['contato']} · cotou {K['cotou']} "
                      f"(sem Contato {K['cotou_sem_contato']}) · Agend. IA {K['ag_ia']} · Agend. {K['ag_equipe']} · os dois {K['ag_ia_e_equipe']} "
                      f"(ganha {K['ag_conf_ganha']}, perdida {K['ag_conf_perdida']}) · contato+cotou+IA {K['caminho_cot_agia']}")
            if DRY:
                print("TESTE: nada foi gravado."); return 0
            gravar(cli, chave, mudaram, {"carga_desde": carga.isoformat(), "ultima_rodada": datetime.now(cv.TZ_LOJA).isoformat(),
                                         "cotacao_os_desde": estado.get("cotacao_os_desde") or carga.isoformat(),
                                         "campos_desde": estado.get("campos_desde") or carga.isoformat()},
                   resumos, abertos)
        print("✅ Gravado.")
        registrar(chave, True, None, inicio)
        return 0
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)[:200]}"
        print("❌ Erro:", msg)
        registrar(chave, False, msg, inicio)
        return 1


if __name__ == "__main__":
    sys.exit(main())
