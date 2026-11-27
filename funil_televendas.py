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
                 se não achar, a coluna "VENDA GANHA" do Kommo (= foi à loja) ou o campo "1ª Venda" do cartão
  · perdido    = etapa "venda perdida" (motivo do Kommo ou o campo "Motivo de perda")
e grava as contas prontas (funil_calculo.montar) em funil_resumo e funil_abertos (SQL 33).
Decisões do TI (27/11/2026): a coluna DISPARO fica de fora; "Outros produtos" = produto que a Fox não trabalha.
Registro público: só contagens. Segredos: KOMMO_TOKEN, ANALYTICS_LOGIN, ANALYTICS_SENHA, SUPABASE_SERVICE_KEY,
MOVERE_API_*. Rodar sem gravar: DRY_RUN=1.
"""
import os, sys, time
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
MESES = 4                                             # leads dos últimos 4 meses (coortes)
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


def datas_marcacoes(k: Kommo, desde: date) -> dict:
    """{lead_id: {etapa: 1º dia em que a marcação foi ligada}} pelo histórico de eventos do Kommo."""
    out = {}
    for etapa, fids in CAMPOS.items():
        for fid in fids:
            for ev in k.todas(f"/events?filter%5Btype%5D=custom_field_{fid}_value_changed&filter%5Bcreated_at%5D%5Bfrom%5D={_ts(desde)}", "events"):
                va = ev.get("value_after") or []
                ligado = any(str((x.get("custom_field_value") or {}).get("text")) in ("1", "true") for x in va)
                if not ligado:
                    continue
                d = _dia(ev.get("created_at"))
                atual = out.setdefault(ev["entity_id"], {}).get(etapa)
                if d and (atual is None or d < atual):
                    out[ev["entity_id"]][etapa] = d
    return out


def ler_kommo(k: Kommo, desde: date):
    users = {u["id"]: u["name"] for u in k.todas("/users", "users")}
    leads = [l for l in k.todas(f"/leads?filter%5Bcreated_at%5D%5Bfrom%5D={_ts(desde)}&filter%5Bpipeline_id%5D={ll.FUNIL}"
                                f"&with=contacts,loss_reason", "leads")
             if l.get("pipeline_id") == ll.FUNIL and l.get("status_id") not in DISPARO]
    marc = datas_marcacoes(k, desde)
    # telefones dos contatos (só para cruzar com o Movere; não vão para o banco)
    cids = sorted({c["id"] for l in leads for c in (l.get("_embedded") or {}).get("contacts") or []})
    tel = {}
    for i in range(0, len(cids), 40):
        d = k.get("/contacts?" + "&".join(f"filter%5Bid%5D%5B%5D={x}" for x in cids[i:i + 40]) + "&limit=250")
        for c in (d or {}).get("_embedded", {}).get("contacts", []):
            for f in c.get("custom_fields_values") or []:
                if f.get("field_code") == "PHONE":
                    tel[c["id"]] = {kk for v in f.get("values") or [] for kk in cv.chaves_tel(v.get("value"))}
    DETALHES.update(kommo_leads=len(leads), kommo_marcacoes=len(marc), kommo_contatos=len(tel))
    return leads, users, marc, tel


# ── Junta tudo numa linha por lead ────────────────────────────────────────────
def montar_linhas(leads, users, marc, tel, cot_tel, vendas, hoje):
    linhas, achou_cot, achou_compra, compra_kommo, compra_antes = [], 0, 0, 0, 0
    for l in leads:
        m = marc.get(l["id"], {})
        tels = set().union(*[tel.get(c["id"], set()) for c in (l.get("_embedded") or {}).get("contacts") or []] or [set()])
        entrou = _dia(l.get("created_at"))
        # cotação: marcação do Kommo; senão a 1ª cotação do televendas no Movere a partir da véspera da entrada
        cots = sorted((c for k in tels for c in cot_tel.get(k, []) if c["data"] >= entrou - timedelta(days=1)), key=lambda c: c["data"])
        d_cot = m.get("cotou") or (cots[0]["data"] if cots else None)
        if not m.get("cotou") and cots:
            achou_cot += 1
        # compra: nota no Movere no dia da entrada ou depois; senão "1ª Venda" do cartão
        comp = sorted((dv, val) for k in tels for dv, val in vendas.get(k, []) if dv >= entrou)
        antes = any(dv < entrou for k in tels for dv, _ in vendas.get(k, []))
        d_comp, val = (comp[0][0], round(sum(v for dv, v in comp if dv == comp[0][0]), 2)) if comp else (None, None)
        if comp:
            achou_compra += 1
        elif l.get("status_id") == GANHA and l.get("closed_at"):
            d_comp = _dia(l["closed_at"])          # a equipe moveu para VENDA GANHA (compareceu na loja)
            compra_kommo += 1
        else:
            v1 = _valor_campo(l, C_1VENDA)
            if v1:
                d1 = _dia(v1) if str(v1).isdigit() else date.fromisoformat(str(v1)[:10])
                if d1 and d1 >= entrou:
                    d_comp, compra_kommo = d1, compra_kommo + 1
            if antes:
                compra_antes += 1
        perdido = l.get("status_id") == PERDIDA
        lr = ((l.get("_embedded") or {}).get("loss_reason") or [{}])
        motivo = (lr[0].get("name") if lr and isinstance(lr[0], dict) else None) or _valor_campo(l, C_MOTIVO)
        vis = _valor_campo(l, C_VISITA)
        linhas.append({"id": l["id"], "operadora": users.get(l.get("responsible_user_id")), "origem": _origem(l),
                       "loja": _valor_campo(l, C_LOJA), "perdido": perdido and not d_comp, "motivo": motivo if perdido else None,
                       "d_entrou": entrou, "d_cotou": d_cot, "d_negociou": m.get("negociou"), "d_agendou": m.get("agendou"),
                       "d_visita": _dia(vis) if vis and str(vis).isdigit() else None,
                       "d_comprou": d_comp, "valor_compra": val, "valor_cotacao": cots[0]["valor"] if cots else None})
    DETALHES.update(cotacao_pelo_movere=achou_cot, compra_pelo_movere=achou_compra, compra_pelo_kommo=compra_kommo,
                    compra_so_antes_da_entrada=compra_antes)
    return linhas


# ── Supabase ──────────────────────────────────────────────────────────────────
def gravar(cli, chave, resumos, abertos):
    H = cv._sb_headers(chave, {"Prefer": "resolution=merge-duplicates,return=minimal"})
    url, agora = f"{cv.SUPABASE_URL}/rest/v1", datetime.now(timezone.utc).isoformat()
    r = cli.post(f"{url}/funil_resumo?on_conflict=periodo", headers=H,
                 json=[{"periodo": p, "dados": d, "atualizado_em": agora} for p, d in resumos.items()])
    r.raise_for_status()
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


def main() -> int:
    inicio = datetime.now(timezone.utc)
    hoje = datetime.now(cv.TZ_LOJA).date()
    seg = {n: os.environ.get(n, "") for n in ("KOMMO_TOKEN", "ANALYTICS_LOGIN", "ANALYTICS_SENHA", "SUPABASE_SERVICE_KEY")}
    faltam = [n for n, v in seg.items() if not v and not (DRY and n == "SUPABASE_SERVICE_KEY")]
    if faltam:
        print("❌ Faltam segredos:", ", ".join(faltam)); return 1
    m0 = hoje.replace(day=1)
    for _ in range(MESES - 1):
        m0 = (m0 - timedelta(days=1)).replace(day=1)
    print(f"📈 Funil do televendas · leads desde {m0:%d/%m/%Y}{' · TESTE (não grava)' if DRY else ''}")
    try:
        with httpx.Client(timeout=120) as cli:
            leads, users, marc, tel = ler_kommo(Kommo(cli, seg["KOMMO_TOKEN"]), m0)
            print(f"🗂️ Kommo: {len(leads)} leads · {len(marc)} com marcações · {len(tel)} contatos com telefone")
            tt = cv.login_analytics(cli, seg["ANALYTICS_LOGIN"], seg["ANALYTICS_SENHA"])
            dias_ = [m0 - timedelta(days=1) + timedelta(days=i) for i in range((hoje - m0).days + 2)]
            els = [u for u in (cv.elemento_dia(cli, tt, d) for d in dias_) if u]
            cots = ll.cotacoes(cv.relatorio(cli, tt, ll.REL_COT, ll.DASH_COT, ll.filtro_dias(els)))
            tt = cv.login_analytics(cli, seg["ANALYTICS_LOGIN"], seg["ANALYTICS_SENHA"])   # o token do Analytics vence rápido
            vendas = cv.vendas_por_telefone(cv.relatorio(cli, tt, cv.REL_VENDAS, None, ll.filtro_dias(els)))
        import movere_api
        api_tel, _ = movere_api.buscar(hoje - timedelta(days=movere_api.DIAS_API), hoje)
        vendas = movere_api.juntar(vendas, api_tel)
        cot_tel = {}
        for c in cots:
            for kk in cv.chaves_tel(c["telefone"]):
                cot_tel.setdefault(kk, []).append(c)
        print(f"🧾 Movere: {len(cots)} cotações do televendas · {len(vendas)} telefones com compra")
        linhas = montar_linhas(leads, users, marc, tel, cot_tel, vendas, hoje)
        resumos, abertos = fc.montar(linhas, hoje)
        r = resumos["mes"]
        print(f"📊 Mês: entrou {r['funil']['etapas']['entrou']} · cotou {r['funil']['etapas']['cotou']} · agendou "
              f"{r['funil']['etapas']['agendou']} · comprou {r['funil']['etapas']['comprou']} · em aberto {len(abertos)}"
              f" · alertas {len(r['alertas'])}")
        DETALHES.update(abertos=len(abertos), alertas=len(r["alertas"]), linhas=len(linhas))
        if DRY:
            print("TESTE: nada foi gravado."); return 0
        with httpx.Client(timeout=120) as cli:
            gravar(cli, seg["SUPABASE_SERVICE_KEY"], resumos, abertos)
        print("✅ Gravado.")
        registrar(seg["SUPABASE_SERVICE_KEY"], True, None, inicio)
        return 0
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)[:200]}"
        print("❌ Erro:", msg)
        registrar(seg.get("SUPABASE_SERVICE_KEY"), False, msg, inicio)
        return 1


if __name__ == "__main__":
    sys.exit(main())
