"""
resultados_varejo.py · Robô do "Resultado Varejo - Geral" (página /resultados)
=============================================================================
De hora em hora (acordado pelo sync-televendas, seg–sáb), gera a ROTINA 553 do Movere com os filtros do Varejo
(8 lojas, 13 tabelas de preço, 11 famílias, frete compõe os valores) LOJA POR LOJA, no mês e hoje, e grava no
Supabase: venda, clientes, itens e ticket por loja e por vendedor (a soma dos vendedores = a loja).

Conferência (a setinha vermelha da página): compara a 553 até ONTEM (mês menos hoje) com o relatório do Analytics
"Jonathan - Faturamento Varejo" (1111480) por loja, e explica a diferença: vendas e devoluções de segmento REVENDA
(o Analytics tira, a 553 não tem esse filtro), com o código do cliente, a nota, o dia e o vendedor.

O registro do GitHub é PÚBLICO: aqui só aparecem contagens. Nada de valor, nome ou código de cliente no registro.
Segredos: MOVERE_USER, MOVERE_PASS, ANALYTICS_LOGIN, ANALYTICS_SENHA, SUPABASE_SERVICE_KEY.
Rodar sem gravar: DRY_RUN=1.
"""
import asyncio, os, sys
from datetime import date, datetime, timedelta, timezone

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_vendas_movere as cv

ROBO = "resultados_varejo"
TZ = timezone(timedelta(hours=-4))          # Porto Velho
SEG_REVENDA = "REVENDA"
M_FAT = f"/gdc/md/{cv.PID}/obj/2160"
A_ESTAB, A_SEGMENTO, A_VENDEDOR = (f"/gdc/md/{cv.PID}/obj/{n}" for n in (1583, 1539, 1669))
A_COD_CLIENTE, A_NOTA = (f"/gdc/md/{cv.PID}/obj/{n}" for n in (1513, 1550))
REL_ANALYTICS = 1111480
DRY = bool(os.environ.get("DRY_RUN"))


