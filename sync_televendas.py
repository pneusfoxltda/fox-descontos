"""
sync_televendas.py - v12
========================
BUGS CRÍTICOS CORRIGIDOS via análise do HTML real do relatório (203KB):

Bug #1 — Grupo Empresarial não setado (causa do relatório em branco)
  - preencher_formulario não setava f0362idgrupoempresarial=4 (TODAS FILIAIS)
  - Campo obrigatório; sem ele o Movere devolve o formulário sem dados
  - Fix v12: step 1b seta o campo logo após Visão Empresarial

Bug #2 — Parser com classes CSS erradas (nenhum item extraído)
  - parse_report_html_detalhado usava _TblParser (TR/TD) mas o HTML real do
    SSRS usa <DIV class="aXXXX"> para todos os valores do relatório
  - Classes corretas descobertas via análise do HTML real:
      .a1152=cod_cliente, .a1156=nome_cliente
      .a1180=cod_item,    .a1184=desc_item
      .a1200=quantidade,  .a1212=vlr_venda
      .a1245='Total Cliente:', .a1267=vlr_venda_total
  - Nota: parse_report_html (resumo) já estava correto — .a5119/.a5123 OK
  - Fix v12: parse_report_html_detalhado completamente reescrita

Herdado da v11 (captura HTML — 0/36 queries capturavam antes):
  1. Filtro html no content-type → remove JS/CSS/.axd
  2. Sem early exit no on_resp → coleta todos os HTMLs
  3. Wait loop sai cedo apenas para URL diferente de rotina553.aspx
  4. Prioridade: URL com relatório > não-formulário > maior HTML
  5. Frame fallback sempre roda
  6. Log de todos os HTMLs capturados com URL + tamanho
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
try:
    import holidays as _holidays_lib
    _FERIADOS_BR = _holidays_lib.Brazil()
except ImportError:
    _FERIADOS_BR = set()  # fallback: sem verificação de feriados

TZ_SP = timezone(timedelta(hours=-3))

MOVERE_USER = os.environ.get("MOVERE_USER", "")
MOVERE_PASS = os.environ.get("MOVERE_PASS", "")

SUPABASE_URL = "https://dxwkiaxpygibzmwzvcuz.supabase.co"
# Chave secreta do robô (GitHub → Settings → Secrets → SUPABASE_SERVICE_KEY).
# Sem ela, usa a chave pública (só funciona enquanto o passo 7 do banco não rodou).
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip() or (
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
DEBUG_HTML        = True   # True = salva HTML/screenshots em /tmp para diagnóstico

# Janela de sincronização:
#   Mês ATUAL    → todos os dias úteis até hoje (dados em tempo real)
#   Mês ANTERIOR → apenas os últimos N dias úteis (ajustes tardios)
DIAS_MES_ANT_JANELA = 5  # últimos N dias úteis do mês anterior

# ── Mês retroativo (uso pontual) ──────────────────────────────────────────────
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

def _e_dia_util(dt: date) -> bool:
    """Retorna True se o dia é útil (Seg–Sáb) e não é feriado nacional brasileiro."""
    if dt.weekday() == 6:  # domingo
        return False
    if _FERIADOS_BR and dt in _FERIADOS_BR:
        return False
    return True

def dias_uteis_mes(ano: int, mes: int, ate_hoje: date) -> list:
    total = monthrange(ano, mes)[1]
    dias = []
    for d in range(1, total + 1):
        dt = date(ano, mes, d)
        if dt > ate_hoje:
            break
        if _e_dia_util(dt):
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

# ─── Parser modo detalhado (v12 — SSRS DIV classes reais) ────────────────────

def parse_report_html_detalhado(html: str) -> tuple:
    """
    Extrai itens individuais por cliente do HTML SSRS da rotina 553
    (Agrupamento=Cliente, sem "Listar somente resumo").

    Estrutura HTML SSRS — cada campo é um <DIV class="aXXXX"> com valor fixo:
      .a1152 = cod_cliente       .a1156 = nome_cliente
      .a1180 = cod_item          .a1184 = descricao_item
      .a1200 = quantidade        .a1212 = vlr_venda  ← chave
      .a1245 = 'Total Cliente:'  .a1267 = vlr_venda total do cliente

    Algoritmo: coleta sequência plana das classes-chave em ordem de documento,
    depois percorre essa sequência agrupando por cliente e item.

    Retorna (records, client_totals):
      records       = lista de dicts com itens por cliente
      client_totals = {codigo_cliente: total_venda} das linhas "Total Cliente:"
    """
    soup = BeautifulSoup(html, 'html.parser')

    KEY_CLASSES = {'a1152', 'a1156', 'a1180', 'a1184', 'a1200', 'a1212', 'a1245', 'a1267'}

    # Sequência plana (classe, texto) apenas das classes que nos interessam
    seq = []
    for div in soup.find_all('div'):
        cls = (div.get('class') or [''])[0]
        if cls in KEY_CLASSES:
            text = div.get_text(strip=True)
            seq.append((cls, text))

    # Diagnóstico rápido
    counts = {}
    for c, _ in seq: counts[c] = counts.get(c, 0) + 1
    print(f"        📊 Chaves SSRS: {counts}")

    records       = []
    client_totals = {}
    cod_cli       = None
    nome_cli      = ''

    i = 0
    while i < len(seq):
        cls, text = seq[i]

        # ── Cabeçalho de cliente (.a1152 = cod, .a1156 = nome) ───────────────
        if cls == 'a1152':
            cod_cli  = text
            nome_cli = ''
            i += 1
            if i < len(seq) and seq[i][0] == 'a1156':
                nome_cli = seq[i][1]
                i += 1
            continue

        # ── Linha de item (.a1180 = cod_item) ────────────────────────────────
        if cls == 'a1180' and cod_cli:
            cod_item  = text
            desc_item = ''
            qtd       = 0.0
            vlr       = 0.0

            j = i + 1
            while j < len(seq):
                c2, v2 = seq[j]
                # Para se bater em novo item, novo cliente ou total
                if c2 in ('a1180', 'a1152', 'a1245'):
                    break
                if c2 == 'a1184':
                    desc_item = v2
                elif c2 == 'a1200':
                    qtd = parse_br_number(v2)
                elif c2 == 'a1212':
                    vlr = parse_br_number(v2)
                    j += 1
                    break
                j += 1

            if vlr > 0:
                records.append({
                    'codigo_cliente': cod_cli,
                    'nome_cliente':   nome_cli,
                    'codigo_item':    cod_item,
                    'descricao_item': desc_item,
                    'quantidade':     qtd,
                    'vlr_venda':      vlr,
                })
            i = j
            continue

        # ── Total por cliente (.a1245 + .a1267) ──────────────────────────────
        if cls == 'a1245' and 'Total Cliente' in text:
            j = i + 1
            while j < len(seq) and j < i + 25:
                c2, v2 = seq[j]
                if c2 == 'a1267':
                    total = parse_br_number(v2)
                    if total > 0 and cod_cli:
                        client_totals[cod_cli] = total
                    break
                if c2 in ('a1152', 'a1180'):
                    break
                j += 1
            # Após Total Cliente vem próximo cliente (ou Total Geral)
            cod_cli  = None
            nome_cli = ''
            i += 1
            continue

        i += 1

    return records, client_totals


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
    """
    url_principal = (
        f"{SUPABASE_URL}/rest/v1/vendas_televendas"
        f"?select=data_ref,operador_codigo,valor_venda"
        f"&data_ref=gte.{mes_ini}&data_ref=lte.{mes_fim}"
        f"&nome_cliente=is.null"
    )
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

