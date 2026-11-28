"""
funil_calculo.py · Monta as contas do painel "Funil do televendas" a partir de uma linha por lead
=================================================================================================
Entrada: lista de leads (dicionários) já com as datas de cada etapa (o robô funil_televendas.py junta Kommo e Movere):
  id, criado (date), operadora, origem, loja, perdido (bool), motivo,
  d_entrou, d_cotou, d_negociou, d_agendou, d_visita, d_comprou (date ou None), valor_compra, valor_cotacao
Saída: o resumo de cada período (para funil_resumo) e as oportunidades em aberto (para funil_abertos).

Regras (decisão do TI, 27/11/2026):
· Fica de fora da conversão (não é oportunidade): "Outros produtos" (produto que a Fox não trabalha), "Chamou errado",
  "Curtidas do Instagram", "Contato com RH", "Cidade sem loja", "Sem cidade". Aparecem à parte.
· Quem comprou conta como tendo passado pelas etapas anteriores (cotou e agendou), senão o funil "subiria".
· Comprou = nota fiscal da O.S. no Movere (data e valor) pelo telefone, a partir do dia da entrada; ou "1ª Venda" no Kommo.
· Compra antes da entrada não conta (cliente antigo).
"""
from datetime import date, timedelta

import funil_estatistica as fe

FORA = ("outros produtos", "chamou errado", "curtidas do instagram", "contato com rh", "cidade sem loja", "sem cidade",
        "disparo sem sucesso")   # disparo que terminou em "venda perdida" (não é atendimento; TI, 27/11/2026)
ETAPAS = ("entrou", "cotou", "agendou", "comprou")
PROX = {"entrou": "cotou", "cotou": "agendou", "agendou": "comprou"}
JANELA_COMPRA = 30      # "comprou em até 30 dias" nas coortes, no controle semanal e no lead scoring


def fora_da_conta(l) -> bool:
    return any(m in (l.get("motivo") or "").lower() for m in FORA)


def alcancou(l, etapa) -> bool:
    """O lead chegou a esta etapa? (quem comprou passou pelas anteriores)."""
    if etapa == "entrou":
        return True
    if l.get("d_comprou"):
        return True
    if etapa == "comprou":
        return False
    if etapa == "agendou":
        return bool(l.get("d_agendou"))
    return bool(l.get("d_cotou") or l.get("d_agendou"))


def data_etapa(l, etapa):
    d = l.get("d_" + etapa)
    if etapa == "cotou" and not d:
        d = l.get("d_agendou") or l.get("d_comprou")
    if etapa == "agendou" and not d:
        d = l.get("d_comprou")
    return d


def dias(a, b):
    return (b - a).days if a and b and b >= a else None


def funil(leads):
    c = {e: sum(1 for l in leads if alcancou(l, e)) for e in ETAPAS}
    passos = []
    for a, b in (("entrou", "cotou"), ("cotou", "agendou"), ("agendou", "comprou")):
        taxa = c[b] / c[a] if c[a] else None
        passos.append({"de": a, "para": b, "taxa": taxa, "perdidos": c[a] - c[b]})
    validos = [p for p in passos if p["taxa"] is not None]
    gargalo = min(validos, key=lambda p: p["taxa"])["de"] + "→" + min(validos, key=lambda p: p["taxa"])["para"] if validos else None
    return {"etapas": c, "passos": passos, "geral": (c["comprou"] / c["entrou"]) if c["entrou"] else None, "gargalo": gargalo}


def tempos(leads):
    pares = {"entrada_cotacao": ("entrou", "cotou"), "cotacao_agendamento": ("cotou", "agendou"),
             "agendamento_compra": ("agendou", "comprou"), "entrada_compra": ("entrou", "comprou")}
    out = {}
    for nome, (a, b) in pares.items():
        vals = [dias(data_etapa(l, a), data_etapa(l, b)) for l in leads if alcancou(l, b)]
        out[nome] = fe.resumo_tempo([v for v in vals if v is not None])
    tot = [dias(l.get("d_entrou"), l.get("d_comprou")) for l in leads if l.get("d_comprou")]
    out["histograma"] = fe.histograma([v for v in tot if v is not None])
    r = out["entrada_compra"]
    out["outliers"] = [l["id"] for l in leads if l.get("d_comprou") and fe.eh_outlier(dias(l["d_entrou"], l["d_comprou"]), r)][:50]
    return out


