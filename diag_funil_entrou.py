"""Diagnóstico (só leitura, só contagens): de onde vêm os "Entraram" do mês no funil do televendas."""
import os, sys
from collections import Counter
from datetime import datetime
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_vendas_movere as cv
import ligacoes_lojas as ll
import funil_televendas as ft

hoje = datetime.now(cv.TZ_LOJA).date()
ini = hoje.replace(day=1)
with httpx.Client(timeout=120) as cli:
    k = ft.Kommo(cli, os.environ["KOMMO_TOKEN"])
    pip = k.get(f"/leads/pipelines/{ll.FUNIL}") or {}
    nomes = {s["id"]: s["name"] for s in (pip.get("_embedded") or {}).get("statuses", [])}
    todos = list(k.todas(f"/leads?filter%5Bcreated_at%5D%5Bfrom%5D={ft._ts(ini)}&filter%5Bpipeline_id%5D={ll.FUNIL}&with=contacts,loss_reason", "leads"))
    todos = [l for l in todos if l.get("pipeline_id") == ll.FUNIL]
    print(f"Leads criados desde {ini:%d/%m} no Funil Principal: {len(todos)}")
    disp = [l for l in todos if l.get("status_id") in ft.DISPARO]
    resto = [l for l in todos if l.get("status_id") not in ft.DISPARO]
    print(f"  nas colunas de DISPARO (fora): {len(disp)}")
    marc = ft.datas_marcacoes(k, ini)
    cont = [l for l in resto if ft.entrou_de_verdade(l, marc.get(l["id"], {}))]
    print(f"  sem disparo: {len(resto)} · contam como 'entrou': {len(cont)} · fora (perdido sem conversa): {len(resto) - len(cont)}")
    tipo = Counter()
    so_aberto = Counter()
    for l in cont:
        m = marc.get(l["id"], {})
        if ft._valor_campo(l, ft.C_CONTATO):
            tipo["1 - Contato Inicial marcado"] += 1
        elif m:
            tipo["sem Contato Inicial, mas com outra marcação"] += 1
        else:
            tipo["NENHUMA marcação (conta só porque está aberto/ganho)"] += 1
            so_aberto[nomes.get(l.get("status_id"), str(l.get("status_id")))] += 1
    for t, n in tipo.most_common():
        print(f"    {t}: {n}")
    print("  Etapa atual dos que contam SEM nenhuma marcação:")
    for t, n in so_aberto.most_common(15):
        print(f"    {t}: {n}")
    print("  Etapa atual de todos os que contam:")
    for t, n in Counter(nomes.get(l.get("status_id"), str(l.get("status_id"))) for l in cont).most_common(20):
        print(f"    {t}: {n}")
    cids = Counter()
    sem_contato = 0
    for l in cont:
        cs = (l.get("_embedded") or {}).get("contacts") or []
        if not cs:
            sem_contato += 1
        for c in cs[:1]:
            cids[c["id"]] += 1
    print(f"  Pessoas diferentes (contato do Kommo) entre os que contam: {len(cids)} · cartões sem contato: {sem_contato}")
    print(f"  Pessoas com mais de 1 cartão no mês: {sum(1 for v in cids.values() if v > 1)} (cartões a mais: {sum(v - 1 for v in cids.values() if v > 1)})")
    com_cont = [l for l in cont if ft._valor_campo(l, ft.C_CONTATO) or marc.get(l["id"])]
    p2 = len({((l.get("_embedded") or {}).get("contacts") or [{}])[0].get("id") for l in com_cont})
    print(f"  Se contar só quem tem marcação (Contato Inicial ou etapa): {len(com_cont)} cartões · {p2} pessoas diferentes")
    print("  Origem (utm) dos que contam:")
    for t, n in Counter(ft._origem(l) or "(sem origem)" for l in cont).most_common(8):
        print(f"    {t}: {n}")
