"""SÓ LEITURA: o que existe para o funil do televendas (Kommo → cotação → agendamento → compra), novembro/2026.
Registro público só com contagens e nomes de etapas/campos; nomes de pessoas e detalhes saem trancados."""
import os
from datetime import date, datetime, timedelta, timezone
import httpx
import conferir_vendas_movere as cv
import ligacoes_lojas as ll
import movere_api
from varejo_teste import trancar

TOK = os.environ["KOMMO_TOKEN"].strip(); H = {"Authorization": "Bearer " + TOK}
hoje = datetime.now(cv.TZ_LOJA).date(); ini = date(2026, 11, 1)
ts_ini = int(datetime(2026, 11, 1, tzinfo=cv.TZ_LOJA).timestamp())
seg = {}
with httpx.Client(timeout=120) as cli:
    def get(u):
        r = cli.get(ll.KOMMO + u, headers=H)
        if r.status_code == 204: return None
        r.raise_for_status(); return r.json()
    pip = get("/leads/pipelines")
    print("FUNIS:", [(p["id"], p["name"], len(p["_embedded"]["statuses"])) for p in pip["_embedded"]["pipelines"]])
    etapas = {}
    for p in pip["_embedded"]["pipelines"]:
        for s in p["_embedded"]["statuses"]:
            etapas[s["id"]] = (p["name"], s["name"])
    print("ETAPAS do funil", ll.FUNIL, ":", [(s["id"], s["name"]) for p in pip["_embedded"]["pipelines"] if p["id"] == ll.FUNIL for s in p["_embedded"]["statuses"]])
    users = {u["id"]: u["name"] for u in (get("/users?limit=250") or {}).get("_embedded", {}).get("users", [])}
    leads, pg = [], 1
    while True:
        d = get(f"/leads?filter%5Bcreated_at%5D%5Bfrom%5D={ts_ini}&with=contacts&limit=250&page={pg}")
        if not d: break
        leads += d["_embedded"]["leads"]
        if not d.get("_links", {}).get("next"): break
        pg += 1
    print("leads criados em novembro:", len(leads))
    por_etapa, por_resp, campos, sem_contato = {}, {}, {}, 0
    for l in leads:
        k = etapas.get(l["status_id"], ("?", str(l["status_id"])))
        por_etapa[k] = por_etapa.get(k, 0) + 1
        por_resp[users.get(l.get("responsible_user_id"), "?")] = por_resp.get(users.get(l.get("responsible_user_id"), "?"), 0) + 1
        for f in l.get("custom_fields_values") or []:
            campos[(f.get("field_name"), f.get("field_type"))] = campos.get((f.get("field_name"), f.get("field_type")), 0) + 1
        if not (l.get("_embedded") or {}).get("contacts"): sem_contato += 1
    print("por etapa:", sorted(((f"{a} / {b}", n) for (a, b), n in por_etapa.items()), key=lambda x: -x[1]))
    print("campos dos leads (nome, tipo, quantos têm):", sorted(((a, b, n) for (a, b), n in campos.items()), key=lambda x: -x[2]))
    print("leads sem contato:", sem_contato, "· responsáveis distintos:", len(por_resp))
    # eventos de mudança de etapa (para saber QUANDO agendou)
    ev = get(f"/events?filter%5Btype%5D=lead_status_changed&filter%5Bcreated_at%5D%5Bfrom%5D={ts_ini}&limit=100")
    print("eventos de mudança de etapa disponíveis:", "sim" if ev else "não", (len(ev["_embedded"]["events"]) if ev else 0), "na 1ª página")
    # telefones dos leads
    cids = sorted({c["id"] for l in leads for c in (l.get("_embedded") or {}).get("contacts") or []})
    tel_c = {}
    for i in range(0, len(cids), 40):
        d = get("/contacts?" + "&".join(f"filter%5Bid%5D%5B%5D={x}" for x in cids[i:i + 40]) + "&limit=250")
        for c in (d or {}).get("_embedded", {}).get("contacts", []):
            for f in c.get("custom_fields_values") or []:
                if f.get("field_code") == "PHONE":
                    tel_c[c["id"]] = {k for v in f.get("values") or [] for k in cv.chaves_tel(v.get("value"))}
    lead_tels = [set().union(*[tel_c.get(c["id"], set()) for c in (l.get("_embedded") or {}).get("contacts") or []] or [set()]) for l in leads]
    print("leads com telefone:", sum(1 for t in lead_tels if t))
    # Movere: cotações do televendas e vendas em novembro
    tt = cv.login_analytics(cli, os.environ["ANALYTICS_LOGIN"], os.environ["ANALYTICS_SENHA"])
    dias = [ini + timedelta(days=i) for i in range((hoje - ini).days + 1)]
    els = [u for u in (cv.elemento_dia(cli, tt, d) for d in dias) if u]
    cots = ll.cotacoes(cv.relatorio(cli, tt, ll.REL_COT, ll.DASH_COT, ll.filtro_dias(els)))
    vendas = cv.vendas_por_telefone(cv.relatorio(cli, tt, cv.REL_VENDAS, None, ll.filtro_dias(els)))
api_tel, _ = movere_api.buscar(hoje - timedelta(days=movere_api.DIAS_API), hoje)
vendas = movere_api.juntar(vendas, api_tel)
print("cotações do televendas em novembro:", len(cots), "· operadoras:", len({c['operador'] for c in cots}), "· telefones de quem comprou:", len(vendas))
cot_tel = {}
for c in cots:
    for k in cv.chaves_tel(c["telefone"]):
        cot_tel.setdefault(k, []).append(c)
n_lead_cot = sum(1 for t in lead_tels if t & set(cot_tel))
n_lead_venda = sum(1 for t in lead_tels if t & set(vendas))
cot_venda = sum(1 for c in cots if cv.chaves_tel(c["telefone"]) & set(vendas))
antes = sum(1 for c in cots if any(dd < c["data"] for k in cv.chaves_tel(c["telefone"]) for dd, _ in vendas.get(k, [])) and not any(dd >= c["data"] for k in cv.chaves_tel(c["telefone"]) for dd, _ in vendas.get(k, [])))
cot_sem_lead = sum(1 for c in cots if not (cv.chaves_tel(c["telefone"]) & set().union(*lead_tels)))
print(f"leads que têm cotação: {n_lead_cot} · leads que compraram: {n_lead_venda} · cotações que viraram compra: {cot_venda}"
      f" · cotações com compra só ANTES da cotação: {antes} · cotações sem lead no Kommo (novembro): {cot_sem_lead}")
print("Z TRANCADO:", trancar({"por_resp": por_resp, "operadores": sorted({c['operador'] for c in cots}), "users": list(users.values())}))
