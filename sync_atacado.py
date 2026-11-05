"""
sync_atacado.py - v2
=====================
Sync de vendas dos Vendedores de Atacado (Fox Pneus).
Tabelas Supabase: vendas_atacado (totais diários por vendedor).

━━━ MIGRAÇÃO SUPABASE — executar UMA VEZ antes de usar ━━━━━━━━━━━━━
(SQL Editor do Supabase → cole e execute)

  CREATE TABLE IF NOT EXISTS vendas_atacado (
    id               BIGSERIAL PRIMARY KEY,
    data_ref         DATE        NOT NULL,
    vendedor_codigo  TEXT        NOT NULL,
    vendedor_nome    TEXT        NOT NULL,
    valor_venda      NUMERIC     DEFAULT 0,
    atualizado_em    TIMESTAMPTZ NOT NULL,
    UNIQUE(data_ref, vendedor_codigo)
  );

  CREATE TABLE IF NOT EXISTS metas_atacado (
    id              BIGSERIAL PRIMARY KEY,
    mes_ref         TEXT        NOT NULL,
    vendedor_codigo TEXT        NOT NULL,
    vendedor_nome   TEXT        NOT NULL,
    meta_valor      NUMERIC     DEFAULT 0,
    dias_uteis_mes  INTEGER     DEFAULT 22,
    atualizado_em   TIMESTAMPTZ NOT NULL,
    UNIQUE(mes_ref, vendedor_codigo)
  );

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import os
import sys
from datetime import datetime, date, timedelta, timezone
from calendar import monthrange
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import httpx

TZ_SP = timezone(timedelta(hours=-3))

MOVERE_USER = os.environ.get("MOVERE_USER", "")
MOVERE_PASS = os.environ.get("MOVERE_PASS", "")

SUPABASE_URL = "https://dxwkiaxpygibzmwzvcuz.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR4d2tpYXhweWdpYnptd3p2Y3V6Iiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3NzczMTE3NzcsImV4cCI6MjA5Mjg4Nzc3N30"
    ".mVbUlLaRCI5OMf539Ehjt-XpfAY-wjr7_WCzPsgVvp0"
)

VENDEDORES = [
    {"codigo": "291608", "nome": "Niorrana Carriço Ghisleri"},
    {"codigo": "303101", "nome": "Nayza Minelli Pereira Oliveira"},
    {"codigo": "322540", "nome": "Alyssandra Sales Marinho"},
    {"codigo": "309110", "nome": "Camila da Silva Feitoza"},
    {"codigo": "318707", "nome": "Camila Ramos Brilhante"},
    {"codigo": "324865", "nome": "Rafaela Fernandes da Silva"},
]

MOVERE_BASE   = "https://foxpneus.moveresoftware.com"
RELATORIO_URL = f"{MOVERE_BASE}/foxpneus/rotinas/005/rotina553.aspx"

REFRESH_MES_TODO = True  # re-sincroniza todos os dias do mês atual a cada sync

# Classes CSS do Movere (resumo)
LABEL_CLS = [
    'a5119','a5128','a5137','a5146','a5155','a5164','a5173','a5182',
    'a5191','a5200','a5209','a5218','a5227','a5236','a5245','a5261'
]
VALUE_CLS = [
    'a5123','a5132','a5141','a5150','a5159','a5168','a5177','a5186',
    'a5195','a5204','a5213','a5222','a5231','a5240','a5249','a5265'
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def dias_uteis_mes(ano: int, mes: int, ate_hoje: date) -> list:
    total = monthrange(ano, mes)[1]
    dias = []
    for d in range(1, total + 1):
        dt = date(ano, mes, d)
        if dt > ate_hoje:
            break
        if dt.weekday() <= 5:  # 0=Seg … 5=Sáb
            dias.append(dt.strftime('%Y-%m-%d'))
    return dias

def parse_br_number(s: str) -> float:
    try:
        return float(s.strip().replace('R$','').replace(' ','').replace('.','').replace(',','.'))
    except Exception:
        return 0.0

# ─── Parser resumo ────────────────────────────────────────────────────────────

def parse_report_html(html: str) -> dict:
    """Extrai pares chave/valor do relatório em modo resumo."""
    soup = BeautifulSoup(html, 'html.parser')
    data = {}
    label = None
    for div in soup.find_all('div'):
        cls_list = div.get('class', [])
        cls = cls_list[0] if cls_list else ''
        text = div.get_text(strip=True)
        if not text:
            continue
        if cls in LABEL_CLS:
            label = text
        elif cls in VALUE_CLS and label:
            data[label] = text
            label = None
    return data

# ─── Supabase ─────────────────────────────────────────────────────────────────

def _headers_sb(extras: dict = None) -> dict:
    h = {
        'apikey':        SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type':  'application/json',
    }
    if extras:
        h.update(extras)
    return h

async def buscar_existentes_atacado(mes_ini: str, mes_fim: str) -> dict:
    """Retorna dict {(data_ref, vendedor_codigo): valor_venda}"""
    url = (
        f"{SUPABASE_URL}/rest/v1/vendas_atacado"
        f"?select=data_ref,vendedor_codigo,valor_venda"
        f"&data_ref=gte.{mes_ini}&data_ref=lte.{mes_fim}"
    )
    result = {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=_headers_sb())
            if r.status_code == 200:
                for row in r.json():
                    chave = (row['data_ref'], str(row['vendedor_codigo']))
                    result[chave] = float(row.get('valor_venda') or 0)
            else:
                print(f"  ⚠️  Supabase GET {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  ⚠️  Erro ao consultar Supabase: {e}")
    return result

async def salvar_atacado(vendedor: dict, data_ref: str, valor: float) -> int:
    """Salva total de vendas do vendedor em vendas_atacado."""
    payload = {
        'data_ref':        data_ref,
        'vendedor_codigo': vendedor['codigo'],
        'vendedor_nome':   vendedor['nome'],
        'valor_venda':     valor,
        'atualizado_em':   datetime.now(TZ_SP).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{SUPABASE_URL}/rest/v1/vendas_atacado"
                f"?on_conflict=data_ref,vendedor_codigo",
                headers=_headers_sb({'Prefer': 'resolution=merge-duplicates,return=minimal'}),
                json=payload,
            )
            return r.status_code
    except Exception as e:
        print(f"    ⚠️  Erro ao salvar: {e}")
        return 500

# ─── Login ────────────────────────────────────────────────────────────────────

async def login(page):
    print("  🔑  Login no Movere…")
    await page.goto(f"{MOVERE_BASE}/foxpneus/default.aspx",
                    wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(2000)

    for sel in ['#txtLogin', 'input[name="txtLogin"]', 'input[type="text"]:visible']:
        try:
            if await page.locator(sel).count() > 0:
                await page.fill(sel, MOVERE_USER); break
        except Exception:
            pass

    for sel in ['#txtSenha', 'input[name="txtSenha"]', 'input[type="password"]:visible']:
        try:
            if await page.locator(sel).count() > 0:
                await page.fill(sel, MOVERE_PASS); break
        except Exception:
            pass

    for sel in ['#btnEntrar', 'input[value="Entrar"]',
                'button:has-text("Entrar")', 'input[type="submit"]:visible']:
        try:
            if await page.locator(sel).count() > 0:
                await page.click(sel); break
        except Exception:
            pass

    await page.wait_for_load_state('networkidle', timeout=20000)
    print("  ✅  Login OK!")

# ─── Preencher formulário (Vendedor 1) ───────────────────────────────────────

async def _fill_autocomplete_field(page, selectors: list[str], codigo: str, label_debug: str) -> bool:
    """Preenche campo de autocomplete do Movere com código.
    Retorna True se o campo foi encontrado e preenchido."""

    # --- diagnóstico: lista todos os inputs disponíveis ---
    all_ids = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('input[type="text"],input:not([type])'))
               .map(el => el.id + '|' + el.name + '|' + el.className)
               .filter(s => s.trim() !== '||');
    }""")
    print(f"  DEBUG inputs ({label_debug}): {all_ids[:20]}")

    for sel in selectors:
        try:
            el = page.locator(sel).first
            cnt = await el.count()
            if cnt == 0:
                continue
            print(f"  🎯 {label_debug}: usando seletor '{sel}'")

            await el.scroll_into_view_if_needed()
            await el.click(click_count=3)
            await el.type(codigo, delay=80)
            await page.wait_for_timeout(2000)   # aguarda autocomplete AJAX

            # 1ª tentativa: clique no primeiro item da lista suspensa
            autocomplete_ok = False
            for drop_sel in [
                'li.autocomplete-result',
                '.dropdown-item',
                '[class*="suggest"]',
                '.ui-menu-item',
                '.ui-autocomplete li',
                '[class*="autocomplete"] li',
                '[class*="result"]',
            ]:
                try:
                    item = page.locator(drop_sel).first
                    if await item.count() > 0:
                        await item.click()
                        autocomplete_ok = True
                        print(f"    Autocomplete clicado via '{drop_sel}'")
                        break
                except Exception:
                    pass

            # 2ª tentativa: teclado (ArrowDown + Enter) — funciona em qualquer autocomplete jQuery-UI
            if not autocomplete_ok:
                await el.press('ArrowDown')
                await page.wait_for_timeout(400)
                await page.keyboard.press('Enter')
                await page.wait_for_timeout(400)
                print(f"    Autocomplete via ArrowDown+Enter")

            await page.wait_for_timeout(700)

            # verifica o que ficou no campo
            val = await el.input_value()
            print(f"    Valor campo após fill: '{val}'")
            return True

        except Exception as e:
            print(f"  Seletor '{sel}' erro: {e}")

    return False