def por_operadora(leads, hoje):
    ops = sorted({l.get("operadora") or "(sem operadora)" for l in leads})
    linhas, taxas = {}, {}
    for op in ops:
        L = [l for l in leads if (l.get("operadora") or "(sem operadora)") == op]
        f = funil(L)
        comp = [l for l in L if l.get("d_comprou")]
        receita = sum(float(l.get("valor_compra") or 0) for l in comp)
        t = [dias(l["d_entrou"], l["d_comprou"]) for l in comp]
        t = [x for x in t if x is not None]
        tq = fe.resumo_tempo(t)
        k, n = f["etapas"]["comprou"], f["etapas"]["entrou"]
        _, lo, hi = fe.wilson(k, n)
        linhas[op] = {"clientes": n, "cotou": f["etapas"]["cotou"], "agendou": f["etapas"]["agendou"], "comprou": k,
                      "conversao": f["geral"], "ic_inf": lo, "ic_sup": hi, "passos": f["passos"],
                      "receita": round(receita, 2), "ticket": round(receita / k, 2) if k else None,
                      "tempo_mediano": tq.get("mediana"), "tempos": t, "q1": tq.get("q1"), "q3": tq.get("q3"),
                      "min": tq.get("min"), "max": tq.get("max")}
        taxas[op] = f["geral"]
    z = fe.zscores({k: v for k, v in taxas.items() if linhas[k]["clientes"] > 0})
    tot_k = sum(x["comprou"] for x in linhas.values())
    tot_n = sum(x["clientes"] for x in linhas.values())
    media = tot_k / tot_n if tot_n else 0
    equipe = funil(leads)
    for op, x in linhas.items():
        x["z"] = z.get(op, 0.0)
        x["classe"] = fe.classificar(x["comprou"], x["clientes"], media, x["z"])
        # Diagnóstico: a etapa em que mais perde em relação à equipe (diferença de taxa)
        dif = []
        for p, pe in zip(x["passos"], equipe["passos"]):
            if p["taxa"] is not None and pe["taxa"] is not None:
                dif.append((p["taxa"] - pe["taxa"], p["de"] + "→" + p["para"]))
        x["pior_etapa"] = min(dif)[1] if dif and min(dif)[0] < 0 else None
        x["pior_dif"] = min(dif)[0] if dif and min(dif)[0] < 0 else None
    return linhas, media


def coortes(leads, hoje):
    meses = {}
    for l in leads:
        m = l["d_entrou"].strftime("%Y-%m")
        meses.setdefault(m, []).append(l)
    out = []
    for m in sorted(meses):
        L = meses[m]
        maduros = [l for l in L if (hoje - l["d_entrou"]).days >= JANELA_COMPRA]
        em30 = sum(1 for l in maduros if l.get("d_comprou") and dias(l["d_entrou"], l["d_comprou"]) <= JANELA_COMPRA)
        f = funil(L)
        out.append({"mes": m, "entrou": len(L), "cotou": f["etapas"]["cotou"], "agendou": f["etapas"]["agendou"],
                    "comprou": f["etapas"]["comprou"], "conversao": f["geral"],
                    "maduros": len(maduros), "comprou_30d": em30, "conv_30d": (em30 / len(maduros)) if maduros else None})
    return out


def semanal(leads, hoje, semanas=16):
    """Conversão em até 14 dias por semana de entrada (só semanas que já tiveram 14 dias)."""
    seg = hoje - timedelta(days=hoje.weekday())
    lin = []
    for i in range(semanas, 0, -1):
        ini = seg - timedelta(weeks=i)
        if (hoje - (ini + timedelta(days=6))).days < 14:
            continue
        L = [l for l in leads if ini <= l["d_entrou"] <= ini + timedelta(days=6)]
        k = sum(1 for l in L if l.get("d_comprou") and dias(l["d_entrou"], l["d_comprou"]) <= 14)
        lin.append((ini.isoformat(), k, len(L)))
    r = fe.controle_semanal(lin)
    r["semanas"] = [{"semana": w, "taxa": t, "n": n} for (w, t), (_, _, n) in zip(r["semanas"], [x for x in lin if x[2]])]
    return r


