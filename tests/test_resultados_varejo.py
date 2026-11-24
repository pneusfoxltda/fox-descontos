"""Testes do robô resultados_varejo.py (sem rede). Rodar: python tests/test_resultados_varejo.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import resultados_varejo as rv
from varejo_filtros import ler_resumos


def t_conferencia_explica_revenda():
    # Caso real de 01 a 21/11/2026: ARIQUEMES tem uma devolução de REVENDA de 1.266,00; o resto bate.
    v553 = {"ARIQUEMES": 319740.76, "MATRIZ": 558211.44}
    ana = {"ARIQUEMES": 321006.76, "MATRIZ": 558211.44}
    rev = [{"loja": "ARIQUEMES", "vendedor": "Camila", "dia": "2026-11-13", "cod_cliente": "239846", "nota": "1301", "valor": -1266.0}]
    c = rv.conferir(v553, ana, rev)
    assert c["MATRIZ"]["diferenca"] == 0 and c["MATRIZ"]["motivos"] == []
    a = c["ARIQUEMES"]
    assert a["diferenca"] == -1266.0, a
    assert len(a["motivos"]) == 1 and a["motivos"][0]["motivo"] == "Devolução de REVENDA" and a["motivos"][0]["cod_cliente"] == "239846"


def t_conferencia_sobra_sem_explicacao():
    c = rv.conferir({"CACOAL": 1000.0}, {"CACOAL": 900.0}, [{"loja": "CACOAL", "vendedor": "X", "dia": "2026-11-02", "cod_cliente": "1", "nota": "9", "valor": 60.0}])
    m = c["CACOAL"]["motivos"]
    assert [x["motivo"] for x in m] == ["Venda de REVENDA", "Diferença sem explicação automática"], m
    assert m[1]["valor"] == 40.0


def t_vendedores_somam_a_loja():
    cab = ["Cod", "Descrição", "Peso Bruto", "Quant.", "Qtd. Mont", "Preço Tabela", "Vlr Venda", "Vlr C Rep", "Vlr Lucro",
           "%Lucro", "% Marg. Liq.", "% Desc. Cond. Pag.", "Qtd. Vendas. Real.", "Ticket Médio"]
    lin = lambda c, n, v, q: [str(c), n, "1,0", "2,000", "0,000", "10,00", v, "1,00", "1,00", "1,00", "1,00", "0,00", str(q), "10,00"]
    toks = (["Resumo por Vendedor"] + cab + lin(10, "ANA  SILVA", "1.000,50", 3) + ["FULANO - Principal MOVERE Pagina: 1 de 2", "Resumo por Vendedor"]
            + cab + lin(11, "BIA", "500,00", 2) + ["Total Geral:", "1", "2", "0", "1", "1.500,50", "1", "1", "1", "1", "0", "5", "300"]
            + ["Resumo por Estabelecimento"] + cab + lin(5, "JI-PARANA", "1.500,50", 5)
            + ["Total Geral:", "1", "2", "0", "1", "1.500,50", "1", "1", "1", "1", "0", "5", "300"])
    r = ler_resumos("<html>" + "".join(f"<div>{t}</div>" for t in toks) + "</html>")
    lj, vd = rv.linha_loja(r, "JI-PARANA", 5), rv.linhas_vendedores(r, "JI-PARANA")
    assert lj["venda"] == 1500.5 and lj["clientes"] == 5
    assert [v["nome"] for v in vd] == ["Ana Silva", "Bia"]
    assert round(sum(v["venda"] for v in vd), 2) == lj["venda"]


def t_data_analytics():
    assert rv.iso_analytics("11/3/2026") == "2026-11-03"


if __name__ == "__main__":
    n = 0
    for nome, f in list(globals().items()):
        if nome.startswith("t_"):
            f(); n += 1; print("OK", nome)
    print(f"{n} testes OK")