# ── Contas (testadas em tests/test_resultados_varejo.py) ──────────────────────
def _n(x):
    try:
        return round(float(x or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def linha_loja(r: dict, loja: str, cod: int) -> dict:
    """Total da loja num relatório da 553 gerado só com ela."""
    e = next((x for x in r.get("estabelecimentos") or []), None)
    if e:
        return {"loja": loja, "cod": cod, "venda": _n(e["venda"]), "clientes": int(e["vendas"] or 0),
                "itens": _n(e["itens"]), "ticket": _n(e["ticket"])}
    t = r.get("totais") or {}
    venda = _n(t.get("Valor Venda Líquida (Venda - Devolução)"))
    cli = int(t.get("Quantidade Clientes Atendidos") or 0)
    return {"loja": loja, "cod": cod, "venda": venda, "clientes": cli,
            "itens": _n(t.get("Quantidade Itens Atendidos")), "ticket": round(venda / cli, 2) if cli else 0.0}


def linhas_vendedores(r: dict, loja: str) -> list:
    out = {}
    for v in r.get("vendedores") or []:
        cod = str(v["cod"]).strip()
        if cod in out:
            continue
        out[cod] = {"loja": loja, "cod": cod, "nome": " ".join(str(v["nome"]).split()).title(), "venda": _n(v["venda"]),
                    "clientes": int(v["vendas"] or 0), "itens": _n(v["itens"]), "ticket": _n(v["ticket"])}
    return list(out.values())


def juntar_pneus(mes: dict, loja: str, lj_pneus: dict, vd_pneus: list):
    """Põe nas linhas do mês a quantidade de pneus (itens) e em quantas vendas, da loja e de cada vendedor."""
    for l in mes["lojas"]:
        if l["loja"] == loja:
            l["pneus"], l["pneus_vendas"] = lj_pneus["itens"], lj_pneus["clientes"]
    pv = {v["cod"]: v for v in vd_pneus}
    for v in mes["vend"]:
        if v["loja"] == loja:
            x = pv.get(v["cod"])
            v["pneus"], v["pneus_vendas"] = (x["itens"], x["clientes"]) if x else (0.0, 0)


def iso_analytics(d: str) -> str:
    """'11/13/2026' (Analytics) → '2026-11-13'."""
    try:
        m, dd, a = d.split("/")
        return f"{a}-{int(m):02d}-{int(dd):02d}"
    except Exception:
        return d


def conferir(v553_ate_ontem: dict, analytics: dict, revenda: list) -> dict:
    """Por loja: diferença 553 − Analytics e os motivos (REVENDA + o que sobrar sem explicação)."""
    out = {}
    for loja in sorted(set(v553_ate_ontem) | set(analytics)):
        a, b = _n(v553_ate_ontem.get(loja)), _n(analytics.get(loja))
        dif = round(a - b, 2)
        motivos = []
        for x in (x for x in revenda if x["loja"] == loja):
            motivos.append({"motivo": "Venda de REVENDA" if x["valor"] >= 0 else "Devolução de REVENDA",
                            "explica": "O Analytics tira o segmento REVENDA; a rotina 553 não tem esse filtro.",
                            "cod_cliente": x["cod_cliente"], "vendedor": x["vendedor"], "dia": x["dia"],
                            "nota": x["nota"], "valor": x["valor"]})
        sobra = round(dif - sum(m["valor"] for m in motivos), 2)
        if abs(sobra) >= 0.05:
            motivos.append({"motivo": "Diferença sem explicação automática",
                            "explica": "Pode ser venda lançada, cancelada ou alterada depois que o Analytics atualizou "
                                       "(ele atualiza de madrugada), ou um filtro diferente. Conferir no Movere.",
                            "valor": sobra})
        out[loja] = {"v553": a, "analytics": b, "diferenca": dif, "motivos": motivos}
    return out


# ── Rotina 553 ────────────────────────────────────────────────────────────────
# Horários (decisão do TI, 25/11/2026): de dia (7h45, 10h45, 13h45, 15h45, 17h45) só o "hoje" das 8 lojas (rápido);
# às 19h o COMPLETO: mês + pneus + conferência com o Analytics. A página soma "mês (retrato das 19h) + hoje".
# Se o retrato do mês ficou velho (a rodada das 19h não aconteceu), a próxima rodada faz o completo.
HORA_COMPLETO = 18


def dia_util_anterior(d: date) -> date:
    d -= timedelta(days=1)
    return d - timedelta(days=1) if d.weekday() == 6 else d


def decidir_modo(hoje: date, hora: int, ultimo_mes) -> str:
    """'completo' (mês + pneus + conferência) ou 'hoje' (só o dia). ultimo_mes = dia do último retrato do mês."""
    m = os.environ.get("MODO", "").strip().lower()
    if m in ("completo", "hoje"):
        return m
    if hora >= HORA_COMPLETO or ultimo_mes is None or ultimo_mes < dia_util_anterior(hoje):
        return "completo"
    return "hoje"


def situacao(res: dict, modo: str, hora: int) -> tuple:
    """(ok, problemas). Amarelo no Monitor: ok com problemas (até 2). Vermelho: mais de 2 ou nada veio.
    'hoje' sem relatório só conta depois das 10h (antes disso a loja pode não ter vendido ainda)."""
    probs = list(res["erros"]) + ([f"hoje {l} (sem relatório)" for l in res["sem_hoje"]] if hora >= 10 else [])
    veio = len(res["hoje"]["lojas"]) + len(res["mes"]["lojas"])
    return (veio > 0 or (modo == "hoje" and hora < 10)) and len(probs) <= 2, probs


def separar_por_loja(r: dict, mapa: dict) -> dict:
    """Relatório da 553 com as 8 lojas juntas → {loja: (linha da loja, vendedores, bate)}.
    O total de cada loja vem do quadro "Resumo por Estabelecimento"; os vendedores vão para a loja do retrato do mês
    (mapa = {cod do vendedor: loja}). bate = a soma dos vendedores dá o total da loja (senão, a loja é lida sozinha)."""
    from varejo_filtros import LOJAS_VAREJO
    vend = linhas_vendedores(r, "")
    out = {}
    for e in r.get("estabelecimentos") or []:
        loja = LOJAS_VAREJO.get(str(e.get("cod")).strip())
        if not loja:
            continue
        lj = {"loja": loja, "cod": int(str(e["cod"]).strip()), "venda": _n(e["venda"]), "clientes": int(e["vendas"] or 0),
              "itens": _n(e["itens"]), "ticket": _n(e["ticket"])}
        vd = [dict(v, loja=loja) for v in vend if mapa.get(v["cod"]) == loja]
        bate = abs(round(sum(v["venda"] for v in vd), 2) - lj["venda"]) < 0.05 and abs(sum(v["itens"] for v in vd) - lj["itens"]) < 0.01
        out[loja] = (lj, vd, bate)
    return out


async def ler_553(hoje: date, modo: str = "completo", ao_ler=None, mapa=None) -> dict:
    """ao_ler(periodo, lj, vd) é chamado assim que cada loja chega (grava na hora).
    No modo "hoje", com o mapa dos vendedores (retrato do mês), lê as 8 lojas num relatório só (e os pneus em outro):
    ≈ 2 relatórios em vez de 16 (cada relatório leva ≈ 45 s só para marcar os filtros). Loja que não bate é lida sozinha."""
    from playwright.async_api import async_playwright
    from sync_televendas import login
    from varejo_teste import gerar
    from varejo_filtros import LOJAS_VAREJO, TABELAS_VAREJO, FAMILIAS_VAREJO, FAMILIAS_PNEUS
    os.environ["FRETE"] = "1"   # "Frete compõe valores totais" (assim bate com o Analytics)
    ini, fim = hoje.replace(day=1).strftime("%d/%m/%Y"), hoje.strftime("%d/%m/%Y")
    res = {"mes": {"lojas": [], "vend": []}, "hoje": {"lojas": [], "vend": []}, "erros": [], "sem_hoje": [], "repescados": 0}
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        page = await (await b.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo",
                                          viewport={"width": 1400, "height": 2400})).new_page()
        await login(page)

        async def tentar(pg, di, familias, loja, tentativas):
            r = None
            for t in tentativas:
                if t > 1:
                    await pg.wait_for_timeout(20000)   # dá um respiro ao Movere antes de pedir de novo
                try:
                    r = await gerar(pg, di, fim, TABELAS_VAREJO, familias, [loja], espera_max=60 if di == fim else 120)
                    if "erro" not in r:
                        return r
                except Exception as e:
                    r = {"erro": type(e).__name__}
                print(f"   ⚠️ tentativa {t} sem relatório")
            return r

        def aplicar(tipo, cod, loja, r):
            """Guarda o relatório lido. Devolve False se ele não veio."""
            if not r or "erro" in r:
                return False
            if tipo == "pneus":
                juntar_pneus(res["mes"], loja, linha_loja(r, loja, cod), linhas_vendedores(r, loja))
                print("   pneus lidos")
                return True
            if tipo == "pneus_hoje":
                # pneus vendidos HOJE (TI, 27/11/2026: os pneus sobem durante o dia): grava a linha do "hoje" de novo, com eles
                lj = next((l for l in res["hoje"]["lojas"] if l["loja"] == loja), None)
                if lj is None:
                    return True          # sem o "hoje" da loja não há onde pôr (a página fica com o mês até ontem)
                juntar_pneus(res["hoje"], loja, linha_loja(r, loja, cod), linhas_vendedores(r, loja))
                print("   pneus de hoje lidos")
                if ao_ler:
                    ao_ler("hoje", lj, [v for v in res["hoje"]["vend"] if v["loja"] == loja])
                return True
            lj, vd = linha_loja(r, loja, cod), linhas_vendedores(r, loja)
            if tipo == "hoje":           # pneus de hoje chegam no relatório seguinte; até lá, vazio (nunca o número de outro dia)
                lj["pneus"] = lj["pneus_vendas"] = None
                for v in vd:
                    v["pneus"] = v["pneus_vendas"] = None
            soma = round(sum(v["venda"] for v in vd), 2)
            ok = abs(soma - lj["venda"]) < 0.05
            print(f"   vendedores: {len(vd)} · soma dos vendedores = loja: {'sim' if ok else 'NÃO'}")
            if not ok:
                res["erros"].append(f"{tipo} {loja}: soma dos vendedores diferente")
            res[tipo]["lojas"].append(lj)
            res[tipo]["vend"].extend(vd)
            if ao_ler:
                ao_ler(tipo, lj, vd)
            return True

        # 1ª volta: mês e hoje de cada loja, depois os pneus do mês. No modo "hoje": o dia e os pneus do dia, loja por loja.
        if modo == "completo":
            pedidos = [(p, cod, loja) for p in ("mes", "hoje", "pneus") for cod, loja in LOJAS_VAREJO.items()]
        else:
            pedidos = [(p, cod, loja) for cod, loja in LOJAS_VAREJO.items() for p in ("hoje", "pneus_hoje")]
            if mapa:
                # Rápido (TI, 28/11/2026): as 8 lojas juntas num relatório; só as que não baterem vão loja por loja
                faltam = []
                for tipo, fam in (("hoje", FAMILIAS_VAREJO), ("pneus_hoje", FAMILIAS_PNEUS)):
                    print(f"▶ {tipo} · 8 lojas juntas")
                    try:
                        r = await gerar(page, fim, fim, TABELAS_VAREJO, fam, list(LOJAS_VAREJO.values()), espera_max=90)
                    except Exception as e:
                        r = {"erro": type(e).__name__}
                    sep = separar_por_loja(r, mapa) if r and "erro" not in r else {}
                    for cod, loja in LOJAS_VAREJO.items():
                        x = sep.get(loja)
                        if not x or not x[2]:
                            faltam.append((tipo, cod, loja))
                            continue
                        lj, vd, _ = x
                        if tipo == "hoje":
                            for o in [lj] + vd:
                                o["pneus"] = o["pneus_vendas"] = None
                            res["hoje"]["lojas"].append(lj); res["hoje"]["vend"].extend(vd)
                            if ao_ler:
                                ao_ler("hoje", lj, vd)
                        else:
                            if not any(l["loja"] == loja for l in res["hoje"]["lojas"]):
                                faltam.append((tipo, cod, loja))
                                continue
                            juntar_pneus(res["hoje"], loja, lj, vd)
                            if ao_ler:
                                ao_ler("hoje", next(l for l in res["hoje"]["lojas"] if l["loja"] == loja),
                                       [v for v in res["hoje"]["vend"] if v["loja"] == loja])
                    print(f"   juntas: {sum(1 for x in sep.values() if x[2])} de 8 lojas batendo")
                res["juntas"] = 16 - len(faltam)
                pedidos = faltam
        di_de = {"mes": ini, "hoje": fim, "pneus": ini, "pneus_hoje": fim}
        fam_de = {"mes": FAMILIAS_VAREJO, "hoje": FAMILIAS_VAREJO, "pneus": FAMILIAS_PNEUS, "pneus_hoje": FAMILIAS_PNEUS}
        falhou = []
        for tipo, cod, loja in pedidos:
            print(f"▶ {tipo} · {loja}")
            r = await tentar(page, di_de[tipo], fam_de[tipo], loja, (1, 2) if tipo not in ("hoje", "pneus_hoje") else (1,))
            if not aplicar(tipo, cod, loja, r):
                falhou.append((tipo, cod, loja))

        # 2ª volta: só o que falhou, entrando no Movere de novo do zero (ele às vezes engasga por alguns minutos)
        if falhou:
            print(f"🔁 2ª volta para {len(falhou)} relatório(s): {', '.join(f'{t} {l}' for t, _, l in falhou)}")
            await page.context.close()
            await asyncio.sleep(60)
            page = await (await b.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo",
                                              viewport={"width": 1400, "height": 2400})).new_page()
            await login(page)
            for tipo, cod, loja in falhou:
                print(f"▶ {tipo} · {loja} (2ª volta)")
                r = await tentar(page, di_de[tipo], fam_de[tipo], loja, (1,) if tipo in ("hoje", "pneus_hoje") else (1, 2))
                if aplicar(tipo, cod, loja, r):
                    res["repescados"] += 1
                    continue
                if tipo == "pneus_hoje":   # sem pneu vendido hoje o Movere não monta o relatório: a página fica com o mês até ontem
                    print("   sem pneus de hoje")
                    continue
                if tipo == "hoje":   # sem venda hoje o Movere não monta o relatório; ou ele falhou: NÃO grava zero, fica o último número
                    print("   sem relatório hoje: fica o último número")
                    res["sem_hoje"].append(loja)
                else:
                    res["erros"].append(f"{tipo} {loja}")
        await b.close()
    return res