def sobrevivencia(leads, hoje):
    pares = []
    for l in leads:
        if l.get("d_comprou"):
            pares.append((dias(l["d_entrou"], l["d_comprou"]), True))
        else:
            pares.append(((hoje - l["d_entrou"]).days, False))
    c = fe.kaplan_meier([p for p in pares if p[0] is not None])
    return {"curva": [[t, round(s, 4)] for t, s in c if t <= 90],
            "chance": {str(d): round(fe.chance_ate(c, d), 4) for d in (7, 15, 30, 60)}}


def etapa_atual(l):
    if l.get("d_agendou"):
        return "agendou"
    if l.get("d_negociou"):
        return "negociou"
    if l.get("d_cotou"):
        return "cotou"
    return "entrou"


def tempo_na_etapa_historico(leads):
    """Quantos dias os leads ficaram em cada etapa antes de seguir (P75 = limite do 'parado')."""
    out = {}
    for e, prox in (("entrou", "cotou"), ("cotou", "agendou"), ("negociou", "agendou"), ("agendou", "comprou")):
        vals = [dias(data_etapa(l, e), data_etapa(l, prox)) for l in leads if l.get("d_" + e) and alcancou(l, prox)]
        out[e] = fe.percentil([v for v in vals if v is not None], 75)
    return out


def caracteristicas(l, hoje):
    o = (l.get("origem") or "").lower()
    v = float(l.get("valor_cotacao") or 0)
    rapido = dias(l.get("d_entrou"), l.get("d_cotou"))
    return [1.0 if "facebook" in o or "meta" in o or "instagram" in o else 0.0,
            1.0 if "google" in o or "site" in o else 0.0,
            1.0 if l.get("d_cotou") else 0.0,
            1.0 if l.get("d_negociou") else 0.0,
            1.0 if l.get("d_agendou") else 0.0,
            1.0 if rapido is not None and rapido <= 1 else 0.0,
            min(1.0, v / 3000.0)]


NOMES_CARAC = ["origem Facebook/Instagram", "origem Google/site", "fez cotação", "negociou", "agendou",
               "cotação no mesmo dia ou no seguinte", "valor da cotação"]


def lead_scoring(leads, hoje):
    """Treina com quem já tem 30 dias (comprou em até 30 dias = 1). Valida nos 20% mais recentes (AUC)."""
    hist = sorted([l for l in leads if (hoje - l["d_entrou"]).days >= JANELA_COMPRA], key=lambda l: l["d_entrou"])
    if len(hist) < 50:
        return None
    y = [1 if l.get("d_comprou") and dias(l["d_entrou"], l["d_comprou"]) <= JANELA_COMPRA else 0 for l in hist]
    X = [caracteristicas(l, hoje) for l in hist]
    corte = int(len(hist) * 0.8)
    w_val = fe.regressao_logistica(X[:corte], y[:corte])
    a = fe.auc([fe.prever(w_val, x) for x in X[corte:]], y[corte:])
    w = fe.regressao_logistica(X, y)
    return {"pesos": w, "auc": a, "base": sum(y) / len(y), "n_treino": len(hist),
            "fatores": sorted(zip(NOMES_CARAC, w[1:]), key=lambda t: -abs(t[1]))}


