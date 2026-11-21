"""Testes do ligacoes_lojas.py (sem rede: Kommo, Analytics e Supabase imitados).
Rodar:  python tests/test_ligacoes_lojas.py"""
import csv
import io
import json
from datetime import datetime
import os
import sys
from datetime import date
from urllib.parse import unquote

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import conferir_vendas_movere as cv  # noqa: E402
import ligacoes_lojas as ll  # noqa: E402

# Cotação, Cliente, Telefone, Periodo, Estabelecimento, NomeOperador, Vendedor, Item, Valor Total
COT = """Cotação,Cliente,Telefone,Periodo,Estabelecimento,NomeOperador,Vendedor,Item,Valor Total
5001,Cliente Novo,69 98888-0001,20/11/2026,CACOAL,Maria,Maria,255/50R20 LISO ALENZA,"300,00"
5001,Cliente Novo,69 98888-0001,20/11/2026,CACOAL,Maria,Maria,Válvula,"20,50"
5002,Já Comprou,69 98888-0002,20/11/2026,CACOAL,Maria,Maria,Pneu B,100
5003,Agendado Kommo,69 98888-0003,20/11/2026,C.AUTO VLH,João,João,Pneu C,200
5004,Repetido Mais Novo,69 98888-0001,20/11/2026,CACOAL,Maria,Maria,Pneu D,50
5005,Atacado,69 98888-0005,20/11/2026,ATACADO,Zé,Zé,Pneu E,999
5006,Outra Loja,69 98888-0006,20/11/2026,C.AUTO VLH,João,João,Pneu F,"1.250,00"
"""
VENDAS = """Data Emissão,Cliente,Telefone Celular,Telefone Comercial,Valor Total
20/11/2026,Já Comprou,69 98888-0002,,100
20/11/2026,Comprou Depois,,(69) 3333-0010,500
19/11/2026,Comprou Antes,69 98888-0011,,80
"""


def ler(txt):
    return list(csv.reader(io.StringIO(txt)))


def test_cotacoes_agrupa_e_soma():
    c = {x["cotacao"]: x for x in ll.cotacoes(ler(COT))}
    assert c["5001"]["valor"] == 320.5 and c["5006"]["valor"] == 1250.0
    assert c["5001"]["data"] == date(2026, 11, 20) and c["5001"]["loja"] == "CACOAL"
    assert c["5001"]["medida"] == "255/50R20" and c["5002"]["medida"] is None
    assert ll.medida_de("PNEU 7.50-16 CARGA") == "7.50-16" and ll.medida_de("31X10.50R15 AT") == "31X10.50R15"


def test_escolher_novas_regras():
    vendas = cv.vendas_por_telefone(ler(VENDAS))
    agendados = {cv.chave_tel("69 98888-0003")}
    novas, motivos = ll.escolher_novas(ll.cotacoes(ler(COT)), vendas, agendados, set(), set())
    assert [c["cotacao"] for c in novas] == ["5001", "5006"]
    assert motivos == {"comprou": 1, "agendou": 1, "repetido": 1, "ja_importada": 0, "loja_ignorada": 1}
    # já importada e telefone que já está aberto na lista
    novas2, m2 = ll.escolher_novas(ll.cotacoes(ler(COT)), vendas, agendados, {"5001"}, {cv.chave_tel("69 98888-0006")})
    assert [c["cotacao"] for c in novas2] == ["5004"] and m2["ja_importada"] == 1


def test_reconferir():
    vendas = cv.vendas_por_telefone(ler(VENDAS))
    abertas = [
        {"id": 1, "telefone": "(69) 3333-0010", "data_cotacao": "2026-11-18", "status": "pendente"},       # comprou 20/11
        {"id": 2, "telefone": "69 98888-0011", "data_cotacao": "2026-11-20", "status": "nao_atende"},      # comprou ANTES → não
        {"id": 3, "telefone": "69 98888-0003", "data_cotacao": "2026-11-18", "status": "retornar"},        # agendou
        {"id": 4, "telefone": "69 98888-0003", "data_cotacao": "2026-11-18", "status": "sem_interesse"},   # sem interesse não vira agendou
        {"id": 5, "telefone": "33330010", "data_cotacao": "2026-11-15", "status": "sem_interesse"},        # mas comprou → televendas
        {"id": 6, "telefone": "33330010", "data_cotacao": "2026-11-15", "status": "agendou"},              # agendou e comprou → televendas
        {"id": 7, "telefone": "33330010", "data_cotacao": "2026-11-15", "status": "venda_perdida"},        # perdida mas comprou → televendas
    ]
    m = {x["id"]: x for x in ll.reconferir(abertas, vendas, {cv.chave_tel("69 98888-0003")})}
    assert set(m) == {1, 3, 5, 6, 7}
    assert m[1]["status"] == "venda_televendas" and m[1]["comprou_em"] == "2026-11-20" and m[1]["quem"] == ll.ROBO_MOVERE
    assert m[5]["status"] == m[6]["status"] == m[7]["status"] == "venda_televendas"
    assert m[3]["status"] == "agendou" and m[3]["quem"] == ll.ROBO_KOMMO


