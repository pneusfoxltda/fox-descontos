"""
resultados_atacado.py · Robô do "Resultado Atacado" (página /atacado, no modelo do painel do Televendas)
======================================================================================================
De hora em hora (seg–sáb), gera a ROTINA 553 do Movere com a Tabela de Preço 2 ATACADO + 5 ATACADO PREMIUM,
todas as lojas, todas as famílias, frete compondo os valores (igual ao relatório que o TI usa), e grava no Supabase:
  · o MÊS até hoje, por vendedor e por loja (venda, clientes, itens) + os PNEUS do mês (famílias de pneu);
  · cada um dos ÚLTIMOS 5 DIAS ÚTEIS (seg–sáb, menos feriados), por vendedor e por loja: as colunas do painel
    (passando o mouse no valor do dia aparecem os clientes e os itens).
Hoje e o dia útil anterior são sempre refeitos; os outros dias só se ainda não estiverem no banco.
Nos 3 primeiros dias do mês também fecha o mês anterior.
O registro do GitHub é PÚBLICO: aqui só aparecem contagens (nada de valor nem de cliente).
Segredos: MOVERE_USER, MOVERE_PASS, SUPABASE_SERVICE_KEY. Rodar sem gravar: DRY_RUN=1.
"""
import asyncio, os, sys
from datetime import date, datetime, timedelta, timezone

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_vendas_movere as cv
from resultados_varejo import _n, _post, linhas_vendedores

ROBO = "resultados_atacado"
TZ = timezone(timedelta(hours=-4))
DRY = bool(os.environ.get("DRY_RUN"))
TOTAL = "TOTAL"     # linha com o total do setor em atacado_lojas (também marca que o dia já foi lido)


# ── Contas (testadas em tests/test_resultados_atacado.py) ─────────────────────
def dias_uteis(ate: date, feriados: set, n: int = 5) -> list:
    """Os n últimos dias úteis (seg–sáb, sem feriados) até 'ate' (inclusive), do mais antigo para o mais novo."""
    out, d = [], ate
    while len(out) < n:
        if d.weekday() != 6 and d not in feriados:
            out.append(d)
        d -= timedelta(days=1)
    return sorted(out)


def lojas_e_total(r: dict) -> tuple:
    """Linhas por loja e a linha TOTAL de um relatório da 553."""
    lojas = [{"loja": " ".join(str(e["nome"]).split()), "cod": int(e["cod"]) if str(e["cod"]).lstrip("-").isdigit() else None,
              "venda": _n(e["venda"]), "clientes": int(e["vendas"] or 0), "itens": _n(e["itens"])} for e in r.get("estabelecimentos") or []]
    t = r.get("totais") or {}
    venda = _n(t.get("Valor Venda Líquida (Venda - Devolução)")) if t.get("Valor Venda Líquida (Venda - Devolução)") is not None \
        else round(sum(l["venda"] for l in lojas), 2)
    cli = int(t.get("Quantidade Clientes Atendidos") or 0) or sum(l["clientes"] for l in lojas)
    total = {"loja": TOTAL, "cod": None, "venda": venda, "clientes": cli, "itens": round(sum(l["itens"] for l in lojas), 2)}
    return lojas, total


def vendedores(r: dict) -> list:
    return [{k: v[k] for k in ("cod", "nome", "venda", "clientes", "itens")} for v in linhas_vendedores(r, "")]


def juntar_pneus(linhas: list, pneus: list, chave: str):
    """Põe nas linhas (do mês) os pneus vendidos e em quantas vendas; quem não vendeu pneu fica com 0."""
    p = {x[chave]: x for x in pneus}
    for l in linhas:
        x = p.get(l[chave])
        l["pneus"], l["pneus_vendas"] = (x["itens"], x["clientes"]) if x else (0.0, 0)


def dias_a_ler(ultimos: list, hoje: date, ja_lidos: set) -> list:
    """Hoje e o dia útil anterior sempre; os outros só se ainda não estão no banco."""
    sempre = set(ultimos[-2:]) | {hoje}
    return [d for d in ultimos if d in sempre or d not in ja_lidos]


