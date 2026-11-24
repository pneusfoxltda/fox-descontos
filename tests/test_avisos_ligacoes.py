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


def test_bom_dia_espera_ate_as_8h():
    t = lambda h, m: datetime(2026, 11, 23, h, m, tzinfo=av.TZ_LOJA)
    assert av.esperar_ate_8h(t(7, 48), "manha1", False) == 12 * 60
    assert av.esperar_ate_8h(t(8, 2), "manha1", False) == 0          # já passou das 8h: manda na hora
    assert av.esperar_ate_8h(t(7, 48), "manha1", True) == 0          # rodada à mão / teste não espera
    assert av.esperar_ate_8h(t(9, 47), "manha2", False) == 0


def test_turno_pelo_horario():
    t = lambda h, m=0: av.turno_do_horario(datetime(2026, 11, 23, h, m))
    assert (t(8), t(10), t(14), t(16, 30)) == ("manha1", "manha2", "tarde1", "tarde2")
    assert (t(9, 40), t(12, 10), t(15, 40)) == ("manha2", "tarde1", "tarde2")


FEL = {"id": "u-fel", "nome": "Felipe Seixas", "apelido": "Felipe", "loja": "MATRIZ", "papel_ligacoes": "vendedor", "ativo": True, "ferias": False, "funcoes": []}
MAR = {"id": "u-mar", "nome": "Marcos", "apelido": "Marcos", "loja": "MATRIZ", "papel_ligacoes": "vendedor", "ativo": True, "ferias": False, "funcoes": []}
WAG = {"id": "u-wag", "nome": "Wagner Raiol", "apelido": "Wagner", "loja": "MATRIZ", "papel_ligacoes": "gerente", "ativo": True, "ferias": False, "funcoes": []}
LUC = {"id": "u-luc", "nome": "Luciana", "apelido": "Luciana", "loja": "CACOAL", "papel_ligacoes": "gerente", "ativo": True, "ferias": False, "funcoes": []}
JON = {"id": "u-jon", "nome": "Jonathan Lemes", "apelido": "Jonathan", "loja": None, "papel_ligacoes": "gerente", "ativo": True, "ferias": False, "funcoes": []}
OUT = {"id": "u-out", "nome": "Lurdes", "apelido": "Lurdes", "loja": "CACOAL", "papel_ligacoes": "vendedor", "ativo": True, "ferias": False, "funcoes": []}
L = lambda i, resp, st, d="2026-11-22", ag=None, loja="MATRIZ", valor=500, por=None: {
    "id": i, "cotacao": str(950000 + i), "loja": loja, "status": st, "data_cotacao": d, "agendado_para": ag,
    "responsavel_id": resp, "valor": valor, "status_por": por if por is not None else (None if st == "pendente" else "Fulano")}
LIGS = [L(1, "u-fel", "pendente", valor=3370.68), L(2, "u-fel", "pendente"), L(3, "u-fel", "nao_atende"), L(4, "u-fel", "agendou", "2026-11-20", "2026-11-23"),
        L(5, "u-fel", "agendou", "2026-11-19", "2026-11-21"), L(6, "u-mar", "pendente"), L(7, "u-mar", "venda_ganha", "2026-11-21"),
        L(8, "u-out", "pendente", loja="CACOAL"), L(9, "u-out", "pendente", loja="CACOAL")]
CTX = {"vendedores": [FEL, MAR, OUT], "gerentes": {"MATRIZ": "Wagner", "CACOAL": "Luciana"}, "ativos_hoje": {"felipe"}}


def test_avisos_do_vendedor():
    a = av.montar_aviso("manha1", FEL, LIGS, HOJE, CTX)
    assert a["titulo"] == "🦊 Bom dia, Felipe!"
    assert "Te mandamos 3 clientes hoje" in a["corpo"] and "O de maior valor é R$ 3.370,68 (cotação 950001)" in a["corpo"]
    assert "1 cliente agendado" in a["corpo"] and "1 agendamento passou" in a["corpo"] and "conto contigo" in a["corpo"]
    a = av.montar_aviso("manha2", FEL, LIGS, HOJE, CTX)
    assert a["titulo"] == "🦊 Oi, Felipe!" and "estão pendentes 2 clientes de hoje. Aconteceu algo?" in a["corpo"]
    assert "nenhum agendamento: vamos mudar a estratégia?" in a["corpo"] and "me conte na Anotação" in a["corpo"]
    a = av.montar_aviso("tarde1", FEL, LIGS, HOJE, CTX)
    assert a["titulo"] == "🦊 Boa tarde, Felipe!" and "Dos 3 clientes de hoje, você já falou com 1 e ainda faltam 2 clientes" in a["corpo"]
    assert "até as 17h" in a["corpo"] and "1 não atendeu: tente pelo WhatsApp" in a["corpo"]
    a = av.montar_aviso("tarde2", FEL, LIGS, HOJE, CTX)
    assert a["titulo"] == "🦊 Fim do dia, Felipe" and "você falou com 1 dos 3 clientes de hoje (1 ligação sem agendar" in a["corpo"]
    assert "Se precisar de ajuda, me avise" in a["corpo"] and a["url"].endswith("/ligacoes.html")


def test_sempre_4_mensagens_por_dia():
    tudo_feito = [L(1, "u-fel", "venda_ganha"), L(2, "u-fel", "sem_interesse")]
    for p in (FEL, WAG, JON):
        for t in ("manha1", "manha2", "tarde1", "tarde2"):
            assert av.montar_aviso(t, p, LIGS, HOJE, CTX), (p["id"], t)
            assert av.montar_aviso(t, p, tudo_feito, HOJE, CTX), (p["id"], t)     # mesmo com tudo feito, avisa (parabeniza)
    assert "Mandou bem" in av.montar_aviso("manha2", FEL, tudo_feito, HOJE, CTX)["corpo"]


