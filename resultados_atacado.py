"""
resultados_atacado.py · Robô do "Resultado Atacado" (página /atacado, no modelo do painel do Televendas)
======================================================================================================
Duas vezes por dia (seg–sáb, 8h e 17h30 de Porto Velho), gera a ROTINA 553 do Movere com a Tabela de Preço 2 ATACADO + 5 ATACADO PREMIUM,
todas as lojas, todas as famílias, frete compondo os valores (igual ao relatório que o TI usa), e grava no Supabase:
  · o MÊS até hoje, por vendedor (venda, clientes, itens) + os PNEUS do mês (famílias de pneu);
  · cada um dos ÚLTIMOS 5 DIAS ÚTEIS (seg–sáb, menos feriados), por vendedor: as colunas do painel
    (passando o mouse no valor do dia aparecem os clientes e os itens).
Só a EQUIPE DO ATACADO (EQUIPE_ATACADO, 7 funcionários) entra; o TOTAL SETOR é a soma dela e não há mais
"por loja" (o Movere soma todos os vendedores na loja). Decisão do TI, 26/11/2026.
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


# Equipe do Atacado (decisão do TI, 26/11/2026): só estes funcionários entram na página e no TOTAL SETOR.
EQUIPE_ATACADO = {   # nome no Movere → nome curto na página (decisão do TI: primeiro nome, ou nome + sobrenome)
    "RAFAELA FERNANDES DA SILVA": "RAFAELA",
    "NIORRANA CARRIÇO GHISLERI": "NIORRANA",
    "CAMILA DA SILVA FEITOZA": "CAMILA SILVA",
    "ALYSSANDRA SALES MARINHO": "ALYSSANDRA",
    "CAMILA RAMOS BRILHANTE": "CAMILA RAMOS",
    "NAYZA MINELLI PEREIRA OLIVEIRA": "NAYZA",
    "KLEBER CAZUZA SILVA": "KLEBER",
}


def _nome(s) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())


def apelido(nome: str):
    """Nome curto se for alguém da equipe; None se não for. Aceita nome cortado pelo Movere ("NAYZA MINELLI PEREIRA OLIV")."""
    n = _nome(nome)
    if len(n) < 5:
        return None
    for completo, curto in EQUIPE_ATACADO.items():
        e = _nome(completo)
        if n == e or (len(n) >= 12 and e.startswith(n)) or n.startswith(e):
            return curto
    return None


def da_equipe(nome: str) -> bool:
    return apelido(nome) is not None


def so_equipe(vend: list) -> tuple:
    """Fica só com a equipe e monta a linha TOTAL com a soma dela (vendas, clientes, itens e pneus)."""
    eq = [dict(v, nome=apelido(v.get("nome"))) for v in vend if da_equipe(v.get("nome"))]
    soma = lambda k: round(sum(float(v.get(k) or 0) for v in eq), 2)
    total = {"loja": TOTAL, "cod": None, "venda": soma("venda"), "clientes": int(soma("clientes")), "itens": soma("itens")}
    if any("pneus" in v for v in vend):
        total["pneus"], total["pneus_vendas"] = soma("pneus"), int(soma("pneus_vendas"))
    return eq, total


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
        if t > 1:
            await page.wait_for_timeout(20000)   # dá um respiro ao Movere antes de pedir de novo
        try:
            r = await gerar(page, ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"), TABELAS_ATACADO, familias, [],
                            espera_max=60 if ini == fim else 120)
            if "erro" not in r:
                return r
        except Exception as e:
            r = {"erro": type(e).__name__}
        print(f"   ⚠️ tentativa {t} sem relatório")
    return r


async def ler(hoje: date, dias: list, meses: list) -> dict:
    from playwright.async_api import async_playwright
    from sync_televendas import login
    from varejo_filtros import FAMILIAS_PNEUS_ATACADO
    os.environ["FRETE"] = "1"   # "Frete compõe valores totais: Sim" (igual ao relatório do TI)
    out = {"meses": {}, "dias": {}, "erros": []}
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        page = await (await b.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo", viewport={"width": 1400, "height": 2400})).new_page()
        await login(page)

        async def mes(pg, ini, fim, tentativas):
            r = await gerar_553(pg, ini, fim, [], tentativas)
            if "erro" in r:
                return False
            vend = vendedores(r)
            print(f"▶ pneus do mês {ini:%m/%Y}")
            rp = await gerar_553(pg, ini, fim, FAMILIAS_PNEUS_ATACADO)
            if "erro" in rp:   # sem venda de pneu também cai aqui: fica zerado
                rp = {}
            juntar_pneus(vend, vendedores(rp) if rp else [], "cod")
            eq, total = so_equipe(vend)
            print(f"   equipe do Atacado com venda no mês: {len(eq)} de {len(EQUIPE_ATACADO)}")
            out["meses"][ini] = {"fim": fim, "lojas": [total], "vend": eq}   # sem "por loja": o Movere soma todo mundo na loja
            return True

        async def dia(pg, d):
            r = await gerar_553(pg, d, d, [], tentativas=(1,))
            if "erro" in r:
                return False
            eq, total = so_equipe(vendedores(r))
            out["dias"][d] = {"lojas": [total], "vend": eq}
            print(f"   equipe com venda no dia: {len(eq)}")
            return True

        falhou = []
        for ini, fim in meses:
            print(f"▶ mês {ini:%m/%Y} até {fim:%d/%m}")
            if not await mes(page, ini, fim, (1, 2)):
                falhou.append(("mes", ini, fim))
        for d in dias:
            print(f"▶ dia {d:%d/%m}")
            if not await dia(page, d):
                falhou.append(("dia", d, d))

        # 2ª volta: só o que falhou, entrando no Movere de novo do zero (ele às vezes engasga por alguns minutos)
        if falhou:
            print(f"🔁 2ª volta para {len(falhou)} relatório(s)")
            await page.context.close()
            await asyncio.sleep(60)
            page = await (await b.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo", viewport={"width": 1400, "height": 2400})).new_page()
            await login(page)
            for tipo, ini, fim in falhou:
                if tipo == "mes":
                    print(f"▶ mês {ini:%m/%Y} até {fim:%d/%m} (2ª volta)")
                    if not await mes(page, ini, fim, (1, 2)):
                        out["erros"].append(f"mês {ini:%m/%Y}")
                else:
                    print(f"▶ dia {ini:%d/%m} (2ª volta)")
                    if not await dia(page, ini):   # sem venda no dia o Movere não monta o relatório: dia zerado
                        print("   sem relatório: dia zerado")
                        out["dias"][ini] = {"lojas": [{"loja": TOTAL, "cod": None, "venda": 0.0, "clientes": 0, "itens": 0.0}], "vend": []}
        await b.close()
    return out


# ── Supabase ──────────────────────────────────────────────────────────────────
def sb_get(cli, chave, caminho):
    r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/{caminho}", headers=cv._sb_headers(chave))
    r.raise_for_status()
    return r.json()


def gravar(cli, chave, res: dict):
    H = cv._sb_headers(chave, {"Prefer": "resolution=merge-duplicates,return=minimal"})
    url, agora = f"{cv.SUPABASE_URL}/rest/v1", datetime.now(timezone.utc).isoformat()
    def trocar(periodo, mes, dia, lojas, vend):
        filtro = f"mes=eq.{mes}&periodo=eq.{periodo}" + (f"&dia=eq.{dia}" if periodo == "dia" else "")
        for t in ("atacado_lojas", "atacado_vendedores"):
            cli.delete(f"{url}/{t}?{filtro}", headers=cv._sb_headers(chave)).raise_for_status()
        base = {"mes": mes, "periodo": periodo, "dia": dia, "atualizado_em": agora}
        _post(cli, f"{url}/atacado_lojas?on_conflict=mes,periodo,dia,loja", H, [dict(l, **base) for l in lojas])
        if vend:
            _post(cli, f"{url}/atacado_vendedores?on_conflict=mes,periodo,dia,cod", H, [dict(v, **base) for v in vend])
    for ini, m in res["meses"].items():
        trocar("mes", ini.isoformat(), m["fim"].isoformat(), m["lojas"], m["vend"])
    for d, x in res["dias"].items():
        trocar("dia", d.replace(day=1).isoformat(), d.isoformat(), x["lojas"], x["vend"])


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
    hoje = datetime.now(TZ).date()
    chave = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    print(f"📦 Resultado Atacado · {hoje:%d/%m/%Y}{' · TESTE (não grava)' if DRY else ''}")
    feriados, ja_lidos = set(), set()
    if chave:
        try:
            with httpx.Client(timeout=30) as cli:
                ini_busca = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
                for x in sb_get(cli, chave, f"atacado_metas?select=mes,chave&chave=like.feriado_*&mes=gte.{ini_busca}"):
                    feriados.add(date.fromisoformat(x["mes"]).replace(day=int(x["chave"][8:])))
                for x in sb_get(cli, chave, f"atacado_lojas?select=dia&periodo=eq.dia&loja=eq.{TOTAL}&dia=gte.{(hoje - timedelta(days=15)).isoformat()}"):
                    ja_lidos.add(date.fromisoformat(x["dia"]))
        except httpx.HTTPStatusError as e:
            print(f"⚠️ Não li feriados/dias já lidos ({e.response.status_code}). Rodou o SQL 30?")
    ultimos = dias_uteis(hoje, feriados)
    dias = dias_a_ler(ultimos, hoje, ja_lidos)
    meses = [(hoje.replace(day=1), hoje)]
    if hoje.day <= 3:   # fecha o mês anterior com o último dia
        fim_ant = hoje.replace(day=1) - timedelta(days=1)
        meses.append((fim_ant.replace(day=1), fim_ant))
    print(f"Dias úteis no painel: {[d.strftime('%d/%m') for d in ultimos]} · a ler: {[d.strftime('%d/%m') for d in dias]}")
    res = asyncio.run(ler(hoje, dias, meses))
    detalhes = {"meses": len(res["meses"]), "dias": len(res["dias"]), "erros": res["erros"][:20],
                "vendedores_mes": sum(len(m["vend"]) for m in res["meses"].values())}
    print("Resumo:", {k: v for k, v in detalhes.items() if k != "erros"}, "· erros:", len(res["erros"]))
    if DRY:
        if os.environ.get("MOSTRAR_TRANCADO"):
            from varejo_teste import trancar
            b = trancar({"meses": {k.isoformat(): dict(v, fim=v["fim"].isoformat()) for k, v in res["meses"].items()},
                         "dias": {k.isoformat(): v for k, v in res["dias"].items()}})
            for i in range(0, len(b), 900):
                print("TRANCADO:" + b[i:i + 900])
        print("TESTE: nada foi gravado.")
        return 0 if not res["erros"] else 1
    if not chave:
        print("❌ Falta o segredo SUPABASE_SERVICE_KEY")
        return 1
    try:
        with httpx.Client(timeout=60) as cli:
            gravar(cli, chave, res)
        print("✅ Gravado no banco.")
    except httpx.HTTPStatusError as e:
        msg = f"Não gravou no banco ({e.response.status_code}). Rodou o SQL 30?"
        print("❌", msg)
        registrar(chave, False, msg, detalhes, inicio)
        return 1
    ok = not res["erros"]
    registrar(chave, ok, "; ".join(res["erros"])[:300], detalhes, inicio)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
