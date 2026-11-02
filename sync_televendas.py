"""
sync_televendas.py - v6
========================
Melhoria do CSV: rotina 553 com Agrupamento=Cliente captura
itens individuais por cliente e salva em tabela separada.

━━━ MIGRAÇÃO SUPABASE — executar UMA VEZ antes de usar ━━━━━━━━━━━━━
(SQL Editor do Supabase → cole e execute)

  CREATE TABLE IF NOT EXISTS vendas_televendas_clientes (
    id               BIGSERIAL PRIMARY KEY,
    data_ref         DATE        NOT NULL,
    operador_codigo  TEXT        NOT NULL,
    operador_nome    TEXT        NOT NULL,
    codigo_cliente   TEXT        NOT NULL,
    nome_cliente     TEXT        NOT NULL,
    codigo_item      TEXT        NOT NULL,
    descricao_item   TEXT        NOT NULL,
    quantidade       NUMERIC     DEFAULT 0,
    vlr_venda        NUMERIC     DEFAULT 0,
    atualizado_em    TIMESTAMPTZ NOT NULL,
    UNIQUE(data_ref, operador_codigo, codigo_cliente, codigo_item)
  );

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mudanças vs v5:
  - MODO_DETALHADO=True agora seta Agrupamento=Cliente no formulário
  - parse_report_html_detalhado() reescrito para estrutura real do Movere:
      linha cliente → 4 células (cod, nome, '', '')
      linha item    → 13 células (cod_item, desc, ..., qty, ..., vlr_venda, ...)
      linha total   → começa com 'Total Cliente:'
  - salvar_clientes_supabase() salva em vendas_televendas_clientes (por item)
    E também salva o total agregado em vendas_televendas (para o dashboard)
  - Não precisa mais de ALTER TABLE / DROP CONSTRAINT na tabela principal
"""

import asyncio
import os
import sys
from datetime import datetime, date, timedelta, timezone
from calendar import monthrange
from html.parser import HTMLParser
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

OPERADORES = [
    {"codigo": "294862", "nome": "Graziele Garcia"},
    {"codigo": "299497", "nome": "Kessya Marques"},
    {"codigo": "286240", "nome": "Sabrina Rocha"},
    {"codigo": "298172", "nome": "Ana Clara"},
]

MOVERE_BASE   = "https://foxpneus.moveresoftware.com"
RELATORIO_URL = f"{MOVERE_BASE}/foxpneus/rotinas/005/rotina553.aspx"

# ─── Configurações ────────────────────────────────────────────────────────────

MODO_DETALHADO   = True   # True = captura itens por cliente / False = só totais (v4)
RETROATIVO       = False  # True = reprocessa TODOS os dias sem detalhes (uso pontual)
DEBUG_HTML       = True   # True = salva HTML bruto em /tmp/movere_debug_*.html
REFRESH_MES_TODO = True   # True = re-sincroniza TODOS os dias do mês atual

# ── Mês retroativo (uso pontual) ──────────────────────────────────────────────
# Para re-sincronizar um mês passado completo, preencha ANO e MES abaixo.
# Após rodar, volte ambos para None.
MES_RETRO_ANO = None   # Ex: 2026  | None = usa mês atual
MES_RETRO_MES = None   # Ex: 10    | None = usa mês atual

# ─── Classes CSS do Movere (resumo) ───────────────────────────────────────────

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
        if dt.weekday() <= 5:
            dias.append(dt.strftime('%Y-%m-%d'))
    return dias

def parse_br_number(s: str) -> float:
    try:
        return float(s.strip().replace('R$','').replace(' ','').replace('.','').replace(',','.'))
    except Exception:
        return 0.0

def parse_int(s: str) -> int:
    try:
        return int(s.strip().replace('.','').replace(',',''))
    except Exception:
        return 0

# ─── Parser modo resumo (v4) ──────────────────────────────────────────────────