def test_sem_dados_de_cliente():
    for t in ("manha1", "manha2", "tarde1", "tarde2"):
        for p in (FEL, WAG, JON):
            a = av.montar_aviso(t, p, LIGS + [dict(L(99, "u-fel", "pendente"), cliente="Zuleica Mendes", telefone="69 99999-0000")], HOJE, CTX)
            assert a is None or ("Zuleica" not in json.dumps(a) and "9999" not in json.dumps(a))


def test_sem_clientes_nao_manda():
    assert av.montar_aviso("manha1", FEL, [], HOJE, CTX) is None
    assert av.montar_aviso("manha1", FEL, [L(1, "u-mar", "pendente")], HOJE, CTX) is None   # nenhum cliente é dele


def test_ferias_e_desativado_nao_recebem():
    assert av.montar_aviso("manha1", dict(FEL, ferias=True), LIGS, HOJE, CTX) is None
    assert av.montar_aviso("manha1", dict(FEL, ativo=False), LIGS, HOJE, CTX) is None


def test_gerente_cobra_cada_vendedor():
    a = av.montar_aviso("manha1", WAG, LIGS, HOJE, CTX)
    assert "Sua loja recebeu hoje 4 clientes (Felipe 3, Marcos 1)" in a["corpo"]
    a = av.montar_aviso("manha2", WAG, LIGS, HOJE, CTX)
    assert "Marcos ainda não falou com nenhum (1)" in a["corpo"] and "Felipe falou com 1 (faltam 2 clientes)" in a["corpo"]
    assert "Marcos ainda não entrou hoje no sistema de ligações" in a["corpo"]
    a = av.montar_aviso("manha2", LUC, LIGS, HOJE, CTX)
    assert "ainda não entraram em contato com nenhum dos 2 clientes de hoje" in a["corpo"]
    a = av.montar_aviso("tarde2", WAG, LIGS, HOJE, CTX)
    assert "Marcos não entrou hoje no sistema de ligações: vamos cobrar?" in a["corpo"] and "Felipe não entrou" not in a["corpo"]
    assert "Por vendedor: Marcos ainda não falou com nenhum (1) · Felipe falou com 1" in a["corpo"]


def test_jonathan_cobra_as_lojas():
    a = av.montar_aviso("manha1", JON, LIGS, HOJE, CTX)
    assert "Hoje as lojas receberam 6 clientes: MATRIZ 4, CACOAL 2" in a["corpo"]
    a = av.montar_aviso("manha2", JON, LIGS, HOJE, CTX)
    assert a["titulo"] == "🦊 Opa, Jonathan!" and "A loja CACOAL (gerente: Luciana) ainda não falou com nenhum cliente" in a["corpo"]
    assert "CACOAL 0/2 (0%) · MATRIZ 1/4 (25%)" in a["corpo"] and "Abaixo de 30%: MATRIZ (gerente: Wagner)" in a["corpo"]
    a = av.montar_aviso("tarde2", JON, LIGS, HOJE, CTX)
    assert "1 de 6 clientes com contato (17%)" in a["corpo"] and "Por loja: CACOAL 0/2 (0%)" in a["corpo"]


def test_robo_nao_conta_como_contato():
    ligs = [L(1, "u-fel", "agendou", ag="2026-11-25", por="Robô (Kommo)"), L(2, "u-fel", "pendente")]
    a = av.montar_aviso("tarde1", FEL, ligs, HOJE, CTX)
    assert "você já falou com 0" in a["corpo"]


# ── Rodada completa com a rede imitada ──
def _rodar(conf_existe=True, status_push=201, dry=False, turno="manha1", via_rodar=False, ja=()):
    ap = Aparelho()
    reg = {"push": [], "config": [], "patch": [], "delete": []}
    pub, priv = av.nova_chave()

    def responder(req: httpx.Request):
        u = unquote(str(req.url))
        if u.startswith(av.SUPABASE_URL):
            if "/robo_execucoes" in u:
                if req.method == "GET":
                    return httpx.Response(200, json=[{"detalhes": {"turno": t}} for t in ja])
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
            if "/perfis" in u:
                return httpx.Response(200, json=[FEL, MAR, WAG, JON])
            if "/ligacoes_historico" in u:
                return httpx.Response(200, json=[{"quem": "Felipe"}])
            if "/avisos_fernanda" in u:
                if req.method == "POST":
                    reg.setdefault("fernanda", []).extend(json.loads(req.content)); return httpx.Response(201)
                return httpx.Response(204)
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
    # Todos ficam com a mensagem guardada para a Fernanda mostrar na página (mesmo sem aviso ligado)
    quem = {m["perfil_id"] for m in reg["fernanda"]}
    assert quem == {"u-fel", "u-mar", "u-wag", "u-jon"} and all(m["turno"] == "manha1" and m["dia"] == "2026-11-23" for m in reg["fernanda"])


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

def test_mesmo_aviso_nao_sai_duas_vezes_no_dia():
    codigo, reg = _rodar(ja=("manha1",))
    assert codigo == 0 and reg["push"] == []            # o "bom dia" de hoje já tinha saído
    codigo, reg = _rodar(ja=("manha1",), turno="manha2")
    assert codigo == 0 and len(reg["push"]) == 1        # o próximo turno sai normalmente

if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
