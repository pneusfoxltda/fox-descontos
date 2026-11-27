"""
funil_estatistica.py · As contas do painel "Funil do televendas" (sem bibliotecas de fora: só Python)
=====================================================================================================
Usado pelo robô funil_televendas.py. Cada função é pequena e testada em tests/test_funil_estatistica.py.

· percentis / resumo de tempo: mediana (medida principal, porque o tempo até a compra tem assimetria positiva),
  média para comparar, Q1, Q3, P90, IQR e outliers pela regra Q1 − 1,5×IQR / Q3 + 1,5×IQR.
· wilson: intervalo de confiança de 95% de uma taxa (bom para amostras pequenas).
· zscores + classificar: ranking justo (z ≥ +1 destaque · entre −1 e +1 esperado · z ≤ −1 precisa de apoio),
  "inconclusivo" quando há menos de 30 clientes ou o intervalo de Wilson cruza a média da equipe.
· kaplan_meier: curva de sobrevivência do tempo até a compra, contando também quem ainda não comprou (censurado).
· controle_semanal: média ± 2 desvios padrão da conversão semanal; semana fora do limite = alerta.
· velocidade: (oportunidades × conversão × ticket médio) ÷ ciclo médio em dias = R$ que passam pelo funil por dia.
· regressao_logistica: lead scoring (chance de compra) treinado com os clientes que já tiveram desfecho.
"""
import math

Z95 = 1.959963984540054


def percentil(vals, p):
    """Percentil p (0–100) com interpolação linear (igual ao Excel PERCENTIL.INC)."""
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    if len(v) == 1:
        return float(v[0])
    pos = (len(v) - 1) * p / 100.0
    i = int(math.floor(pos))
    f = pos - i
    return float(v[i]) if i + 1 >= len(v) else v[i] + (v[i + 1] - v[i]) * f


def resumo_tempo(vals):
    """Mediana, média, Q1, Q3, P90, IQR, limites de outlier e quantos são outliers."""
    v = [float(x) for x in vals if x is not None]
    if not v:
        return {"n": 0}
    q1, q3 = percentil(v, 25), percentil(v, 75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return {"n": len(v), "mediana": percentil(v, 50), "media": sum(v) / len(v), "q1": q1, "q3": q3,
            "p25": q1, "p50": percentil(v, 50), "p75": q3, "p90": percentil(v, 90), "iqr": iqr,
            "lim_inf": lo, "lim_sup": hi, "outliers": sum(1 for x in v if x < lo or x > hi),
            "min": min(v), "max": max(v)}


def eh_outlier(x, resumo):
    return resumo.get("n", 0) > 0 and x is not None and (x < resumo["lim_inf"] or x > resumo["lim_sup"])


def histograma(vals, larguras=(0, 1, 3, 7, 14, 21, 30, 45, 60, 90)):
    """Faixas de dias (0, 1–2, 3–6, 7–13 …) com a contagem em cada uma."""
    v = [x for x in vals if x is not None]
    out = []
    for i, a in enumerate(larguras):
        b = larguras[i + 1] if i + 1 < len(larguras) else None
        n = sum(1 for x in v if x >= a and (b is None or x < b))
        out.append({"de": a, "ate": b, "n": n})
    return out


def wilson(k, n, z=Z95):
    """(taxa, limite inferior, limite superior) do intervalo de Wilson. n = 0 → (None, 0, 1)."""
    if not n:
        return None, 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centro - meia), min(1.0, centro + meia)


def zscores(taxas):
    """{nome: taxa} → {nome: z}. Desvio padrão amostral da equipe; sem variação → z = 0."""
    vals = [t for t in taxas.values() if t is not None]
    if len(vals) < 2:
        return {k: 0.0 for k in taxas}
    m = sum(vals) / len(vals)
    dp = math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))
    return {k: (0.0 if (t is None or dp == 0) else (t - m) / dp) for k, t in taxas.items()}


def classificar(k, n, media_equipe, z, n_min=30):
    """Classificação justa: inconclusivo com poucos clientes ou quando o intervalo de Wilson cruza a média."""
    _, lo, hi = wilson(k, n)
    if n < n_min or (lo <= media_equipe <= hi):
        return "inconclusivo"
    if z >= 1:
        return "destaque"
    if z <= -1:
        return "precisa de apoio"
    return "dentro do esperado"


def kaplan_meier(dur_evento):
    """[(dias, comprou)] → curva [(dia, chance de AINDA NÃO ter comprado)]. Quem não comprou entra censurado."""
    dados = sorted((float(d), bool(e)) for d, e in dur_evento if d is not None and d >= 0)
    n = len(dados)
    s, curva, i = 1.0, [(0.0, 1.0)], 0
    while i < len(dados):
        t = dados[i][0]
        eventos = sum(1 for d, e in dados[i:] if d == t and e)
        saem = sum(1 for d, e in dados[i:] if d == t)
        if eventos:
            s *= 1 - eventos / n
            curva.append((t, s))
        n -= saem
        i += saem
    return curva


def chance_ate(curva, dias):
    """Chance de comprar em até `dias` (1 − sobrevivência)."""
    s = 1.0
    for t, v in curva:
        if t <= dias:
            s = v
        else:
            break
    return 1 - s


def controle_semanal(semanas):
    """[(semana, k, n)] → média, limites (± 2 desvios) e as semanas fora. Só semanas com n > 0."""
    taxas = [(w, k / n) for w, k, n in semanas if n]
    if len(taxas) < 3:
        return {"media": None, "lim_inf": None, "lim_sup": None, "fora": [], "semanas": taxas}
    vals = [t for _, t in taxas]
    m = sum(vals) / len(vals)
    dp = math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))
    lo, hi = max(0.0, m - 2 * dp), min(1.0, m + 2 * dp)
    return {"media": m, "lim_inf": lo, "lim_sup": hi, "fora": [w for w, t in taxas if t < lo or t > hi], "semanas": taxas}


def velocidade(oportunidades, conversao, ticket, ciclo_dias):
    """Velocidade do pipeline: R$ por dia. Ciclo zero ou vazio → None."""
    if not ciclo_dias or ciclo_dias <= 0:
        return None
    return oportunidades * conversao * ticket / ciclo_dias


def regressao_logistica(X, y, passos=400, taxa=0.3, l2=0.01):
    """Lead scoring: pesos de uma regressão logística (gradiente descendente com regularização L2).
    X = lista de listas (características já entre 0 e 1), y = 0/1. Devolve [viés, pesos...]."""
    if not X:
        return []
    m, d = len(X), len(X[0])
    w = [0.0] * (d + 1)
    for _ in range(passos):
        g = [0.0] * (d + 1)
        for xi, yi in zip(X, y):
            z = w[0] + sum(wj * xj for wj, xj in zip(w[1:], xi))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            e = p - yi
            g[0] += e
            for j in range(d):
                g[j + 1] += e * xi[j]
        w[0] -= taxa * g[0] / m
        for j in range(d):
            w[j + 1] -= taxa * (g[j + 1] / m + l2 * w[j + 1])
    return w


def prever(w, x):
    if not w:
        return None
    z = w[0] + sum(wj * xj for wj, xj in zip(w[1:], x))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def auc(probs, y):
    """Área sob a curva ROC (validação do lead scoring): 0,5 = chute, 1 = perfeito."""
    pos = [p for p, t in zip(probs, y) if t]
    neg = [p for p, t in zip(probs, y) if not t]
    if not pos or not neg:
        return None
    vitorias = sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in pos for b in neg)
    return vitorias / (len(pos) * len(neg))
