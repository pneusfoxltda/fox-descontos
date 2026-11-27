"""SÓ LEITURA: onde o Kommo guarda as DATAS das marcações (campos 1 a 7), motivos de perda e volume por mês.
Registro público só com nomes de campos/tipos e contagens."""
import os, time
from datetime import datetime
import httpx
import ligacoes_lojas as ll
import conferir_vendas_movere as cv
H = {"Authorization": "Bearer " + os.environ["KOMMO_TOKEN"].strip()}
with httpx.Client(timeout=120) as cli:
    def get(u):
        for t in range(4):
            try:
                r = cli.get(ll.KOMMO + u, headers=H); break
            except httpx.TransportError: time.sleep(5)
        if r.status_code == 204: return None
        r.raise_for_status(); return r.json()
    campos = []
    pg = 1
    while True:
        d = get(f"/leads/custom_fields?limit=250&page={pg}")
        if not d: break
        campos += d["_embedded"]["custom_fields"]
        if not d.get("_links", {}).get("next"): break
        pg += 1
    alvo = {c["id"]: c["name"] for c in campos if c["name"] in ("1 - Contato Inicial", "2 - Fez cotação", "3 - Cotação criada pela IA",
            "4 - Negociação realizada", "5 - Recuperação Inicial", "6 - Agendamento IA", "7 - Agendamento", "Data da visita", "1ª Venda", "Motivo de perda", "Lojas")}
    print("campos-alvo:", alvo)
    mp = next((c for c in campos if c["name"] == "Motivo de perda"), None)
    if mp: print("opções de 'Motivo de perda':", [e["value"] for e in mp.get("enums") or []])
    lr = get("/leads/loss_reasons?limit=250")
    print("motivos de perda do Kommo (loss_reasons):", [x["name"] for x in (lr or {}).get("_embedded", {}).get("loss_reasons", [])])
    ts = int(datetime(2026, 11, 20, tzinfo=cv.TZ_LOJA).timestamp())
    for fid, nome in alvo.items():
        d = get(f"/events?filter%5Btype%5D=custom_field_{fid}_value_changed&filter%5Bcreated_at%5D%5Bfrom%5D={ts}&limit=100")
        evs = (d or {}).get("_embedded", {}).get("events", [])
        ex = evs[0] if evs else {}
        print(f"eventos '{nome}' desde 20/11 (1ª página): {len(evs)} · chaves: {sorted(ex.keys())} · tipo do valor: {type((ex.get('value_after') or [{}])[0]).__name__ if ex else '-'}"
              + (f" · exemplo value_after (sem dado de cliente): {str(ex.get('value_after'))[:120]}" if nome.startswith(('1','2','3','4','5','6','7')) and ex else ""))
    # volume por mês no Funil Principal (fora disparos) e quantos têm alguma marcação 1-7
    DISP = {108557363, 89179007}
    for (a, m) in ((2026, 8), (2026, 9), (2026, 10), (2026, 11)):
        i = int(datetime(a, m, 1, tzinfo=cv.TZ_LOJA).timestamp()); f = int(datetime(a + (m == 12), m % 12 + 1, 1, tzinfo=cv.TZ_LOJA).timestamp()) - 1
        n = marc = perd = perd_mot = 0; pg = 1
        while True:
            d = get(f"/leads?filter%5Bcreated_at%5D%5Bfrom%5D={i}&filter%5Bcreated_at%5D%5Bto%5D={f}&filter%5Bpipeline_id%5D={ll.FUNIL}&with=loss_reason&limit=250&page={pg}")
            if not d: break
            for l in d["_embedded"]["leads"]:
                if l["status_id"] in DISP or l["pipeline_id"] != ll.FUNIL: continue
                n += 1
                if any(c.get("field_id") in alvo and str(c.get("field_name", "")).startswith(("1 ", "2 ", "3 ", "6 ", "7 ")) for c in l.get("custom_fields_values") or []): marc += 1
                if l["status_id"] == 143:
                    perd += 1
                    if (l.get("_embedded") or {}).get("loss_reason"): perd_mot += 1
            if not d.get("_links", {}).get("next"): break
            pg += 1
        print(f"{m:02d}/{a}: leads {n} · com alguma marcação 1/2/3/6/7: {marc} · venda perdida {perd} (com motivo do Kommo: {perd_mot})")