def parse_report_html(html: str) -> dict:
    """Extrai pares chave/valor do relatório em modo resumo (Listar somente resumo = sim)."""
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

# ─── Parser modo detalhado (v6 — estrutura real do Movere) ────────────────────

class _TblParser(HTMLParser):
    """Parser de tabela HTML leve (sem BeautifulSoup)."""
    def __init__(self):
        super().__init__()
        self.all_rows = []
        self._row = []
        self._cell = ''
        self._in = False

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == 'tr':
            self._row = []
        elif t in ('td', 'th'):
            self._in = True; self._cell = ''

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ('td', 'th'):
            self._row.append(self._cell.strip()); self._in = False
        elif t == 'tr':
            if self._row: self.all_rows.append(self._row[:])

    def handle_data(self, data):
        if self._in: self._cell += data


def parse_report_html_detalhado(html: str) -> list:
    """
    Extrai itens individuais por cliente do HTML da rotina 553
    com Agrupamento=Cliente (sem "Listar somente resumo").

    Estrutura real do Movere:
      Linha cliente : 4 células — [cod_cli, nome_cli, '', '']
                      (primeiro campo é dígitos, últimas 2 vazias)
      Linha item    : 13 células — [cod_item, descrição, cód_fab, fornec,
                                    peso, qtd, preço_tab, vlr_venda, ...]
      Linha total   : começa com 'Total Cliente:'

    Retorna lista de dicts:
      { codigo_cliente, nome_cliente, codigo_item, descricao_item,
        quantidade, vlr_venda }
    """
    p = _TblParser()
    p.feed(html)

    records = []
    cod_cli = None
    nome_cli = None

    for cells in p.all_rows:
        if not cells:
            continue
        first = cells[0].strip()

        # ── Linha de cabeçalho de cliente ──────────────────────────────────
        # Critério: 4 células, primeira = número, células 2 e 3 vazias
        if (len(cells) == 4
                and first.isdigit()
                and not cells[2].strip()
                and not cells[3].strip()):
            cod_cli  = first
            nome_cli = cells[1].strip()
            continue

        # ── Total por cliente → ignora ─────────────────────────────────────
        if first.startswith('Total'):
            continue

        # ── Linha de item (≥ 12 células, cliente já definido) ──────────────
        # Colunas: [0]=cod_item [1]=desc [2]=cod_fab [3]=fornec
        #          [4]=peso [5]=qtd [6]=preco_tab [7]=vlr_venda ...
        if cod_cli and len(cells) >= 12:
            try:
                records.append({
                    'codigo_cliente': cod_cli,
                    'nome_cliente':   nome_cli or '',
                    'codigo_item':    cells[0],
                    'descricao_item': cells[1],
                    'quantidade':     parse_br_number(cells[5]),
                    'vlr_venda':      parse_br_number(cells[7]),
                })
            except Exception:
                pass

    return records

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

async def buscar_existentes(mes_ini: str, mes_fim: str) -> dict:
    """
    Retorna dict {(data_ref, operador_codigo): {'valor': float, 'tem_detalhes': bool}}
    Verifica a tabela principal (totais) e se já existe na tabela de detalhes.
    """
    # 1. Busca totais na tabela principal
    url_principal = (
        f"{SUPABASE_URL}/rest/v1/vendas_televendas"
        f"?select=data_ref,operador_codigo,valor_venda"
        f"&data_ref=gte.{mes_ini}&data_ref=lte.{mes_fim}"
        f"&nome_cliente=is.null"   # somente linhas de resumo
    )
    # 2. Busca detalhes existentes
    url_detalhe = (
        f"{SUPABASE_URL}/rest/v1/vendas_televendas_clientes"
        f"?select=data_ref,operador_codigo"
        f"&data_ref=gte.{mes_ini}&data_ref=lte.{mes_fim}"
        f"&limit=2000"
    )
    result = {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url_principal, headers=_headers_sb())
            if r.status_code == 200:
                for row in r.json():
                    chave = (row['data_ref'], str(row['operador_codigo']))
                    result[chave] = {
                        'valor': float(row.get('valor_venda') or 0),
                        'tem_detalhes': False
                    }
            else:
                print(f"  ⚠️  Supabase GET principal {r.status_code}: {r.text[:200]}")

            r2 = await client.get(url_detalhe, headers=_headers_sb())
            if r2.status_code == 200:
                for row in r2.json():
                    chave = (row['data_ref'], str(row['operador_codigo']))
                    if chave in result:
                        result[chave]['tem_detalhes'] = True
                    else:
                        result[chave] = {'valor': 0.0, 'tem_detalhes': True}
            # 404 = tabela ainda não existe → ignora silenciosamente
    except Exception as e:
        print(f"  ⚠️  Erro ao consultar Supabase: {e}")
    return result