# ─── Correção de vlr_venda inflado ───────────────────────────────────────────

def _normalizar_desc_lado(desc: str) -> str:
    return desc.upper().rstrip().removesuffix(' LD').removesuffix(' LE')


def _corrigir_vlr_inflado(items: list, client_totals: dict) -> list:
    if not client_totals:
        return items

    from collections import defaultdict

    por_cliente: dict[str, list[int]] = defaultdict(list)
    for i, it in enumerate(items):
        por_cliente[it['codigo_cliente']].append(i)

    corrected: dict[int, float] = {}

    for cod_cli, indices in por_cliente.items():
        total_correto = client_totals.get(cod_cli, 0.0)
        if not total_correto:
            continue

        soma = sum(items[i]['vlr_venda'] for i in indices)

        if soma <= total_correto * 1.005:
            continue

        for idx_i in indices:
            it_i  = items[idx_i]
            base_i = _normalizar_desc_lado(it_i['descricao_item'])
            v_i    = it_i['vlr_venda']

            for idx_j in indices:
                if idx_i == idx_j:
                    continue
                it_j   = items[idx_j]
                base_j = _normalizar_desc_lado(it_j['descricao_item'])
                v_j    = it_j['vlr_venda']

                if base_i != base_j or v_j <= 0:
                    continue

                ratio = v_i / v_j
                if ratio >= 1.9 and abs(ratio - round(ratio)) < 0.03:
                    corrected[idx_i] = v_j
                    print(
                        f"    ⚠️  VLR INFLADO CORRIGIDO [{cod_cli}] "
                        f"'{it_i['descricao_item']}': "
                        f"R${v_i:.2f} → R${v_j:.2f} "
                        f"(era {round(ratio):.0f}× '{it_j['descricao_item']}')"
                    )
                    break

    if not corrected:
        return items

    result = []
    for i, it in enumerate(items):
        if i in corrected:
            result.append({**it, 'vlr_venda': corrected[i]})
        else:
            result.append(it)
    return result