def resumo(leads, hoje, desde, ate=None):
    """Todas as contas de um período (leads que ENTRARAM de `desde` até `ate`)."""
    todos = [l for l in leads if l["d_entrou"] and l["d_entrou"] >= desde and (ate is None or l["d_entrou"] <= ate)]
    base = [l for l in todos if not fora_da_conta(l)]
    fora = {}
    for l in todos:
        if fora_da_conta(l):
            m = (l.get("motivo") or "").strip()
            fora[m] = fora.get(m, 0) + 1
    f = funil(base)
    ops, media = por_operadora(base, hoje)
    abertos = [l for l in base if not l.get("perdido") and not l.get("d_comprou")]
    comp = [l for l in base if l.get("d_comprou")]
    receita = sum(float(l.get("valor_compra") or 0) for l in comp)
    ticket = receita / len(comp) if comp else 0
    ciclo = [dias(l["d_entrou"], l["d_comprou"]) for l in comp]
    ciclo = [c for c in ciclo if c is not None]
    ciclo_m = sum(ciclo) / len(ciclo) if ciclo else None
    vel = {"oportunidades": len(abertos), "conversao": f["geral"] or 0, "ticket": round(ticket, 2), "ciclo_dias": ciclo_m,
           "por_dia": fe.velocidade(len(abertos), f["geral"] or 0, ticket, max(ciclo_m or 0, 1) if ciclo_m is not None else None)}
    for op, x in ops.items():
        ab = sum(1 for l in abertos if (l.get("operadora") or "(sem operadora)") == op)
        x["velocidade"] = fe.velocidade(ab, x["conversao"] or 0, x["ticket"] or 0, max(x["tempo_mediano"] or 0, 1)) if x["comprou"] else 0
        x["abertos"] = ab
    motivos = {}
    for l in base:
        if l.get("perdido") and not l.get("d_comprou"):
            m = (l.get("motivo") or "Sem motivo").strip()
            motivos[m] = motivos.get(m, 0) + 1
    origens = {}
    for l in base:
        o = l.get("origem") or "(sem origem)"
        x = origens.setdefault(o, {"entrou": 0, "comprou": 0})
        x["entrou"] += 1
        x["comprou"] += 1 if l.get("d_comprou") else 0
    fontes = {}
    for l in comp:
        fo = l.get("compra_fonte") or "sem_fonte"
        fontes[fo] = fontes.get(fo, 0) + 1
    for op in ops.values():
        op.pop("tempos", None)          # o boxplot usa mínimo, Q1, mediana, Q3 e máximo (a lista inteira não vai para o banco)
    return {"desde": desde.isoformat(), "ate": (ate or hoje).isoformat(), "total_leads": len(todos), "fora_da_conta": fora,
            "funil": f, "tempos": tempos(base), "operadoras": ops, "media_equipe": media,
            "velocidade": vel, "motivos_perda": dict(sorted(motivos.items(), key=lambda kv: -kv[1])),
            "origens": origens, "fontes_compra": fontes, "sobrevivencia": sobrevivencia(base, hoje)}


