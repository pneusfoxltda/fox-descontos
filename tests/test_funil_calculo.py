"""Testes da montagem do funil com leads inventados. Rodar: python tests/test_funil_calculo.py"""
import os, sys, random
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import funil_calculo as fc

HOJE = date(2026, 11, 27)


def lead(i, entrou, op="Ana", cot=None, age=None, comp=None, perdido=False, motivo=None, valor=500, origem="facebook"):
    d = lambda x: entrou + timedelta(days=x) if x is not None else None
    return {"id": i, "operadora": op, "origem": origem, "loja": "Matriz", "perdido": perdido, "motivo": motivo,
            "d_entrou": entrou, "d_cotou": d(cot), "d_negociou": None, "d_agendou": d(age), "d_visita": None,
            "d_comprou": d(comp), "valor_compra": valor if comp is not None else None, "valor_cotacao": 800 if cot is not None else None}


def t_funil_e_gargalo():
    e = date(2026, 11, 2)
    L = [lead(1, e, cot=0, age=1, comp=3), lead(2, e, cot=0), lead(3, e, cot=1, age=2), lead(4, e),
         lead(5, e, comp=2),                       # comprou sem marcações: conta como cotou e agendou
         lead(6, e, motivo="Outros produtos", perdido=True)]
    r = fc.resumo(L, HOJE, date(2026, 11, 1))
    assert r["funil"]["etapas"] == {"entrou": 5, "cotou": 4, "agendou": 3, "comprou": 2}
    assert r["fora_da_conta"] == {"Outros produtos": 1}
    assert r["funil"]["gargalo"] == "agendou→comprou"            # 2/3 é a pior passagem
    assert abs(r["funil"]["geral"] - 0.4) < 1e-9


def t_tempos_e_operadoras():
    e = date(2026, 10, 1)
    L = [lead(i, e, op="Ana" if i % 2 else "Kessya", cot=0, age=1, comp=c) for i, c in enumerate([2, 3, 4, 5, 40, None, None, 6])]
    r = fc.resumo(L, HOJE, date(2026, 9, 1))
    t = r["tempos"]["entrada_compra"]
    assert t["n"] == 6 and t["mediana"] == 4.5 and t["outliers"] == 1
    assert set(r["operadoras"]) == {"Ana", "Kessya"}
    assert r["operadoras"]["Ana"]["classe"] == "inconclusivo"     # poucos clientes
    assert "tempos" not in r["operadoras"]["Ana"]


def t_montar_completo():
    random.seed(1)
    L = []
    for i in range(600):
        e = date(2026, 8, 1) + timedelta(days=random.randint(0, 115))
        op = random.choice(["Ana", "Graziele", "Kessya", "Sabrina"])
        cot = 0 if random.random() < 0.6 else None
        age = (cot or 0) + 1 if cot is not None and random.random() < 0.4 else None
        comp = (age or 0) + random.randint(0, 10) if age is not None and random.random() < 0.6 else None
        if comp is not None and e + timedelta(days=comp) > HOJE:
            comp = None
        L.append(lead(i, e, op=op, cot=cot, age=age, comp=comp, perdido=comp is None and random.random() < 0.5,
                      origem=random.choice(["facebook", "google", None])))
    res, abertos = fc.montar(L, HOJE)
    assert set(res) == {"mes", "30d", "90d"}
    r = res["90d"]
    assert r["modelo"] and r["modelo"]["auc"] > 0.6                # agendar pesa muito: o modelo aprende
    assert r["previsao"]["minimo"] <= r["previsao"]["previsao"] <= r["previsao"]["maximo"]
    assert all(0 <= a["chance"] <= 1 for a in abertos) and any(a["atrasado"] for a in abertos)
    assert r["coortes"][0]["mes"] == "2026-08" and r["coortes"][0]["conv_30d"] is not None
    assert 0 < r["sobrevivencia"]["chance"]["30"] < 1
    import json; json.dumps(res)                                    # tudo cabe no banco (jsonb)


if __name__ == "__main__":
    n = 0
    for nome, f in list(globals().items()):
        if nome.startswith("t_"):
            f(); n += 1; print("OK", nome)
    print(f"{n} testes OK")
