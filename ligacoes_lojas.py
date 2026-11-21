"""
ligacoes_lojas.py
=================
Monta a lista de "Ligações das lojas" no FOXNET (tabela ligacoes do Supabase).
Mesma lógica do Apps Script das planilhas — que CONTINUA funcionando igual.

Toda rodada:
  1. IMPORTA as cotações dos dias ainda não importados (até ontem; no máximo 7),
     tirando quem já comprou, quem está agendado no Kommo (etapas 6 e 7) e
     telefones repetidos (fica a cotação mais antiga).
  2. RECONFERE a lista dos últimos 30 dias:
       comprou (telefone nas vendas do Analytics) e a loja NÃO marcou
       "Venda ganha" (com a O.S.)                        → "Venda ganha televendas"
       agendado no Kommo depois                          → "agendou"
  A lista começa nas cotações de 19/11/2026 (decisão do TI).

Segredos (GitHub → Settings → Secrets → Actions):
  ANALYTICS_LOGIN, ANALYTICS_SENHA, SUPABASE_SERVICE_KEY, KOMMO_TOKEN

Opcional: DRY_RUN=1 mostra o que faria, sem gravar nada.

⚠️ O registro do GitHub Actions é PÚBLICO: este script nunca escreve nome,
   telefone ou número de cotação de cliente no registro — só contagens.
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone

import httpx

import conferir_vendas_movere as cv   # login/relatórios do Analytics e utilidades

ROBO = "ligacoes_lojas"
REL_COT, DASH_COT = 782403, 782276       # "Validação Cotações rápidas televendas"
REL_VENDAS = cv.REL_VENDAS               # vendas de todas as lojas (sem filtro do dashboard)
KOMMO = "https://foxpneusltda.kommo.com/api/v4"
FUNIL = 11611467
ETAPAS = [112913852, 89179011]           # 6 - AGENDADOS (IA), 7 - AGENDADO
LOJAS_IGNORADAS = {"ATACADO"}            # igual ao Apps Script
DIAS_RECONFERIR = 30
MAX_DIAS_IMPORTAR = 7
INICIO = date(2026, 11, 19)              # primeiras cotações da lista (decisão do TI)
# Se o cliente comprou e a loja não marcou "Venda ganha" → "Venda ganha televendas"
ABERTOS = ("pendente", "nao_atende", "retornar", "sem_interesse", "agendou", "venda_perdida")
SEM_CONTATO = ("pendente", "nao_atende", "retornar")                 # podem virar "agendou"
ROBO_MOVERE, ROBO_KOMMO = "Robô (Movere)", "Robô (Kommo)"

RESUMO = {"inicio": None, "inseridas": 0, "comprou": 0, "agendou": 0, "abertas": 0}
STATUS_COMPROU = "venda_televendas"


# ── Kommo ─────────────────────────────────────────────────────────────────────
def telefones_kommo(cli: httpx.Client, token: str) -> set:
    """Telefones (últimos 8 dígitos) dos contatos dos leads nas etapas de agendamento."""
    h = {"Authorization": "Bearer " + token.strip()}

    def get(url):
        r = cli.get(url, headers=h)
        if r.status_code == 204:
            return None
        if r.status_code == 401:
            raise RuntimeError("token do Kommo expirado ou inválido (401)")
        if r.status_code >= 300:
            raise RuntimeError(f"Kommo respondeu {r.status_code}")
        return r.json()

    contatos = set()
    for etapa in ETAPAS:
        pagina = 1
        while True:
            d = get(f"{KOMMO}/leads?filter%5Bstatuses%5D%5B0%5D%5Bpipeline_id%5D={FUNIL}"
                    f"&filter%5Bstatuses%5D%5B0%5D%5Bstatus_id%5D={etapa}&with=contacts&limit=250&page={pagina}")
            if not d:
                break
            for lead in (d.get("_embedded") or {}).get("leads") or []:
                for c in ((lead.get("_embedded") or {}).get("contacts") or []):
                    contatos.add(c["id"])
            if not (d.get("_links") or {}).get("next"):
                break
            pagina += 1

    tels, ids = set(), sorted(contatos)
    for i in range(0, len(ids), 40):          # lotes de 40 (limite de tamanho da URL)
        q = "&".join(f"filter%5Bid%5D%5B%5D={x}" for x in ids[i:i + 40])
        d = get(f"{KOMMO}/contacts?{q}&limit=250")
        if not d:
            continue
        for c in (d.get("_embedded") or {}).get("contacts") or []:
            for f in c.get("custom_fields_values") or []:
                if f.get("field_code") == "PHONE":
                    for v in f.get("values") or []:
                        tels |= cv.chaves_tel(v.get("value"))
    return tels


# ── Analytics ─────────────────────────────────────────────────────────────────
def filtro_dias(uris: list) -> str:
    return f"[{cv._md()}/obj/{cv.ATTR_DIA}] IN ({', '.join('[' + u + ']' for u in uris)})"


def cotacoes(linhas: list) -> list:
    """CSV de cotações → uma linha por cotação (valor somado), mais antigas primeiro.
    Colunas (igual ao Apps Script): Cotação, Cliente, Telefone, Período,
    Estabelecimento, NomeOperador, Vendedor, Item, Valor Total."""
    grupos = {}
    for r in linhas[1:]:
        if len(r) < 9:
            continue
        cot, cli_, tel, per, est, op, _, _, val = r[:9]
        d = cv.data_br(per)
        if not cot or d is None:
            continue
        g = grupos.setdefault(cot, {"cotacao": cot.strip(), "cliente": cli_.strip(), "telefone": tel.strip(),
                                    "data": d, "loja": est.strip(), "operador": op.strip(), "valor": 0.0})
        g["valor"] += cv.numero_br(val)
    lista = sorted(grupos.values(), key=lambda x: (x["data"], x["cotacao"]))
    for g in lista:
        g["valor"] = round(g["valor"], 2)
    return lista


def comprou_desde(tel: str, desde: date, vendas: dict):
    """Primeira data de compra do telefone no dia `desde` ou depois (None se não comprou)."""
    datas = [d for k in cv.chaves_tel(tel) for (d, _) in vendas.get(k, []) if d >= desde]
    return min(datas) if datas else None


# ── Regras (testáveis sem rede) ───────────────────────────────────────────────
def escolher_novas(cots: list, vendas: dict, agendados: set, ja_existem: set, tel_abertos: set):
    """Decide quais cotações entram na lista. Devolve (novas, contagem dos motivos)."""
    motivos = {"comprou": 0, "agendou": 0, "repetido": 0, "ja_importada": 0, "loja_ignorada": 0}
    vistos, novas = set(), []
    for c in cots:
        if c["cotacao"] in ja_existem:
            motivos["ja_importada"] += 1
            continue
        if c["loja"].upper() in LOJAS_IGNORADAS:
            motivos["loja_ignorada"] += 1
            continue
        chaves = cv.chaves_tel(c["telefone"])
        if comprou_desde(c["telefone"], c["data"], vendas):
            motivos["comprou"] += 1
            continue
        if chaves & agendados:
            motivos["agendou"] += 1
            continue
        if chaves and (chaves & vistos or chaves & tel_abertos):
            motivos["repetido"] += 1
            continue
        vistos |= chaves
        novas.append(c)
    return novas, motivos


def reconferir(abertas: list, vendas: dict, agendados: set) -> list:
    """Lista aberta → mudanças: comprou (prioridade) ou agendou."""
    mudancas = []
    for l in abertas:
        dia = comprou_desde(l.get("telefone"), date.fromisoformat(l["data_cotacao"]), vendas)
        if dia:
            mudancas.append({"id": l["id"], "status": STATUS_COMPROU, "comprou_em": dia.isoformat(), "quem": ROBO_MOVERE})
        elif l["status"] in SEM_CONTATO and cv.chaves_tel(l.get("telefone")) & agendados:
            mudancas.append({"id": l["id"], "status": "agendou", "quem": ROBO_KOMMO})
    return mudancas


def dias_para_importar(ultima, hoje: date) -> list:
    """Dias depois do último importado até ontem (no máximo 7, nunca antes de 19/11).
    Primeira vez: desde 19/11."""
    ontem = hoje - timedelta(days=1)
    inicio = (ultima + timedelta(days=1)) if ultima else INICIO
    inicio = max(inicio, hoje - timedelta(days=MAX_DIAS_IMPORTAR), INICIO)
    return [inicio + timedelta(days=i) for i in range((ontem - inicio).days + 1)]


# ── Supabase ──────────────────────────────────────────────────────────────────
def sb_get(cli, chave, caminho):
    r = cli.get(f"{cv.SUPABASE_URL}/rest/v1/{caminho}", headers=cv._sb_headers(chave))
    if r.status_code == 404 or (r.status_code == 400 and "ligacoes" in r.text):
        raise RuntimeError("falta rodar o SQL 12_ligacoes.sql no Supabase")
    r.raise_for_status()
    return r.json()


def registrar_rodada(ok: bool, mensagem: str = None, teste: bool = False):
    chave = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not chave:
        return
    agora = datetime.now(timezone.utc)
    corpo = {"robo": ROBO, "ok": ok, "teste": teste,
             "inicio": (RESUMO["inicio"] or agora).isoformat(), "fim": agora.isoformat(),
             "conferidos": RESUMO["abertas"], "encontrados": RESUMO["comprou"] + RESUMO["agendou"],
             "mensagem": (mensagem or "")[:300] or None}
    try:
        with httpx.Client(timeout=20) as cli:
            cli.post(f"{cv.SUPABASE_URL}/rest/v1/robo_execucoes",
                     headers=cv._sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo)
    except Exception as e:
        print(f"⚠️ Não consegui registrar a rodada: {type(e).__name__}")


# ── Principal ─────────────────────────────────────────────────────────────────
def main() -> int:
    segredos = {n: os.environ.get(n, "").strip() for n in
                ("SUPABASE_SERVICE_KEY", "ANALYTICS_LOGIN", "ANALYTICS_SENHA", "KOMMO_TOKEN")}
    segredos["ANALYTICS_SENHA"] = os.environ.get("ANALYTICS_SENHA", "")
    faltam = [n for n, v in segredos.items() if not v]
    if faltam:
        raise RuntimeError("faltam segredos no GitHub: " + ", ".join(faltam))
    chave = segredos["SUPABASE_SERVICE_KEY"]
    dry = os.environ.get("DRY_RUN", "") == "1"
    RESUMO["inicio"] = datetime.now(timezone.utc)
    hoje = datetime.now(cv.TZ_LOJA).date()

    with httpx.Client(timeout=60) as cli:
        # Estado atual da lista
        ult = sb_get(cli, chave, "ligacoes?select=data_cotacao&order=data_cotacao.desc&limit=1")
        ultima = date.fromisoformat(ult[0]["data_cotacao"]) if ult else None
        desde = (hoje - timedelta(days=DIAS_RECONFERIR)).isoformat()
        abertas = sb_get(cli, chave, "ligacoes?select=id,telefone,tel_chave,data_cotacao,status"
                                     f"&status=in.({','.join(ABERTOS)})&data_cotacao=gte.{desde}&limit=10000")
        RESUMO["abertas"] = len(abertas)
        dias = dias_para_importar(ultima, hoje)
        print(f"📋 Lista aberta (últimos {DIAS_RECONFERIR} dias): {len(abertas)} · "
              f"dias para importar: {', '.join(d.strftime('%d/%m') for d in dias) or 'nenhum'}")

        agendados = telefones_kommo(cli, segredos["KOMMO_TOKEN"])
        print(f"📅 Telefones agendados no Kommo: {len(agendados)}")

        tt = cv.login_analytics(cli, segredos["ANALYTICS_LOGIN"], segredos["ANALYTICS_SENHA"])
        print("🔐 Login no Analytics OK")

        # Vendas desde a cotação aberta mais antiga (ou o 1º dia a importar) até hoje
        inicio_vendas = min([date.fromisoformat(l["data_cotacao"]) for l in abertas] + dias + [hoje])
        dias_vendas = [inicio_vendas + timedelta(days=i) for i in range((hoje - inicio_vendas).days + 1)]
        uris_vendas = {d: u for d in dias_vendas if (u := cv.elemento_dia(cli, tt, d))}
        vendas = {}
        if uris_vendas:
            vendas = cv.vendas_por_telefone(cv.relatorio(cli, tt, REL_VENDAS, None, filtro_dias(list(uris_vendas.values()))))
        print(f"🧾 Vendas: {len(uris_vendas)} dia(s) no Analytics · {len(vendas)} telefones")

        # 1) Importar — só os dias que já existem no Analytics (senão, tenta na próxima rodada)
        prontos = []
        for d in dias:
            if d not in uris_vendas:
                break
            prontos.append(d)
        if dias and not prontos:
            print(f"⏳ O Analytics ainda não tem {dias[0].strftime('%d/%m')}: importo na próxima rodada.")
        novas = []
        if prontos:
            linhas = cv.relatorio(cli, tt, REL_COT, DASH_COT, filtro_dias([uris_vendas[d] for d in prontos]))
            cots = [c for c in cotacoes(linhas) if c["data"] in prontos]
            existentes = {c["cotacao"] for c in sb_get(
                cli, chave, "ligacoes?select=cotacao&limit=20000&data_cotacao=in.(" +
                ",".join(d.isoformat() for d in prontos) + ")")}
            tel_abertos = {l["tel_chave"] for l in abertas if l.get("tel_chave")}
            novas, motivos = escolher_novas(cots, vendas, agendados, existentes, tel_abertos)
            por_loja = {}
            for c in novas:
                por_loja[c["loja"]] = por_loja.get(c["loja"], 0) + 1
            print(f"📥 Cotações em {', '.join(d.strftime('%d/%m') for d in prontos)}: {len(cots)} · "
                  f"novas na lista: {len(novas)} · fora: comprou {motivos['comprou']}, agendou {motivos['agendou']}, "
                  f"telefone repetido {motivos['repetido']}, já importadas {motivos['ja_importada']}, "
                  f"atacado {motivos['loja_ignorada']}")
            if por_loja:
                print("   por loja: " + " · ".join(f"{l} {n}" for l, n in sorted(por_loja.items())))
            if novas and not dry:
                corpo = [{"cotacao": c["cotacao"], "cliente": c["cliente"] or None, "telefone": c["telefone"] or None,
                          "tel_chave": cv.chave_tel(c["telefone"]) or None, "loja": c["loja"],
                          "operador": c["operador"] or None, "valor": c["valor"],
                          "data_cotacao": c["data"].isoformat()} for c in novas]
                for i in range(0, len(corpo), 500):
                    r = cli.post(f"{cv.SUPABASE_URL}/rest/v1/ligacoes?on_conflict=cotacao",
                                 headers=cv._sb_headers(chave, {"Prefer": "resolution=ignore-duplicates,return=minimal"}),
                                 json=corpo[i:i + 500])
                    r.raise_for_status()
        RESUMO["inseridas"] = len(novas)

        # 2) Reconferir a lista aberta
        mudancas = reconferir(abertas, vendas, agendados)
        RESUMO["comprou"] = sum(1 for m in mudancas if m["status"] == STATUS_COMPROU)
        RESUMO["agendou"] = sum(1 for m in mudancas if m["status"] == "agendou")
        print(f"🔁 Reconferência: venda ganha televendas {RESUMO['comprou']} · agendou no Kommo {RESUMO['agendou']}"
              + (" (teste, nada gravado)" if dry else ""))
        if not dry:
            agora = datetime.now(timezone.utc).isoformat()
            for m in mudancas:
                corpo = {"status": m["status"], "status_em": agora, "status_por": m["quem"]}
                if m.get("comprou_em"):
                    corpo["comprou_em"] = m["comprou_em"]
                cli.patch(f"{cv.SUPABASE_URL}/rest/v1/ligacoes?id=eq.{m['id']}",
                          headers=cv._sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo).raise_for_status()
                obs = (f"Comprou em {date.fromisoformat(m['comprou_em']).strftime('%d/%m/%Y')}"
                       if m.get("comprou_em") else "Agendado no Kommo")
                cli.post(f"{cv.SUPABASE_URL}/rest/v1/ligacoes_historico",
                         headers=cv._sb_headers(chave, {"Prefer": "return=minimal"}),
                         json={"ligacao_id": m["id"], "quem": m["quem"], "status": m["status"], "obs": obs}).raise_for_status()

    registrar_rodada(True, f"novas {RESUMO['inseridas']} · venda televendas {RESUMO['comprou']} · agendou {RESUMO['agendou']}",
                     teste=dry)
    print("✅ Fim.")
    return 0


def rodar() -> int:
    try:
        return main()
    except Exception as e:   # mensagem curta, sem dados de clientes
        print(f"❌ Erro: {e}")
        registrar_rodada(False, str(e), teste=os.environ.get("DRY_RUN", "") == "1")
        return 1


if __name__ == "__main__":
    sys.exit(rodar())
