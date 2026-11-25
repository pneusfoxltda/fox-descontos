"""Testes do robô resultados_atacado.py (sem rede). Rodar: python tests/test_resultados_atacado.py"""
import os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import resultados_atacado as ra
from varejo_filtros import ler_resumos


def t_dias_uteis_pula_domingo_e_feriado():
    # 25/11/2026 é quarta; 22/11 domingo; 20/11 feriado
    d = ra.dias_uteis(date(2026, 11, 25), {date(2026, 11, 20)})
    assert d == [date(2026, 11, 19), date(2026, 11, 21), date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25)], d


def t_dias_a_ler():
    ult = ra.dias_uteis(date(2026, 11, 25), set())
    ja = {date(2026, 11, 20), date(2026, 11, 21), date(2026, 11, 23), date(2026, 11, 24)}
    # hoje e o dia útil anterior sempre; 20/11, 21/11 e 23/11 já lidos
    assert ra.dias_a_ler(ult, date(2026, 11, 25), ja) == [date(2026, 11, 24), date(2026, 11, 25)]
    assert ra.dias_a_ler(ult, date(2026, 11, 25), set()) == ult


def t_relatorio_e_pneus():
    cab = ["Cod", "Descrição", "Peso Bruto", "Quant.", "Qtd. Mont", "Preço Tabela", "Vlr Venda", "Vlr C Rep", "Vlr Lucro",
           "%Lucro", "% Marg. Liq.", "% Desc. Cond. Pag.", "Qtd. Vendas. Real.", "Ticket Médio"]
    lin = lambda c, n, v, q, it: [str(c), n, "1,0", it, "0,000", "10,00", v, "1,00", "1,00", "1,00", "1,00", "0,00", str(q), "10,00"]
    tot = ["Total Geral:", "1", "2", "0", "1", "1.500,50", "1", "1", "1", "1", "0", "5", "300"]
    toks = (["Resumo por Vendedor"] + cab + lin(303101, "NAYZA  MINELLI", "1.000,50", 3, "40,000") + lin(107560, "KLEBER", "500,00", 2, "10,000") + tot
            + ["Resumo por Estabelecimento"] + cab + lin(10, "FOX-GM", "1.200,50", 4, "45,000") + lin(202, "MANAUS", "300,00", 1, "5,000") + tot
            + ["Valor Venda Líquida (Venda - Devolução)", "1.500,50", "Quantidade Clientes Atendidos", "4"])
    r = ler_resumos("<html>" + "".join(f"<div>{t}</div>" for t in toks) + "</html>")
    lojas, total = ra.lojas_e_total(r)
    assert [l["loja"] for l in lojas] == ["FOX-GM", "MANAUS"] and total["venda"] == 1500.5 and total["clientes"] == 4 and total["itens"] == 50.0
    vend = ra.vendedores(r)
    assert vend[0] == {"cod": "303101", "nome": "Nayza Minelli", "venda": 1000.5, "clientes": 3, "itens": 40.0}
    ra.juntar_pneus(vend, [{"cod": "303101", "itens": 36.0, "clientes": 3}], "cod")
    assert vend[0]["pneus"] == 36.0 and vend[1]["pneus"] == 0.0 and vend[1]["pneus_vendas"] == 0


if __name__ == "__main__":
    n = 0
    for nome, f in list(globals().items()):
        if nome.startswith("t_"):
            f(); n += 1; print("OK", nome)
    print(f"{n} testes OK")
