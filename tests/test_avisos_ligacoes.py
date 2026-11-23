"""Testes do robô dos avisos (sem rede: o Supabase e o serviço de avisos são imitados)."""
import base64
import json
import os
import sys
from datetime import date, datetime
from urllib.parse import unquote

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import avisos_ligacoes as av  # noqa: E402

HOJE = date(2026, 11, 23)


# ── O "aparelho": abre o aviso como o navegador faria (RFC 8291) ──
class Aparelho:
    def __init__(self):
        self.k = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        self.pub = self.k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)

    def insc(self, endpoint="https://fcm.googleapis.com/fcm/send/abc"):
        return {"id": 1, "perfil_id": "u-fel", "endpoint": endpoint, "p256dh": av.b64u(self.pub), "auth": av.b64u(self.auth), "falhas": 0}

    def abrir(self, corpo: bytes) -> bytes:
        salt, rs, idlen = corpo[:16], int.from_bytes(corpo[16:20], "big"), corpo[20]
        as_pub = corpo[21:21 + idlen]
        assert rs == 4096 and idlen == 65
        comp = self.k.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
        ikm = av._hkdf(self.auth, comp, b"WebPush: info\x00" + self.pub + as_pub, 32)
        cek = av._hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = av._hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
        claro = AESGCM(cek).decrypt(nonce, corpo[21 + idlen:], None)
        assert claro.endswith(b"\x02")
        return claro[:-1]


def test_criptografia_o_aparelho_consegue_abrir():
    ap = Aparelho()
    corpo = av.criptografar("Bom dia, Felipe! 🦊".encode(), av.b64u(ap.pub), av.b64u(ap.auth))
    assert ap.abrir(corpo).decode() == "Bom dia, Felipe! 🦊"
    # outro aparelho não abre
    try:
        Aparelho().abrir(corpo)
        assert False, "outro aparelho abriu"
    except Exception:
        pass


def test_criptografia_igual_ao_exemplo_oficial_rfc8291():
    # Exemplo do Apêndice A da RFC 8291 (o mesmo padrão que Chrome, Firefox, Edge e Safari usam)
    efemera = av.chave_privada("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw")
    corpo = av.criptografar(b"When I grow up, I want to be a watermelon",
                            "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4",
                            "BTBZMqHH6r4Tts7J_aSIgg", salt=av.de_b64u("DGv6ra1nlYgDCS1FRnbzlw"), efemera=efemera)
    assert av.b64u(corpo) == ("DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")

def test_assinatura_vapid_valida():
    pub, priv = av.nova_chave()
    jwt = av.jwt_vapid("https://fcm.googleapis.com/fcm/send/abc", priv, agora=1_000_000)
    cab, corpo, ass = jwt.split(".")
    claims = json.loads(av.de_b64u(corpo))
    assert claims == {"aud": "https://fcm.googleapis.com", "exp": 1_000_000 + 12 * 3600, "sub": av.SITE}
    raw = av.de_b64u(ass)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    chave_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), av.de_b64u(pub))
    chave_pub.verify(der, f"{cab}.{corpo}".encode(), ec.ECDSA(hashes.SHA256()))   # dá erro se a assinatura não bater


def test_turno_pelo_horario():
    t = lambda h, m=0: av.turno_do_horario(datetime(2026, 11, 23, h, m))
    assert (t(8), t(10), t(14), t(16, 30)) == ("manha1", "manha2", "tarde1", "tarde2")
    assert (t(9, 40), t(12, 10), t(15, 40)) == ("manha2", "tarde1", "tarde2")


FEL = {"id": "u-fel", "nome": "Felipe Seixas", "apelido": "Felipe", "loja": "MATRIZ", "papel_ligacoes": "vendedor", "ativo": True, "ferias": False, "funcoes": []}
MAR = {"id": "u-mar", "nome": "Marcos", "apelido": "Marcos", "loja": "MATRIZ", "papel_ligacoes": "vendedor", "ativo": True, "ferias": False, "funcoes": []}
WAG = {"id": "u-wag", "nome": "Wagner Raiol", "apelido": "Wagner", "loja": "MATRIZ", "papel_ligacoes": "gerente", "ativo": True, "ferias": False, "funcoes": []}
JON = {"id": "u-jon", "nome": "Jonathan Lemes", "apelido": "Jonathan", "loja": None, "papel_ligacoes": "gerente", "ativo": True, "ferias": False, "funcoes": []}
L = lambda i, resp, st, d="2026-11-22", ag=None, loja="MATRIZ": {"id": i, "loja": loja, "status": st, "data_cotacao": d, "agendado_para": ag, "responsavel_id": resp}
LIGS = [L(1, "u-fel", "pendente"), L(2, "u-fel", "pendente"), L(3, "u-fel", "nao_atende"), L(4, "u-fel", "agendou", "2026-11-20", "2026-11-23"),
        L(5, "u-fel", "agendou", "2026-11-19", "2026-11-21"), L(6, "u-mar", "pendente"), L(7, "u-mar", "venda_ganha", "2026-11-21"),
        L(8, "u-out", "pendente", loja="CACOAL")]
NOMES = {"u-fel": "Felipe", "u-mar": "Marcos"}


