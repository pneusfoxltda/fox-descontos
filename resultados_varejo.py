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
async def ler_553(hoje: date) -> dict:
    from playwright.async_api import async_playwright
    from sync_televendas import login
    from varejo_teste import gerar
    from varejo_filtros import LOJAS_VAREJO, TABELAS_VAREJO, FAMILIAS_VAREJO, FAMILIAS_PNEUS
    os.environ["FRETE"] = "1"   # "Frete compõe valores totais" (assim bate com o Analytics)
    ini, fim = hoje.replace(day=1).strftime("%d/%m/%Y"), hoje.strftime("%d/%m/%Y")
    res = {"mes": {"lojas": [], "vend": []}, "hoje": {"lojas": [], "vend": []}, "erros": []}
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        page = await (await b.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo",
                                          viewport={"width": 1400, "height": 2400})).new_page()
        await login(page)
        for periodo, di in (("mes", ini), ("hoje", fim)):
            for cod, loja in LOJAS_VAREJO.items():
                print(f"▶ {periodo} · {loja}")
                r = None
                for tentativa in ((1, 2) if periodo == "mes" else (1,)):
                    try:
                        r = await gerar(page, di, fim, TABELAS_VAREJO, FAMILIAS_VAREJO, [loja])
                        if "erro" not in r:
                            break
                    except Exception as e:
                        r = {"erro": type(e).__name__}
                    print(f"   ⚠️ tentativa {tentativa} sem relatório")
                if not r or "erro" in r:
                    if periodo == "hoje":   # sem venda hoje o Movere não monta o relatório: conta como zero
                        print("   sem relatório hoje: fica zerado")
                        res[periodo]["lojas"].append({"loja": loja, "cod": cod, "venda": 0.0, "clientes": 0, "itens": 0.0, "ticket": 0.0})
                    else:
                        res["erros"].append(f"{periodo} {loja}")
                    continue
                lj, vd = linha_loja(r, loja, cod), linhas_vendedores(r, loja)
                soma = round(sum(v["venda"] for v in vd), 2)
                ok = abs(soma - lj["venda"]) < 0.05
                print(f"   vendedores: {len(vd)} · soma dos vendedores = loja: {'sim' if ok else 'NÃO'}")
                if not ok:
                    res["erros"].append(f"{periodo} {loja}: soma dos vendedores diferente")
                res[periodo]["lojas"].append(lj)
                res[periodo]["vend"].extend(vd)
        # Coluna "Pneus" (mês): o mesmo relatório só com as famílias de pneu → pneus vendidos e em quantas vendas
        for cod, loja in LOJAS_VAREJO.items():
            print(f"▶ pneus · {loja}")
            r = None
            for tentativa in (1, 2):
                try:
                    r = await gerar(page, ini, fim, TABELAS_VAREJO, FAMILIAS_PNEUS, [loja])
                    if "erro" not in r:
                        break
                except Exception as e:
                    r = {"erro": type(e).__name__}
                print(f"   ⚠️ tentativa {tentativa} sem relatório")
            if not r or "erro" in r:
                res["erros"].append(f"pneus {loja}")
                continue
            juntar_pneus(res["mes"], loja, linha_loja(r, loja, cod), linhas_vendedores(r, loja))
            print("   pneus lidos")
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


def gravar(cli, chave, hoje: date, res: dict, conf: dict):
    H = cv._sb_headers(chave, {"Prefer": "resolution=merge-duplicates,return=minimal"})
    url = f"{cv.SUPABASE_URL}/rest/v1"
    mes, agora = hoje.replace(day=1).isoformat(), datetime.now(timezone.utc).isoformat()
    for periodo in ("mes", "hoje"):
        lojas = res[periodo]["lojas"]
        if not lojas:
            continue
        rows = [dict(l, mes=mes, periodo=periodo, dia=hoje.isoformat(), atualizado_em=agora) for l in lojas]
        _post(cli, f"{url}/varejo_lojas?on_conflict=mes,periodo,loja", H, rows)
        # vendedores: troca os da loja inteira (quem saiu da lista some)
        for l in lojas:
            cli.delete(f"{url}/varejo_vendedores?mes=eq.{mes}&periodo=eq.{periodo}&loja=eq.{l['loja']}",
                       headers=cv._sb_headers(chave)).raise_for_status()
        vend = [dict(v, mes=mes, periodo=periodo, dia=hoje.isoformat(), atualizado_em=agora) for v in res[periodo]["vend"]]
        if vend:
            _post(cli, f"{url}/varejo_vendedores?on_conflict=mes,periodo,loja,cod", H, vend)
    if conf:
        ontem = (hoje - timedelta(days=1)).isoformat()
        rows = [{"mes": mes, "loja": k, "ate": ontem, "atualizado_em": agora, **v} for k, v in conf.items()]
        cli.post(f"{url}/varejo_conferencia?on_conflict=mes,loja", headers=H, json=rows).raise_for_status()


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


def main() -> int:
    inicio = datetime.now(timezone.utc)
    hoje = datetime.now(TZ).date()
    chave = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    print(f"📊 Resultado Varejo · {hoje:%d/%m/%Y}{' · TESTE (não grava)' if DRY else ''}")
    res = asyncio.run(ler_553(hoje))
    conf, aviso = {}, ""
    if hoje.day > 1 and len(res["mes"]["lojas"]) == 8 and len(res["hoje"]["lojas"]) == 8:
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
    detalhes = {"lojas_mes": len(res["mes"]["lojas"]), "lojas_hoje": len(res["hoje"]["lojas"]),
                "vendedores_mes": len(res["mes"]["vend"]), "erros": res["erros"][:20],
                "lojas_com_diferenca": sum(1 for c in conf.values() if abs(c["diferenca"]) >= 0.05)}
    print("Resumo:", {k: v for k, v in detalhes.items() if k != "erros"}, "· erros:", len(res["erros"]))
    if DRY:
        if os.environ.get("MOSTRAR_TRANCADO"):   # conferência do TI: o resultado sai criptografado no registro público
            from varejo_teste import trancar
            b = trancar({"res": res, "conf": conf})
            for i in range(0, len(b), 900):
                print("TRANCADO:" + b[i:i + 900])
        print("TESTE: nada foi gravado.")
        return 0 if not res["erros"] else 1
    if not chave:
        print("❌ Falta o segredo SUPABASE_SERVICE_KEY")
        return 1
    try:
        with httpx.Client(timeout=60) as cli:
            gravar(cli, chave, hoje, res, conf)
        print("✅ Gravado no banco.")
    except httpx.HTTPStatusError as e:
        msg = f"Não gravou no banco ({e.response.status_code}). Rodou o SQL 26?"
        print("❌", msg)
        registrar(chave, False, msg, detalhes, inicio)
        return 1
    ok = not res["erros"]
    registrar(chave, ok, "; ".join(res["erros"])[:300] if res["erros"] else aviso, detalhes, inicio)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