# ─────────────────────────────────────────────────────────────────────────────

async def salvar_clientes_supabase(operador: dict, data_ref: str, items: list,
                                   override_total: float = 0.0,
                                   client_totals: dict = None) -> tuple:
    """
    Salva itens por cliente em vendas_televendas_clientes (upsert por item).
    Também salva o total agregado em vendas_televendas (para o dashboard).
    """
    items = [it for it in items if (it.get('vlr_venda') or 0) > 0]
    items = _corrigir_vlr_inflado(items, client_totals)
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

    dedup: dict = {}
    for row in payload:
        key = (row['codigo_cliente'], row['codigo_item'])
        if key in dedup:
            dedup[key]['vlr_venda']  += row['vlr_venda']
            dedup[key]['quantidade'] += row['quantidade']
        else:
            dedup[key] = dict(row)
    payload = list(dedup.values())

    if override_total and override_total > 0:
        total_valor = override_total
    else:
        total_valor = sum(r['vlr_venda'] for r in payload)

    clientes_uniq = len({r['codigo_cliente'] for r in payload if r['codigo_cliente']})

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

        payload_total = {
            'data_ref':        data_ref,
            'operador_codigo': operador['codigo'],
            'operador_nome':   operador['nome'],
            'valor_venda':     total_valor,
            'qtd_clientes':    clientes_uniq,
            'qtd_itens':       len(payload),
            'atualizado_em':   agora,
        }
        r_total = await client.post(
            f"{SUPABASE_URL}/rest/v1/vendas_televendas"
            f"?on_conflict=data_ref,operador_codigo",
            headers=_headers_sb({'Prefer': 'resolution=merge-duplicates,return=minimal'}),
            json=payload_total,
        )
        if r_total.status_code not in (200, 201):
            print(f"    ⚠️  Supabase resumo {r_total.status_code}: {r_total.text[:200]}")
            err += 1

    return (200 if err == 0 else 207), total_valor, len(payload)

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
    await page.wait_for_timeout(800)

    # 1. Visão Empresarial = 1
    await page.evaluate("""() => {
        const inp = document.querySelector('[id*="idvisaoempresarial"]');
        if (inp && (!inp.value || inp.value.trim() === '')) {
            inp.value = '1';
            ['input','change','blur'].forEach(e =>
                inp.dispatchEvent(new Event(e, {bubbles:true})));
        }
    }""")
    await page.wait_for_timeout(300)

    # 1b. Grupo Empresarial = 4 (TODAS FILIAIS) — campo obrigatório no formulário
    #     Sem isso o Movere devolve o formulário em branco sem executar o relatório
    await page.evaluate("""() => {
        const inp = document.querySelector(
            '[id*="idgrupoempresarial"],[id*="f0362"],[name*="idgrupoempresarial"]'
        );
        if (inp) {
            inp.value = '4';
            ['input','change','blur'].forEach(e =>
                inp.dispatchEvent(new Event(e, {bubbles:true})));
        }
    }""")
    await page.wait_for_timeout(300)

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
    await page.wait_for_timeout(200)

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
    await page.wait_for_timeout(200)

    # 4. Operador — digita código e clica na lupa de busca (Movere exige confirmação)
    for sel in ['[id*="idcliforoperador"]','input[id*="operador"]',
                'input[id*="Operador"]','input[name*="operador"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.clear()
                await el.type(operador['codigo'], delay=80)
                await page.wait_for_timeout(600)

                # Tenta clicar no botão lupa (🔍) ao lado do campo de operador
                lupa_clicada = False
                for lupa_sel in [
                    'input[id*="operador"] ~ input[type="button"]',
                    'input[id*="operador"] ~ button',
                    'input[id*="Operador"] + input[type="button"]',
                    'input[id*="Operador"] + button',
                ]:
                    try:
                        lupa = page.locator(lupa_sel).first
                        if await lupa.count() > 0:
                            await lupa.click()
                            lupa_clicada = True
                            break
                    except Exception:
                        pass

                # Fallback JS: busca no container/row do campo operador
                if not lupa_clicada:
                    try:
                        lupa_clicada = await page.evaluate("""() => {
                            const inp = document.querySelector(
                                '[id*="idcliforoperador"],[id*="operador"],[id*="Operador"]'
                            );
                            if (!inp) return false;
                            // Busca no mesmo <tr> ou container pai
                            const container = inp.closest('tr') || inp.closest('td') || inp.parentElement;
                            if (container) {
                                // Tenta botão irmão seguinte
                                let el = inp.nextElementSibling;
                                while (el) {
                                    if (el.tagName === 'INPUT' && (el.type === 'button' || el.type === 'submit')) {
                                        el.click(); return true;
                                    }
                                    if (el.tagName === 'BUTTON') { el.click(); return true; }
                                    el = el.nextElementSibling;
                                }
                                // Tenta qualquer botão no container
                                const btn = container.querySelector(
                                    'input[type="button"],button,input[type="submit"]'
                                );
                                if (btn) { btn.click(); return true; }
                                // Tenta container pai (pode estar em td adjacente)
                                const tr = inp.closest('tr');
                                if (tr) {
                                    const tdbtn = tr.querySelector(
                                        'input[type="button"],button,input[type="submit"]'
                                    );
                                    if (tdbtn) { tdbtn.click(); return true; }
                                }
                            }
                            return false;
                        }""")
                    except Exception:
                        pass

                # Aguarda lookup AJAX validar o operador
                await page.wait_for_timeout(1200)

                # Fallback: Tab para disparar evento blur/change
                await el.press('Tab')
                await page.wait_for_timeout(400)
                break
        except Exception:
            pass

    # 5. Checkboxes e Agrupamento
    if MODO_DETALHADO:
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

            findAndSet('Listar somente resumo', 'checkbox', false);
            findAndSet('Filtrar somente base de venda', 'checkbox', true);

            let clienteRadioMarcado = false;
            for (const row of document.querySelectorAll('tr')) {
                const txt = row.innerText || '';
                if (txt.includes('Vendedor') && txt.includes('Fornecedor') && txt.includes('Cliente')) {
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
    await page.wait_for_timeout(200)

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
    await page.wait_for_timeout(150)

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
    await page.wait_for_timeout(150)

# ─── Capturar relatório ───────────────────────────────────────────────────────

_URL_EXCLUIR = ('default.aspx', '/login', '/Login', 'LoginPage')

def _frame_e_relatorio(url: str, body: str) -> bool:
    """Verifica se um frame parece ser o relatório (não o login)."""
    for excl in _URL_EXCLUIR:
        if excl in url:
            return False
    return len(body) > 2000

async def buscar_relatorio(page, operador: dict, data_iso: str,
                           debug_ss: bool = False) -> str | None:
    # v11: armazena tuplas (url, body) para identificar a melhor resposta
    html_cap_items = []   # list of (url, body)
    popup_pgs      = []
    data_fmt       = datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')
    context        = page.context

    # ── Listener de resposta ──────────────────────────────────────────────────
    # v11 FIX:
    #   - Recoloca filtro 'html' no content-type (remove JS/CSS/.axd)
    #   - Remove 'if html_cap: return' — coleta TODOS os HTMLs do Movere
    #   - Armazena (url, body) para escolher o melhor depois
    async def on_resp(response):
        url = response.url
        if MOVERE_BASE not in url:
            return
        url_path = url.split('?')[0].lower()
        for ext in ('.css', '.js', '.png', '.jpg', '.gif', '.ico',
                    '.woff', '.woff2', '.svg', '.map'):
            if url_path.endswith(ext):
                return

        ct = response.headers.get('content-type', '')
        # v11: só captura respostas HTML — filtra application/x-javascript,
        # application/octet-stream, etc. (incluindo WebResource.axd que era o bug)
        if 'html' not in ct.lower():
            return

        st   = response.status
        clen = response.headers.get('content-length', '?')
        print(f"        🌐 [{st}] ...{url[-80:]} | {ct[:40]} | {clen}b")

        if st != 200:
            return
        for excl in _URL_EXCLUIR:
            if excl in url:
                print(f"        ↳ ignorado (excluído: {excl})")
                return

        try:
            body = await response.text()
            if len(body) > 2000:
                html_cap_items.append((url, body))
                print(f"        ✅ HTML capturado: {len(body)} bytes de ...{url[-60:]}")
        except Exception as e:
            print(f"        ⚠️ Erro ao ler resposta: {e}")

    def on_new_page(popup):
        popup_pgs.append(popup)

    await preencher_formulario(page, operador, data_fmt)
    print(f"        (URL após form-fill: ...{page.url[-60:]})")

    # Screenshot 1: formulário preenchido (primeiros 4 pares para diagnóstico)
    if debug_ss and DEBUG_HTML:
        try:
            ss1 = f"/tmp/movere_ss_{operador['codigo']}_{data_iso}_1form.png"
            await page.screenshot(path=ss1)
            print(f"        📸 Screenshot form: {ss1}")
        except Exception as e:
            print(f"        ⚠️ Screenshot form falhou: {e}")

    try:
        await page.wait_for_load_state('networkidle', timeout=8000)
    except Exception:
        pass

    page.on('response', on_resp)
    context.on('page', on_new_page)

    executar_clicado = False
    for sel in ['input[value="Executar"]', '#btnExecutar',
                'button:has-text("Executar")', 'input[type="submit"]',
                'button[type="submit"]', '#cmdExecutar',
                'input[id*="Executar"]', 'button[id*="Executar"]']:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click()
                executar_clicado = True
                break
        except Exception:
            pass

    if not executar_clicado:
        try:
            clicou = await page.evaluate("""() => {
                const btn = document.querySelector(
                    'input[value="Executar"],#btnExecutar,#cmdExecutar,' +
                    'input[id*="Executar"],button[id*="Executar"],' +
                    'input[type="submit"],button[type="submit"]'
                );
                if (btn) { btn.click(); return true; }
                return false;
            }""")
            if clicou:
                executar_clicado = True
        except Exception:
            pass

    if not executar_clicado:
        try:
            clicou = await page.evaluate("""() => {
                const candidatos = [
                    ...document.querySelectorAll('input[type="submit"],input[type="button"],button')
                ];
                for (const el of candidatos) {
                    const txt = (el.value || el.innerText || el.id || '').toLowerCase();
                    if (txt.includes('execut') || txt.includes('gerar') || txt.includes('pesquis')) {
                        const id = el.id || el.name;
                        if (id && typeof __doPostBack === 'function') {
                            __doPostBack(id, '');
                            return true;
                        }
                        el.click();
                        return true;
                    }
                }
                if (typeof __doPostBack === 'function') {
                    __doPostBack('btnExecutar', '');
                    return true;
                }
                return false;
            }""")
            if clicou:
                executar_clicado = True
        except Exception:
            pass

    print(f"        (URL após Executar: ...{page.url[-60:]} | clicado={executar_clicado})")

    # ── v11: espera inteligente ───────────────────────────────────────────────
    # Sai cedo APENAS se temos um HTML de URL diferente de rotina553.aspx
    # (o relatório real vem de outra URL — ImpressaoRelatorio, etc.)
    # Aguarda até 15 segundos para o relatório carregar (iframe/nova resposta)
    for tick in range(37):  # 37 × 400ms ≈ 15 segundos
        await page.wait_for_timeout(400)
        bons = [b for u, b in html_cap_items if 'rotina553' not in u.lower()]
        if bons or popup_pgs:
            print(f"        ⚡ Relatório detectado no tick {tick+1} ({(tick+1)*400}ms)")
            break

    # Screenshot 2: estado após espera
    if debug_ss and DEBUG_HTML:
        try:
            ss2 = f"/tmp/movere_ss_{operador['codigo']}_{data_iso}_2result.png"
            await page.screenshot(path=ss2)
            print(f"        📸 Screenshot resultado: {ss2}")
        except Exception as e:
            print(f"        ⚠️ Screenshot resultado falhou: {e}")

    # Log de diagnóstico: todos os HTMLs capturados
    if html_cap_items:
        print(f"        HTMLs capturados: {[(u.split('/')[-1][:40], len(b)) for u, b in html_cap_items]}")
    else:
        print(f"        HTMLs capturados: nenhum")

    # Log de frames para diagnóstico
    all_frames = page.frames
    frame_urls = [f.url for f in all_frames if f.url and f.url != 'about:blank']
    if len(frame_urls) > 1:
        print(f"        Frames ({len(all_frames)}): {[u[-50:] for u in frame_urls]}")

    # ── Popups ────────────────────────────────────────────────────────────────
    if popup_pgs:
        for popup in popup_pgs:
            try:
                await popup.wait_for_load_state('domcontentloaded', timeout=12000)
                await popup.wait_for_timeout(2000)
                content = await popup.content()
                if len(content) > 2000:
                    html_cap_items.append((popup.url or 'popup://', content))
                    print(f"        📋 Popup capturado: {len(content)} bytes")
                else:
                    await popup.wait_for_timeout(2000)
                    content = await popup.content()
                    if len(content) > 2000:
                        html_cap_items.append((popup.url or 'popup://', content))
                        print(f"        📋 Popup (2a espera) capturado: {len(content)} bytes")
            except Exception:
                pass
            finally:
                try:
                    await popup.close()
                except Exception:
                    pass

    # ── Frame fallback: sempre executa (v11) ─────────────────────────────────
    # Captura conteúdo de iframes que podem ter carregado o relatório
    for frame in [page, *page.frames]:
        try:
            furl = frame.url or ''
            # Prioriza frames com URL de relatório (ImpressaoRelatorio, etc.)
            is_relatorio_url = any(
                kw in furl.lower()
                for kw in ['impressao', 'relatorio', 'report', 'visualiza']
            )
            content = await frame.content()
            if is_relatorio_url and len(content) > 2000:
                html_cap_items.append((furl, content))
                print(f"        📋 Frame relatorio: {furl[-60:]} ({len(content)}b)")
            elif len(content) > 2000 and 'rotina553' not in furl.lower():
                # Frame sem URL de relatório mas com conteúdo substancial
                # (pode ser iframe anônimo ou about:blank com conteúdo injetado)
                already = any(b == content for _, b in html_cap_items)
                if not already:
                    html_cap_items.append((furl or 'frame://', content))
                    print(f"        📋 Frame extra: {furl[-40:] or 'anônimo'} ({len(content)}b)")
        except Exception:
            pass

    # ── Escolhe o melhor HTML ─────────────────────────────────────────────────
    best_html = None
    if html_cap_items:
        # Prioridade 1: URL contém palavras-chave de relatório
        for u, b in html_cap_items:
            if any(kw in u.lower() for kw in ['impressao', 'relatorio', 'report', 'visualiza', 'popup']):
                best_html = b
                print(f"        🎯 P1 — URL relatório: ...{u[-60:]} ({len(b)}b)")
                break

        # Prioridade 2: Qualquer URL que não seja o formulário principal
        if not best_html:
            outros = [(u, b) for u, b in html_cap_items if 'rotina553' not in u.lower()]
            if outros:
                u, b = max(outros, key=lambda x: len(x[1]))
                best_html = b
                print(f"        🎯 P2 — não-formulário: ...{u[-60:]} ({len(b)}b)")

        # Prioridade 3: Maior HTML (pode ser o formulário com dados embutidos)
        if not best_html:
            u, b = max(html_cap_items, key=lambda x: len(x[1]))
            best_html = b
            print(f"        🔄 P3 — fallback maior HTML: ...{u[-60:]} ({len(b)}b)")

    # ── Debug: salva melhor HTML ───────────────────────────────────────────────
    if best_html and DEBUG_HTML:
        dbg = f"/tmp/movere_debug_{operador['codigo']}_{data_iso}.html"
        try:
            with open(dbg, 'w', encoding='utf-8') as f:
                f.write(best_html)
        except Exception:
            pass

    if best_html:
        try:
            await page.wait_for_load_state('networkidle', timeout=6000)
        except Exception:
            pass
        await page.wait_for_timeout(500)

    page.remove_listener('response', on_resp)
    context.remove_listener('page', on_new_page)
    return best_html

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
    print(f"\n🔄  Sync Televendas v12 — {agora_sp.strftime('%d/%m/%Y %H:%M')} (Brasília)")
    print(f"    Modo: {modo_txt}\n")

    fila = []

    if bool(MES_RETRO_ANO and MES_RETRO_MES):
        todos_dias_retro = dias_uteis_mes(ano, mes, data_ref_fim)
        existentes_fila  = await buscar_existentes(mes_ini, mes_fim)
        print(f"  ⚠️  Modo RETROATIVO: re-sincronizando {mes:02d}/{ano} completo\n")
        for dia in todos_dias_retro:
            for op in OPERADORES:
                fila.append((dia, op, 'retro_mes'))
    else:
        # ── Mês atual: todos os dias úteis até hoje (excl. feriados) ─────────
        dias_mes_atual = []
        for d in range(1, hoje.day + 1):
            dt = date(hoje.year, hoje.month, d)
            if _e_dia_util(dt):
                dias_mes_atual.append(dt.strftime('%Y-%m-%d'))

        # ── Mês anterior: últimos DIAS_MES_ANT_JANELA dias úteis ─────────────
        mes_ant = hoje.month - 1 if hoje.month > 1 else 12
        ano_ant = hoje.year if hoje.month > 1 else hoje.year - 1
        ultimo_dia_ant = _cal.monthrange(ano_ant, mes_ant)[1]
        dias_mes_ant_todos = []
        for d in range(1, ultimo_dia_ant + 1):
            dt = date(ano_ant, mes_ant, d)
            if _e_dia_util(dt):
                dias_mes_ant_todos.append(dt.strftime('%Y-%m-%d'))
        dias_mes_ant = dias_mes_ant_todos[-DIAS_MES_ANT_JANELA:]

        dias_janela = dias_mes_ant + dias_mes_atual

        janela_ini_str = dias_janela[0] if dias_janela else data_hoje
        janela_fim_str = data_hoje

        mes_ant_ini = f"{ano_ant}-{mes_ant:02d}-01"
        existentes_fila = await buscar_existentes(mes_ant_ini, janela_fim_str)

        print(f"  Mês anterior ({mes_ant:02d}/{ano_ant}): últimos {DIAS_MES_ANT_JANELA} dias úteis → {', '.join(d[5:] for d in dias_mes_ant) or '—'}")
        print(f"  Mês atual    ({hoje.month:02d}/{hoje.year}): todos os dias úteis → {', '.join(d[5:] for d in dias_mes_atual) or '—'}")
        print(f"  Total dias   : {len(dias_janela)}  ×  {len(OPERADORES)} operadores = {len(dias_janela)*len(OPERADORES)} queries")
        print(f"  Registros Supabase : {len(existentes_fila)} pares (data, operador)")

        for dia in dias_janela:
            for op in OPERADORES:
                motivo = 'hoje' if dia == data_hoje else 'atualizar'
                fila.append((dia, op, motivo))

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
            info_anterior = existentes_fila.get((dia, op['codigo']))

            print(f"  [{i+1:>3}/{len(fila)}] {data_br}  {op['nome']}  [{motivo}]…")
            try:
                # debug_ss para os primeiros 4 pares (2 operadores × 2 dias)
                html = await buscar_relatorio(page, op, dia, debug_ss=(i < 4))

                if html:
                    if MODO_DETALHADO:
                        items, client_totals = parse_report_html_detalhado(html)

                        if items:
                            dados_resumo  = parse_report_html(html)
                            VALOR_KEY     = 'Valor Total das Notas Emitidas'
                            valor_resumo  = parse_br_number(dados_resumo.get(VALOR_KEY, '0')) if dados_resumo else 0.0

                            valor_totais  = sum(client_totals.values()) if client_totals else 0.0

                            override_total = valor_resumo or valor_totais or 0.0
                            fonte = ("resumo CSS"   if valor_resumo > 0
                                     else "Total Cliente" if valor_totais > 0
                                     else "soma itens")

                            st, total, n = await salvar_clientes_supabase(op, dia, items, override_total, client_totals=client_totals)
                            emoji = "✅" if st in (200, 201) else "⚠️"
                            cli_uniq = len({it['codigo_cliente'] for it in items if it.get('codigo_cliente')})
                            print(f"    {emoji}  R$ {total:>12,.2f}  —  {cli_uniq} clientes, {n} itens  [{fonte}]  (Supabase {st})")
                            if eh_hoje: total_hoje += total
                            qtd_ok      += 1
                            qtd_itens_t += n
                        else:
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
    if DEBUG_HTML:
        import glob as _glob
        ss_files = _glob.glob('/tmp/movere_ss_*.png')
        if ss_files:
            print(f"  Screenshots     : {len(ss_files)} arquivo(s) em /tmp/movere_ss_*.png")
    print(f"{'─'*50}\n")


if __name__ == '__main__':
    asyncio.run(main())