def test_dias_para_importar():
    hoje = date(2026, 11, 23)  # segunda
    # primeira vez: desde 19/11 (quinta)
    assert ll.dias_para_importar(None, hoje) == [date(2026, 11, d) for d in (19, 20, 21, 22)]
    assert ll.dias_para_importar(None, date(2026, 11, 21)) == [date(2026, 11, 19), date(2026, 11, 20)]
    assert ll.dias_para_importar(date(2026, 11, 20), hoje) == [date(2026, 11, 21), date(2026, 11, 22)]
    assert ll.dias_para_importar(date(2026, 11, 22), hoje) == []
    assert ll.dias_para_importar(date(2026, 10, 1), date(2026, 12, 10))[0] == date(2026, 12, 3)   # no máximo 7 dias
    assert ll.dias_para_importar(date(2026, 10, 1), hoje)[0] == date(2026, 11, 19)              # nunca antes de 19/11


def _rodar_com_rede(dias_no_analytics, dry=False):
    reg = {"post_ligacoes": [], "patch": [], "hist": [], "rodadas": [], "logs": []}

    def responder(req: httpx.Request):
        u = unquote(str(req.url))
        if u.startswith(cv.SUPABASE_URL):
            if "/robo_execucoes" in u:
                reg["rodadas"].append(json.loads(req.content)); return httpx.Response(201)
            if "/ligacoes_historico" in u:
                reg["hist"].append(json.loads(req.content)); return httpx.Response(201)
            if req.method == "PATCH":
                reg["patch"].append((u, json.loads(req.content))); return httpx.Response(204)
            if req.method == "POST":
                reg["post_ligacoes"] += json.loads(req.content); return httpx.Response(201)
            if "select=medida&limit=1" in u:
                return httpx.Response(200, json=[])
            if "order=data_cotacao.desc" in u:
                return httpx.Response(200, json=[{"data_cotacao": "2026-11-19"}])
            if "status=in." in u:
                return httpx.Response(200, json=[{"id": 77, "cotacao": "5001", "telefone": "(69) 3333-0010", "tel_chave": "33330010",
                                                  "data_cotacao": "2026-11-19", "status": "pendente"}])
            if "select=cotacao" in u:
                return httpx.Response(200, json=[])
        if u.startswith(ll.KOMMO):
            assert req.headers["Authorization"] == "Bearer kommo"
            if "/leads" in u:
                return httpx.Response(200, json={"_embedded": {"leads": [{"_embedded": {"contacts": [{"id": 9}]}}]}, "_links": {}})
            if "/contacts" in u:
                return httpx.Response(200, json={"_embedded": {"contacts": [{"custom_fields_values": [
                    {"field_code": "PHONE", "values": [{"value": "+55 69 98888-0003"}]}]}]}})
        if u.endswith("/gdc/account/login"):
            return httpx.Response(200, headers={"X-GDC-AuthSST": "s"}, json={})
        if u.endswith("/gdc/account/token"):
            return httpx.Response(200, headers={"X-GDC-AuthTT": "t"}, json={})
        if f"/obj/{cv.DF_DIA}/elements" in u:
            t = req.url.params["filter"]
            els = [{"title": t, "uri": f"/el/{t}"}] if t in dias_no_analytics else []
            return httpx.Response(200, json={"attributeElements": {"elements": els}})
        if u.endswith(f"/obj/{ll.REL_COT}") or u.endswith(f"/obj/{ll.REL_VENDAS}"):
            rel = "cot" if u.endswith(str(ll.REL_COT)) else "ven"
            return httpx.Response(200, json={"report": {"content": {"definitions": [f"/def/{rel}"]}}})
        if "/def/" in u:
            return httpx.Response(200, json={"reportDefinition": {"content": {"filters": [], "rel": u[-3:]}}})
        if u.endswith(f"/obj/{ll.DASH_COT}"):
            return httpx.Response(200, json={"projectDashboard": {"content": {"filters": []}}})
        if u.endswith("/execute/raw"):
            rel = json.loads(req.content)["report_req"]["definitionContent"]["content"]["reportDefinition"]["content"]["rel"]
            return httpx.Response(201, json={"uri": f"/res/{rel}"})
        if u.endswith("/res/cot"):
            return httpx.Response(200, content=COT.encode())
        if u.endswith("/res/ven"):
            return httpx.Response(200, content=VENDAS.encode())
        raise AssertionError("chamada inesperada: " + req.method + " " + u)

    original, dt_real = httpx.Client, cv.datetime
    cv.httpx.Client = lambda **kw: original(transport=httpx.MockTransport(responder))
    ll.httpx.Client = cv.httpx.Client

    class DT(dt_real):
        @classmethod
        def now(cls, tz=None):
            return dt_real(2026, 11, 21, 9, 0, tzinfo=tz)
    cv.datetime = ll.datetime = DT
    os.environ.update(SUPABASE_SERVICE_KEY="k", ANALYTICS_LOGIN="l", ANALYTICS_SENHA="s", KOMMO_TOKEN="kommo",
                      DRY_RUN="1" if dry else "")
    for k in ll.RESUMO:
        ll.RESUMO[k] = None if k == "inicio" else 0
    try:
        return ll.rodar(), reg
    finally:
        cv.httpx.Client = ll.httpx.Client = original
        cv.datetime = ll.datetime = dt_real
        os.environ["DRY_RUN"] = ""


