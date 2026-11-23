"""
Avisos das Ligações das lojas no computador e no celular (notificação push do navegador).

Workflow avisos-ligacoes.yml: segunda a sábado, 8h, 10h, 14h e 16h30 de Porto Velho.
Para cada pessoa que clicou em "Quero receber avisos" (tabela push_inscricoes, SQL 17):
  · vendedor: os números DELE (clientes de ontem, sem contato, não atendeu, agendados de hoje);
  · gerente da loja: os números da loja e quem tem mais clientes sem contato;
  · gerente de todas as lojas / admin: o total da rede.
O aviso leva SÓ NÚMEROS (nada de nome ou telefone de cliente) e vai criptografado até o aparelho.
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
ABERTOS = ("pendente", "nao_atende", "retornar", "agendou")
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


def numeros(lista: list, hoje: date) -> dict:
    ontem = (hoje - timedelta(days=1)).isoformat()
    h = hoje.isoformat()
    return {
        "ontem": sum(1 for l in lista if l["data_cotacao"] == ontem),
        "sem": sum(1 for l in lista if l["status"] == "pendente"),
        "nao": sum(1 for l in lista if l["status"] == "nao_atende"),
        "ag_hoje": sum(1 for l in lista if l["status"] == "agendou" and l.get("agendado_para") == h),
        "ag_atras": sum(1 for l in lista if l["status"] == "agendou" and l.get("agendado_para") and l["agendado_para"] < h),
    }


def nome_curto(p: dict) -> str:
    n = (p.get("apelido") or p.get("nome") or "").strip().split(" ")[0]
    return n[:1].upper() + n[1:].lower() if n else ""


def papel(p: dict) -> str:
    if "admin" in (p.get("funcoes") or []):
        return "admin"
    if p.get("papel_ligacoes") == "gerente":
        return "gerente" if p.get("loja") else "gerente_todas"
    return "vendedor" if p.get("papel_ligacoes") == "vendedor" or p.get("loja") else ""


def montar_aviso(turno: str, p: dict, ligs: list, hoje: date, nomes_vend: dict = None):
    """Texto do aviso para uma pessoa (ou None quando não há nada para dizer)."""
    pap, nome = papel(p), nome_curto(p)
    if not pap or not p.get("ativo", True) or (pap == "vendedor" and p.get("ferias")):
        return None
    if pap == "vendedor":
        meus = [l for l in ligs if l.get("responsavel_id") == p["id"]]
        voce, tem = "Você", "Você tem"
    elif pap == "gerente":
        meus = [l for l in ligs if l.get("loja") == p.get("loja")]
        voce, tem = "A loja", "A loja tem"
    else:
        meus, voce, tem = ligs, "As lojas", "As lojas têm"
    n = numeros(meus, hoje)
    oi = f", {nome}" if nome else ""
    ag = f" 📅 {plural(n['ag_hoje'], 'agendado', 'agendados')} para hoje." if n["ag_hoje"] else ""
    atras = f" ⚠️ {plural(n['ag_atras'], 'agendamento atrasado', 'agendamentos atrasados')} sem resultado." if n["ag_atras"] else ""
    quem_falta = ""
    if pap == "gerente" and n["sem"] and nomes_vend:
        cont = {}
        for l in meus:
            if l["status"] == "pendente" and l.get("responsavel_id"):
                cont[l["responsavel_id"]] = cont.get(l["responsavel_id"], 0) + 1
        top = sorted(cont.items(), key=lambda x: -x[1])[:3]
        if top:
            quem_falta = " Sem contato: " + ", ".join(f"{nomes_vend.get(i, '?')} {c}" for i, c in top) + "."

    if turno == "manha1":
        titulo = f"🦊 Bom dia{oi}!"
        if n["ontem"]:
            corpo = f"{voce} {'recebeu' if pap != 'gerente_todas' and pap != 'admin' else 'receberam'} {plural(n['ontem'], 'cliente que cotou', 'clientes que cotaram')} ontem. Bora começar as ligações?"
        elif n["sem"]:
            corpo = f"{tem} {plural(n['sem'], 'cliente esperando contato', 'clientes esperando contato')}. Bora começar?"
        elif n["ag_hoje"] or n["ag_atras"]:
            corpo = "Bora confirmar os agendados pelo WhatsApp?"
        else:
            return None
        corpo += ag + atras
    elif turno == "manha2":
        if not (n["sem"] or n["nao"] or n["ag_hoje"]):
            return None
        titulo = f"🦊 {nome + ', como' if nome else 'Como'} estão as ligações?"
        partes = []
        if n["sem"]:
            partes.append(f"Ainda {'falta' if n['sem'] == 1 else 'faltam'} {plural(n['sem'], 'cliente sem contato', 'clientes sem contato')}.")
        if n["nao"]:
            partes.append(f"{plural(n['nao'], 'não atendeu', 'não atenderam')}: que tal um WhatsApp?")
        corpo = " ".join(partes) + ag + quem_falta
    elif turno == "tarde1":
        if not (n["sem"] or n["nao"] or n["ag_hoje"] or n["ag_atras"]):
            return None
        titulo = f"🦊 Boa tarde{oi}!"
        corpo = ("Vamos concluir as ligações de hoje? " + (f"{tem} {plural(n['sem'], 'cliente sem contato', 'clientes sem contato')}" if n["sem"] else "Todos já tiveram contato 👏") +
                 (f" e {plural(n['nao'], 'que não atendeu', 'que não atenderam')}" if n["nao"] else "") + "." +
                 (f" 📅 {plural(n['ag_hoje'], 'agendado', 'agendados')} para hoje: já {'veio' if n['ag_hoje'] == 1 else 'vieram'}?" if n["ag_hoje"] else "") + atras + quem_falta)
    else:  # tarde2
        if not (n["sem"] or n["nao"]):
            return None
        titulo = f"🦊 Reta final do dia{oi}!"
        corpo = (f"Ainda dá tempo: {'falta' if n['sem'] + n['nao'] == 1 else 'faltam'} {plural(n['sem'], 'cliente sem contato', 'clientes sem contato')}" +
                 (f" e {plural(n['nao'], 'que não atendeu', 'que não atenderam')} (manda um WhatsApp!)" if n["nao"] else "") + ". Vamos lá! 💪" + quem_falta)
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

        inscs = sb_get(cli, chave, "push_inscricoes?select=id,perfil_id,endpoint,p256dh,auth,falhas")
        print(f"📱 Aparelhos com aviso: {len(inscs)}")
        DETALHES.update(turno=turno, aparelhos=len(inscs), chave_pronta=True)
        if not inscs:
            print("✅ Fim (ninguém ligou os avisos ainda).")
            return 0
        ids = sorted({i["perfil_id"] for i in inscs})
        perfis = {p["id"]: p for p in sb_get(cli, chave, "perfis?select=id,nome,apelido,loja,papel_ligacoes,ativo,ferias,funcoes"
                                                         f"&id=in.({','.join(ids)})")}
        desde = (hoje - timedelta(days=DIAS)).isoformat()
        ligs = sb_get(cli, chave, "ligacoes?select=id,loja,status,data_cotacao,agendado_para,responsavel_id"
                                  f"&data_cotacao=gte.{desde}&order=id")
        vend = sb_get(cli, chave, "perfis?select=id,nome,apelido&papel_ligacoes=eq.vendedor")
        nomes_vend = {v["id"]: nome_curto(v) for v in vend}

        avisos = {pid: montar_aviso(turno, perfis[pid], ligs, hoje, nomes_vend) for pid in ids if pid in perfis}
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
