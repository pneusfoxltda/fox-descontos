"""
Avisos das Ligações das lojas no computador e no celular (notificação push do navegador).

Acordado pelo Sync Televendas (7h45, 9h45, 13h45, 16h45 de Porto Velho, seg–sáb); turnos manha1, manha2,
tarde1 e tarde2 (fim do dia). A Fernanda fala como uma coordenadora (decisão do TI, 24/11/2026):
  · vendedor: quantos clientes recebeu hoje, o de maior valor para começar, quantos faltam, se mudar a
    estratégia, e o resumo do fim do dia (ligações, agendamentos, mensagens, vendas);
  · gerente da loja: a loja e CADA vendedor (quem falou com quantos, quem não falou com nenhum, quem não
    entrou no sistema hoje) para ela cobrar;
  · gerente de todas as lojas (Jonathan) / admin: as lojas que não falaram com ninguém, as abaixo de 30%
    e o resumo da rede, com o nome do gerente de cada loja.
A mensagem vai no aviso (para quem ligou o aviso, tabela push_inscricoes, SQL 17) e fica guardada para a
Fernanda mostrar na página (tabela avisos_fernanda, SQL 23). Nada de nome ou telefone de CLIENTE: só
números, o valor e o nº da cotação. O aviso vai criptografado até o aparelho.
Vendedor de férias ou desativado não recebe. Sem custo: quem entrega é o serviço de avisos do
próprio navegador (Google, Apple, Microsoft).

A chave dos avisos (VAPID) é criada pelo próprio robô na 1ª vez e fica na tabela push_config,
que só a chave de serviço lê. O registro do GitHub Actions é público: aqui só se imprimem contagens.

Rodar à mão: TURNO=manha1|manha2|tarde1|tarde2 (sem TURNO = pelo horário) e DRY_RUN=1 (não envia).
Testes: python tests/test_avisos_ligacoes.py
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SUPABASE_URL = "https://dxwkiaxpygibzmwzvcuz.supabase.co"
TZ_LOJA = timezone(timedelta(hours=-4))          # Porto Velho
SITE = "https://fox-descontos.vercel.app"
LINK = SITE + "/ligacoes.html"
ABERTOS = ("pendente", "nao_atende", "retornar", "aguardando_wa", "agendou")
DIAS = 31


# ── Utilidades ────────────────────────────────────────────────────────────────
def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def de_b64u(s: str) -> bytes:
    s = str(s).strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def plural(n, um, varios):
    return f"{n} {um if n == 1 else varios}"


def sb_headers(chave, extra=None):
    h = {"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json"}
    h.update(extra or {})
    return h


def sb_get(cli, chave, caminho):
    """GET no Supabase em partes de 1000 (o máximo que o banco entrega por vez)."""
    linhas, sep = [], "&" if "?" in caminho else "?"
    while True:
        r = cli.get(f"{SUPABASE_URL}/rest/v1/{caminho}{sep}limit=1000&offset={len(linhas)}", headers=sb_headers(chave))
        if r.status_code == 404:
            raise RuntimeError("falta rodar o SQL 17_avisos_push.sql no Supabase")
        r.raise_for_status()
        parte = r.json()
        linhas += parte
        if len(parte) < 1000:
            return linhas


# ── Chave dos avisos (VAPID) ──────────────────────────────────────────────────
def nova_chave():
    k = ec.generate_private_key(ec.SECP256R1())
    privada = k.private_numbers().private_value.to_bytes(32, "big")
    publica = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return b64u(publica), b64u(privada)


def chave_privada(b64: str):
    return ec.derive_private_key(int.from_bytes(de_b64u(b64), "big"), ec.SECP256R1())


def jwt_vapid(endpoint: str, privada_b64: str, agora: int = None) -> str:
    """Assinatura VAPID (JWT ES256) que prova ao serviço de avisos que o aviso é nosso."""
    u = httpx.URL(endpoint)
    aud = f"{u.scheme}://{u.host}" + (f":{u.port}" if u.port else "")
    cab = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    corpo = b64u(json.dumps({"aud": aud, "exp": (agora or int(time.time())) + 12 * 3600, "sub": SITE},
                            separators=(",", ":")).encode())
    der = chave_privada(privada_b64).sign(f"{cab}.{corpo}".encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return f"{cab}.{corpo}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def _hkdf(salt: bytes, ikm: bytes, info: bytes, n: int) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:n]


def criptografar(texto: bytes, p256dh_b64: str, auth_b64: str, salt: bytes = None, efemera=None) -> bytes:
    """Criptografia do aviso (RFC 8291, aes128gcm): só o aparelho da pessoa consegue ler."""
    ua_pub = de_b64u(p256dh_b64)
    segredo_auth = de_b64u(auth_b64)
    efemera = efemera or ec.generate_private_key(ec.SECP256R1())
    as_pub = efemera.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    compartilhado = efemera.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    ikm = _hkdf(segredo_auth, compartilhado, b"WebPush: info\x00" + ua_pub + as_pub, 32)
    salt = salt or os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    cifrado = AESGCM(cek).encrypt(nonce, texto + b"\x02", None)
    return salt + (4096).to_bytes(4, "big") + bytes([len(as_pub)]) + as_pub + cifrado


def enviar(cli, insc: dict, aviso: dict, publica_b64: str, privada_b64: str) -> int:
    corpo = criptografar(json.dumps(aviso, ensure_ascii=False).encode(), insc["p256dh"], insc["auth"])
    r = cli.post(insc["endpoint"], content=corpo, headers={
        "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
        "TTL": str(3 * 3600), "Urgency": "normal",
        "Authorization": f"vapid t={jwt_vapid(insc['endpoint'], privada_b64)}, k={publica_b64}"})
    return r.status_code


# ── Os números e o texto do aviso ─────────────────────────────────────────────
def turno_do_horario(agora: datetime) -> str:
    h = agora.hour + agora.minute / 60
    return "manha1" if h < 9.5 else "manha2" if h < 12 else "tarde1" if h < 15.5 else "tarde2"


def nome_curto(p: dict) -> str:
    n = (p.get("apelido") or p.get("nome") or "").strip().split(" ")[0]
    return n[:1].upper() + n[1:].lower() if n else ""


def nome_historico(p: dict) -> str:
    """O nome que fica no histórico quando a pessoa registra algo (igual ao marcar_ligacao do banco)."""
    return ((p.get("apelido") or "").strip() or (p.get("nome") or "").strip() or (p.get("email") or "")).lower()


def papel(p: dict) -> str:
    if "admin" in (p.get("funcoes") or []):
        return "admin"
    if p.get("papel_ligacoes") == "gerente":
        return "gerente" if p.get("loja") else "gerente_todas"
    return "vendedor" if p.get("papel_ligacoes") == "vendedor" or p.get("loja") else ""


def eh_robo(quem) -> bool:
    q = str(quem or "").lower()
    return q.startswith("robô") or q.startswith("robo") or q.startswith("divis")


def reais(v) -> str:
    s = f"{float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + s


def faltam(n: int) -> str:
    return ("falta " if n == 1 else "faltam ") + plural(n, "cliente", "clientes")


def dia_da_lista(ligs: list, hoje: date):
    """A lista que 'entrou hoje': o dia de cotação mais recente até ontem (o robô importa D em D+1)."""
    ontem = (hoje - timedelta(days=1)).isoformat()
    dias = [l["data_cotacao"] for l in ligs if l.get("data_cotacao") and l["data_cotacao"] <= ontem]
    return max(dias) if dias else None


def numeros(lista: list, hoje: date, dia=None) -> dict:
    """Números de um grupo de clientes (de um vendedor, de uma loja ou da rede)."""
    h = hoje.isoformat()
    do_dia = [l for l in lista if dia and l.get("data_cotacao") == dia]
    pessoa = lambda l: l["status"] != "pendente" and not eh_robo(l.get("status_por"))
    pend_dia = [l for l in do_dia if l["status"] == "pendente"]
    top = max(pend_dia or [l for l in lista if l["status"] == "pendente"] or [None],
              key=lambda l: float(l.get("valor") or 0) if l else 0)
    return {
        "dia": len(do_dia),                                                     # clientes que entraram hoje
        "falou": sum(1 for l in do_dia if pessoa(l)),                           # já tiveram contato de alguém
        "pend": len(pend_dia),                                                  # da lista de hoje, sem contato
        "pend_todos": sum(1 for l in lista if l["status"] == "pendente"),
        "antigos": sum(1 for l in lista if l["status"] == "pendente" and l.get("data_cotacao") != dia),
        "ligou": sum(1 for l in do_dia if l["status"] in ("nao_atende", "retornar", "sem_interesse") and pessoa(l)),
        "nao": sum(1 for l in lista if l["status"] == "nao_atende"),
        "msg": sum(1 for l in do_dia if l["status"] == "aguardando_wa"),
        "agend": sum(1 for l in do_dia if l["status"] == "agendou" and pessoa(l)),
        "ganha": sum(1 for l in do_dia if l["status"] == "venda_ganha"),
        "perdida": sum(1 for l in do_dia if l["status"] == "venda_perdida"),
        "ag_hoje": sum(1 for l in lista if l["status"] == "agendou" and l.get("agendado_para") == h),
        "ag_atras": sum(1 for l in lista if l["status"] == "agendou" and l.get("agendado_para") and l["agendado_para"] < h),
        "top": top,
    }


def _linhas_vendedores(meus: list, vendedores: list, hoje: date, dia) -> list:
    """['Lurdes falou com 5 (faltam 3)', 'Ana ainda não falou com nenhum (8)'] · piores primeiro."""
    out = []
    for v in vendedores:
        n = numeros([l for l in meus if l.get("responsavel_id") == v["id"]], hoje, dia)
        if not n["dia"]:
            continue
        nome = nome_curto(v)
        if not n["falou"]:
            out.append((0, -n["dia"], f"{nome} ainda não falou com nenhum ({n['dia']})"))
        elif n["pend"]:
            out.append((n["falou"] / n["dia"], 0, f"{nome} falou com {n['falou']} ({faltam(n['pend'])})"))
        else:
            out.append((2, 0, f"{nome} falou com todos os {n['dia']} 👏"))
    return [t for _, _, t in sorted(out)]


def montar_aviso(turno: str, p: dict, ligs: list, hoje: date, ctx: dict = None):
    """Mensagem da Fernanda para uma pessoa (ou None quando não há nada para dizer).
    Vai no aviso do computador/celular e aparece na raposa da página das Ligações.
    Fala o nome dos vendedores e das lojas, mas NUNCA nome ou telefone de cliente."""
    ctx = ctx or {}
    pap, nome = papel(p), nome_curto(p)
    if not pap or not p.get("ativo", True) or (pap == "vendedor" and p.get("ferias")):
        return None
    dia = dia_da_lista(ligs, hoje)
    oi = f", {nome}" if nome else ""
    vocativo = f"{nome}, " if nome else ""
    ativos_hoje = ctx.get("ativos_hoje") or set()
    vendedores = ctx.get("vendedores") or []
    titulo = corpo = None

    if pap == "vendedor":
        n = numeros([l for l in ligs if l.get("responsavel_id") == p["id"]], hoje, dia)
        ag = f" 📅 Hoje tem {plural(n['ag_hoje'], 'cliente agendado', 'clientes agendados')} para vir na loja." if n["ag_hoje"] else ""
        atras = f" ⚠️ {plural(n['ag_atras'], 'agendamento passou', 'agendamentos passaram')} da data sem resultado." if n["ag_atras"] else ""
        top = n["top"]
        maior = f" Que tal começar agora ligando (ou mandando mensagem) para o de maior valor: {reais(top['valor'])}, cotação {top.get('cotacao')}?" if top else ""
        if turno == "manha1":
            if not (n["dia"] or n["pend_todos"] or n["ag_hoje"]):
                return None
            titulo = f"🦊 Bom dia{oi}!"
            corpo = ((f"Te mandamos {plural(n['dia'], 'cliente', 'clientes')} hoje." if n["dia"] else
                      f"Você tem {plural(n['pend_todos'], 'cliente esperando contato', 'clientes esperando contato')}.") + maior +
                     (f" E ainda tem {plural(n['antigos'], 'cliente', 'clientes')} de dias anteriores sem contato." if n["dia"] and n["antigos"] else "") +
                     ag + atras + " Tenha um excelente dia, conto contigo: vamos vender muito juntos! 💪")
        elif turno == "manha2":
            if not (n["pend_todos"] or n["ag_hoje"]):
                return None
            titulo = f"🦊 {vocativo}como estão as ligações?"
            partes = []
            if n["pend"]:
                partes.append(f"Ainda {'está pendente' if n['pend'] == 1 else 'estão pendentes'} {plural(n['pend'], 'cliente', 'clientes')} de hoje. Aconteceu algo?")
            elif n["pend_todos"]:
                partes.append(f"Ainda {faltam(n['pend_todos'])} sem contato.")
            if n["falou"] and not n["agend"] and not n["ganha"]:
                partes.append("Ainda não conseguimos nenhum agendamento: vamos mudar a estratégia?")
            partes.append("Ligue primeiro; se o cliente atender, registre e me conte na Anotação o que houve, que eu te ajudo no próximo contato.")
            corpo = " ".join(partes) + ag
        elif turno == "tarde1":
            if not (n["pend_todos"] or n["nao"] or n["ag_hoje"] or n["ag_atras"]):
                return None
            titulo = f"🦊 Boa tarde{oi}!"
            if n["dia"]:
                corpo = (f"Dos {n['dia']} clientes de hoje, você já falou com {n['falou']}" +
                         (f" e ainda {faltam(n['pend'])}." if n["pend"] else ". 👏"))
            else:
                corpo = f"Ainda {faltam(n['pend_todos'])} sem contato."
            corpo += (" Você tem até as 17h: quanto mais rápido, mais chance de virar venda. Bora?" if n["pend_todos"] else "") + \
                     (f" {plural(n['nao'], 'não atendeu', 'não atenderam')}: tente pelo WhatsApp." if n["nao"] else "") + ag + atras
        else:  # tarde2 = fim do dia
            if not n["dia"] and not n["pend_todos"]:
                return None
            titulo = f"🦊 Fim do dia{oi}"
            corpo = (f"Hoje ficou assim: ligamos para {plural(n['ligou'], 'cliente', 'clientes')}, " +
                     f"{plural(n['agend'], 'agendamento', 'agendamentos')}, {plural(n['msg'], 'mensagem', 'mensagens')} no WhatsApp esperando retorno" +
                     f" e {plural(n['ganha'], 'venda', 'vendas')}." +
                     (f" Ainda {faltam(n['pend_todos'])} sem contato: é agora ou nunca!" if n["pend_todos"] else " Todos tiveram contato. 👏") +
                     " Amanhã vamos com tudo converter mais clientes em vendas. Se precisar de ajuda, me avise! 💪")

    elif pap == "gerente":
        loja = p.get("loja")
        meus = [l for l in ligs if l.get("loja") == loja]
        n = numeros(meus, hoje, dia)
        vs = [v for v in vendedores if v.get("loja") == loja and v.get("ativo", True) and not v.get("ferias")]
        linhas = _linhas_vendedores(meus, vs, hoje, dia)
        lista_v = " · ".join(linhas[:6])
        sumidos = [nome_curto(v) for v in vs if nome_historico(v) not in ativos_hoje and
                   any(l.get("responsavel_id") == v["id"] and l["status"] == "pendente" for l in meus)]
        if turno == "manha1":
            if not (n["dia"] or n["pend_todos"]):
                return None
            titulo = f"🦊 Bom dia{oi}!"
            div = {}
            for l in meus:
                if l.get("data_cotacao") == dia and l.get("responsavel_id"):
                    div[l["responsavel_id"]] = div.get(l["responsavel_id"], 0) + 1
            nomes = {v["id"]: nome_curto(v) for v in vendedores}
            divisao = ", ".join(f"{nomes.get(i, '?')} {c}" for i, c in sorted(div.items(), key=lambda x: -x[1]))
            corpo = ((f"Sua loja recebeu hoje {plural(n['dia'], 'cliente', 'clientes')}" + (f" ({divisao})" if divisao else "") + "." if n["dia"] else
                      f"Sua loja tem {plural(n['pend_todos'], 'cliente esperando contato', 'clientes esperando contato')}.") +
                     " Vamos começar cedo com os vendedores? Quanto mais rápido o contato, mais vendas para a meta da loja! 💪" +
                     (f" 📅 {plural(n['ag_hoje'], 'agendado', 'agendados')} para hoje." if n["ag_hoje"] else ""))
        elif turno == "manha2":
            if not n["pend_todos"]:
                return None
            titulo = f"🦊 Oi{oi}! Como estão as ligações?"
            if n["dia"] and not n["falou"]:
                corpo = f"Os vendedores ainda não entraram em contato com nenhum dos {n['dia']} clientes de hoje. Vamos agir, temos que vender muito para a meta da loja!"
            else:
                corpo = (f"Até agora: {lista_v}." if lista_v else f"Ainda {faltam(n['pend_todos'])} sem contato.") + \
                        " Vamos falar com os vendedores? Temos que vender muito para a meta da loja!"
        elif turno == "tarde1":
            if not (n["pend_todos"] or n["ag_atras"]):
                return None
            titulo = f"🦊 Boa tarde{oi}! Tudo bem por aí?"
            corpo = ("Que tal falarmos de novo com os vendedores? " +
                     (f"Os clientes de hoje estão assim: {lista_v}." if lista_v else f"Ainda {faltam(n['pend_todos'])} sem contato.") +
                     " Eles têm até as 17h: quanto mais rápido, mais chance de converter em venda." +
                     (f" ⚠️ {plural(n['ag_atras'], 'agendamento atrasado', 'agendamentos atrasados')} sem resultado." if n["ag_atras"] else ""))
        else:
            if not (n["dia"] or n["pend_todos"]):
                return None
            titulo = f"🦊 Fim do dia{oi}"
            corpo = (f"Hoje finalizamos assim: {plural(n['ligou'], 'ligação', 'ligações')}, {plural(n['msg'], 'mensagem', 'mensagens')} no WhatsApp esperando retorno, " +
                     f"{plural(n['agend'], 'agendamento', 'agendamentos')} e {plural(n['ganha'], 'venda', 'vendas')}." +
                     (f" {' e '.join(sumidos[:3]) if len(sumidos) <= 2 else ', '.join(sumidos[:-1]) + ' e ' + sumidos[-1]} não {'entrou' if len(sumidos) == 1 else 'entraram'} hoje no sistema de ligações: vamos cobrar?" if sumidos else "") +
                     (f" Ainda dá tempo de converter os {n['pend_todos']} que faltam. Conto contigo!" if n["pend_todos"] else " Todos os clientes tiveram contato. 👏"))

    else:  # gerente de todas as lojas (Jonathan) e admin
        lojas = sorted({l["loja"] for l in ligs if l.get("loja")})
        gerentes = ctx.get("gerentes") or {}
        por_loja = []
        for lj in lojas:
            nl = numeros([l for l in ligs if l.get("loja") == lj], hoje, dia)
            if nl["dia"]:
                por_loja.append((lj, nl))
        n = numeros(ligs, hoje, dia)
        ger = lambda lj: f" (gerente: {gerentes[lj]})" if gerentes.get(lj) else ""
        zerados = [lj for lj, nl in por_loja if not nl["falou"]]
        fracos = sorted([(nl["falou"] / nl["dia"], lj) for lj, nl in por_loja if nl["falou"] and nl["falou"] / nl["dia"] < 0.3])
        if turno == "manha1":
            if not n["dia"] and not n["pend_todos"]:
                return None
            titulo = f"🦊 Bom dia{oi}!"
            corpo = ((f"Hoje as lojas receberam {plural(n['dia'], 'cliente', 'clientes')}: " +
                      ", ".join(f"{lj} {nl['dia']}" for lj, nl in sorted(por_loja, key=lambda x: -x[1]['dia'])) + "." if n["dia"] else
                      f"As lojas têm {plural(n['pend_todos'], 'cliente esperando contato', 'clientes esperando contato')}.") +
                     " Bora cobrar os gerentes cedo? Quanto mais rápido o contato, mais vendas! 💪")
        elif turno in ("manha2", "tarde1"):
            if not (zerados or fracos or n["pend_todos"]):
                return None
            titulo = f"🦊 Opa{oi}!" if turno == "manha2" else f"🦊 Boa tarde{oi}!"
            partes = []
            if zerados:
                partes.append(("A loja " + zerados[0] + ger(zerados[0]) + " ainda não falou com nenhum cliente." if len(zerados) == 1 else
                               "Ainda não falaram com nenhum cliente: " + ", ".join(lj + ger(lj) for lj in zerados) + "."))
            if fracos:
                partes.append("Abaixo de 30%: " + ", ".join(f"{lj} {round(p * 100)}%" for p, lj in fracos) + ".")
            if not partes:
                partes.append(f"A rede já falou com {n['falou']} dos {n['dia']} clientes de hoje" + (f" e ainda {faltam(n['pend_todos'])} sem contato." if n["pend_todos"] else ". 👏"))
            partes.append("Que tal uma mensagem para os gerentes cobrarem os vendedores?" if zerados or fracos else "Bom trabalho das lojas!")
            corpo = " ".join(partes)
        else:
            if not n["dia"]:
                return None
            titulo = f"🦊 Fim do dia{oi}"
            pct = round(100 * n["falou"] / n["dia"]) if n["dia"] else 0
            piores = sorted(por_loja, key=lambda x: x[1]["falou"] / x[1]["dia"])[:3]
            corpo = (f"Hoje a rede ficou assim: {n['falou']} de {n['dia']} clientes com contato ({pct}%), " +
                     f"{plural(n['agend'], 'agendamento', 'agendamentos')}, {plural(n['msg'], 'mensagem', 'mensagens')} no WhatsApp e {plural(n['ganha'], 'venda', 'vendas')} pela loja." +
                     (" Lojas que menos ligaram: " + ", ".join(f"{lj} {round(100 * nl['falou'] / nl['dia'])}%" for lj, nl in piores) + "." if piores else "") +
                     " Vale cobrar os gerentes amanhã cedo.")
    if not corpo:
        return None
    return {"titulo": titulo, "corpo": corpo.strip(), "url": LINK, "tag": "fe-lig-" + turno}


# ── Registro da rodada (🩺 Monitor; só contagens) ─────────────────────────────
def registrar(ok: bool, mensagem: str, detalhes: dict, teste: bool, inicio: datetime):
    chave = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not chave:
        return
    corpo = {"robo": "avisos_ligacoes", "ok": ok, "teste": teste, "inicio": inicio.isoformat(),
             "fim": datetime.now(timezone.utc).isoformat(), "conferidos": detalhes.get("aparelhos"),
             "encontrados": detalhes.get("enviados"), "mensagem": (mensagem or "")[:300] or None, "detalhes": detalhes}
    try:
        with httpx.Client(timeout=20) as cli:
            r = cli.post(f"{SUPABASE_URL}/rest/v1/robo_execucoes", headers=sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo)
            if r.status_code == 400:      # SQL 18 ainda não rodou
                corpo.pop("detalhes")
                cli.post(f"{SUPABASE_URL}/rest/v1/robo_execucoes", headers=sb_headers(chave, {"Prefer": "return=minimal"}), json=corpo)
    except Exception as e:
        print(f"⚠️ Não consegui registrar a rodada: {type(e).__name__}")


DETALHES = {}


def rodar() -> int:
    inicio = datetime.now(timezone.utc)
    DETALHES.clear()
    teste = os.environ.get("DRY_RUN", "") == "1"
    try:
        codigo = main()
    except Exception as e:      # mensagem curta, sem dados de clientes
        print(f"❌ Erro: {type(e).__name__}: {str(e)[:200]}")
        registrar(False, f"{type(e).__name__}: {str(e)[:200]}", DETALHES, teste, inicio)
        return 1
    registrar(codigo == 0, None if codigo == 0 else "rodada terminou com erro", DETALHES, teste, inicio)
    return codigo


def ja_enviado(cli, chave, turno: str, hoje: date) -> bool:
    """Já houve rodada de verdade (não teste) deste turno hoje? (lê o registro das rodadas)"""
    inicio_dia = datetime(hoje.year, hoje.month, hoje.day, tzinfo=TZ_LOJA).astimezone(timezone.utc).isoformat()
    try:
        r = cli.get(f"{SUPABASE_URL}/rest/v1/robo_execucoes", headers=sb_headers(chave), params={
            "select": "detalhes", "robo": "eq.avisos_ligacoes", "ok": "eq.true", "teste": "eq.false",
            "inicio": f"gte.{inicio_dia}", "limit": "50"})
        if r.status_code != 200:
            return False
        return any((x.get("detalhes") or {}).get("turno") == turno and not (x.get("detalhes") or {}).get("repetido")
                   for x in r.json())
    except httpx.HTTPError:
        return False


def guardar_para_fernanda(cli, chave, avisos: dict, turno: str, hoje: date, dry: bool):
    """Guarda a mensagem de cada pessoa para a Fernanda mostrar na página (SQL 23). Sem o SQL, só não guarda."""
    linhas = [{"perfil_id": pid, "dia": hoje.isoformat(), "turno": turno, "titulo": a["titulo"], "texto": a["corpo"]}
              for pid, a in avisos.items() if a]
    DETALHES["mensagens_fernanda"] = len(linhas)
    if dry or not linhas:
        return
    try:
        r = cli.post(f"{SUPABASE_URL}/rest/v1/avisos_fernanda?on_conflict=perfil_id,dia,turno",
                     headers=sb_headers(chave, {"Prefer": "resolution=merge-duplicates,return=minimal"}), json=linhas)
        if r.status_code in (404, 400):
            print("⚠️ Falta rodar o SQL 23 (mensagens da Fernanda na página): os avisos saem só no computador/celular.")
            return
        r.raise_for_status()
        antigo = (hoje - timedelta(days=15)).isoformat()
        cli.delete(f"{SUPABASE_URL}/rest/v1/avisos_fernanda?dia=lt.{antigo}", headers=sb_headers(chave))
        print(f"🦊 Mensagens guardadas para a Fernanda: {len(linhas)}")
    except httpx.HTTPError as e:
        print(f"⚠️ Não consegui guardar as mensagens da Fernanda: {type(e).__name__}")


# ── Principal ─────────────────────────────────────────────────────────────────
def main() -> int:
    chave = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not chave:
        print("❌ Falta o segredo SUPABASE_SERVICE_KEY no GitHub")
        return 1
    dry = os.environ.get("DRY_RUN", "") == "1"
    agora = datetime.now(TZ_LOJA)
    hoje = agora.date()
    turno = (os.environ.get("TURNO", "") or "").strip() or turno_do_horario(agora)
    if turno not in ("manha1", "manha2", "tarde1", "tarde2"):
        print(f"❌ Turno desconhecido: {turno}")
        return 1
    print(f"🕗 Turno: {turno} · {agora.strftime('%d/%m %H:%M')}" + (" (teste: não envia)" if dry else ""))

    with httpx.Client(timeout=30) as cli:
        conf = sb_get(cli, chave, "push_config?select=chave_publica,chave_privada&id=eq.1")
        if conf:
            publica, privada = conf[0]["chave_publica"], conf[0]["chave_privada"]
        else:
            publica, privada = nova_chave()
            if not dry:
                cli.post(f"{SUPABASE_URL}/rest/v1/push_config", headers=sb_headers(chave, {"Prefer": "return=minimal"}),
                         json={"id": 1, "chave_publica": publica, "chave_privada": privada}).raise_for_status()
            print("🔑 Chave dos avisos criada (agora as pessoas já podem ligar os avisos)")

        # O mesmo aviso (turno) não sai duas vezes no dia: o robô pode ser acordado pelo despertador
        # (Sync Televendas) e também pelo horário agendado do GitHub, que às vezes chega atrasado.
        if not dry and ja_enviado(cli, chave, turno, hoje):
            print(f"✅ O aviso '{turno}' de hoje já foi enviado. Nada a fazer.")
            DETALHES.update(turno=turno, repetido=True)
            return 0
        inscs = sb_get(cli, chave, "push_inscricoes?select=id,perfil_id,endpoint,p256dh,auth,falhas")
        print(f"📱 Aparelhos com aviso: {len(inscs)}")
        DETALHES.update(turno=turno, aparelhos=len(inscs), chave_pronta=True)
        # Todas as pessoas das Ligações recebem a mensagem na raposa da página (mesmo sem o aviso ligado);
        # quem ligou o aviso recebe também no computador/celular.
        pessoas = sb_get(cli, chave, "perfis?select=id,nome,apelido,email,loja,papel_ligacoes,ativo,ferias,funcoes"
                                     "&or=(papel_ligacoes.not.is.null,funcoes.cs.{admin})")
        perfis = {p["id"]: p for p in pessoas}
        desde = (hoje - timedelta(days=DIAS)).isoformat()
        ligs = sb_get(cli, chave, "ligacoes?select=id,cotacao,loja,status,status_por,valor,data_cotacao,agendado_para,responsavel_id"
                                  f"&data_cotacao=gte.{desde}&order=id")
        inicio_dia = datetime(hoje.year, hoje.month, hoje.day, tzinfo=TZ_LOJA).astimezone(timezone.utc).isoformat()
        try:
            hist = sb_get(cli, chave, f"ligacoes_historico?select=quem&quando=gte.{inicio_dia}")
        except Exception:
            hist = []
        ctx = {
            "vendedores": [p for p in pessoas if p.get("papel_ligacoes") == "vendedor"],
            "gerentes": {p["loja"]: nome_curto(p) for p in pessoas if p.get("papel_ligacoes") == "gerente" and p.get("loja") and p.get("ativo", True)},
            "ativos_hoje": {str(h.get("quem") or "").strip().lower() for h in hist},
        }
        avisos = {pid: montar_aviso(turno, p, ligs, hoje, ctx) for pid, p in perfis.items()}
        guardar_para_fernanda(cli, chave, avisos, turno, hoje, dry)
        if not inscs:
            print("✅ Fim (ninguém ligou os avisos ainda).")
            return 0
        ids = sorted({i["perfil_id"] for i in inscs})
        enviados = sem_nada = falhas = removidos = 0
        for insc in inscs:
            aviso = avisos.get(insc["perfil_id"])
            if not aviso:
                sem_nada += 1
                continue
            if dry:
                enviados += 1
                continue
            try:
                st = enviar(cli, insc, aviso, publica, privada)
            except httpx.HTTPError:
                st = 0
            if st in (200, 201, 202):
                enviados += 1
                cli.patch(f"{SUPABASE_URL}/rest/v1/push_inscricoes?id=eq.{insc['id']}", headers=sb_headers(chave, {"Prefer": "return=minimal"}),
                          json={"ultimo_envio": datetime.now(timezone.utc).isoformat(), "falhas": 0})
            elif st in (404, 410):   # a pessoa desligou o aviso ou o aparelho não existe mais
                removidos += 1
                cli.delete(f"{SUPABASE_URL}/rest/v1/push_inscricoes?id=eq.{insc['id']}", headers=sb_headers(chave))
            else:
                falhas += 1
                cli.patch(f"{SUPABASE_URL}/rest/v1/push_inscricoes?id=eq.{insc['id']}", headers=sb_headers(chave, {"Prefer": "return=minimal"}),
                          json={"falhas": int(insc.get("falhas") or 0) + 1})
        print(f"📨 Avisos enviados: {enviados} · nada a avisar: {sem_nada} · aparelhos removidos: {removidos} · falhas: {falhas}")
        DETALHES.update(enviados=enviados, nada_a_avisar=sem_nada, removidos=removidos, falhas=falhas, pessoas=len(ids))
    print("✅ Fim.")
    return 0


if __name__ == "__main__":
    sys.exit(rodar())