# ── Analytics (conferência até ontem) ─────────────────────────────────────────
def ler_analytics(hoje: date) -> tuple:
    from analytics_varejo_diag import executar, df, q
    ontem = hoje - timedelta(days=1)
    with httpx.Client(timeout=180) as cli:
        tt = cv.login_analytics(cli, os.environ["ANALYTICS_LOGIN"], os.environ["ANALYTICS_SENHA"])
        rep = q(cli, tt, f"/gdc/md/{cv.PID}/obj/{REL_ANALYTICS}")["report"]
        base = q(cli, tt, rep["content"]["definitions"][-1])["reportDefinition"]["content"]
        dias = [cv.elemento_dia(cli, tt, hoje.replace(day=1) + timedelta(days=i)) for i in range(ontem.day)]
        dias = [u for u in dias if u]
        if not dias:
            return {}, []
        fdia = f"[/gdc/md/{cv.PID}/obj/{cv.ATTR_DIA}] IN ({', '.join('[' + u + ']' for u in dias)})"
        E = df(cli, tt, A_ESTAB)
        por_loja = executar(cli, tt, base, [E], [M_FAT], (), (fdia,))
        if not isinstance(por_loja, list):
            raise RuntimeError(f"Analytics por loja: {por_loja}")
        analytics = {l[0]: _n(l[1]) for l in por_loja[1:] if len(l) >= 2}
        linhas = [E, df(cli, tt, A_VENDEDOR), df(cli, tt, A_SEGMENTO), df(cli, tt, f"/gdc/md/{cv.PID}/obj/{cv.ATTR_DIA}"),
                  df(cli, tt, A_COD_CLIENTE), df(cli, tt, A_NOTA)]
        rv = executar(cli, tt, base, linhas, [M_FAT], ("obj/1539]",), (fdia,))   # sem o filtro de segmento
        revenda = []
        if isinstance(rv, list):
            for l in rv[1:]:
                if len(l) >= 7 and str(l[2]).upper() == SEG_REVENDA and _n(l[6]):
                    revenda.append({"loja": l[0], "vendedor": " ".join(l[1].split()).title(), "dia": iso_analytics(l[3]),
                                    "cod_cliente": l[4], "nota": l[5], "valor": _n(l[6])})
    return analytics, revenda


