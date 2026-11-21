"""Testes do conferir_vendas_movere.py (sem rede: Analytics e Supabase imitados).
Rodar:  python -m pytest tests/  (ou  python tests/test_conferir_vendas_movere.py)"""
import json
import os
import sys
from datetime import date

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import conferir_vendas_movere as cv  # noqa: E402

CSV = (
    "Data Emissão,Cliente,Telefone Celular,Telefone Comercial,Valor Total\n"
    "19/11/2026,Cliente A,(69) 99999-1234,,\"1.250,50\"\n"
    "20/11/2026,Cliente A,69999991234,,100\n"
    "18/11/2026,Cliente B,,(69) 3217-0000,300\n"
    "21/11/2026,Cliente C,69 98888-7777,,\"80,00\"\n"
)


def linhas():
    import csv, io
    return list(csv.reader(io.StringIO(CSV)))


def test_chave_tel():
    assert cv.chave_tel("(69) 99999-1234") == "99991234"
    assert cv.chave_tel("123") == ""
    assert cv.chaves_tel("69 99999-1234 / 69 3217-0000") == {"99991234", "32170000"}


def test_regras_do_cruzamento():
    vendas = cv.vendas_por_telefone(linhas())
    descontos = [
        # comprou no MESMO dia do cadastro → marca (e pega a 1ª venda)
        {"id": "a", "numero": "1", "telefone_cliente": "69 99999-1234", "criado_em": "2026-11-19T15:00:00+00:00"},
        # comprou ANTES do cadastro (18/11) → não marca
        {"id": "b", "numero": "2", "telefone_cliente": "3217-0000 ramal", "criado_em": "2026-11-19T12:00:00+00:00"},
        # comprou dias DEPOIS (21/11), desconto vencido → marca mesmo assim
        {"id": "c", "numero": "3", "telefone_cliente": "(69)98888-7777", "criado_em": "2026-11-10T12:00:00+00:00"},
        # telefone que não comprou → não marca
        {"id": "d", "numero": "4", "telefone_cliente": "69 91111-2222", "criado_em": "2026-11-01T12:00:00+00:00"},
        # 23h em Porto Velho (03h UTC do dia seguinte) conta como o dia 19
        {"id": "e", "numero": "5", "telefone_cliente": "99999-1234", "criado_em": "2026-11-20T03:00:00+00:00"},
    ]
    m = {x["id"]: x for x in cv.cruzar(descontos, vendas)}
    assert set(m) == {"a", "c", "e"}
    assert m["a"]["venda_movere_em"] == "2026-11-19" and m["a"]["venda_movere_valor"] == 1250.5
    assert m["c"]["venda_movere_em"] == "2026-11-21" and m["c"]["venda_movere_valor"] == 80.0
    assert m["e"]["venda_movere_em"] == "2026-11-19"


def test_fluxo_completo_com_rede_imitada(capsys=None):
    chamadas = {"patch": []}

    def responder(req: httpx.Request):
        u = str(req.url)
        if u.startswith(cv.SUPABASE_URL) and req.method == "GET":
            assert "venda_movere=is.false" in u and "tipo=neq.conc" in u and "liberado=not.is.true" in u
            return httpx.Response(200, json=[
                {"id": "a", "numero": "777", "tipo": "orcamento", "telefone_cliente": "69 99999-1234",
                 "criado_em": "2026-11-19T15:00:00+00:00"},
                {"id": "z", "numero": "888", "tipo": "orcamento", "telefone_cliente": "sem número",
                 "criado_em": "2026-11-19T15:00:00+00:00"},
            ])
        if u.startswith(cv.SUPABASE_URL) and req.method == "PATCH":
            chamadas["patch"].append((u, json.loads(req.content)))
            return httpx.Response(204)
        if u.endswith("/gdc/account/login"):
            return httpx.Response(200, headers={"X-GDC-AuthSST": "sst"}, json={})
        if u.endswith("/gdc/account/token"):
            assert req.headers["X-GDC-AuthSST"] == "sst"
            return httpx.Response(200, headers={"X-GDC-AuthTT": "tt"}, json={})
        assert req.headers.get("X-GDC-AuthTT") == "tt" or "/download/" in u
        if f"/obj/{cv.DF_DIA}/elements" in u:
            titulo = req.url.params["filter"]
            if titulo in ("19/11/2026", "20/11/2026"):
                return httpx.Response(200, json={"attributeElements": {"elements": [
                    {"title": titulo, "uri": f"/gdc/md/x/obj/{cv.DF_DIA}/elements?id={titulo[:2]}"}]}})
            return httpx.Response(200, json={"attributeElements": {"elements": []}})
        if u.endswith(f"/obj/{cv.REL_VENDAS}"):
            return httpx.Response(200, json={"report": {"content": {"definitions": ["/gdc/md/x/obj/def1"]}}})
        if u.endswith("/obj/def1"):
            return httpx.Response(200, json={"reportDefinition": {"content": {"filters": []}}})
        if u.endswith("/execute/raw"):
            corpo = json.loads(req.content)
            filtros = corpo["report_req"]["definitionContent"]["content"]["reportDefinition"]["content"]["filters"]
            assert len(filtros) == 1 and f"obj/{cv.ATTR_DIA}" in filtros[0]["expression"]
            return httpx.Response(201, json={"uri": "/gdc/exporter/result/1"})
        if u.endswith("/gdc/exporter/result/1"):
            chamadas.setdefault("poll", 0)
            chamadas["poll"] += 1
            if chamadas["poll"] == 1:
                return httpx.Response(202)
            return httpx.Response(302, headers={"Location": "https://storage.exemplo/download/x.csv"})
        if u == "https://storage.exemplo/download/x.csv":
            assert "X-GDC-AuthTT" not in req.headers   # não manda o token para outro site
            return httpx.Response(200, content=("﻿" + CSV).encode("utf-8"))
        raise AssertionError("chamada inesperada: " + req.method + " " + u)

    original = httpx.Client
    cv.time.sleep = lambda s: None
    cv.httpx.Client = lambda **kw: original(transport=httpx.MockTransport(responder))
    os.environ.update(SUPABASE_SERVICE_KEY="k", ANALYTICS_LOGIN="l", ANALYTICS_SENHA="s")
    hoje_real = cv.datetime

    class DT(hoje_real):
        @classmethod
        def now(cls, tz=None):
            return hoje_real(2026, 11, 21, 12, 0, tzinfo=tz)
    cv.datetime = DT
    try:
        assert cv.main() == 0
    finally:
        cv.httpx.Client = original
        cv.datetime = hoje_real
    assert len(chamadas["patch"]) == 1
    url, corpo = chamadas["patch"][0]
    assert url.endswith("id=eq.a")
    assert corpo["venda_movere"] is True and corpo["venda_movere_em"] == "2026-11-19"
    assert corpo["venda_movere_por"] == "telefone"


def test_sem_segredos_nao_roda():
    for n in ("SUPABASE_SERVICE_KEY", "ANALYTICS_LOGIN", "ANALYTICS_SENHA"):
        os.environ.pop(n, None)
    assert cv.main() == 1


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
