"""
varejo_teste.py · Etapa 3 do dashboard do VAREJO (TESTE: não grava nada no banco)
==================================================================================
Gera a rotina 553 do Movere de 01/11 até hoje, só com os quadros de resumo, em 2 cenários:
  A) como o PDF de conferência do TI: tabela só "1: VAREJO", sem filtro de família, 8 lojas;
  B) filtros do Varejo: 13 tabelas de preço + 11 famílias + 8 lojas.
O registro do GitHub é PÚBLICO: o resultado sai TRANCADO (criptografado com uma chave pública).
Só quem tem a chave privada (fora do repositório) consegue ler. Nada de cliente é lido nem guardado.
"""
import asyncio, base64, json, os, sys
from datetime import datetime, timedelta, timezone

from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_televendas import login, RELATORIO_URL, MOVERE_BASE
from varejo_filtros import ler_quadro_familia, LOJAS_VAREJO, FAMILIAS_VAREJO, TABELAS_VAREJO, TABELAS_FORA_VAREJO, marcar_lista, ler_resumos, JS_LIMPAR

CHAVE_PUBLICA = """-----BEGIN PUBLIC KEY-----
MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAzijlXhYa99ik9jnObJRO
UxrP6ziw2C0sxxB/Pya+vtv0LnLwYmhjjSVHntQ8oUK23ylsCDxtf9ACqTuTOwQE
daUzraMBEj2tAYPCIe1PG3RaOzyKicbm7qH8ear6vfnwLE0iM93qpqbC3HJ8OOxN
vrwknj9+nMLgu9RilU0sN7evrkrOzIJ+INOL+gahDiILNAD3AREFpX2N5iYSH2zk
Afc7f3Dvm7/ZclEoOTcPDUzZQG3gPIotRhAYYbwuielFoahD0fzMcyFJbATKg4Tb
V7WKjdh0CVvtBMK1QiSfbZbWnOO9xU3CIY6RMv9WKZ7WR1U3ypG2oG59yccgpBrp
dhxBJVZY4z6lTAE2UHONcKMpL2LU4zEhNh4KVMQNiKcjzlD71neWTlzG0UCvTiX9
Hfged2mXx9jUzgX7KlF6DfKvImg0RT+8uizyl4tLSHCJZVA7ho0ew28ZTnqd7sKq
CDTMzfqZccvdl+Ujz2gYpacQCQZsV6YtMpJBLQfp5McPAgMBAAE=
-----END PUBLIC KEY-----"""
P = "ctl00_ctl00_Corpo_Corpo_"