async def preencher_formulario_atacado(page, vendedor: dict, data_fmt: str):
    await page.goto(RELATORIO_URL, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(2000)

    # 1. Visão Empresarial = 1
    await page.evaluate("""() => {
        const inp = document.querySelector('[id*="idvisaoempresarial"]');
        if (inp && (!inp.value || inp.value.trim() === '')) {
            inp.value = '1';
            ['input','change','blur'].forEach(e =>
                inp.dispatchEvent(new Event(e, {bubbles:true})));
        }
    }""")
    await page.wait_for_timeout(600)

    # 2. Data Inicial
    for sel in ['[id*="cdtaini"]','[name*="cdtaini"]',
                'input[id*="dtaini"]','input[id*="DataIni"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click(click_count=3)
                await el.fill(data_fmt)
                await el.press('Tab')
                break
        except Exception:
            pass
    await page.wait_for_timeout(400)

    # 3. Data Final
    for sel in ['[id*="cdtafim"]','[name*="cdtafim"]',
                'input[id*="dtafim"]','input[id*="DataFim"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click(click_count=3)
                await el.fill(data_fmt)
                await el.press('Tab')
                break
        except Exception:
            pass
    await page.wait_for_timeout(400)

    # 4. Vendedor 1 — seletores ampliados + autocomplete robusto
    vendedor_preenchido = await _fill_autocomplete_field(
        page,
        selectors=[
            '[id*="idcliforvendedor1"]',   # padrão Movere (igual operador)
            '[id*="idcliforvendedor"]',    # sem número — pega o 1º
            '[id*="vendedor1"]',
            '[id*="Vendedor1"]',
            'input[id*="vendedor"][id*="1"]',
            'input[name*="vendedor1"]',
            'input[name*="Vendedor1"]',
        ],
        codigo=vendedor['codigo'],
        label_debug='Vendedor1',
    )

    # Fallback: busca campo via proximidade ao label "Vendedor 1"
    if not vendedor_preenchido:
        print(f"  ⚠️  Seletores diretos não encontraram campo — tentando JS por label…")
        result = await page.evaluate(f"""() => {{
            const codigo = '{vendedor['codigo']}';
            for (const el of document.querySelectorAll('td,label,span,div,th')) {{
                const txt = (el.innerText || el.textContent || '').trim();
                if (txt === 'Vendedor 1' || txt === 'Vendedor1') {{
                    const container = el.closest('tr') || el.parentElement;
                    if (!container) continue;
                    const input = container.querySelector('input[type="text"],input:not([type])');
                    if (input) {{
                        input.focus();
                        input.click();
                        input.value = codigo;
                        ['input','change','blur','keyup'].forEach(e =>
                            input.dispatchEvent(new Event(e, {{bubbles:true}})));
                        return 'OK:' + input.id + '/' + input.name;
                    }}
                }}
            }}
            return 'NOT_FOUND';
        }}""")
        print(f"    JS fallback: {result}")
        await page.wait_for_timeout(1500)
        # ArrowDown+Enter mesmo via fallback
        await page.keyboard.press('ArrowDown')
        await page.wait_for_timeout(400)
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(600)

    # 5. Modo resumo + filtro base de venda
    await page.evaluate("""() => {
        function check(texto, tipo, valor) {
            for (const el of document.querySelectorAll('td,label,span,div')) {
                if (el.childElementCount === 0 && el.innerText &&
                    el.innerText.trim().replace(/[?]/g,'').includes(texto)) {
                    let inp = el.querySelector('input[type="'+tipo+'"]')
                           || (() => { const row = el.closest('tr')||el.parentElement;
                                       return row && row.querySelector('input[type="'+tipo+'"]'); })()
                           || (() => { const n = el.nextElementSibling;
                                       return n && n.querySelector('input[type="'+tipo+'"]'); })();
                    if (inp) {
                        inp.checked = valor;
                        inp.dispatchEvent(new Event('change',{bubbles:true}));
                        return true;
                    }
                }
            }
            return false;
        }
        check('Listar somente resumo',         'checkbox', true);
        check('Filtrar somente base de venda',  'checkbox', true);
    }""")
    await page.wait_for_timeout(400)

    # 6. Formato HTML
    try:
        for sel_el in await page.query_selector_all('select'):
            for opt in await sel_el.query_selector_all('option'):
                txt = await opt.inner_text()
                if 'HTML' in txt or 'Visualiza' in txt:
                    await sel_el.select_option(value=await opt.get_attribute('value'))
                    break
    except Exception:
        pass
    await page.wait_for_timeout(300)

# ─── Capturar relatório ───────────────────────────────────────────────────────

async def buscar_relatorio_atacado(page, vendedor: dict, data_iso: str) -> str | None:
    html_cap = []
    data_fmt = datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')

    async def on_resp(response):
        if 'ImpressaoRelatorio' in response.url and response.status == 200:
            ct = response.headers.get('content-type', '')
            if 'html' in ct.lower():
                try:
                    body = await response.text()
                    if ('a5119' in body or 'Valor Venda' in body or
                            'Valor Total' in body) and len(body) > 300:
                        html_cap.append(body)
                except Exception:
                    pass

    await preencher_formulario_atacado(page, vendedor, data_fmt)

    try:
        await page.wait_for_load_state('networkidle', timeout=8000)
    except Exception:
        pass

    page.on('response', on_resp)

    for sel in ['input[value="Executar"]','#btnExecutar',
                'button:has-text("Executar")','input[type="submit"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click(); break
        except Exception:
            pass

    for _ in range(40):
        if html_cap: break
        await page.wait_for_timeout(500)

    if html_cap:
        try:
            await page.wait_for_load_state('networkidle', timeout=6000)
        except Exception:
            pass
        await page.wait_for_timeout(500)

    page.remove_listener('response', on_resp)

    if not html_cap:
        return None

    html = html_cap[-1]

    # ── Verificação crítica: o vendedor foi realmente filtrado? ──────────────
    # O relatório exibe "Vendedor 1: 291608-NOME" na seção de filtros.
    # Se o campo ficou vazio, o código do vendedor NÃO estará no HTML.
    if vendedor['codigo'] not in html:
        print(f"    ❌  AVISO: código {vendedor['codigo']} NÃO encontrado no HTML "
              f"→ Vendedor 1 não foi filtrado! Descartando resultado para evitar dado errado.")
        return None

    return html

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    if not MOVERE_USER or not MOVERE_PASS:
        print("❌  MOVERE_USER / MOVERE_PASS não definidos!")
        sys.exit(1)

    agora_sp = datetime.now(TZ_SP)
    hoje     = agora_sp.date()
    import calendar as _cal

    ano, mes     = hoje.year, hoje.month
    ultimo_dia   = _cal.monthrange(ano, mes)[1]
    mes_ini      = f"{ano}-{mes:02d}-01"
    mes_fim      = f"{ano}-{mes:02d}-{ultimo_dia:02d}"
    data_hoje    = hoje.strftime('%Y-%m-%d')
    mes_atual_str = data_hoje[:7]

    print(f"\n🔄  Sync Atacado v1 — {agora_sp.strftime('%d/%m/%Y %H:%M')} (Brasília)\n")

    todos_dias = dias_uteis_mes(ano, mes, hoje)
    print(f"  Dias úteis até hoje : {len(todos_dias)}")

    existentes = await buscar_existentes_atacado(mes_ini, mes_fim)
    print(f"  Registros Supabase  : {len(existentes)} pares (data, vendedor)")

    fila = []
    for dia in todos_dias:
        for v in VENDEDORES:
            chave = (dia, v['codigo'])
            valor_atual = existentes.get(chave)
            eh_hoje      = (dia == data_hoje)
            eh_mes_atual = dia.startswith(mes_atual_str)

            if valor_atual is None:
                fila.append((dia, v, 'novo'))
            elif valor_atual == 0.0:
                fila.append((dia, v, 'zero'))
            elif eh_hoje:
                fila.append((dia, v, 'hoje'))
            elif REFRESH_MES_TODO and eh_mes_atual:
                fila.append((dia, v, 'mes_atual'))
            # else: valor > 0, mantém

    print(f"  Queries a executar  : {len(fila)}\n")

    if not fila:
        print("  ✅  Tudo já atualizado.\n")
        return

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
        )
        page = await context.new_page()

        try:
            await login(page)
        except Exception as e:
            print(f"❌  Erro no login: {e}")
            await browser.close()
            return

        total_hoje = 0.0
        qtd_ok     = 0
        qtd_skip   = 0

        for i, (dia, v, motivo) in enumerate(fila):
            data_br = datetime.strptime(dia, '%Y-%m-%d').strftime('%d/%m/%Y')
            eh_hoje = (dia == data_hoje)
            print(f"  [{i+1:>3}/{len(fila)}] {data_br}  {v['nome']}  [{motivo}]…")

            try:
                html = await buscar_relatorio_atacado(page, v, dia)

                if html:
                    dados = parse_report_html(html)
                    VALOR_KEY = 'Valor Total das Notas Emitidas'
                    valor = parse_br_number(dados.get(VALOR_KEY, '0')) if dados else 0.0

                    # Fallback: tenta outras chaves se a principal não encontrar
                    if valor == 0.0 and dados:
                        for k in ['Valor Venda', 'Valor Venda Líquida (Venda - Devolução)']:
                            v2 = parse_br_number(dados.get(k, '0'))
                            if v2 > 0:
                                valor = v2; break

                    st = await salvar_atacado(v, dia, valor)
                    emoji = "✅" if st in (200, 201) else "⚠️"
                    print(f"    {emoji}  R$ {valor:>12,.2f}  (Supabase {st})")
                    if eh_hoje:
                        total_hoje += valor
                    qtd_ok += 1

                elif eh_hoje:
                    st = await salvar_atacado(v, dia, 0.0)
                    print(f"    —   R$ 0,00  (sem vendas hoje — Supabase {st})")
                else:
                    print(f"    ⚠️  Sem HTML — pulando")
                    qtd_skip += 1

            except Exception as e:
                print(f"    ❌  Erro: {e}")
                import traceback; traceback.print_exc()
                qtd_skip += 1

            # Re-login a cada 20 queries para manter sessão
            if (i + 1) % 20 == 0 and (i + 1) < len(fila):
                print("\n  🔁  Re-login para manter sessão…\n")
                try:
                    await login(page)
                except Exception:
                    pass

        await browser.close()

    print(f"\n{'─'*50}")
    print(f"  Capturados  : {qtd_ok}/{len(fila)}")
    print(f"  Pulados     : {qtd_skip}/{len(fila)}")
    if total_hoje > 0:
        print(f"  Total hoje  : R$ {total_hoje:,.2f}")
    print(f"{'─'*50}\n")


if __name__ == '__main__':
    asyncio.run(main())
