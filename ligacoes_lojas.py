"""
ligacoes_lojas.py
=================
Monta a lista de "Ligações das lojas" no FOXNET (tabela ligacoes do Supabase).
Mesma lógica do Apps Script das planilhas — que CONTINUA funcionando igual.

Roda TODOS os dias (inclusive sábado e domingo) às 7h, 10h, 15h e 18h de Porto Velho.
Toda rodada:
  1. IMPORTA as cotações dos dias ainda não importados (até ontem; no máximo 7),
     tirando quem já comprou (no dia da cotação ou depois), quem está nas duas
     colunas de agendados do Kommo (etapas 6 e 7, com ou sem data) e telefones
     repetidos (fica a cotação mais antiga). Normalmente o dia anterior entra às 7h;
     se o Analytics ainda não atualizou, entra na rodada seguinte.
  2. RECONFERE a lista dos últimos 30 dias:
       comprou (telefone nas vendas do Analytics) e a loja NÃO marcou
       "Venda ganha" (com a O.S.)                        → "Venda ganha televendas"
       agendado no Kommo depois                          → "agendou"
  3. DIVIDE os clientes sem responsável entre os vendedores ativos de cada loja
     (função distribuir_ligacoes do SQL 15; a sobra vai para quem ficou com menos).
  A lista começa nas cotações de 19/11/2026 (decisão do TI).

Aviso de erro: se a rodada falhar, ou se às 18h o dia anterior ainda não tiver
entrado na lista, a rodada termina com erro → o GitHub manda e-mail ao dono do
repositório, e o admin vê o aviso na tela das Ligações.

Segredos (GitHub → Settings → Secrets → Actions):
  ANALYTICS_LOGIN, ANALYTICS_SENHA, SUPABASE_SERVICE_KEY, KOMMO_TOKEN

Opcional: DRY_RUN=1 mostra o que faria, sem gravar nada.

⚠️ O registro do GitHub Actions é PÚBLICO: este script nunca escreve nome,
   telefone ou número de cotação de cliente no registro — só contagens.
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone

import re as _re

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

RESUMO = {"inicio": None, "inseridas": 0, "comprou": 0, "agendou": 0, "abertas": 0, "divididos": 0}
HORA_ULTIMA_RODADA = 17     # a rodada das 18h (com folga de atraso do GitHub) é a última do dia
# O dia D só é importado a partir das 6h de D+1: de madrugada o Analytics ainda está carregando o dia
# (em 21/11, à 1h30, o 20/11 tinha só 3 cotações). A data existe no calendário do Analytics mesmo sem
# dados, então "a data existe" não serve para saber se o dia chegou.
HORA_MIN_IMPORTAR = 6
STATUS_COMPROU = "venda_televendas"


# ── Kommo ─────────────────────────────────────────────────────────────────────
def data_do_campo(f: dict):
    """Data de um campo do Kommo (data, data e hora, ou texto como 26/11 ou 26/11/2026)."""
    for v in f.get("values") or []:
        x = v.get("value")
        if x in (None, ""):
            continue
        if isinstance(x, (int, float)) or (isinstance(x, str) and x.strip().isdigit()):
            return datetime.fromtimestamp(int(x), cv.TZ_LOJA).date()
        t = str(x).strip()
        m = _re.match(r"(\d{4})-(\d{2})-(\d{2})", t)
        if m:
            return date(int(m[1]), int(m[2]), int(m[3]))
        m = _re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
        if m:
            hoje = datetime.now(cv.TZ_LOJA).date()
            ano = int(m[3]) if m[3] else hoje.year
            ano += 2000 if ano < 100 else 0
            try:
                d = date(ano, int(m[2]), int(m[1]))
            except ValueError:
                return None
            if not m[3] and d < hoje - timedelta(days=60):   # 05/01 escrito em dezembro → ano que vem
                d = date(ano + 1, d.month, d.day)
            return d
    return None


def prioridade_campo(f: dict):
    """Campo do lead com a data do agendamento: "Data da visita" (o certo, confirmado pelo TI);
    na falta dele, outro campo de data com "visita" ou "agend" no nome. None = não serve."""
    nome = str(f.get("field_name") or "").strip().lower()
    if nome == "data da visita":
        return 0
    if f.get("field_type") in ("date", "date_time") and ("visita" in nome or "agend" in nome):
        return 1
    return None


def eh_campo_agendamento(f: dict) -> bool:
    return prioridade_campo(f) is not None


def telefones_kommo(cli: httpx.Client, token: str):
    """Leads nas etapas de agendamento → (telefones, {telefone: data do agendamento}).
    Telefone = últimos 8 dígitos. A data vem do campo do lead com "agend" no nome."""
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

    contatos, data_contato, campos_data, com_data, leads, usados = set(), {}, set(), 0, 0, {}
    for etapa in ETAPAS:
        pagina = 1
        while True:
            d = get(f"{KOMMO}/leads?filter%5Bstatuses%5D%5B0%5D%5Bpipeline_id%5D={FUNIL}"
                    f"&filter%5Bstatuses%5D%5B0%5D%5Bstatus_id%5D={etapa}&with=contacts&limit=250&page={pagina}")
            if not d:
                break
            for lead in (d.get("_embedded") or {}).get("leads") or []:
                leads += 1
                quando, melhor, campo = None, 9, ""
                for f in lead.get("custom_fields_values") or []:
                    if f.get("field_type") in ("date", "date_time"):
                        campos_data.add(str(f.get("field_name") or ""))   # só o NOME do campo (sem dados do cliente)
                    pr = prioridade_campo(f)
                    if pr is not None and pr < melhor:
                        d_ = data_do_campo(f)
                        if d_:
                            quando, melhor, campo = d_, pr, str(f.get("field_name") or "")
                if quando:
                    com_data += 1
                    usados[campo] = usados.get(campo, 0) + 1
                for c in ((lead.get("_embedded") or {}).get("contacts") or []):
                    contatos.add(c["id"])
                    if quando and (c["id"] not in data_contato or quando > data_contato[c["id"]]):
                        data_contato[c["id"]] = quando
            if not (d.get("_links") or {}).get("next"):
                break
            pagina += 1
    print(f"📅 Kommo: {leads} lead(s) agendado(s), {com_data} com data de agendamento"
          + (" (" + ", ".join(f"{n}: {q}" for n, q in sorted(usados.items())) + ")" if usados else "")
          + (f" · campos de data nos leads: {', '.join(sorted(campos_data))}" if campos_data else " · nenhum campo de data nos leads"))

    tels, datas, ids = set(), {}, sorted(contatos)
    for i in range(0, len(ids), 40):          # lotes de 40 (limite de tamanho da URL)
        q = "&".join(f"filter%5Bid%5D%5B%5D={x}" for x in ids[i:i + 40])
        d = get(f"{KOMMO}/contacts?{q}&limit=250")
        if not d:
            continue
        for c in (d.get("_embedded") or {}).get("contacts") or []:
            quando = data_contato.get(c.get("id"))
            for f in c.get("custom_fields_values") or []:
                if f.get("field_code") == "PHONE":
                    for v in f.get("values") or []:
                        for k in cv.chaves_tel(v.get("value")):
                            tels.add(k)
                            if quando and (k not in datas or quando > datas[k]):
                                datas[k] = quando
    return tels, datas


# ── Analytics ─────────────────────────────────────────────────────────────────
def filtro_dias(uris: list) -> str:
    return f"[{cv._md()}/obj/{cv.ATTR_DIA}] IN ({', '.join('[' + u + ']' for u in uris)})"


_MEDIDA = [_re.compile(r"(\d{3})\s*/\s*(\d{2})\s*Z?R\s*(\d{2}(?:[.,]5)?)", _re.I),
           _re.compile(r"(\d{1,2}[.,]\d{2})\s*[-–]\s*(\d{2})"),
           _re.compile(r"(\d{2,3})\s*[xX]\s*(\d{1,2}[.,]\d{2})\s*R\s*(\d{2})", _re.I)]


def medida_de(texto: str):
    """Medida do pneu na descrição do item: '255/50R20 LISO ALENZA' → '255/50R20'."""
    t = str(texto or "")
    m = _MEDIDA[0].search(t)
    if m:
        return f"{m.group(1)}/{m.group(2)}R{m.group(3).replace(',', '.')}"
    m = _MEDIDA[1].search(t)
    if m:
        return f"{m.group(1).replace(',', '.')}-{m.group(2)}"
    m = _MEDIDA[2].search(t)
    if m:
        return f"{m.group(1)}X{m.group(2).replace(',', '.')}R{m.group(3)}"
    return None


def cotacoes(linhas: list) -> list:
    """CSV de cotações → uma linha por cotação (valor somado), mais antigas primeiro.
    Colunas (igual ao Apps Script): Cotação, Cliente, Telefone, Período,
    Estabelecimento, NomeOperador, Vendedor, Item, Valor Total."""
    grupos = {}
    for r in linhas[1:]:
        if len(r) < 9:
            continue
        cot, cli_, tel, per, est, op, _, item, val = r[:9]
        d = cv.data_br(per)
        if not cot or d is None:
            continue
        g = grupos.setdefault(cot, {"cotacao": cot.strip(), "cliente": cli_.strip(), "telefone": tel.strip(),
                                    "data": d, "loja": est.strip(), "operador": op.strip(), "valor": 0.0})
        g["valor"] += cv.numero_br(val)
        if not g.get("medida"):
            g["medida"] = medida_de(item)
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


def data_kommo(tel, datas: dict):
    ds = [datas[k] for k in cv.chaves_tel(tel) if k in datas]
    return max(ds) if ds else None


def reconferir(abertas: list, vendas: dict, agendados: set, datas: dict = None) -> list:
    """Lista aberta → mudanças: comprou (prioridade), agendou no Kommo, ou data do agendamento do Kommo.
    A data do Kommo entra quando a lista está sem data ou com uma data mais antiga (fica a mais recente)."""
    datas, mudancas = datas or {}, []
    for l in abertas:
        dia = comprou_desde(l.get("telefone"), date.fromisoformat(l["data_cotacao"]), vendas)
        quando = data_kommo(l.get("telefone"), datas)
        if dia:
            mudancas.append({"id": l["id"], "status": STATUS_COMPROU, "comprou_em": dia.isoformat(), "quem": ROBO_MOVERE})
        elif l["status"] in SEM_CONTATO and cv.chaves_tel(l.get("telefone")) & agendados:
            m = {"id": l["id"], "status": "agendou", "quem": ROBO_KOMMO}
            if quando:
                m["agendado_para"] = quando.isoformat()
            mudancas.append(m)
        elif l["status"] == "agendou" and quando and (not l.get("agendado_para") or quando.isoformat() > l["agendado_para"]):
            mudancas.append({"id": l["id"], "status": "agendou", "agendado_para": quando.isoformat(),
                             "so_data": True, "quem": ROBO_KOMMO})
    return mudancas


def dias_para_importar(ultima, hoje: date) -> list:
    """Dias depois do último importado até ontem (no máximo 7, nunca antes de 19/11).
    Primeira vez: desde 19/11."""
    ontem = hoje - timedelta(days=1)
    inicio = (ultima + timedelta(days=1)) if ultima else INICIO
    inicio = max(inicio, hoje - timedelta(days=MAX_DIAS_IMPORTAR), INICIO)
    return [inicio + timedelta(days=i) for i in range((ontem - inicio).days + 1)]


def dias_para_revisar(ultima, dias: list) -> list:
    """Os 2 últimos dias já importados (se não estão em "dias"), para pegar cotações que chegaram
    atrasadas no Analytics."""
    if not ultima:
        return []
    return [d for d in (ultima - timedelta(days=1), ultima) if d >= INICIO and d not in dias]


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
        # Coluna "medida" (SQL 14) já existe?
        tem_medida = cli.get(f"{cv.SUPABASE_URL}/rest/v1/ligacoes?select=medida&limit=1",
                             headers=cv._sb_headers(chave)).status_code == 200
        if not tem_medida:
            print("⚠️ Falta rodar o SQL 14 (coluna da medida): sigo sem a medida do pneu.")
        # Estado atual da lista
        ult = sb_get(cli, chave, "ligacoes?select=data_cotacao&order=data_cotacao.desc&limit=1")
        ultima = date.fromisoformat(ult[0]["data_cotacao"]) if ult else None
        desde = (hoje - timedelta(days=DIAS_RECONFERIR)).isoformat()
        abertas = sb_get(cli, chave, "ligacoes?select=id,cotacao,telefone,tel_chave,data_cotacao,status,agendado_para" + (",medida" if tem_medida else "") +
                                     f"&status=in.({','.join(ABERTOS)})&data_cotacao=gte.{desde}&limit=10000")
        # Cotações já na lista sem a medida (últimos 7 dias): completar com o relatório
        sem_medida = [l for l in abertas if tem_medida and not l.get("medida")
                      and date.fromisoformat(l["data_cotacao"]) >= hoje - timedelta(days=7)]
        RESUMO["abertas"] = len(abertas)
        dias = dias_para_importar(ultima, hoje)
        # Os últimos dias já importados são conferidos de novo: se o Analytics ainda não tinha o dia
        # inteiro quando foi importado, as cotações que faltaram entram agora (sem repetir as que já estão).
        revisar = dias_para_revisar(ultima, dias)
        print(f"📋 Lista aberta (últimos {DIAS_RECONFERIR} dias): {len(abertas)} · "
              f"dias para importar: {', '.join(d.strftime('%d/%m') for d in dias) or 'nenhum'}"
              f" · conferir de novo: {', '.join(d.strftime('%d/%m') for d in revisar) or 'nenhum'}")

        agendados, datas_kommo = telefones_kommo(cli, segredos["KOMMO_TOKEN"])
        print(f"📅 Telefones agendados no Kommo: {len(agendados)} · com data: {len(datas_kommo)}")

        tt = cv.login_analytics(cli, segredos["ANALYTICS_LOGIN"], segredos["ANALYTICS_SENHA"])
        print("🔐 Login no Analytics OK")

        # Vendas desde a cotação aberta mais antiga (ou o 1º dia a importar) até hoje
        inicio_vendas = min([date.fromisoformat(l["data_cotacao"]) for l in abertas] + dias + revisar + [hoje])
        dias_vendas = [inicio_vendas + timedelta(days=i) for i in range((hoje - inicio_vendas).days + 1)]
        uris_vendas = {d: u for d in dias_vendas if (u := cv.elemento_dia(cli, tt, d))}
        vendas = {}
        if uris_vendas:
            vendas = cv.vendas_por_telefone(cv.relatorio(cli, tt, REL_VENDAS, None, filtro_dias(list(uris_vendas.values()))))
        print(f"🧾 Vendas: {len(uris_vendas)} dia(s) no Analytics · {len(vendas)} telefones")

        # 1) Importar — só os dias que já existem no Analytics (senão, tenta na próxima rodada)
        agora = datetime.now(cv.TZ_LOJA).replace(tzinfo=None)
        prontos = []
        for d in dias:
            fechou = agora >= datetime(d.year, d.month, d.day) + timedelta(days=1, hours=HORA_MIN_IMPORTAR)
            if d not in uris_vendas or not fechou:
                break
            prontos.append(d)
        if dias and not prontos:
            print(f"⏳ {dias[0].strftime('%d/%m')} ainda não está pronto no Analytics: importo na próxima rodada.")
        prontos = sorted(set(prontos) | {d for d in revisar if d in uris_vendas})
        novas = []
        dias_cot = sorted(set(prontos) | {date.fromisoformat(l["data_cotacao"]) for l in sem_medida} & set(uris_vendas))
        todas_cots = cotacoes(cv.relatorio(cli, tt, REL_COT, DASH_COT, filtro_dias([uris_vendas[d] for d in dias_cot]))) if dias_cot else []
        # Dia novo sem nenhuma cotação: ainda não chegou (fica para a próxima rodada; às 18h vira aviso)
        com_dados = {c["data"] for c in todas_cots}
        vazios = [d for d in prontos if d in dias and d not in com_dados]
        if vazios:
            print(f"⏳ Sem nenhuma cotação ainda em {', '.join(d.strftime('%d/%m') for d in vazios)}: importo na próxima rodada.")
            prontos = [d for d in prontos if d not in vazios]
        if sem_medida and not dry:
            medidas = {c["cotacao"]: c.get("medida") for c in todas_cots if c.get("medida")}
            completas = 0
            for l in sem_medida:
                med = medidas.get(l.get("cotacao"))
                if med:
                    cli.patch(f"{cv.SUPABASE_URL}/rest/v1/ligacoes?id=eq.{l['id']}",
                              headers=cv._sb_headers(chave, {"Prefer": "return=minimal"}), json={"medida": med}).raise_for_status()
                    completas += 1
            print(f"📏 Medida do pneu completada em {completas} cotação(ões) da lista")
        if prontos:
            cots = [c for c in todas_cots if c["data"] in prontos]
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
                          "data_cotacao": c["data"].isoformat(),
                          **({"medida": c.get("medida")} if tem_medida else {})} for c in novas]
                for i in range(0, len(corpo), 500):
                    r = cli.post(f"{cv.SUPABASE_URL}/rest/v1/ligacoes?on_conflict=cotacao",
                                 headers=cv._sb_headers(chave, {"Prefer": "resolution=ignore-duplicates,return=minimal"}),
                                 json=corpo[i:i + 500])
                    r.raise_for_status()
        RESUMO["inseridas"] = len(novas)

        # 2) Reconferir a lista aberta
        bate = [l for l in abertas if cv.chaves_tel(l.get("telefone")) & agendados]
        por_st = {}
        for l in bate:
            por_st[l["status"]] = por_st.get(l["status"], 0) + 1
        print(f"🔎 Na lista e agendados no Kommo: {len(bate)}"
              + (" (" + ", ".join(f"{k} {v}" for k, v in sorted(por_st.items())) + ")" if por_st else "")
              + f" · com Data da visita: {sum(1 for l in bate if data_kommo(l.get('telefone'), datas_kommo))}")
        mudancas = reconferir(abertas, vendas, agendados, datas_kommo)
        RESUMO["comprou"] = sum(1 for m in mudancas if m["status"] == STATUS_COMPROU)
        RESUMO["agendou"] = sum(1 for m in mudancas if m["status"] == "agendou" and not m.get("so_data"))
        so_data = sum(1 for m in mudancas if m.get("so_data"))
        print(f"🔁 Reconferência: venda ganha televendas {RESUMO['comprou']} · agendou no Kommo {RESUMO['agendou']}"
              f" · data do agendamento atualizada pelo Kommo {so_data}"
              + (" (teste, nada gravado)" if dry else ""))
        if not dry:
            agora = datetime.now(timezone.utc).isoformat()
            for m in mudancas:
                corpo = {} if m.get("so_data") else {"status": m["status"], "status_em": agora, "status_por": m["quem"]}
                if m.get("comprou_em"):
                    corpo["comprou_em"] = m["comprou_em"]
                if m.get("agendado_para"):
                    corpo["agendado_para"] = m["agendado_para"]
                cli.patch(f"{cv.SUPABASE_URL}/rest/v1/ligacoes?id=eq.{m['id']}",
                          headers=cv._sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo).raise_for_status()
                obs = (f"Comprou em {date.fromisoformat(m['comprou_em']).strftime('%d/%m/%Y')}"
                       if m.get("comprou_em") else
                       ("Data do agendamento no Kommo: " + date.fromisoformat(m["agendado_para"]).strftime("%d/%m/%Y")
                        if m.get("agendado_para") else "Agendado no Kommo"))
                cli.post(f"{cv.SUPABASE_URL}/rest/v1/ligacoes_historico",
                         headers=cv._sb_headers(chave, {"Prefer": "return=minimal"}),
                         json={"ligacao_id": m["id"], "quem": m["quem"], "status": m["status"], "obs": obs}).raise_for_status()

        # 3) Dividir os clientes sem responsável entre os vendedores de cada loja
        if not dry:
            r = cli.post(f"{cv.SUPABASE_URL}/rest/v1/rpc/distribuir_ligacoes",
                         headers=cv._sb_headers(chave), json={})
            if r.status_code == 404:
                print("⚠️ Falta rodar o SQL 15 (divisão entre vendedores): clientes ficam sem responsável.")
            else:
                r.raise_for_status()
                RESUMO["divididos"] = int(r.json() or 0)
                print(f"👥 Clientes divididos entre os vendedores: {RESUMO['divididos']}")

    faltando = [d for d in dias if d not in prontos]
    resumo = (f"novas {RESUMO['inseridas']} · divididos {RESUMO['divididos']} · "
              f"venda televendas {RESUMO['comprou']} · agendou {RESUMO['agendou']}")
    if faltando and datetime.now(cv.TZ_LOJA).hour >= HORA_ULTIMA_RODADA:
        msg = (f"lista de {', '.join(d.strftime('%d/%m') for d in faltando)} NÃO foi para as lojas: "
               f"o Analytics ainda não tinha esse dia na última rodada (18h). " + resumo)
        print(f"❌ {msg}")
        registrar_rodada(False, msg, teste=dry)
        return 1
    registrar_rodada(True, resumo, teste=dry)
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
