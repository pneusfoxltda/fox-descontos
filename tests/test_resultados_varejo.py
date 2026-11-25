"""Testes do robô resultados_varejo.py (sem rede). Rodar: python tests/test_resultados_varejo.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import resultados_varejo as rv
from varejo_filtros import ler_resumos


def t_conferencia_explica_revenda():
    # Exemplo (números de mentira): uma loja com uma devolução de REVENDA de 1.266,00; a outra bate.
    v553 = {"ARIQUEMES": 1000.0, "MATRIZ": 500.0}
    ana = {"ARIQUEMES": 2266.0, "MATRIZ": 500.0}
    rev = [{"loja": "ARIQUEMES", "vendedor": "Camila", "dia": "2026-11-13", "cod_cliente": "000001", "nota": "1301", "valor": -1266.0}]
    c = rv.conferir(v553, ana, rev)
    assert c["MATRIZ"]["diferenca"] == 0 and c["MATRIZ"]["motivos"] == []
    a = c["ARIQUEMES"]
    assert a["diferenca"] == -1266.0, a
    assert len(a["motivos"]) == 1 and a["motivos"][0]["motivo"] == "Devolução de REVENDA" and a["motivos"][0]["cod_cliente"] == "000001"


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


def t_pneus_por_loja_e_vendedor():
    mes = {"lojas": [{"loja": "MATRIZ", "venda": 10.0}, {"loja": "CACOAL", "venda": 5.0}],
           "vend": [{"loja": "MATRIZ", "cod": "1"}, {"loja": "MATRIZ", "cod": "2"}, {"loja": "CACOAL", "cod": "9"}]}
    rv.juntar_pneus(mes, "MATRIZ", {"itens": 12.0, "clientes": 5}, [{"cod": "1", "itens": 12.0, "clientes": 5}])
    assert mes["lojas"][0]["pneus"] == 12.0 and mes["lojas"][0]["pneus_vendas"] == 5
    assert "pneus" not in mes["lojas"][1]
    assert mes["vend"][0]["pneus"] == 12.0 and mes["vend"][1]["pneus"] == 0.0 and "pneus" not in mes["vend"][2]


def t_gravar_mesmas_colunas():
    enviados = []
    class R:
        status_code, text = 201, ""
        def raise_for_status(self): pass
    class Cli:
        def post(self, url, headers=None, json=None): enviados.append(json); return R()
    rv._post(Cli(), "u", {}, [{"loja": "A", "pneus": 1}, {"loja": "B"}])
    assert enviados[0][1] == {"loja": "B", "pneus": None}


def t_data_analytics():
    assert rv.iso_analytics("11/3/2026") == "2026-11-03"


def t_modo_do_dia():
    from datetime import date as D
    os.environ.pop("MODO", None)
    qua = D(2026, 11, 25)
    assert rv.decidir_modo(qua, 10, D(2026, 11, 24)) == "hoje"          # de dia, com o retrato de ontem
    assert rv.decidir_modo(qua, 19, D(2026, 11, 24)) == "completo"      # 19h: mês completo
    assert rv.decidir_modo(qua, 10, D(2026, 11, 23)) == "completo"      # a rodada das 19h de ontem não aconteceu
    assert rv.decidir_modo(qua, 10, None) == "completo"                 # mês novo, sem retrato
    assert rv.decidir_modo(D(2026, 11, 30), 8, D(2026, 11, 28)) == "hoje"   # segunda: o anterior útil é sábado


def t_situacao_amarelo_e_vermelho():
    base = {"mes": {"lojas": [], "vend": []}, "hoje": {"lojas": [{"loja": "A"}], "vend": []}, "erros": [], "sem_hoje": []}
    assert rv.situacao(dict(base, sem_hoje=["B"]), "hoje", 8) == (True, [])                 # cedo: loja sem venda ainda
    ok, p = rv.situacao(dict(base, sem_hoje=["B"]), "hoje", 14)
    assert ok and p == ["hoje B (sem relatório)"]                                            # 1 faltando: amarelo
    ok, p = rv.situacao(dict(base, sem_hoje=["B", "C", "D"]), "hoje", 14)
    assert not ok and len(p) == 3                                                            # muita coisa: vermelho
    assert rv.situacao(dict(base, hoje={"lojas": [], "vend": []}), "completo", 19)[0] is False   # nada veio


if __name__ == "__main__":
    n = 0
    for nome, f in list(globals().items()):
        if nome.startswith("t_"):
            f(); n += 1; print("OK", nome)
    print(f"{n} testes OK")
