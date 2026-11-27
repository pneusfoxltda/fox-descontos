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
    assert g["d_comprou"] == ft._dia(1762228800) and g["_fonte"] == "venda_ganha"


def t_juntar_mantem_a_primeira_data():
    a = {"id": 1, "d_entrou": date(2025, 1, 1), "d_cotou": date(2025, 1, 3), "d_agendou": None, "d_negociou": None, "d_visita": None,
         "d_comprou": None, "perdido": True, "motivo": "Preço", "valor_compra": None}
    b = dict(a, d_cotou=date(2025, 1, 9), d_agendou=date(2025, 1, 10), d_comprou=date(2025, 1, 12), perdido=False, motivo=None, valor_compra=500.0)
    j = ft.juntar(a, b)
    assert j["d_cotou"] == date(2025, 1, 3) and j["d_agendou"] == date(2025, 1, 10) and j["d_comprou"] == date(2025, 1, 12)
    assert j["perdido"] is False and j["motivo"] is None and j["valor_compra"] == 500.0


def t_mes_anterior():
    assert ft.mes_anterior(date(2026, 11, 27), 3) == date(2026, 8, 1) and ft.mes_anterior(date(2026, 1, 5), 2) == date(2025, 11, 1)


if __name__ == "__main__":
    n = 0
    for nome, f in list(globals().items()):
        if nome.startswith("t_"):
            f(); n += 1; print("OK", nome)
    print(f"{n} testes OK")
