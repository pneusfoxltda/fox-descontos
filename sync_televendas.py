"""
sync_televendas.py - v5
========================
Agora captura clientes individuais por venda (modo detalhado).
Com fallback automático para totais agregados (comportamento v4).

━━━ MIGRAÇÃO SUPABASE — executar UMA VEZ antes de usar ━━━━━━━━━━━━━
(SQL Editor do Supabase → cole e execute)

  -- 1. Adicionar colunas de cliente
  ALTER TABLE vendas_televendas
    ADD COLUMN IF NOT EXISTS nome_cliente   TEXT,
    ADD COLUMN IF NOT EXISTS codigo_cliente TEXT;

  -- 2. Remover constraint única antiga (impede múltiplas linhas por op/dia)
  --    Para saber o nome exato: SELECT constraint_name
  --    FROM information_schema.table_constraints
  --    WHERE table_name = 'vendas_televendas';
  ALTER TABLE vendas_televendas
    DROP CONSTRAINT IF EXISTS vendas_televendas_data_ref_operador_codigo_key;

  -- (Opcional) Adicionar nova constraint de 3 colunas:
  -- ALTER TABLE vendas_televendas
  --   ADD CONSTRAINT vendas_televendas_unico
  --   UNIQUE(data_ref, operador_codigo, codigo_cliente);
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mudanças vs v4:
  - MODO_DETALHADO: desmarca "Listar somente resumo" → relatório com clientes individuais
  - RETROATIVO:     se True, reprocessa dias passados que só têm dados agregados
  - DEBUG_HTML:     salva HTML bruto em /tmp para depurar a estrutura do Movere
  - parse_report_html_detalhado(): extrai tabela de clientes do relatório expandido
  - deletar_dia_operador():        apaga linhas antigas antes de inserir novas
  - salvar_clientes_supabase():    insere uma linha por cliente em batch

Lógica:
  1. Busca Supabase: quais (data, operador) existem, valor total e se tem clientes
  2. Fila = sem dados + R$0 + hoje + mês atual (REFRESH_MES_TODO) + (sem clientes se RETROATIVO=True)
  3. Movere (modo detalhado):
     → Achou clientes:   apaga linhas antigas, insere uma por cliente
     → Não achou + hoje: salva R$0 agregado (sem vendas ainda)
     → Não achou + passado: mantém o que já existe no Supabase
  4. Fallback: se o parser não reconhecer a estrutura HTML,
     salva o resumo agregado (comportamento v4 — sem perder dados)
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

OPERADORES = [
    {"codigo": "294862", "nome": "Graziele Garcia"},
    {"codigo": "299497", "nome": "Kessya Marques"},
    {"codigo": "286240", "nome": "Sabrina Rocha"},
    {"codigo": "298172", "nome": "Ana Clara"},
]

MOVERE_BASE   = "https://foxpneus.moveresoftware.com"
RELATORIO_URL = f"{MOVERE_BASE}/foxpneus/rotinas/005/rotina553.aspx"

# ─── Configurações v5 ─────────────────────────────────────────────────────────

MODO_DETALHADO   = False  # True = captura clientes individuais / False = v4 (só totais)
RETROATIVO       = False  # True = reprocessa TODOS os dias sem clientes (uso pontual)
DEBUG_HTML       = False  # True = salva HTML bruto em /tmp/movere_debug_*.html
REFRESH_MES_TODO = True   # True = re-sincroniza TODOS os dias do mês atual (vendas retroativas)

# ── MÊS RETROATIVO (uso pontual) ─────────────────────────────────────────────
# Para re-sincronizar um mês passado completo, preencha ANO e MES abaixo.
# Após rodar, volte ambos para None.
MES_RETRO_ANO = 2026   # Ex: 2026  | None = usa mês atual
MES_RETRO_MES = 10     # Ex: 10    | None = usa mês atual

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
        if dt.weekday() <= 5:          # seg–sáb
            dias.append(dt.strftime('%Y-%m-%d'))
    return dias

def parse_br_number(s: str) -> float:
    """Converte '1.234,56' → 1234.56"""
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

# ─── Parser modo detalhado (v5) ───────────────────────────────────────────────

def parse_report_html_detalhado(html: str) -> list[dict]:
    """
    Tenta extrair linhas individuais de clientes do relatório detalhado.
    Retorna lista de dicts {codigo_cliente, nome_cliente, qtd_itens, valor_venda}
    ou lista vazia se a estrutura não for reconhecida.

    O Movere rotina 553 sem "Listar somente resumo" provavelmente exibe
    uma tabela HTML com colunas como "Cód. Cliente", "Nome", "Qtd. Itens", "Valor".
    Esta função tenta detectar esse padrão automaticamente.
    """
    soup = BeautifulSoup(html, 'html.parser')
    clientes = []

    # ── Estratégia 1: tabelas HTML com cabeçalhos de cliente ──────────────────
    for table in soup.find_all('table'):
        headers   = []
        col_idx   = {}
        linhas    = table.find_all('tr')

        for row in linhas:
            cells = row.find_all(['th', 'td'])
            texts = [c.get_text(strip=True) for c in cells]

            if not headers:
                # Detecta linha de cabeçalho pelo conteúdo
                joined = ' '.join(texts).lower()
                palavras_chave = ['cliente', 'nome', 'código', 'codigo', 'cod.']
                if any(p in joined for p in palavras_chave):
                    headers = texts
                    for i, h in enumerate(texts):
                        h_l = h.lower()
                        # Código do cliente
                        if ('cód' in h_l or 'cod' in h_l) and ('cli' in h_l or 'for' in h_l or len(h_l) < 8):
                            col_idx.setdefault('codigo', i)
                        # Nome do cliente
                        elif 'nome' in h_l or ('cli' in h_l and 'cód' not in h_l and 'cod' not in h_l):
                            col_idx.setdefault('nome', i)
                        # Valor
                        elif 'valor' in h_l or 'total' in h_l or 'venda' in h_l:
                            col_idx.setdefault('valor', i)
                        # Qtd. Itens
                        elif ('item' in h_l or 'iten' in h_l or 'qtd' in h_l or 'qt.' in h_l) \
                             and 'cli' not in h_l:
                            col_idx.setdefault('qtd_itens', i)
                continue

            # Linha de dados
            if len(texts) < 2:
                continue
            # Pula totais/subtotais
            if texts and any(
                t in texts[0].lower()
                for t in ['total', 'subtotal', 'resumo', 'consolidado']
            ):
                continue

            cli = {}
            if 'codigo' in col_idx and col_idx['codigo'] < len(texts):
                v = texts[col_idx['codigo']].strip()
                if v and v not in ('-', '—', ''):
                    cli['codigo_cliente'] = v
            if 'nome' in col_idx and col_idx['nome'] < len(texts):
                v = texts[col_idx['nome']].strip()
                if v and v not in ('-', '—', ''):
                    cli['nome_cliente'] = v
            if 'valor' in col_idx and col_idx['valor'] < len(texts):
                cli['valor_venda'] = parse_br_number(texts[col_idx['valor']])
            if 'qtd_itens' in col_idx and col_idx['qtd_itens'] < len(texts):
                cli['qtd_itens'] = parse_int(texts[col_idx['qtd_itens']])

            # Só inclui se tiver pelo menos nome ou código
            if cli.get('nome_cliente') or cli.get('codigo_cliente'):
                clientes.append(cli)

        if clientes:
            return clientes          # achou na primeira tabela relevante

    # ── Estratégia 2: divs repetidos com padrão cliente (Movere custom) ───────
    # Alguns relatórios Movere usam classes com padrão de repetição numérica.
    # Ex.: a5119, a5128, a5137... (label) e a5123, a5132, a5141... (valor).
    # No modo detalhado pode haver padrões similares para cada linha de cliente.
    # Tentamos detectar pares onde label parece código/nome de cliente.
    data_resumo = parse_report_html(html)
    if data_resumo:
        # O HTML usa o formato resumo mesmo em modo "detalhado" do formulário —
        # retorna lista vazia para acionar o fallback para salvar_supabase (v4).
        return []

    # ── Estratégia 3: linhas de lista (li, p, div simples) ───────────────────
    # Tenta encontrar padrões como "CÓDIGO - NOME - VALOR" em elementos inline.
    import re
    padrao_linha = re.compile(
        r'(?P<codigo>\d{4,8})\s*[-–]\s*(?P<nome>[A-Z][^R$\n]{3,60})\s*R?\$?\s*(?P<valor>[\d.,]+)',
        re.IGNORECASE
    )
    for elem in soup.find_all(['li', 'p', 'span', 'div']):
        if elem.find(['table', 'ul', 'ol']):
            continue    # ignora containers
        txt = elem.get_text(strip=True)
        m = padrao_linha.match(txt)
        if m:
            clientes.append({
                'codigo_cliente': m.group('codigo'),
                'nome_cliente':   m.group('nome').strip(),
                'valor_venda':    parse_br_number(m.group('valor')),
            })

    return clientes

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
    Retorna dict {(data_ref, operador_codigo): {'valor': float, 'tem_clientes': bool}}
    Agrega múltiplas linhas por (data_ref, operador) quando há dados individuais.
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/vendas_televendas"
        f"?select=data_ref,operador_codigo,valor_venda,codigo_cliente"
        f"&data_ref=gte.{mes_ini}&data_ref=lte.{mes_fim}"
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=_headers_sb())
            if r.status_code == 200:
                result = {}
                for row in r.json():
                    chave = (row['data_ref'], str(row['operador_codigo']))
                    valor = float(row.get('valor_venda') or 0)
                    tem_cli = bool(row.get('codigo_cliente'))
                    if chave not in result:
                        result[chave] = {'valor': 0.0, 'tem_clientes': False}
                    result[chave]['valor'] += valor
                    if tem_cli:
                        result[chave]['tem_clientes'] = True
                return result
            else:
                print(f"  ⚠️  Supabase GET {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  ⚠️  Erro ao consultar Supabase: {e}")
    return {}

async def deletar_dia_operador(operador_codigo: str, data_ref: str) -> bool:
    """Apaga TODAS as linhas de (data_ref, operador) — preparação para INSERT."""
    url = (
        f"{SUPABASE_URL}/rest/v1/vendas_televendas"
        f"?data_ref=eq.{data_ref}&operador_codigo=eq.{operador_codigo}"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.delete(url, headers=_headers_sb())
            return r.status_code in (200, 204)
    except Exception as e:
        print(f"    ⚠️  Erro ao deletar linhas: {e}")
        return False

async def salvar_clientes_supabase(operador: dict, data_ref: str, clientes: list) -> tuple:
    """
    Salva clientes individuais: DELETE linhas antigas → INSERT uma por cliente.
    Retorna (status_code, total_valor, qtd_clientes).
    """
    # 1. Apagar linhas antigas do dia/operador
    ok = await deletar_dia_operador(operador['codigo'], data_ref)
    if not ok:
        print(f"    ⚠️  Falha ao deletar linhas antigas — abortando INSERT")
        return (500, 0.0, 0)

    agora = datetime.now(TZ_SP).isoformat()
    payload = []
    for cli in clientes:
        payload.append({
            'data_ref':        data_ref,
            'operador_codigo': operador['codigo'],
            'operador_nome':   operador['nome'],
            'codigo_cliente':  (cli.get('codigo_cliente') or '').strip(),
            'nome_cliente':    (cli.get('nome_cliente')   or '').strip(),
            'valor_venda':     cli.get('valor_venda', 0.0),
            'qtd_clientes':    1,       # cada linha = 1 cliente
            'qtd_itens':       cli.get('qtd_itens', 0),
            'atualizado_em':   agora,
        })

    total = sum(c.get('valor_venda', 0.0) for c in clientes)

    # 2. INSERT em batch (Supabase aceita array no POST)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{SUPABASE_URL}/rest/v1/vendas_televendas",
                headers=_headers_sb({'Prefer': 'return=minimal'}),
                json=payload,
            )
            return (r.status_code, total, len(clientes))
    except Exception as e:
        print(f"    ⚠️  Erro ao salvar clientes: {e}")
        return (500, total, len(clientes))

async def salvar_supabase(operador: dict, data_ref: str, dados: dict, force_zero: bool = False):
    """
    Salva TOTAL AGREGADO (comportamento v4 — fallback quando não há dados individuais).
    Usa upsert com on_conflict para a constraint existente ou novas colunas.
    """
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
        # Sem codigo_cliente/nome_cliente → linha agregada
        'atualizado_em':   datetime.now(TZ_SP).isoformat(),
    }

    # Tenta upsert padrão; se falhar (constraint mudada), usa DELETE+INSERT simples
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{SUPABASE_URL}/rest/v1/vendas_televendas"
                f"?on_conflict=data_ref,operador_codigo",
                headers=_headers_sb({'Prefer': 'resolution=merge-duplicates,return=minimal'}),
                json=payload,
            )
            if r.status_code not in (200, 201):
                # Constraint pode ter mudado → tenta DELETE+INSERT
                await deletar_dia_operador(operador['codigo'], data_ref)
                r2 = await client.post(
                    f"{SUPABASE_URL}/rest/v1/vendas_televendas",
                    headers=_headers_sb({'Prefer': 'return=minimal'}),
                    json=payload,
                )
                return r2.status_code, valor
            return r.status_code, valor
    except Exception as e:
        print(f"    ⚠️  Erro ao salvar agregado: {e}")
        return 500, valor

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

    # 5. Checkboxes — v5: MODO_DETALHADO desmarca "Listar somente resumo"
    listar_resumo_valor = 'false' if MODO_DETALHADO else 'true'
    await page.evaluate(f"""() => {{
        function check(texto, tipo, valor) {{
            for (const el of document.querySelectorAll('td,label,span,div')) {{
                if (el.childElementCount === 0 && el.innerText &&
                    el.innerText.trim().replace(/[?]/g,'').includes(texto)) {{
                    let inp = el.querySelector('input[type="'+tipo+'"]')
                           || (() => {{ const row = el.closest('tr')||el.parentElement;
                                        return row && row.querySelector('input[type="'+tipo+'"]'); }})()
                           || (() => {{ const n = el.nextElementSibling;
                                        return n && n.querySelector('input[type="'+tipo+'"]'); }})();
                    if (inp) {{ inp.checked = valor;
                                inp.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }}
                }}
            }}
            return false;
        }}
        check('Listar somente resumo',        'checkbox', {listar_resumo_valor});
        check('Filtrar somente base de venda', 'checkbox', true);
    }}""")
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
                    # v4: verificava 'a5119' (classe do resumo)
                    # v5: aceita também HTML de relatório detalhado (tabelas, etc.)
                    tem_resumo   = 'a5119' in body or 'Valor Venda' in body
                    tem_detalhe  = '<table' in body or 'Quantidade' in body
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
    # Mês retroativo ou mês atual
    if MES_RETRO_ANO and MES_RETRO_MES:
        ano, mes = MES_RETRO_ANO, MES_RETRO_MES
        # Para mês retroativo, processa todos os dias úteis do mês (sem limitar a "até hoje")
        data_ref_fim = date(ano, mes, _cal.monthrange(ano, mes)[1])
    else:
        ano, mes = hoje.year, hoje.month
        data_ref_fim = hoje
    data_hoje = hoje.strftime('%Y-%m-%d')
    ultimo_dia = _cal.monthrange(ano, mes)[1]
    mes_ini   = f"{ano}-{mes:02d}-01"
    mes_fim   = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    modo_txt = "DETALHADO (clientes individuais)" if MODO_DETALHADO else "RESUMO (totais)"
    print(f"\n🔄  Sync Televendas v5 — {agora_sp.strftime('%d/%m/%Y %H:%M')} (Brasília)")
    print(f"    Modo: {modo_txt}\n")

    todos_dias = dias_uteis_mes(ano, mes, data_ref_fim)
    if todos_dias:
        print(f"  Dias úteis até hoje : {len(todos_dias)}  ({todos_dias[0]} → {todos_dias[-1]})")
    else:
        print(f"  Dias úteis até hoje : 0  (nenhum dia útil até hoje no mês)")

    existentes = await buscar_existentes(mes_ini, mes_fim)
    print(f"  Registros Supabase  : {len(existentes)} pares (data, operador)")

    # ── Monta fila ────────────────────────────────────────────────────────────
    # Mês retroativo: força todos os dias na fila
    eh_retro = bool(MES_RETRO_ANO and MES_RETRO_MES)
    if eh_retro:
        print(f"  ⚠️  Modo RETROATIVO: re-sincronizando {mes:02d}/{ano} completo\n")
    mes_atual = data_hoje[:7]   # 'YYYY-MM'
    dias_mes_atual = set(d for d in todos_dias if d.startswith(mes_atual))

    fila = []
    for dia in todos_dias:
        for op in OPERADORES:
            chave  = (dia, op['codigo'])
            info   = existentes.get(chave)   # None | {'valor': float, 'tem_clientes': bool}
            eh_hoje = (dia == data_hoje)
            eh_mes_atual = (dia in dias_mes_atual)

            if eh_retro:
                # Modo retroativo: força todos os dias do mês
                fila.append((dia, op, 'retro_mes'))
            elif info is None:
                # Nunca capturado
                fila.append((dia, op, 'novo'))
            elif info['valor'] == 0.0:
                # R$0 = possível falha anterior → retenta
                fila.append((dia, op, 'zero'))
            elif eh_hoje:
                # Hoje → refresh sempre
                fila.append((dia, op, 'hoje'))
            elif REFRESH_MES_TODO and eh_mes_atual:
                # Mês atual → sempre re-sincroniza (vendas retroativas no ERP)
                fila.append((dia, op, 'mes_atual'))
            elif MODO_DETALHADO and RETROATIVO and not info['tem_clientes']:
                # Tem valor mas só dados agregados → reprocessa em modo retroativo
                fila.append((dia, op, 'retroativo'))
            # else: tem valor (>0) e mês anterior → mantém

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
        qtd_cli    = 0
        qtd_skip   = 0

        for i, (dia, op, motivo) in enumerate(fila):
            data_br = datetime.strptime(dia, '%Y-%m-%d').strftime('%d/%m/%Y')
            eh_hoje = (dia == data_hoje)
            chave   = (dia, op['codigo'])
            info_anterior = existentes.get(chave)

            print(f"  [{i+1:>3}/{len(fila)}] {data_br}  {op['nome']}  [{motivo}]…")
            try:
                html = await buscar_relatorio(page, op, dia)

                if html:
                    # ── Salva HTML de debug se solicitado ─────────────────────
                    if DEBUG_HTML:
                        dbg = f"/tmp/movere_debug_{op['codigo']}_{dia}.html"
                        with open(dbg, 'w', encoding='utf-8') as f:
                            f.write(html)
                        print(f"    🔍  HTML salvo: {dbg}")

                    if MODO_DETALHADO:
                        # ── Tenta parser detalhado ────────────────────────────
                        clientes = parse_report_html_detalhado(html)

                        if clientes:
                            st, total, n = await salvar_clientes_supabase(op, dia, clientes)
                            emoji = "✅" if st in (200, 201) else "⚠️"
                            print(f"    {emoji}  R$ {total:>12,.2f}  —  {n} clientes  (Supabase {st})")
                            if eh_hoje:
                                total_hoje += total
                            qtd_ok  += 1
                            qtd_cli += n
                        else:
                            # Fallback: salva total agregado (modo v4)
                            dados = parse_report_html(html)
                            if dados:
                                st, v = await salvar_supabase(op, dia, dados)
                                emoji = "✅" if st in (200, 201) else "⚠️"
                                print(f"    {emoji}  R$ {v:>12,.2f}  (fallback agregado — parser sem clientes)")
                                if eh_hoje:
                                    total_hoje += v
                                qtd_ok += 1
                            else:
                                # HTML sem estrutura reconhecível
                                if eh_hoje:
                                    await salvar_supabase(op, dia, {}, force_zero=True)
                                    print(f"    —   R$ 0,00  (HTML sem estrutura — Supabase R$0)")
                                else:
                                    _v = info_anterior['valor'] if info_anterior else 0
                                    print(f"    🔒  HTML sem estrutura — mantendo R$ {_v:,.2f}")
                                qtd_skip += 1
                    else:
                        # Modo resumo (v4 puro)
                        dados = parse_report_html(html)
                        st, v = await salvar_supabase(op, dia, dados)
                        emoji = "✅" if st in (200, 201) else "⚠️"
                        print(f"    {emoji}  R$ {v:>12,.2f}  (Supabase {st})")
                        if eh_hoje:
                            total_hoje += v
                        qtd_ok += 1

                elif eh_hoje:
                    # Hoje sem HTML → zero (sem vendas ainda)
                    st, _ = await salvar_supabase(op, dia, {}, force_zero=True)
                    print(f"    —   R$ 0,00  (sem vendas hoje — Supabase {st})")

                else:
                    # Dia passado sem HTML → não sobrescreve
                    _v = info_anterior['valor'] if info_anterior else 0
                    if _v > 0:
                        print(f"    🔒  Sem HTML — mantendo R$ {_v:,.2f}")
                    else:
                        print(f"    ⚠️  Sem HTML — pulando (sem dado real)")
                    qtd_skip += 1

            except Exception as e:
                print(f"    ❌  Erro: {e}")
                import traceback; traceback.print_exc()
                qtd_skip += 1

            # Re-login a cada 25 queries
            if (i + 1) % 25 == 0 and (i + 1) < len(fila):
                print("\n  🔁  Re-login para manter sessão…\n")
                try:
                    await login(page)
                except Exception:
                    pass

        await browser.close()

    print(f"\n{'─'*50}")
    print(f"  Capturados       : {qtd_ok}/{len(fila)}")
    if MODO_DETALHADO and qtd_cli > 0:
        print(f"  Clientes salvos  : {qtd_cli}")
    print(f"  Pulados/erro     : {qtd_skip}/{len(fila)}")
    if total_hoje > 0:
        print(f"  Total hoje       : R$ {total_hoje:,.2f}")
    print(f"{'─'*50}\n")


if __name__ == '__main__':
    asyncio.run(main())