# ── Supabase ──────────────────────────────────────────────────────────────────
def _post(cli, url, headers, rows):
    """Grava; se o SQL 27 (colunas de pneus) ainda não rodou, grava sem os pneus."""
    chaves = {k for x in rows for k in x}               # o banco exige as mesmas colunas em todas as linhas
    rows = [{k: x.get(k) for k in chaves} for x in rows]
    r = cli.post(url, headers=headers, json=rows)
    if r.status_code == 400 and "pneus" in r.text:
        print("⚠️ Falta rodar o SQL 27 (pneus): gravando sem a coluna Pneus")
        r = cli.post(url, headers=headers, json=[{k: v for k, v in x.items() if not k.startswith("pneus")} for x in rows])
    r.raise_for_status()


def gravar_loja(cli, chave, hoje: date, periodo: str, lj: dict, vd: list):
    """Grava UMA loja (e os vendedores dela) num período: chamado assim que a loja chega."""
    H = cv._sb_headers(chave, {"Prefer": "resolution=merge-duplicates,return=minimal"})
    url = f"{cv.SUPABASE_URL}/rest/v1"
    mes, agora = hoje.replace(day=1).isoformat(), datetime.now(timezone.utc).isoformat()
    _post(cli, f"{url}/varejo_lojas?on_conflict=mes,periodo,loja", H, [dict(lj, mes=mes, periodo=periodo, dia=hoje.isoformat(), atualizado_em=agora)])
    # vendedores: troca os da loja inteira (quem saiu da lista some)
    cli.delete(f"{url}/varejo_vendedores?mes=eq.{mes}&periodo=eq.{periodo}&loja=eq.{lj['loja']}",
               headers=cv._sb_headers(chave)).raise_for_status()
    if vd:
        _post(cli, f"{url}/varejo_vendedores?on_conflict=mes,periodo,loja,cod", H,
              [dict(v, mes=mes, periodo=periodo, dia=hoje.isoformat(), atualizado_em=agora) for v in vd])


