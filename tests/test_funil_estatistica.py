"""Testes das contas do funil (valores conferidos à mão / com referências conhecidas).
Rodar: python tests/test_funil_estatistica.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import funil_estatistica as fe


def perto(a, b, tol=1e-3):
    return abs(a - b) <= tol


def t_percentil_e_outliers():
    v = [1, 2, 2, 3, 3, 3, 4, 5, 6, 40]
    r = fe.resumo_tempo(v)
    assert r["mediana"] == 3 and perto(r["media"], 6.9)
    assert perto(r["q1"], 2.25) and perto(r["q3"], 4.75)
    assert r["outliers"] == 1 and fe.eh_outlier(40, r) and not fe.eh_outlier(6, r)
    assert fe.percentil([10], 90) == 10 and fe.percentil([], 50) is None


def t_wilson():
    p, lo, hi = fe.wilson(5, 10)          # referência: 0,5 [0,2366 ; 0,7634]
    assert p == 0.5 and perto(lo, 0.2366) and perto(hi, 0.7634)
    p, lo, hi = fe.wilson(0, 20)          # zero sucessos: limite inferior 0
    assert lo == 0 and perto(hi, 0.1611)
    assert fe.wilson(0, 0) == (None, 0.0, 1.0)


def t_ranking_justo():
    z = fe.zscores({"A": 0.10, "B": 0.20, "C": 0.30})
    assert perto(z["A"], -1) and perto(z["B"], 0) and perto(z["C"], 1)
    assert fe.classificar(3, 10, 0.2, 1.5) == "inconclusivo"          # menos de 30 clientes
    assert fe.classificar(60, 200, 0.2, 1.2) == "destaque"            # 30% [24%;37%] não cruza 20%
    assert fe.classificar(20, 200, 0.2, -1.3) == "precisa de apoio"
    assert fe.classificar(42, 200, 0.2, 0.3) == "inconclusivo"        # 21% [16%;27%] cruza 20%


def t_kaplan_meier():
    # 5 clientes: compram nos dias 2, 4, 4; dois ainda não compraram (censurados em 3 e 10)
    c = fe.kaplan_meier([(2, True), (3, False), (4, True), (4, True), (10, False)])
    assert c[1] == (2.0, 0.8)
    assert perto(c[2][1], 0.8 * (1 - 2 / 3))                          # no dia 4 sobram 3 em risco
    assert perto(fe.chance_ate(c, 3), 0.2) and perto(fe.chance_ate(c, 30), 1 - 0.8 / 3)


def t_controle_semanal():
    sem = [("s1", 10, 100), ("s2", 11, 100), ("s3", 9, 100), ("s4", 10, 100), ("s5", 30, 100)]
    r = fe.controle_semanal(sem)
    assert r["fora"] == [] and r["lim_sup"] > 0.3           # 1 semana muito alta puxa o desvio
    r = fe.controle_semanal(sem[:4] * 3 + [("s9", 2, 100)])
    assert r["fora"] == ["s9"]
    assert fe.controle_semanal(sem[:2])["media"] is None


def t_velocidade():
    assert fe.velocidade(100, 0.2, 500, 10) == 1000.0
    assert fe.velocidade(100, 0.2, 500, 0) is None


def t_lead_scoring_aprende():
    # quem agendou compra muito mais: o modelo tem que dar chance maior a quem agendou
    X = [[1, 0]] * 40 + [[0, 0]] * 60 + [[1, 1]] * 10
    y = [1] * 28 + [0] * 12 + [1] * 6 + [0] * 54 + [1] * 9 + [0]
    w = fe.regressao_logistica(X, y)
    assert fe.prever(w, [1, 0]) > fe.prever(w, [0, 0])
    a = fe.auc([fe.prever(w, x) for x in X], y)
    assert a > 0.75


if __name__ == "__main__":
    n = 0
    for nome, f in list(globals().items()):
        if nome.startswith("t_"):
            f(); n += 1; print("OK", nome)
    print(f"{n} testes OK")
