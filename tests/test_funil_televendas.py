"""Testes do robô do funil (sem rede). Rodar: python tests/test_funil_televendas.py"""
import os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import funil_televendas as ft

SAL = b"x" * 32


def lead(**k):
    base = {"id": 1, "created_at": 1761969600, "status_id": 89179003, "responsible_user_id": 7, "custom_fields_values": [], "_embedded": {}}
    base.update(k); return base


def t_codigo_do_telefone():
    a = ft.codigo_tel("99990001", SAL)
    assert a == ft.codigo_tel("99990001", SAL) and a != ft.codigo_tel("99990002", SAL) and "9999" not in a and len(a) == 24


def t_entrou_de_verdade():
    assert ft.entrou_de_verdade(lead(), {})                                     # aberto
    assert not ft.entrou_de_verdade(lead(status_id=143), {})                    # perdido sem conversa
    assert ft.entrou_de_verdade(lead(status_id=143), {"cotou": date(2025, 11, 1)})
    assert ft.entrou_de_verdade(lead(status_id=143, custom_fields_values=[{"field_id": ft.C_CONTATO, "values": [{"value": True}]}]), {})


def t_linha_compra_e_venda_ganha():
    entrou = ft._dia(1761969600)
    cot = {"99990001": [{"data": entrou, "valor": 900.0}]}
    vendas = {"99990001": [(date(2020, 1, 1), 50.0), (entrou, 700.0)]}       # compra antiga não conta
    l = ft.linha_do_lead(lead(), {7: "Ana"}, {}, {"99990001"}, cot, vendas)
    assert l["d_cotou"] == entrou and l["d_comprou"] == entrou and l["valor_compra"] == 700.0 and l["operadora"] == "Ana"
    g = ft.linha_do_lead(lead(status_id=142, closed_at=1762228800), {}, {}, set(), {}, {})
    assert g["d_comprou"] == ft._dia(1762228800) and g["compra_fonte"] == "venda_ganha"


def t_juntar_mantem_a_primeira_data():
    a = {"id": 1, "d_entrou": date(2025, 1, 1), "d_cotou": date(2025, 1, 3), "d_agendou": None, "d_negociou": None, "d_visita": None,
         "d_comprou": None, "perdido": True, "motivo": "Preço", "valor_compra": None}
    b = dict(a, d_cotou=date(2025, 1, 9), d_agendou=date(2025, 1, 10), d_comprou=date(2025, 1, 12), perdido=False, motivo=None, valor_compra=500.0)
    j = ft.juntar(a, b)
    assert j["d_cotou"] == date(2025, 1, 3) and j["d_agendou"] == date(2025, 1, 10) and j["d_comprou"] == date(2025, 1, 12)
    assert j["perdido"] is False and j["motivo"] is None and j["valor_compra"] == 500.0


def t_mes_anterior():
    assert ft.mes_anterior(date(2026, 11, 27), 3) == date(2026, 8, 1) and ft.mes_anterior(date(2026, 1, 5), 2) == date(2025, 11, 1)



def t_cotacao_virou_os_e_venda():
    banco = {1: {"id": 1, "d_entrou": date(2026, 11, 2), "d_comprou": None, "cotacoes": ["24"], "perdido": True, "motivo": "Preço"},
             2: {"id": 2, "d_entrou": date(2026, 11, 10), "d_comprou": None, "cotacoes": ["30"]},          # O.S. antes da entrada: não vale
             3: {"id": 3, "d_entrou": date(2026, 11, 1), "d_comprou": date(2026, 11, 3), "cotacoes": ["40"], "compra_fonte": "movere"}}
    os_map = {"24": (date(2026, 11, 5), 1200.0, "nota"), "30": (date(2026, 11, 8), 900.0, "os"), "40": (date(2026, 11, 9), 500.0, "nota")}
    m = ft.aplicar_os(banco, os_map)
    assert [x["id"] for x in m] == [1]
    assert banco[1]["d_comprou"] == date(2026, 11, 5) and banco[1]["valor_compra"] == 1200.0 and banco[1]["compra_fonte"] == "os"
    assert banco[1]["perdido"] is False and banco[1]["motivo"] is None
    assert banco[3]["compra_fonte"] == "movere"                       # a compra mais antiga continua valendo
    j = ft.juntar({"id": 1, "cotacoes": ["24"], "d_comprou": date(2026, 11, 5), "valor_compra": 1200.0, "compra_fonte": "os"},
                  {"id": 1, "cotacoes": ["25"], "d_comprou": date(2026, 11, 20), "valor_compra": 99.0, "compra_fonte": "venda_ganha", "perdido": False})
    assert j["cotacoes"] == ["24", "25"] and j["d_comprou"] == date(2026, 11, 5) and j["compra_fonte"] == "os" and j["valor_compra"] == 1200.0



def t_campos_do_lead():
    l = {"status_id": 142, "custom_fields_values": [
        {"field_name": "1 - Contato Inicial", "values": [{"value": True}]},
        {"field_name": "3 - Cotação criada pela IA", "values": [{"value": "1"}]},
        {"field_name": "5 - Recuperação Inicial", "values": [{"value": False}]},
        {"field_name": "6 - Agendamento IA", "values": [{"value": True}]},
        {"field_name": "1ª Venda", "values": [{"value": 1764000000}]}]}
    assert ft.campos_do_lead(l) == ["1", "3", "6"] and ft.etapa_do_lead(l) == "ganha"
    l["custom_fields_values"] += [{"field_id": 777920, "field_name": "Disparo", "values": [{"value": "Sucesso no disparo"}]},
                                  {"field_name": "Respondeu", "values": [{"value": "Sim"}]}]
    assert ft.disparo_do_lead(l) == ("Sim", "Sucesso no disparo")
    m = ft.linha_minima(dict(l, id=9, created_at=1764000000), {})
    assert m["entrou"] is False and m["campos"] == ["1", "3", "6"] and m["disparo"] == "Sucesso no disparo"



def t_perda_equipe_ou_automatica():
    base = {"id": 5, "created_at": 1764000000, "status_id": 143, "responsible_user_id": 1, "_embedded": {}}
    eq = ft.linha_do_lead(dict(base, _embedded={"loss_reason": [{"name": "Preço"}]}), {}, {}, set(), {}, {})
    au = ft.linha_do_lead(dict(base, custom_fields_values=[{"field_id": 783662, "values": [{"value": "Não respondeu"}]}]), {}, {}, set(), {}, {})
    assert eq["motivo"] == "Preço" and eq["perda_auto"] is False
    assert au["motivo"] == "Não respondeu" and au["perda_auto"] is True


if __name__ == "__main__":
    n = 0
    for nome, f in list(globals().items()):
        if nome.startswith("t_"):
            f(); n += 1; print("OK", nome)
    print(f"{n} testes OK")