def trancar(obj) -> str:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    pub = serialization.load_pem_public_key(CHAVE_PUBLICA.encode())
    k, n = AESGCM.generate_key(bit_length=256), os.urandom(12)
    ct = AESGCM(k).encrypt(n, json.dumps(obj, ensure_ascii=False).encode(), None)
    ek = pub.encrypt(k, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return base64.b64encode(len(ek).to_bytes(2, "big") + ek + n + ct).decode()


async def gerar(page, data_ini: str, data_fim: str, tabelas: list, familias: list, lojas: list = None) -> dict:
    await page.goto(RELATORIO_URL, wait_until="domcontentloaded", timeout=40000)
    await page.wait_for_timeout(2500)
    print(f"   campos limpos (lembrados pelo Movere): {await page.evaluate(JS_LIMPAR)}")
    if os.environ.get("FRETE"):
        await page.evaluate("() => { window.__FRETE = true; }")
    await page.wait_for_timeout(500)
    for campo, val in (("cdtaini_edt", data_ini), ("cdtafim_edt", data_fim)):
        el = page.locator(f"#{P}{campo}")
        await el.click(click_count=3); await el.fill(val); await el.press("Tab")
    log = []
    res = {"lojas": await marcar_lista(page, "cEstabelecimentos", lojas or list(LOJAS_VAREJO.values()), log.append),
           "tabelas": await marcar_lista(page, "cTabelaPreco", tabelas, log.append) if tabelas else {"ok": [], "faltou": []}}
    if familias:
        res["familias"] = await marcar_lista(page, "cFamiliaItens", familias, log.append)
    marcados = {k: f"{len(v['ok'])} ok, faltou {v['faltou']}" for k, v in res.items()}
    print("   filtros:", marcados)
    await page.evaluate("""(p) => {
      const set = (id, v) => { const e = document.getElementById(p + id); if (e && e.checked !== v) { e.checked = v; e.dispatchEvent(new Event('change', {bubbles: true})); } };
      set('csomenteresumo', true); set('cExibirResumoPorEstabelecimento', true); set('cExibirResumoPorVendedor', true);
      set('chkSomenteBaseVenda', true); set('chkFamiliaItens', true);
      if (window.__FRETE) set('cFreteCompoeValoresTotais', true);
      const f = document.getElementById(p + 'cFormato'); if (f) { f.value = '2'; f.dispatchEvent(new Event('change', {bubbles: true})); }
    }""", P)
    await page.wait_for_timeout(500)

    capt, popups = [], []
    async def on_resp(r):
        try:
            if MOVERE_BASE in r.url and "html" in r.headers.get("content-type", "").lower() and r.status == 200 and "rotina553" not in r.url.lower():
                b = await r.text()
                if len(b) > 2000: capt.append((r.url, b))
        except Exception:
            pass
    page.on("response", on_resp)
    page.context.on("page", lambda pg: popups.append(pg))
    clicou = await page.evaluate("""() => {
      const c = [...document.querySelectorAll('input[type=submit],input[type=button],button,a')]
        .find(e => /execut|gerar|imprimir|visualiz/i.test((e.value || e.innerText || e.id || '')) && (e.offsetWidth || e.offsetHeight));
      if (c) { c.click(); return (c.value || c.innerText || c.id || '').trim().slice(0, 40); }
      return null; }""")
    print(f"   botão: {clicou!r}")
    for _ in range(150):  # até 60 s
        await page.wait_for_timeout(400)
        if capt or popups:
            break
    for pg in popups:
        try:
            await pg.wait_for_load_state("domcontentloaded", timeout=30000); await pg.wait_for_timeout(4000)
            capt.append((pg.url, await pg.content()))
        except Exception:
            pass
    for fr in page.frames:
        try:
            c = await fr.content()
            if len(c) > 2000 and "rotina553" not in (fr.url or "").lower():
                capt.append((fr.url, c))
        except Exception:
            pass
    page.remove_listener("response", on_resp)
    melhor = max((b for _, b in capt if "Resumo por" in b), key=len, default=None)
    print(f"   respostas: {len(capt)} · com resumo: {'sim' if melhor else 'não'} · urls: {[u[-50:] for u, _ in capt][:5]}")
    if not melhor:
        await page.screenshot(path="screenshot_varejo_sem_relatorio.png", full_page=True)
        return {"erro": "relatório não veio", "filtros": marcados, "log": log}
    r = ler_resumos(melhor)
    r["familias"] = ler_quadro_familia(melhor)
    r["filtros"] = marcados
    # Para ajustar a leitura: o texto dos quadros de resumo (vai TRANCADO; o modo resumo não lista clientes)
    from bs4 import BeautifulSoup
    toks = [" ".join(d.get_text(" ", strip=True).split()) for d in BeautifulSoup(melhor, "html.parser").find_all(["div", "td"]) if not d.find(["div", "td"])]
    toks = [t for t in toks if t]
    i = next((k for k, t in enumerate(toks) if t.startswith("Resumo por")), 0)
    r["_tokens"] = []
    r["_tags"] = sorted({t.name for t in BeautifulSoup(melhor, "html.parser").find_all(True)})[:40]
    return r


async def main():
    hoje = datetime.now(timezone(timedelta(hours=-4))).date()
    ini, fim = hoje.replace(day=1).strftime("%d/%m/%Y"), hoje.strftime("%d/%m/%Y")
    ini, fim = os.environ.get("DATA_INI") or ini, os.environ.get("DATA_FIM") or fim   # conferência com um período fechado
    print(f"🧪 Teste do Varejo · {ini} a {fim} (nada é gravado; resultado trancado)")
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        page = await (await b.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo", viewport={"width": 1400, "height": 2400})).new_page()
        await login(page)
        out = {"periodo": [ini, fim]}
        cenarios = (("A_como_pdf", ["VAREJO"], []), ("B_filtros_varejo", TABELAS_VAREJO, FAMILIAS_VAREJO))
        if os.environ.get("SEM_ATACADO"):   # pedido do TI: todas as tabelas menos ATACADO e ATACADO PREMIUM
            cenarios = (("E_tudo_menos_atacado", TABELAS_VAREJO + ["AMAGGI", "GK FROTAS/ZANELATTO/PINGO"], FAMILIAS_VAREJO),
                        ("B_filtros_varejo", TABELAS_VAREJO, FAMILIAS_VAREJO))
        elif os.environ.get("POR_LOJA"):
            cenarios = tuple((f"F_{lj}", TABELAS_VAREJO, FAMILIAS_VAREJO, [lj]) for lj in os.environ["POR_LOJA"].split(","))
        elif os.environ.get("SO_B"):
            cenarios = (("C_sem_filtro_tabela", [], FAMILIAS_VAREJO), ("D_tabelas_fora", TABELAS_FORA_VAREJO, FAMILIAS_VAREJO))
        for nome, tab, fam, *lj in cenarios:
            print(f"\n▶ Cenário {nome}")
            try:
                out[nome] = await gerar(page, ini, fim, tab, fam, lj[0] if lj else None)
                e = out[nome].get("estabelecimentos") or []
                print(f"   lojas no resumo: {len(e)} · vendedores: {len(out[nome].get('vendedores') or [])}")
            except Exception as ex:
                out[nome] = {"erro": f"{type(ex).__name__}: {str(ex)[:200]}"}
                print("   ❌", out[nome]["erro"])
        await b.close()
    print("\n===== RESULTADO TRANCADO (início) =====")
    blob = trancar(out)
    for i in range(0, len(blob), 900):
        print("TRANCADO:" + blob[i:i + 900])
    print("===== RESULTADO TRANCADO (fim) =====")


if __name__ == "__main__":
    asyncio.run(main())
