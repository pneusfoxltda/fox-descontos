"""Testes da venda pela API do Movere (sem rede). Rodar: python tests/test_movere_api.py
Números e telefones de mentira."""
import os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import movere_api as ma
import conferir_vendas_movere as cv


def nota(desc, valor, orc, cel, dia="2026-11-24T00:00:00"):
    return {"NF": {"descricaoentradaesaida": desc, "valortotalnota": valor, "dtaemissao": dia,
                   "Comercial": {"idorcamento": orc}, "Cliente": {"fonecelular": cel, "fonecom": ""}}}


def t_tipos_de_nota():
    assert ma.tipo_nota({"descricaoentradaesaida": "VENDA DE MERCADORIA ADQUIRIDA DE TERCEIROS"}) == "venda"
    assert ma.tipo_nota({"descricaoentradaesaida": "DEVOLUÇÃO DE VENDA"}) == "devolucao"
    assert ma.tipo_nota({"descricaoentradaesaida": "SAIDA DE TRANSFERENCIA"}) == "outra"
    assert ma.tipo_nota({"descricaoentradaesaida": "ENTRADA DE CARCAÇAS P/ REFORMA"}) == "outra"


def t_vendas_por_telefone_e_orcamento():
    ns = [ma.simplificar(nota("VENDA DE MERCADORIA", 1000.0, 5501, "(69) 9 9999-0001"), 1),
          ma.simplificar(nota("SAIDA DE TRANSFERENCIA", 9999.0, None, "(69) 9 9999-0002"), 1),
          ma.simplificar(nota("DEVOLUÇÃO DE VENDA", -50.0, 5501, "(69) 9 9999-0001"), 1)]
    tel, orc = ma.vendas_por_telefone(ns), ma.vendas_por_orcamento(ns)
    assert tel == {"99990001": [(date(2026, 11, 24), 1000.0)]}, tel   # transferência e devolução ficam de fora
    assert orc == {"5501": (date(2026, 11, 24), 1000.0)}, orc


def t_juntar_sem_repetir():
    a = {"1": [(date(2026, 11, 24), 10.0)]}
    b = {"1": [(date(2026, 11, 24), 10.0), (date(2026, 11, 25), 5.0)], "2": [(date(2026, 11, 25), 1.0)]}
    j = ma.juntar(a, b)
    assert j["1"] == [(date(2026, 11, 24), 10.0), (date(2026, 11, 25), 5.0)] and j["2"] == [(date(2026, 11, 25), 1.0)]


def t_cruzar_pelo_numero_do_orcamento():
    # desconto cadastrado em 24/11 (UTC 13h = 9h em Porto Velho), telefone diferente do da nota: acha pelo número
    d = [{"id": 1, "numero": "005501", "tipo": "orcamento", "telefone_cliente": "69 98888-7777", "criado_em": "2026-11-24T13:00:00Z"},
         {"id": 2, "numero": "777", "tipo": "orcamento", "telefone_cliente": "69 99999-0001", "criado_em": "2026-11-24T13:00:00Z"},
         {"id": 3, "numero": "888", "tipo": "os", "telefone_cliente": "69 91111-2222", "criado_em": "2026-11-25T13:00:00Z"}]
    tel = {"99990001": [(date(2026, 11, 24), 1000.0)]}
    orc = {"5501": (date(2026, 11, 24), 1000.0), "888": (date(2026, 11, 24), 50.0)}   # 888: venda ANTES do cadastro, não conta
    m = {x["id"]: x for x in cv.cruzar(d, tel, orc)}
    assert m[1]["por"] == "orçamento" and m[1]["venda_movere_valor"] == 1000.0
    assert m[2]["por"] == "telefone"
    assert 3 not in m


def t_sem_segredos_segue_sem_api():
    for n in ("MOVERE_API_AMBIENTE", "MOVERE_API_USUARIO", "MOVERE_API_SENHA"):
        os.environ.pop(n, None)
    assert ma.buscar(date(2026, 11, 24), date(2026, 11, 25), log=lambda *a: None) == ({}, {})


if __name__ == "__main__":
    n = 0
    for nome, f in list(globals().items()):
        if nome.startswith("t_"):
            f(); n += 1; print("OK", nome)
    print(f"{n} testes OK")