def previsao_mes(leads, hoje, modelo, ticket):
    """Receita já vendida no mês + chance × ticket médio das oportunidades abertas (com a faixa de 95%)."""
    ini = hoje.replace(day=1)
    vendido = sum(float(l.get("valor_compra") or 0) for l in leads if l.get("d_comprou") and l["d_comprou"] >= ini)
    fim = (ini + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    resta = (fim - hoje).days
    esp = var = 0.0
    abertos = [l for l in leads if not l.get("perdido") and not l.get("d_comprou") and not fora_da_conta(l)
               and (hoje - l["d_entrou"]).days <= 60]
    for l in abertos:
        p = fe.prever(modelo["pesos"], caracteristicas(l, hoje)) if modelo else 0.0
        p *= min(1.0, resta / JANELA_COMPRA)          # só a parte que ainda cabe no mês
        esp += p
        var += p * (1 - p)
    meio = vendido + esp * ticket
    margem = 1.96 * (var ** 0.5) * ticket
    return {"vendido": round(vendido, 2), "esperado_abertos": round(esp * ticket, 2), "previsao": round(meio, 2),
            "minimo": round(max(vendido, meio - margem), 2), "maximo": round(meio + margem, 2), "dias_restantes": resta}


def disparos(L, c):
    """Disparo noturno (TI, 28/11/2026): quem recebeu (campo 5), se respondeu e o que respondeu (campo "Disparo"),
    e quantos de cada resposta cotaram, agendaram e compraram (VENDA GANHA e Movere)."""
    rec = [l for l in L if "5" in c(l)]
    def bloco(xs):
        return {"n": len(xs), "cotou": sum(1 for l in xs if "2" in c(l)), "agendou": sum(1 for l in xs if c(l) & {"6", "7"}),
                "ganha": sum(1 for l in xs if l.get("etapa") == "ganha"), "comprou_real": sum(1 for l in xs if l.get("d_comprou"))}
    grupos = lambda chave: {k: bloco([l for l in rec if (l.get(chave) or "(vazio)") == k])
                            for k in sorted({l.get(chave) or "(vazio)" for l in rec})}
    return {"recebeu": bloco(rec), "nao_recebeu": bloco([l for l in L if "1" in c(l) and "5" not in c(l)]),
            "respondeu": grupos("respondeu"), "resposta": grupos("disparo")}


def pelo_kommo(todos, desde, ate=None):
    """Contas como os filtros do Kommo (campos do Trackeamento AGORA = Sim), pedido do TI 28/11/2026.
    todos = todos os leads do Funil Principal sem disparo (inclusive os que nunca tiveram Contato Inicial)."""
    L = [l for l in todos if l.get("d_entrou") and l["d_entrou"] >= desde and (ate is None or l["d_entrou"] <= ate)]
    if not any(l.get("campos") is not None for l in L):
        return None                                   # antes do SQL 35 / da 1ª rodada que lê os campos
    c = lambda l: set(l.get("campos") or [])
    ci = [l for l in L if "1" in c(l)]
    sem = [l for l in L if "1" not in c(l)]
    n = lambda xs, f: sum(1 for l in xs if f(l))
    return {"alguma_forma": len(L), "contato": len(ci), "sem_contato": len(sem),
            # Cotou = "2 - Fez cotação: Sim" (filtro do TI no Kommo, 28/11/2026: nov 7.212); o 3 (IA) aparece à parte
            "cotou": n(ci, lambda l: "2" in c(l)), "cotou_ia": n(ci, lambda l: "3" in c(l)),
            "cotou_ia_e_2": n(ci, lambda l: {"2", "3"} <= c(l)), "so_cotacao_ia": n(ci, lambda l: "3" in c(l) and "2" not in c(l)),
            "cotou_sem_ia": n(ci, lambda l: "2" in c(l) and "3" not in c(l)),     # cotou sem passar pela IA (a equipe fez)
            "cotou_sem_contato": n(sem, lambda l: c(l) & {"2", "3"}), "negociou": n(ci, lambda l: "4" in c(l)),
            "recuperacao": n(L, lambda l: "5" in c(l)), "recuperacao_comprou": n(L, lambda l: "5" in c(l) and l.get("d_comprou")),
            "ag_ia": n(ci, lambda l: "6" in c(l)), "ag_equipe": n(ci, lambda l: "7" in c(l)),
            "ag_ia_e_equipe": n(ci, lambda l: {"6", "7"} <= c(l)), "ag_so_ia": n(ci, lambda l: "6" in c(l) and "7" not in c(l)),
            "ag_so_equipe": n(ci, lambda l: "7" in c(l) and "6" not in c(l)), "agendou": n(ci, lambda l: c(l) & {"6", "7"}),
            "venda_ganha": n(ci, lambda l: l.get("etapa") == "ganha"), "venda_perdida": n(ci, lambda l: l.get("etapa") == "perdida"),
            "comprou_real": n(ci, lambda l: l.get("d_comprou")),
            # dentro dos agendados confirmados (IA + equipe), como no Kommo do TI: 1632 → VENDA GANHA 462 · venda perdida 820
            "ag_conf_ganha": n(ci, lambda l: {"6", "7"} <= c(l) and l.get("etapa") == "ganha"),
            "ag_conf_perdida": n(ci, lambda l: {"6", "7"} <= c(l) and l.get("etapa") == "perdida"),
            "ag_conf_comprou_real": n(ci, lambda l: {"6", "7"} <= c(l) and l.get("d_comprou")),
            # caminho completo (TI): Contato Inicial + Fez cotação (2) + Agendamento IA (6)
            "caminho_cot_agia": n(ci, lambda l: {"2", "6"} <= c(l)),
            "caminho_cot_agia_ganha": n(ci, lambda l: {"2", "6"} <= c(l) and l.get("etapa") == "ganha"),
            "caminho_cot_agia_perdida": n(ci, lambda l: {"2", "6"} <= c(l) and l.get("etapa") == "perdida"),
            "disparo": disparos(L, c),
                        "agendou_ganha": n(ci, lambda l: c(l) & {"6", "7"} and l.get("etapa") == "ganha"),
            "agendou_perdida": n(ci, lambda l: c(l) & {"6", "7"} and l.get("etapa") == "perdida")}


def montar(leads, hoje, inicio_hist=None):
    """Tudo para o banco: {periodo: resumo} + lista de abertos (aging + scoring) + modelo + previsão + alertas.
    Períodos: mês, 30 e 90 dias, este ano, o ano passado (quando houver dados) e desde o início da carga.
    Leads com entrou = False (sem Contato Inicial nem etapa: "adicionados") só entram no quadro "Pelo Kommo"."""
    todos_kommo = leads
    leads = [l for l in leads if l.get("entrou") is not False]
    periodos = {"mes": (hoje.replace(day=1), None), "30d": (hoje - timedelta(days=30), None), "90d": (hoje - timedelta(days=90), None),
                "ano": (date(hoje.year, 1, 1), None)}
    primeiro = min((l["d_entrou"] for l in leads if l.get("d_entrou")), default=hoje)
    if primeiro <= date(hoje.year - 1, 12, 31):
        periodos[str(hoje.year - 1)] = (max(date(hoje.year - 1, 1, 1), primeiro), date(hoje.year - 1, 12, 31))
    periodos["tudo"] = (primeiro, None)
    resumos = {p: resumo(leads, hoje, d, a) for p, (d, a) in periodos.items()}
    for p, (d, a) in periodos.items():
        resumos[p]["kommo"] = pelo_kommo(todos_kommo, d, a)
    base90 = [l for l in leads if l["d_entrou"] >= periodos["90d"][0] and not fora_da_conta(l)]
    modelo = lead_scoring([l for l in leads if not fora_da_conta(l)], hoje)
    p75 = tempo_na_etapa_historico(base90)
    abertos = []
    for l in base90:
        if l.get("perdido") or l.get("d_comprou"):
            continue
        e = etapa_atual(l)
        desde = l.get("d_" + e) or l["d_entrou"]
        parado = (hoje - desde).days
        lim = p75.get(e)
        abertos.append({"lead_id": l["id"], "operadora": l.get("operadora"), "etapa": e, "desde": desde.isoformat(),
                        "dias_parado": parado, "p75_etapa": lim, "atrasado": lim is not None and parado > lim,
                        "valor_cotacao": l.get("valor_cotacao"), "origem": l.get("origem"), "loja": l.get("loja"),
                        "chance": round(fe.prever(modelo["pesos"], caracteristicas(l, hoje)), 4) if modelo else None})
    ticket = resumos["90d"]["velocidade"]["ticket"] or 0
    prev = previsao_mes(leads, hoje, modelo, ticket)
    extra = {"coortes": coortes([l for l in leads if not fora_da_conta(l)], hoje),
             "semanal": semanal([l for l in leads if not fora_da_conta(l)], hoje),
             "p75_etapa": p75, "modelo": ({k: v for k, v in modelo.items() if k != "pesos"} if modelo else None),
             "previsao": prev}
    alertas = []
    s = extra["semanal"]
    if s["fora"]:
        alertas.append(f"Conversão semanal fora do normal nas semanas: {', '.join(x[8:10] + '/' + x[5:7] for x in s['fora'])}")
    for op, x in resumos["30d"]["operadoras"].items():
        if x["classe"] == "precisa de apoio":
            alertas.append(f"{op}: conversão abaixo da equipe nos últimos 30 dias" + (f" (perde mais em {x['pior_etapa']})" if x["pior_etapa"] else ""))
    atras = sum(1 for a in abertos if a["atrasado"])
    if atras:
        alertas.append(f"{atras} oportunidade(s) paradas há mais tempo que o normal da etapa")
    extra["alertas"] = alertas
    extra["carga_desde"] = (inicio_hist or primeiro).isoformat()
    for p in resumos.values():
        p.update(extra)
    return resumos, abertos