def gravar(cli, chave, hoje: date, res: dict, conf: dict):
    """No completo: grava de novo as lojas do mês já com os pneus, e a conferência com o Analytics."""
    for l in res["mes"]["lojas"]:
        gravar_loja(cli, chave, hoje, "mes", l, [v for v in res["mes"]["vend"] if v["loja"] == l["loja"]])
    if conf:
        H = cv._sb_headers(chave, {"Prefer": "resolution=merge-duplicates,return=minimal"})
        mes, agora = hoje.replace(day=1).isoformat(), datetime.now(timezone.utc).isoformat()
        ontem = (hoje - timedelta(days=1)).isoformat()
        rows = [{"mes": mes, "loja": k, "ate": ontem, "atualizado_em": agora, **v} for k, v in conf.items()]
        cli.post(f"{cv.SUPABASE_URL}/rest/v1/varejo_conferencia?on_conflict=mes,loja", headers=H, json=rows).raise_for_status()


def registrar(chave, ok: bool, msg: str, detalhes: dict, inicio: datetime):
    if not chave or DRY:
        return
    corpo = {"robo": ROBO, "ok": ok, "teste": False, "inicio": inicio.isoformat(),
             "fim": datetime.now(timezone.utc).isoformat(), "mensagem": (msg or "")[:300] or None, "detalhes": detalhes}
    try:
        with httpx.Client(timeout=20) as cli:
            r = cli.post(f"{cv.SUPABASE_URL}/rest/v1/robo_execucoes", headers=cv._sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo)
            if r.status_code == 400:
                corpo.pop("detalhes")
                cli.post(f"{cv.SUPABASE_URL}/rest/v1/robo_execucoes", headers=cv._sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo)
    except Exception as e:
        print(f"⚠️ Não consegui registrar a rodada: {type(e).__name__}")