def test_fluxo_completo():
    codigo, reg = _rodar_com_rede({"20/11/2026", "21/11/2026"})
    assert codigo == 0
    assert sorted(x["cotacao"] for x in reg["post_ligacoes"]) == ["5001", "5006"]
    n = {x["cotacao"]: x for x in reg["post_ligacoes"]}["5001"]
    assert n["tel_chave"] == "88880001" and n["valor"] == 320.5 and n["data_cotacao"] == "2026-11-20"
    assert n["medida"] == "255/50R20"
    # completa a medida de quem já estava na lista sem ela
    assert any(c.get("medida") == "255/50R20" for _, c in reg["patch"])
    st = [c for _, c in reg["patch"] if "status" in c]
    assert len(st) == 1 and st[0]["status"] == "venda_televendas" and st[0]["comprou_em"] == "2026-11-20"
    assert reg["hist"][0]["quem"] == ll.ROBO_MOVERE
    assert reg["rodadas"][-1]["ok"] is True and reg["rodadas"][-1]["robo"] == "ligacoes_lojas"


def test_analytics_sem_o_dia_nao_importa_mas_reconfere():
    codigo, reg = _rodar_com_rede({"19/11/2026"})       # 20/11 ainda não chegou no Analytics
    assert codigo == 0 and reg["post_ligacoes"] == []


def test_modo_teste_nao_grava():
    codigo, reg = _rodar_com_rede({"20/11/2026"}, dry=True)
    assert codigo == 0 and reg["post_ligacoes"] == [] and reg["patch"] == [] and reg["hist"] == []
    assert reg["rodadas"][-1]["teste"] is True


def test_sem_token_kommo_falha_e_registra():
    os.environ.pop("KOMMO_TOKEN", None)
    os.environ.update(SUPABASE_SERVICE_KEY="", ANALYTICS_LOGIN="l", ANALYTICS_SENHA="s")
    assert ll.rodar() == 1


def test_data_do_campo_kommo():
    from datetime import date as D
    ts = int(datetime(2026, 11, 26, 14, 0, tzinfo=cv.TZ_LOJA).timestamp())
    assert ll.data_do_campo({"values": [{"value": ts}]}) == D(2026, 11, 26)
    assert ll.data_do_campo({"values": [{"value": str(ts)}]}) == D(2026, 11, 26)
    assert ll.data_do_campo({"values": [{"value": "2026-11-27T10:00:00-04:00"}]}) == D(2026, 11, 27)
    assert ll.data_do_campo({"values": [{"value": "Dia 28/11 às 9h"}]}).day == 28
    assert ll.data_do_campo({"values": [{"value": "sem data"}]}) is None
    assert ll.eh_campo_agendamento({"field_name": "Data do Agendamento"})
    assert not ll.eh_campo_agendamento({"field_name": "Aniversário"})


def test_reconferir_com_data_do_kommo():
    from datetime import date as D
    tel = "(69) 98888-0003"
    k = cv.chave_tel(tel)
    datas = {k: D(2026, 11, 26)}
    base = {"telefone": tel, "data_cotacao": "2026-11-19"}
    m = ll.reconferir([{**base, "id": 1, "status": "pendente"}], {}, {k}, datas)
    assert m == [{"id": 1, "status": "agendou", "quem": ll.ROBO_KOMMO, "agendado_para": "2026-11-26"}]
    # já agendou sem data (Kommo) → só completa a data
    m = ll.reconferir([{**base, "id": 2, "status": "agendou", "agendado_para": None}], {}, {k}, datas)
    assert m[0]["so_data"] and m[0]["agendado_para"] == "2026-11-26"
    # a loja marcou data mais antiga → fica a do Kommo (mais recente)
    assert ll.reconferir([{**base, "id": 3, "status": "agendou", "agendado_para": "2026-11-24"}], {}, {k}, datas)[0]["agendado_para"] == "2026-11-26"
    # a loja marcou data igual ou mais nova → não mexe
    assert ll.reconferir([{**base, "id": 4, "status": "agendou", "agendado_para": "2026-11-28"}], {}, {k}, datas) == []
    # já tem resultado (venda perdida) → não mexe
    assert ll.reconferir([{**base, "id": 5, "status": "venda_perdida"}], {}, {k}, datas) == []


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