# ── Rotina 553 ────────────────────────────────────────────────────────────────
async def gerar_553(page, ini: date, fim: date, familias: list, tentativas=(1, 2)):
    from varejo_teste import gerar
    from varejo_filtros import TABELAS_ATACADO
    r = None
    for t in tentativas:
        try:
            r = await gerar(page, ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"), TABELAS_ATACADO, familias, [])
            if "erro" not in r:
                return r
        except Exception as e:
            r = {"erro": type(e).__name__}
        print(f"   ⚠️ tentativa {t} sem relatório")
    return r


async def ler(hoje: date, dias: list, meses: list, ao_ler=None) -> dict:
    """Lê os meses (com pneus) e os dias. ao_ler(tipo, chave, dados) grava cada um assim que chega.
    Quem falhar volta para uma REPESCAGEM no fim, depois de entrar de novo no Movere. Dia que não veio NÃO
    vira zero: fica o último número (e o dia passado continua "não lido", a próxima rodada tenta de novo)."""
    from playwright.async_api import async_playwright
    from sync_televendas import login
    from varejo_filtros import FAMILIAS_PNEUS_ATACADO
    os.environ["FRETE"] = "1"   # "Frete compõe valores totais: Sim" (igual ao relatório do TI)
    out = {"meses": {}, "dias": {}, "erros": [], "sem_dia": [], "repescados": 0}
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        page = await (await b.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo", viewport={"width": 1400, "height": 2400})).new_page()
        await login(page)

        async def um_mes(ini, fim):
            print(f"▶ mês {ini:%m/%Y} até {fim:%d/%m}")
            r = await gerar_553(page, ini, fim, [])
            if "erro" in r:
                return False
            lojas, total = lojas_e_total(r)
            vend = vendedores(r)
            print(f"   lojas: {len(lojas)} · vendedores: {len(vend)} · soma dos vendedores = total: "
                  f"{'sim' if abs(sum(v['venda'] for v in vend) - total['venda']) < 0.05 else 'NÃO'}")
            print(f"▶ pneus do mês {ini:%m/%Y}")
            rp = await gerar_553(page, ini, fim, FAMILIAS_PNEUS_ATACADO)
            if "erro" in rp:   # sem venda de pneu também cai aqui: fica zerado
                rp = {}
            lp, tp = lojas_e_total(rp) if rp else ([], {"itens": 0.0, "clientes": 0})
            juntar_pneus(lojas, lp, "loja")
            juntar_pneus(vend, vendedores(rp) if rp else [], "cod")
            total["pneus"], total["pneus_vendas"] = tp["itens"], tp["clientes"]
            out["meses"][ini] = {"fim": fim, "lojas": lojas + [total], "vend": vend}
            if ao_ler:
                ao_ler("mes", ini, out["meses"][ini])
            return True

        async def um_dia(d):
            print(f"▶ dia {d:%d/%m}")
            r = await gerar_553(page, d, d, [])
            if "erro" in r:
                return False
            lojas, total = lojas_e_total(r)
            out["dias"][d] = {"lojas": lojas + [total], "vend": vendedores(r)}
            print(f"   lojas: {len(lojas)} · vendedores: {len(out['dias'][d]['vend'])}")
            if ao_ler:
                ao_ler("dia", d, out["dias"][d])
            return True

        falhas = []
        for ini, fim in meses:
            if not await um_mes(ini, fim):
                falhas.append(("mes", (ini, fim)))
        for d in dias:
            if not await um_dia(d):
                falhas.append(("dia", d))
        if falhas:
            print(f"🔁 Repescagem: {len(falhas)} relatório(s) que não vieram, entrando de novo no Movere")
            try:
                await login(page)
            except Exception as e:
                print(f"   ⚠️ não entrei de novo ({type(e).__name__}): sigo com a mesma sessão")
            ainda = []
            for tipo, x in falhas:
                if await (um_mes(*x) if tipo == "mes" else um_dia(x)):
                    out["repescados"] += 1
                else:
                    ainda.append((tipo, x))
            falhas = ainda
        for tipo, x in falhas:
            if tipo == "mes":
                out["erros"].append(f"mês {x[0]:%m/%Y}")
            else:   # sem venda no dia o Movere não monta o relatório; ou o Movere falhou: não grava zero
                out["sem_dia"].append(x.isoformat())
        await b.close()
    return out


# ── Supabase ──────────────────────────────────────────────────────────────────
def sb_get(cli, chave, caminho):
    r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/{caminho}", headers=cv._sb_headers(chave))
    r.raise_for_status()
    return r.json()


def gravar_um(cli, chave, tipo: str, k, x: dict):
    """Grava um mês (tipo 'mes', k = 1º dia) ou um dia (tipo 'dia', k = o dia), trocando o que havia."""
    H = cv._sb_headers(chave, {"Prefer": "resolution=merge-duplicates,return=minimal"})
    url, agora = f"{cv.SUPABASE_URL}/rest/v1", datetime.now(timezone.utc).isoformat()
    mes, dia = (k.isoformat(), x["fim"].isoformat()) if tipo == "mes" else (k.replace(day=1).isoformat(), k.isoformat())
    filtro = f"mes=eq.{mes}&periodo=eq.{tipo}" + (f"&dia=eq.{dia}" if tipo == "dia" else "")
    for t in ("atacado_lojas", "atacado_vendedores"):
        cli.delete(f"{url}/{t}?{filtro}", headers=cv._sb_headers(chave)).raise_for_status()
    base = {"mes": mes, "periodo": tipo, "dia": dia, "atualizado_em": agora}
    _post(cli, f"{url}/atacado_lojas?on_conflict=mes,periodo,dia,loja", H, [dict(l, **base) for l in x["lojas"]])
    if x["vend"]:
        _post(cli, f"{url}/atacado_vendedores?on_conflict=mes,periodo,dia,cod", H, [dict(v, **base) for v in x["vend"]])


def gravar(cli, chave, res: dict):
    for ini, m in res["meses"].items():
        gravar_um(cli, chave, "mes", ini, m)
    for d, x in res["dias"].items():
        gravar_um(cli, chave, "dia", d, x)


def decidir_modo(hoje: date, hora: int, ultimo_mes, feriados=frozenset()) -> str:
    """'completo' (mês + pneus + dias) às 19h ou se o retrato do mês ficou velho; de dia, 'dias' (só os dias)."""
    m = os.environ.get("MODO", "").strip().lower()
    if m in ("completo", "dias", "hoje"):
        return "dias" if m == "hoje" else m
    anterior = dias_uteis(hoje - timedelta(days=1), set(feriados), 1)[0]
    if hora >= 18 or ultimo_mes is None or ultimo_mes < anterior:
        return "completo"
    return "dias"


def registrar(chave, ok, msg, detalhes, inicio):
    if not chave or DRY:
        return
    corpo = {"robo": ROBO, "ok": ok, "teste": False, "inicio": inicio.isoformat(), "fim": datetime.now(timezone.utc).isoformat(),
             "mensagem": (msg or "")[:300] or None, "detalhes": detalhes}
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
    agora = datetime.now(TZ)
    hoje = agora.date()
    chave = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    feriados, ja_lidos, ultimo = set(), set(), None
    if chave:
        try:
            with httpx.Client(timeout=30) as cli:
                ini_busca = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
                for x in sb_get(cli, chave, f"atacado_metas?select=mes,chave&chave=like.feriado_*&mes=gte.{ini_busca}"):
                    feriados.add(date.fromisoformat(x["mes"]).replace(day=int(x["chave"][8:])))
                for x in sb_get(cli, chave, f"atacado_lojas?select=dia&periodo=eq.dia&loja=eq.{TOTAL}&dia=gte.{(hoje - timedelta(days=15)).isoformat()}"):
                    ja_lidos.add(date.fromisoformat(x["dia"]))
                um = sb_get(cli, chave, f"atacado_lojas?select=dia&periodo=eq.mes&loja=eq.{TOTAL}&mes=eq.{hoje.replace(day=1).isoformat()}")
                ultimo = date.fromisoformat(um[0]["dia"]) if um else None
        except httpx.HTTPStatusError as e:
            print(f"⚠️ Não li feriados/dias já lidos ({e.response.status_code}). Rodou o SQL 30?")
    modo = decidir_modo(hoje, agora.hour, ultimo, feriados)
    ultimos = dias_uteis(hoje, feriados)
    dias = dias_a_ler(ultimos, hoje, ja_lidos)
    meses = []
    if modo == "completo":
        meses = [(hoje.replace(day=1), hoje)]
        if hoje.day <= 3:   # fecha o mês anterior com o último dia
            fim_ant = hoje.replace(day=1) - timedelta(days=1)
            meses.append((fim_ant.replace(day=1), fim_ant))
    print(f"📦 Resultado Atacado · {hoje:%d/%m/%Y} · modo {modo.upper()} (retrato do mês: {ultimo.strftime('%d/%m') if ultimo else 'nenhum'})"
          f"{' · TESTE (não grava)' if DRY else ''}")
    print(f"Dias úteis no painel: {[d.strftime('%d/%m') for d in ultimos]} · a ler: {[d.strftime('%d/%m') for d in dias]}")
    if not DRY and not chave:
        print("❌ Falta o segredo SUPABASE_SERVICE_KEY")
        return 1
    cli = None if DRY else httpx.Client(timeout=60)
    falhas_gravar = []

    def ao_ler(tipo, k, x):
        if cli is None:
            return
        try:
            gravar_um(cli, chave, tipo, k, x)
        except httpx.HTTPStatusError as e:
            falhas_gravar.append(f"{tipo} {k} ({e.response.status_code})")

    try:
        res = asyncio.run(ler(hoje, dias, meses, ao_ler))
    finally:
        if cli is not None:
            cli.close()
    # 'hoje' sem relatório antes das 10h é normal (ainda sem venda); dia passado sem relatório é problema
    sem = [d for d in res["sem_dia"] if d != hoje.isoformat() or agora.hour >= 10]
    probs = res["erros"] + [f"dia {d[8:10]}/{d[5:7]} sem relatório" for d in sem] + (
        ["não gravou: " + ", ".join(falhas_gravar) + " (rodou o SQL 30?)"] if falhas_gravar else [])
    veio = len(res["meses"]) + len(res["dias"])
    ok = not falhas_gravar and not res["erros"] and len(probs) <= 2 and (veio > 0 or not (meses or dias))
    detalhes = {"modo": modo, "meses": len(res["meses"]), "dias": len(res["dias"]), "repescados": res["repescados"],
                "erros": probs[:20], "vendedores_mes": sum(len(m["vend"]) for m in res["meses"].values())}
    print("Resumo:", {k: v for k, v in detalhes.items() if k != "erros"}, "· problemas:", len(probs))
    if DRY:
        if os.environ.get("MOSTRAR_TRANCADO"):
            from varejo_teste import trancar
            b = trancar({"meses": {k.isoformat(): dict(v, fim=v["fim"].isoformat()) for k, v in res["meses"].items()},
                         "dias": {k.isoformat(): v for k, v in res["dias"].items()}})
            for i in range(0, len(b), 900):
                print("TRANCADO:" + b[i:i + 900])
        print("TESTE: nada foi gravado.")
        return 0 if ok else 1
    print("✅ Gravado no banco (cada mês e dia assim que chegou)." if ok else "⚠️ Rodada com problemas: " + "; ".join(probs)[:300])
    registrar(chave, ok, "; ".join(probs)[:300], detalhes, inicio)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
