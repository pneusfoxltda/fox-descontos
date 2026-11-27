"""SÓ LEITURA: por que o Kommo mostra ~2.100 leads em 30 dias e o robô ~15 mil? Motivos e marcação de contato inicial."""
import os
from datetime import date, datetime
import funil_televendas as ft, httpx, ligacoes_lojas as ll, conferir_vendas_movere as cv
with httpx.Client(timeout=120) as cli:
    k = ft.Kommo(cli, os.environ["KOMMO_TOKEN"])
    ini = date(2026, 10, 28)
    L = [l for l in k.todas(f"/leads?filter%5Bcreated_at%5D%5Bfrom%5D={ft._ts(ini)}&filter%5Bpipeline_id%5D={ll.FUNIL}&with=loss_reason", "leads") if l.get("pipeline_id") == ll.FUNIL and l.get("status_id") not in ft.DISPARO]
print("leads criados nos últimos 30 dias (Funil Principal, fora disparo):", len(L))
def tem(l, fid): return any(f.get("field_id") == fid and (f.get("values") or [{}])[0].get("value") for f in l.get("custom_fields_values") or [])
mot = {}
for l in L:
    if l["status_id"] == 143:
        lr = ((l.get("_embedded") or {}).get("loss_reason") or [{}])
        m = (lr[0].get("name") if lr and isinstance(lr[0], dict) else None) or ft._valor_campo(l, ft.C_MOTIVO) or "(sem motivo)"
        mot[m] = mot.get(m, 0) + 1
print("perdidos por motivo:", sorted(mot.items(), key=lambda x: -x[1]))
ci = [l for l in L if tem(l, 586964)]
print("com '1 - Contato Inicial':", len(ci), "· destes perdidos:", sum(1 for l in ci if l['status_id'] == 143))
qual = [l for l in L if any(tem(l, f) for f in (586966, 798926, 822817, 586976, 822865)) or l["status_id"] not in (143,)]
print("com cotação/negociação/agendamento ou ainda abertos/ganhos:", len(qual))
st = {}
for l in L: st[l["status_id"]] = st.get(l["status_id"], 0) + 1
print("por etapa (id):", sorted(st.items(), key=lambda x: -x[1]))