def mapa_vendedores(chave, hoje: date) -> dict:
    """{cod do vendedor: loja} pelo retrato do mês (só quem aparece em UMA loja). Sem banco: {} (lê loja por loja)."""
    if not chave:
        return {}
    try:
        with httpx.Client(timeout=30) as cli:
            r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/varejo_vendedores?select=cod,loja&mes=eq.{hoje.replace(day=1).isoformat()}"
                        f"&periodo=eq.mes", headers=cv._sb_headers(chave))
            r.raise_for_status()
            lojas = {}
            for x in r.json():
                lojas.setdefault(str(x["cod"]).strip(), set()).add(x["loja"])
            return {c: next(iter(l)) for c, l in lojas.items() if len(l) == 1}
    except Exception as e:
        print(f"⚠️ Sem o mapa dos vendedores ({type(e).__name__}): lê loja por loja")
        return {}


def ultimo_retrato_mes(chave, hoje: date):
    """Dia do último retrato do mês (rodada completa) no banco, ou None."""
    if not chave:
        return None
    try:
        with httpx.Client(timeout=30) as cli:
            r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/varejo_lojas?select=dia&mes=eq.{hoje.replace(day=1).isoformat()}"
                        f"&periodo=eq.mes&order=dia.asc&limit=1", headers=cv._sb_headers(chave))
            r.raise_for_status()
            x = r.json()
            return date.fromisoformat(x[0]["dia"]) if x else None
    except Exception as e:
        print(f"⚠️ Não li o último retrato do mês ({type(e).__name__}): faço o completo")
        return None