async def salvar_supabase(operador: dict, data_ref: str, dados: dict, force_zero: bool = False):
    """Salva TOTAL AGREGADO em vendas_televendas (dashboard)."""
    VALOR_KEY = 'Valor Total das Notas Emitidas'
    valor = 0.0 if force_zero else parse_br_number(dados.get(VALOR_KEY, '0'))

    qtd_clientes = 0
    qtd_itens    = 0
    if not force_zero:
        qtd_cli = dados.get('Quantidade Clientes Atendidos', '0').replace('.', '')
        qtd_ite = dados.get('Quantidade Itens Atendidos',   '0').replace('.', '')
        qtd_clientes = int(qtd_cli) if qtd_cli.isdigit() else 0
        qtd_itens    = int(qtd_ite) if qtd_ite.isdigit() else 0

    payload = {
        'data_ref':        data_ref,
        'operador_codigo': operador['codigo'],
        'operador_nome':   operador['nome'],
        'valor_venda':     valor,
        'qtd_clientes':    qtd_clientes,
        'qtd_itens':       qtd_itens,
        'atualizado_em':   datetime.now(TZ_SP).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{SUPABASE_URL}/rest/v1/vendas_televendas"
                f"?on_conflict=data_ref,operador_codigo",
                headers=_headers_sb({'Prefer': 'resolution=merge-duplicates,return=minimal'}),
                json=payload,
            )
            return r.status_code, valor
    except Exception as e:
        print(f"    ⚠️  Erro ao salvar agregado: {e}")
        return 500, valor