def test_avisos_do_vendedor():
    a = av.montar_aviso("manha1", FEL, LIGS, HOJE)
    assert a["titulo"] == "🦊 Bom dia, Felipe!"
    assert "Você recebeu 3 clientes que cotaram ontem" in a["corpo"] and "1 agendado para hoje" in a["corpo"] and "1 agendamento atrasado" in a["corpo"]
    a = av.montar_aviso("manha2", FEL, LIGS, HOJE)
    assert "Felipe, como estão" in a["titulo"] and "faltam 2 clientes sem contato" in a["corpo"] and "1 não atendeu: que tal um WhatsApp?" in a["corpo"]
    a = av.montar_aviso("tarde1", FEL, LIGS, HOJE)
    assert a["titulo"] == "🦊 Boa tarde, Felipe!" and "Vamos concluir" in a["corpo"] and "já veio?" in a["corpo"]
    a = av.montar_aviso("tarde2", FEL, LIGS, HOJE)
    assert "Reta final" in a["titulo"] and "faltam 2 clientes sem contato e 1 que não atendeu" in a["corpo"]
    assert a["url"].endswith("/ligacoes.html")


def test_so_numeros_sem_dados_de_cliente():
    for t in ("manha1", "manha2", "tarde1", "tarde2"):
        a = av.montar_aviso(t, FEL, LIGS + [dict(L(99, "u-fel", "pendente"), cliente="Lucia Mendes", telefone="69 99999-0000")], HOJE)
        assert "Lucia" not in json.dumps(a) and "9999" not in json.dumps(a)


def test_sem_nada_a_avisar_nao_manda():
    tudo_feito = [L(1, "u-fel", "venda_ganha"), L(2, "u-fel", "sem_interesse")]
    assert av.montar_aviso("manha2", FEL, tudo_feito, HOJE) is None
    assert av.montar_aviso("tarde2", FEL, tudo_feito, HOJE) is None
    assert av.montar_aviso("manha1", FEL, [], HOJE) is None


def test_ferias_e_desativado_nao_recebem():
    assert av.montar_aviso("manha1", dict(FEL, ferias=True), LIGS, HOJE) is None
    assert av.montar_aviso("manha1", dict(FEL, ativo=False), LIGS, HOJE) is None


def test_gerente_ve_a_loja_e_quem_falta():
    a = av.montar_aviso("manha2", WAG, LIGS, HOJE, NOMES)
    assert "faltam 3 clientes sem contato" in a["corpo"] and "Sem contato: Felipe 2, Marcos 1" in a["corpo"]
    a = av.montar_aviso("manha1", JON, LIGS, HOJE, NOMES)
    assert "As lojas receberam 5 clientes" in a["corpo"]


# ── Rodada completa com a rede imitada ──
def _rodar(conf_existe=True, status_push=201, dry=False, turno="manha1", via_rodar=False):
    ap = Aparelho()
    reg = {"push": [], "config": [], "patch": [], "delete": []}
    pub, priv = av.nova_chave()

    def responder(req: httpx.Request):
        u = unquote(str(req.url))
        if u.startswith(av.SUPABASE_URL):
            if "/robo_execucoes" in u:
                reg.setdefault("rodadas", []).append(json.loads(req.content)); return httpx.Response(201)
            if "/push_config" in u:
                if req.method == "POST":
                    reg["config"].append(json.loads(req.content)); return httpx.Response(201)
                return httpx.Response(200, json=[{"chave_publica": pub, "chave_privada": priv}] if conf_existe else [])
            if "/push_inscricoes" in u:
                if req.method == "PATCH":
                    reg["patch"].append(json.loads(req.content)); return httpx.Response(204)
                if req.method == "DELETE":
                    reg["delete"].append(u); return httpx.Response(204)
                return httpx.Response(200, json=[ap.insc()])
            if "/perfis" in u and "papel_ligacoes=eq.vendedor" in u:
                return httpx.Response(200, json=[FEL, MAR])
            if "/perfis" in u:
                return httpx.Response(200, json=[FEL])
            if "/ligacoes" in u:
                return httpx.Response(200, json=LIGS)
        if u.startswith("https://fcm.googleapis.com/"):
            assert req.headers["Content-Encoding"] == "aes128gcm" and req.headers["Authorization"].startswith("vapid t=")
            reg["push"].append(json.loads(ap.abrir(req.content)))
            return httpx.Response(status_push)
        raise AssertionError("chamada inesperada: " + req.method + " " + u)

    original = httpx.Client
    av.httpx.Client = lambda **kw: original(transport=httpx.MockTransport(responder))
    os.environ.update(SUPABASE_SERVICE_KEY="k", TURNO=turno, DRY_RUN="1" if dry else "")

    class DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 23, 8, 0, tzinfo=tz)
    dt_real, av.datetime = av.datetime, DT
    try:
        return (av.rodar() if via_rodar else av.main()), reg
    finally:
        av.httpx.Client = original
        av.datetime = dt_real
        os.environ["DRY_RUN"] = ""
        os.environ["TURNO"] = ""


def test_rodada_envia_e_o_aparelho_le():
    codigo, reg = _rodar()
    assert codigo == 0 and len(reg["push"]) == 1
    assert reg["push"][0]["titulo"] == "🦊 Bom dia, Felipe!" and reg["patch"][0]["falhas"] == 0


def test_primeira_vez_cria_a_chave():
    codigo, reg = _rodar(conf_existe=False)
    assert codigo == 0 and len(reg["config"]) == 1 and len(av.de_b64u(reg["config"][0]["chave_publica"])) == 65


def test_aparelho_que_desligou_e_removido():
    codigo, reg = _rodar(status_push=410)
    assert codigo == 0 and len(reg["delete"]) == 1


def test_modo_teste_nao_envia():
    codigo, reg = _rodar(dry=True)
    assert codigo == 0 and reg["push"] == [] and reg["patch"] == []


def test_rodada_fica_registrada_para_o_monitor():
    codigo, reg = _rodar(via_rodar=True)
    r = reg["rodadas"][-1]
    assert codigo == 0 and r["robo"] == "avisos_ligacoes" and r["ok"] is True
    assert r["detalhes"]["enviados"] == 1 and r["detalhes"]["turno"] == "manha1" and r["detalhes"]["aparelhos"] == 1

if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