def main() -> int:
    inicio = datetime.now(timezone.utc)
    agora = datetime.now(TZ)
    hoje = agora.date()
    chave = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    ultimo = ultimo_retrato_mes(chave, hoje)
    modo = decidir_modo(hoje, agora.hour, ultimo)
    print(f"📊 Resultado Varejo · {hoje:%d/%m/%Y} · modo {modo.upper()}"
          f" (retrato do mês: {ultimo.strftime('%d/%m') if ultimo else 'nenhum'}){' · TESTE (não grava)' if DRY else ''}")
    if not DRY and not chave:
        print("❌ Falta o segredo SUPABASE_SERVICE_KEY")
        return 1
    cli = None if DRY else httpx.Client(timeout=60)
    falhas_gravar = []

    def ao_ler(periodo, lj, vd):
        if cli is None:
            return
        try:
            gravar_loja(cli, chave, hoje, periodo, lj, vd)
        except httpx.HTTPStatusError as e:
            falhas_gravar.append(f"{periodo} {lj['loja']} ({e.response.status_code})")

    conf, aviso = {}, ""
    try:
        res = asyncio.run(ler_553(hoje, modo, ao_ler, mapa_vendedores(chave, hoje) if modo == "hoje" else None))
        if modo == "completo" and hoje.day > 1 and len(res["mes"]["lojas"]) == 8 and len(res["hoje"]["lojas"]) == 8:
            try:
                analytics, revenda = ler_analytics(hoje)
                hj = {l["loja"]: l["venda"] for l in res["hoje"]["lojas"]}
                ate_ontem = {l["loja"]: round(l["venda"] - hj.get(l["loja"], 0), 2) for l in res["mes"]["lojas"]}
                conf = conferir(ate_ontem, analytics, revenda) if analytics else {}
                print(f"🔎 Conferência com o Analytics: {sum(1 for c in conf.values() if abs(c['diferenca']) >= 0.05)} loja(s) com diferença"
                      f" · {len(revenda)} lançamento(s) de REVENDA")
            except Exception as e:
                aviso = f"conferência com o Analytics não rodou ({type(e).__name__})"
                print("⚠️", aviso)
        if cli is not None and modo == "completo" and res["mes"]["lojas"]:
            try:
                gravar(cli, chave, hoje, res, conf)   # o mês de novo, agora com os pneus, e a conferência
            except httpx.HTTPStatusError as e:
                falhas_gravar.append(f"mês com pneus ({e.response.status_code})")
    finally:
        if cli is not None:
            cli.close()
    ok, probs = situacao(res, modo, agora.hour)
    if falhas_gravar:
        ok, probs = False, probs + ["não gravou: " + ", ".join(falhas_gravar) + " (rodou o SQL 26?)"]
    detalhes = {"modo": modo, "lojas_mes": len(res["mes"]["lojas"]), "lojas_hoje": len(res["hoje"]["lojas"]),
                "vendedores_mes": len(res["mes"]["vend"]), "repescados": res["repescados"], "sem_hoje": res["sem_hoje"],
                "juntas": res.get("juntas"),
                "erros": probs[:20], "lojas_com_diferenca": sum(1 for c in conf.values() if abs(c["diferenca"]) >= 0.05)}
    print("Resumo:", {k: v for k, v in detalhes.items() if k not in ("erros", "sem_hoje")},
          f"· sem relatório hoje: {len(res['sem_hoje'])} · problemas: {len(probs)}")
    if DRY:
        if os.environ.get("MOSTRAR_TRANCADO"):   # conferência do TI: o resultado sai criptografado no registro público
            from varejo_teste import trancar
            b = trancar({"res": res, "conf": conf})
            for i in range(0, len(b), 900):
                print("TRANCADO:" + b[i:i + 900])
        print("TESTE: nada foi gravado.")
        return 0 if ok else 1
    print("✅ Gravado no banco (loja por loja)." if ok else "⚠️ Rodada com problemas: " + "; ".join(probs)[:300])
    registrar(chave, ok, "; ".join(probs)[:300] if probs else aviso, detalhes, inicio)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