async def salvar_clientes_supabase(operador: dict, data_ref: str, items: list) -> tuple:
    """
    Salva itens por cliente em vendas_televendas_clientes (upsert por item).
    Também salva o total agregado em vendas_televendas (para o dashboard).
    Retorna (status_code, total_valor, qtd_itens).
    """
    if not items:
        return 0, 0.0, 0

    agora    = datetime.now(TZ_SP).isoformat()
    payload  = []
    for it in items:
        payload.append({
            'data_ref':        data_ref,
            'operador_codigo': operador['codigo'],
            'operador_nome':   operador['nome'],
            'codigo_cliente':  (it.get('codigo_cliente') or '').strip(),
            'nome_cliente':    (it.get('nome_cliente')   or '').strip(),
            'codigo_item':     (it.get('codigo_item')    or '').strip(),
            'descricao_item':  (it.get('descricao_item') or '').strip(),
            'quantidade':      it.get('quantidade', 0.0),
            'vlr_venda':       it.get('vlr_venda',  0.0),
            'atualizado_em':   agora,
        })

    # ── Deduplica: mesmo (codigo_cliente, codigo_item) → soma valores ────────────
    dedup: dict = {}
    for row in payload:
        key = (row['codigo_cliente'], row['codigo_item'])
        if key in dedup:
            dedup[key]['vlr_venda']  += row['vlr_venda']
            dedup[key]['quantidade'] += row['quantidade']
        else:
            dedup[key] = dict(row)
    payload = list(dedup.values())
    # ─────────────────────────────────────────────────────────────────────────────

    total_valor   = sum(r['vlr_venda'] for r in payload)
    clientes_uniq = len({r['codigo_cliente'] for r in payload if r['codigo_cliente']})

    # 1. Upsert na tabela de detalhes (em chunks de 400)
    CHUNK = 400
    ok = 0; err = 0
    headers_upsert = _headers_sb({'Prefer': 'resolution=merge-duplicates,return=minimal'})
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(payload), CHUNK):
            chunk = payload[i:i + CHUNK]
            r = await client.post(
                f"{SUPABASE_URL}/rest/v1/vendas_televendas_clientes"
                f"?on_conflict=data_ref,operador_codigo,codigo_cliente,codigo_item",
                headers=headers_upsert,
                json=chunk,
            )
            if r.status_code in (200, 201):
                ok += len(chunk)
            else:
                err += len(chunk)
                print(f"    ⚠️  Supabase detalhe {r.status_code}: {r.text[:200]}")

        # 2. Salva total agregado em vendas_televendas (para o dashboard)
        payload_total = {
            'data_ref':        data_ref,
            'operador_codigo': operador['codigo'],
            'operador_nome':   operador['nome'],
            'valor_venda':     total_valor,
            'qtd_clientes':    clientes_uniq,
            'qtd_itens':       len(items),
            'atualizado_em':   agora,
        }
        await client.post(
            f"{SUPABASE_URL}/rest/v1/vendas_televendas"
            f"?on_conflict=data_ref,operador_codigo",
            headers=_headers_sb({'Prefer': 'resolution=merge-duplicates,return=minimal'}),
            json=payload_total,
        )

    return (200 if err == 0 else 207), total_valor, len(items)

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

# ─── Preencher formulário ─────────────────────────────────────────────────────

