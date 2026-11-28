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


def t_disparo_sem_sucesso_fica_fora():
    e = date(2026, 11, 2)
    r = fc.resumo([lead(1, e, cot=0), lead(2, e, perdido=True, motivo="Disparo sem sucesso")], HOJE, date(2026, 11, 1))
    assert r["funil"]["etapas"]["entrou"] == 1 and r["fora_da_conta"] == {"Disparo sem sucesso": 1}


def t_periodo_ano_passado():
    L = [lead(1, date(2025, 3, 1), cot=0, comp=5), lead(2, date(2026, 2, 1), cot=0)]
    res, _ = fc.montar(L, HOJE)
    assert res["2025"]["funil"]["etapas"]["entrou"] == 1 and res["ano"]["funil"]["etapas"]["entrou"] == 1
    assert res["tudo"]["funil"]["etapas"]["entrou"] == 2 and res["2025"]["ate"] == "2025-12-31"


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
    assert {"mes", "30d", "90d", "ano", "tudo"} <= set(res)
    r = res["90d"]
    assert r["modelo"] and r["modelo"]["auc"] > 0.6                # agendar pesa muito: o modelo aprende
    assert r["previsao"]["minimo"] <= r["previsao"]["previsao"] <= r["previsao"]["maximo"]
    assert all(0 <= a["chance"] <= 1 for a in abertos) and any(a["atrasado"] for a in abertos)
    assert r["coortes"][0]["mes"] == "2026-08" and r["coortes"][0]["conv_30d"] is not None
    assert 0 < r["sobrevivencia"]["chance"]["30"] < 1
    import json; json.dumps(res)                                    # tudo cabe no banco (jsonb)


def t_pelo_kommo():
    d = date(2026, 11, 5)
    L = [{"id": 1, "d_entrou": d, "campos": ["1", "2"], "etapa": "aberto"},
         {"id": 2, "d_entrou": d, "campos": ["1", "3", "6", "7"], "etapa": "ganha", "d_comprou": d},
         {"id": 3, "d_entrou": d, "campos": ["1", "6"], "etapa": "perdida"},
         {"id": 4, "d_entrou": d, "campos": ["1", "7"], "etapa": "aberto"},
         {"id": 5, "d_entrou": d, "campos": ["2"], "etapa": "aberto", "entrou": True},
         {"id": 6, "d_entrou": d, "campos": [], "etapa": "perdida", "entrou": False},
         {"id": 7, "d_entrou": date(2026, 10, 1), "campos": ["1"], "etapa": "aberto"}]
    k = fc.pelo_kommo(L, date(2026, 11, 1))
    assert k["alguma_forma"] == 6 and k["contato"] == 4 and k["sem_contato"] == 2 and k["cotou"] == 1 and k["cotou_ia"] == 1 and k["so_cotacao_ia"] == 1 and k["cotou_sem_ia"] == 1 and k["cotou_sem_contato"] == 1
    assert k["ag_ia"] == 2 and k["ag_equipe"] == 2 and k["ag_ia_e_equipe"] == 1 and k["ag_so_ia"] == 1 and k["ag_so_equipe"] == 1 and k["agendou"] == 3
    assert k["ag_conf_ganha"] == 1 and k["ag_conf_perdida"] == 0 and k["venda_perdida"] == 1 and k["agendou_perdida"] == 1
    assert k["caminho_cot_agia"] == 0
    L2 = [{"id": 1, "d_entrou": d, "campos": ["1", "5", "2"], "etapa": "ganha", "respondeu": "Sim", "disparo": "Sucesso no disparo", "d_comprou": d},
          {"id": 2, "d_entrou": d, "campos": ["1", "5"], "etapa": "aberto", "respondeu": "Não", "disparo": "Não respondeu 48h no disparo"},
          {"id": 3, "d_entrou": d, "campos": ["1"], "etapa": "aberto"}]
    D = fc.pelo_kommo(L2, date(2026, 11, 1))["disparo"]
    assert D["recebeu"]["n"] == 2 and D["recebeu"]["comprou_real"] == 1 and D["nao_recebeu"]["n"] == 1
    assert D["resposta"]["Sucesso no disparo"]["ganha"] == 1 and D["respondeu"]["Não"]["n"] == 1
    assert fc.pelo_kommo([{"id": 1, "d_entrou": d}], date(2026, 11, 1)) is None
    r, _ = fc.montar(L, date(2026, 11, 28))
    assert r["mes"]["kommo"]["contato"] == 4 and r["mes"]["total_leads"] == 5     # o "adicionado" (entrou False) fica fora do funil


if __name__ == "__main__":
    n = 0
    for nome, f in list(globals().items()):
        if nome.startswith("t_"):
            f(); n += 1; print("OK", nome)
    print(f"{n} testes OK")