async def preencher_formulario(page, operador: dict, data_fmt: str):
    await page.goto(RELATORIO_URL, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(1500)

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

    # 4. Operador
    for sel in ['[id*="idcliforoperador"]','input[id*="operador"]',
                'input[id*="Operador"]','input[name*="operador"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.clear()
                await el.type(operador['codigo'], delay=80)
                await page.wait_for_timeout(1200)
                for drop in ['li.autocomplete-result','.dropdown-item','[class*="suggest"]']:
                    try:
                        item = page.locator(drop).first
                        if await item.count() > 0:
                            await item.click(); break
                    except Exception:
                        pass
                await el.press('Tab')
                await page.wait_for_timeout(600)
                break
        except Exception:
            pass

    # 5. Checkboxes e Agrupamento
    if MODO_DETALHADO:
        # Modo detalhado:
        #   - "Listar somente resumo" → DESMARCADO
        #   - "Filtrar somente base de venda" → MARCADO
        #   - Agrupamento → CLIENTE (radio button)
        await page.evaluate("""() => {
            function findAndSet(texto, tipo, valor) {
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

            // Desmarca "Listar somente resumo"
            findAndSet('Listar somente resumo', 'checkbox', false);
            // Marca "Filtrar somente base de venda"
            findAndSet('Filtrar somente base de venda', 'checkbox', true);

            // Agrupamento = Cliente (radio button)
            // Estratégia 1: localiza a linha que contém Vendedor/Fornecedor/Cliente
            // e procura o radio dentro da célula com texto "Cliente"
            let clienteRadioMarcado = false;
            for (const row of document.querySelectorAll('tr')) {
                const txt = row.innerText || '';
                if (txt.includes('Vendedor') && txt.includes('Fornecedor') && txt.includes('Cliente')) {
                    // Tenta por texto "Cliente"
                    for (const el of row.querySelectorAll('td, span, label, div')) {
                        const elTxt = (el.innerText||'').trim();
                        if (el.childElementCount === 0 && elTxt === 'Cliente') {
                            const td = el.closest('td') || el.parentElement;
                            if (td) {
                                const radio = td.querySelector('input[type="radio"]');
                                if (radio) {
                                    radio.checked = true;
                                    radio.dispatchEvent(new Event('change',{bubbles:true}));
                                    clienteRadioMarcado = true; break;
                                }
                            }
                            const prev = el.previousElementSibling;
                            if (prev && prev.type === 'radio') {
                                prev.checked = true;
                                prev.dispatchEvent(new Event('change',{bubbles:true}));
                                clienteRadioMarcado = true; break;
                            }
                        }
                    }
                    // Estratégia 2: pega todos os radios da linha e marca o último
                    // (ordem usual: Vendedor=0, Fornecedor=1, Estabelecimento=2, Cliente=3)
                    if (!clienteRadioMarcado) {
                        const radios = Array.from(row.querySelectorAll('input[type="radio"]'));
                        if (radios.length > 0) {
                            const r = radios[radios.length - 1];
                            r.checked = true;
                            r.dispatchEvent(new Event('change',{bubbles:true}));
                            clienteRadioMarcado = true;
                        }
                    }
                    break;
                }
            }
            // Estratégia 3: qualquer radio cujo label/parent contém "Cliente"
            if (!clienteRadioMarcado) {
                for (const r of document.querySelectorAll('input[type="radio"]')) {
                    const ctx = (r.closest('td')||r.parentElement||{}).innerText || '';
                    if (ctx.trim() === 'Cliente' || (r.nextSibling && (r.nextSibling.textContent||'').trim() === 'Cliente')) {
                        r.checked = true;
                        r.dispatchEvent(new Event('change',{bubbles:true}));
                        break;
                    }
                }
            }
        }""")
    else:
        # Modo resumo (v4 puro)
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
                        if (inp) { inp.checked = valor;
                                   inp.dispatchEvent(new Event('change',{bubbles:true})); return true; }
                    }
                }
                return false;
            }
            check('Listar somente resumo',        'checkbox', true);
            check('Filtrar somente base de venda', 'checkbox', true);
        }""")
    await page.wait_for_timeout(400)

    # FIX: desmarcar checkboxes de aro acidentalmente marcados
    await page.evaluate("""() => {
        for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
            if (!cb.checked) continue;
            const container = cb.closest('tr') || cb.closest('td') || cb.parentElement;
            const txt = [
                container ? (container.innerText||'') : '',
                cb.id||'', cb.name||'', cb.value||''
            ].join(' ');
            if (/aro/i.test(txt)) {
                cb.checked = false;
                cb.dispatchEvent(new Event('change', {bubbles: true}));
            }
        }
    }""")
    await page.wait_for_timeout(300)

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

async def buscar_relatorio(page, operador: dict, data_iso: str) -> str | None:
    html_cap = []
    data_fmt = datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')

    async def on_resp(response):
        if 'ImpressaoRelatorio' in response.url and response.status == 200:
            ct = response.headers.get('content-type', '')
            if 'html' in ct.lower():
                try:
                    body = await response.text()
                    tem_resumo  = 'a5119' in body or 'Valor Venda' in body
                    tem_detalhe = 'Total Cliente' in body
                    if (tem_resumo or tem_detalhe) and len(body) > 500:
                        html_cap.append(body)
                except Exception:
                    pass

    await preencher_formulario(page, operador, data_fmt)

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
    return html_cap[-1] if html_cap else None

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    if not MOVERE_USER or not MOVERE_PASS:
        print("❌  MOVERE_USER / MOVERE_PASS não definidos!")
        sys.exit(1)

    agora_sp  = datetime.now(TZ_SP)
    hoje      = agora_sp.date()
    import calendar as _cal

    if MES_RETRO_ANO and MES_RETRO_MES:
        ano, mes = MES_RETRO_ANO, MES_RETRO_MES
        data_ref_fim = date(ano, mes, _cal.monthrange(ano, mes)[1])
    else:
        ano, mes = hoje.year, hoje.month
        data_ref_fim = hoje

    data_hoje  = hoje.strftime('%Y-%m-%d')
    ultimo_dia = _cal.monthrange(ano, mes)[1]
    mes_ini    = f"{ano}-{mes:02d}-01"
    mes_fim    = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    modo_txt = "DETALHADO (itens por cliente → vendas_televendas_clientes)" if MODO_DETALHADO else "RESUMO (totais)"
    print(f"\n🔄  Sync Televendas v6 — {agora_sp.strftime('%d/%m/%Y %H:%M')} (Brasília)")
    print(f"    Modo: {modo_txt}\n")

    todos_dias = dias_uteis_mes(ano, mes, data_ref_fim)
    print(f"  Dias úteis até hoje : {len(todos_dias)}  ({todos_dias[0] if todos_dias else '-'} → {todos_dias[-1] if todos_dias else '-'})")

    existentes = await buscar_existentes(mes_ini, mes_fim)
    print(f"  Registros Supabase  : {len(existentes)} pares (data, operador)")

    eh_retro   = bool(MES_RETRO_ANO and MES_RETRO_MES)
    mes_atual  = data_hoje[:7]
    dias_mes_atual = set(d for d in todos_dias if d.startswith(mes_atual))

    if eh_retro:
        print(f"  ⚠️  Modo RETROATIVO: re-sincronizando {mes:02d}/{ano} completo\n")

    fila = []

    # ── Mês anterior: verifica dias faltando / com zero ──────────────────────
    if not eh_retro:
        prev_mes = mes - 1 if mes > 1 else 12
        prev_ano = ano if mes > 1 else ano - 1
        prev_ult = _cal.monthrange(prev_ano, prev_mes)[1]
        prev_ini = f"{prev_ano}-{prev_mes:02d}-01"
        prev_fim = f"{prev_ano}-{prev_mes:02d}-{prev_ult:02d}"
        dias_prev = dias_uteis_mes(prev_ano, prev_mes, date(prev_ano, prev_mes, prev_ult))
        exist_prev = await buscar_existentes(prev_ini, prev_fim)
        faltando_prev = sum(
            1 for d in dias_prev for op in OPERADORES
            if exist_prev.get((d, op['codigo'])) is None
            or exist_prev.get((d, op['codigo']), {}).get('valor', 1) == 0.0
        )
        if faltando_prev:
            print(f"  Mês anterior ({prev_mes:02d}/{prev_ano}) : {faltando_prev} pares faltando/zero → serão sincronizados")
        for dia in dias_prev:
            for op in OPERADORES:
                chave = (dia, op['codigo'])
                info  = exist_prev.get(chave)
                if info is None:
                    fila.append((dia, op, 'novo'))
                elif info['valor'] == 0.0:
                    fila.append((dia, op, 'zero'))
                elif MODO_DETALHADO and not info['tem_detalhes']:
                    fila.append((dia, op, 'retroativo'))

    for dia in todos_dias:
        for op in OPERADORES:
            chave = (dia, op['codigo'])
            info  = existentes.get(chave)
            eh_hoje    = (dia == data_hoje)
            eh_mes_atual = (dia in dias_mes_atual)

            if eh_retro:
                fila.append((dia, op, 'retro_mes'))
            elif info is None:
                fila.append((dia, op, 'novo'))
            elif info['valor'] == 0.0:
                fila.append((dia, op, 'zero'))
            elif eh_hoje:
                fila.append((dia, op, 'hoje'))
            elif REFRESH_MES_TODO and eh_mes_atual:
                fila.append((dia, op, 'mes_atual'))
            elif MODO_DETALHADO and RETROATIVO and not info['tem_detalhes']:
                fila.append((dia, op, 'retroativo'))
            # else: valor > 0, mês anterior, mantém

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

        total_hoje  = 0.0
        qtd_ok      = 0
        qtd_itens_t = 0
        qtd_skip    = 0

        for i, (dia, op, motivo) in enumerate(fila):
            data_br = datetime.strptime(dia, '%Y-%m-%d').strftime('%d/%m/%Y')
            eh_hoje = (dia == data_hoje)
            info_anterior = existentes.get((dia, op['codigo']))

            print(f"  [{i+1:>3}/{len(fila)}] {data_br}  {op['nome']}  [{motivo}]…")
            try:
                html = await buscar_relatorio(page, op, dia)

                if html:
                    if DEBUG_HTML:
                        dbg = f"/tmp/movere_debug_{op['codigo']}_{dia}.html"
                        with open(dbg, 'w', encoding='utf-8') as f:
                            f.write(html)
                        print(f"    🔍  HTML salvo: {dbg}")

                    if MODO_DETALHADO:
                        items = parse_report_html_detalhado(html)

                        if items:
                            st, total, n = await salvar_clientes_supabase(op, dia, items)
                            emoji = "✅" if st in (200, 201) else "⚠️"
                            cli_uniq = len({it['codigo_cliente'] for it in items if it.get('codigo_cliente')})
                            print(f"    {emoji}  R$ {total:>12,.2f}  —  {cli_uniq} clientes, {n} itens  (Supabase {st})")
                            if eh_hoje: total_hoje += total
                            qtd_ok      += 1
                            qtd_itens_t += n
                        else:
                            # Fallback: salva só o total agregado (v4)
                            dados = parse_report_html(html)
                            if dados:
                                st, v = await salvar_supabase(op, dia, dados)
                                emoji = "✅" if st in (200, 201) else "⚠️"
                                print(f"    {emoji}  R$ {v:>12,.2f}  (fallback resumo — sem itens no HTML)")
                                if eh_hoje: total_hoje += v
                                qtd_ok += 1
                            else:
                                if eh_hoje:
                                    await salvar_supabase(op, dia, {}, force_zero=True)
                                    print(f"    —   R$ 0,00  (HTML sem estrutura reconhecida)")
                                else:
                                    _v = info_anterior['valor'] if info_anterior else 0
                                    print(f"    🔒  HTML sem estrutura — mantendo R$ {_v:,.2f}")
                                qtd_skip += 1
                    else:
                        # Modo resumo puro (v4)
                        dados = parse_report_html(html)
                        st, v = await salvar_supabase(op, dia, dados)
                        emoji = "✅" if st in (200, 201) else "⚠️"
                        print(f"    {emoji}  R$ {v:>12,.2f}  (Supabase {st})")
                        if eh_hoje: total_hoje += v
                        qtd_ok += 1

                elif eh_hoje:
                    st, _ = await salvar_supabase(op, dia, {}, force_zero=True)
                    print(f"    —   R$ 0,00  (sem vendas hoje — Supabase {st})")
                else:
                    _v = info_anterior['valor'] if info_anterior else 0
                    if _v > 0:
                        print(f"    🔒  Sem HTML — mantendo R$ {_v:,.2f}")
                    else:
                        print(f"    ⚠️  Sem HTML — pulando")
                    qtd_skip += 1

            except Exception as e:
                print(f"    ❌  Erro: {e}")
                import traceback; traceback.print_exc()
                qtd_skip += 1

            if (i + 1) % 25 == 0 and (i + 1) < len(fila):
                print("\n  🔁  Re-login para manter sessão…\n")
                try:
                    await login(page)
                except Exception:
                    pass

        await browser.close()

    print(f"\n{'─'*50}")
    print(f"  Capturados      : {qtd_ok}/{len(fila)}")
    if MODO_DETALHADO and qtd_itens_t > 0:
        print(f"  Itens salvos    : {qtd_itens_t}")
    print(f"  Pulados/erro    : {qtd_skip}/{len(fila)}")
    if total_hoje > 0:
        print(f"  Total hoje      : R$ {total_hoje:,.2f}")
    print(f"{'─'*50}\n")


if __name__ == '__main__':
    asyncio.run(main())
