"""
sync_televendas.py - v10
========================
DIAGNÓSTICO: screenshots + log de todas as respostas Movere
para identificar por que o HTML não é capturado.

Mudanças vs v9 (v10):
  - buscar_relatorio: on_resp loga TODAS as respostas do domínio
    Movere (URL, content-type, tamanho) para diagnóstico no Actions.
  - buscar_relatorio: remove filtro 'html' no content-type —
    aceita qualquer resposta do Movere com conteúdo > 2000 bytes.
  - buscar_relatorio: adiciona screenshots após form-fill e após
    Executar (para os 2 primeiros pares) → /tmp/movere_ss_*.png.
  - buscar_relatorio: imprime page.url antes e depois de Executar.
  - preencher_formulario: após digitar o código do operador, tenta
    clicar no botão de busca (🔍) além do Tab — o Movere pode exigir
    o clique na lupa para validar o operador antes de Executar.
  - Janela de verificação: mudada de 20 dias corridos para os
    últimos DIAS_JANELA_MES=5 dias úteis do mês + hoje sempre incluso.

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

Mudanças vs v8 (v9):
  - buscar_relatorio: removidos filtros de string do relatório
    ('a5119', 'Valor Venda', 'Total Cliente') — Movere pode ter mudado
    o HTML do relatório. Agora aceita qualquer HTML grande do domínio.
  - Adicionado handler de popup (context.on 'page') para capturar
    relatórios que abram em nova janela/aba.
  - Frame fallback: também sem filtro de string — aceita qualquer
    frame com conteúdo grande que não seja a página de login/formulário.
  - DEBUG_HTML=True por padrão para diagnóstico (salva HTML em /tmp).

Mudanças vs v7 (v8):
  - Janela retroativa simplificada: últimos JANELA_RETRO_DIAS=20 dias corridos
    (elimina lógica de mês atual/mês anterior; hoje sempre re-sincroniza,
    dias passados só re-sincronizam se faltando ou zerados)
  - Waits reduzidos em preencher_formulario (~2,5 s menos por query)
  - Loop de espera reduzido (30×400 ms = 12 s máx em vez de 40×500 ms = 20 s)

Mudanças vs v6 (v7):
  - buscar_relatorio: removido filtro de URL 'ImpressaoRelatorio' do listener
    de resposta (Movere mudou o padrão de URL → todas as queries retornavam
    "Sem HTML — pulando"). Agora confia apenas na verificação de conteúdo
    (a5119 / Valor Venda / Total Cliente) para identificar o relatório.
  - Executar: seletores ampliados (8 opções) + fallback JS (btn.click /
    form.submit) caso nenhum seletor Playwright encontre o botão.
  - Fallback de frames: se o listener não capturou nada, lê o conteúdo de
    todos os frames da página procurando o HTML do relatório.

Mudanças vs v5 (v6):
  - MODO_DETALHADO=True agora seta Agrupamento=Cliente no formulário
  - parse_report_html_detalhado() reescrito para estrutura real do Movere
  - salvar_clientes_supabase() salva em vendas_televendas_clientes (por item)
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
try:
    import holidays as _holidays_lib
    _FERIADOS_BR = _holidays_lib.Brazil()
except ImportError:
    _FERIADOS_BR = set()  # fallback: sem verificação de feriados

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
DEBUG_HTML        = True   # True = salva HTML/screenshots em /tmp para diagnóstico

# Janela de sincronização:
#   Mês ATUAL    → todos os dias úteis até hoje (dados em tempo real)
#   Mês ANTERIOR → apenas os últimos N dias úteis (ajustes tardios)
# Ex.: hoje=05/11 → Nov: [03,04,05] + Out: [27,28,29,30,31] = ~8 dias × 4 ops
DIAS_MES_ANT_JANELA = 5  # últimos N dias úteis do mês anterior

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


def parse_report_html_detalhado(html: str) -> tuple:
    """
    Extrai itens individuais por cliente do HTML da rotina 553
    com Agrupamento=Cliente (sem "Listar somente resumo").

    Estrutura real do Movere:
      Linha cliente : 4 células — [cod_cli, nome_cli, '', '']
                      (primeiro campo é dígitos, últimas 2 vazias)
      Linha item    : 13 células — [cod_item, descrição, cód_fab, fornec,
                                    peso, qtd, preço_tab, vlr_venda, ...]
      Linha total   : começa com 'Total Cliente:'

    Retorna (records, client_totals):
      records       = lista de dicts com itens por cliente
      client_totals = dict {codigo_cliente: total_valor} lido das linhas
                      "Total Cliente:" — valor correto para o dashboard
    """
    p = _TblParser()
    p.feed(html)

    records      = []
    client_totals = {}   # {cod_cli: total_venda_correto}
    cod_cli  = None
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

        # ── Total por cliente → captura o valor correto ────────────────────
        # CRÍTICO: no Movere, cells[0] costuma ser VAZIO na linha "Total
        # Cliente:" — o texto fica em outra célula.  Por isso verificamos
        # TODAS as células, não só cells[0].
        is_total_cli = any('Total Cliente' in c for c in cells)
        if is_total_cli:
            if cod_cli:
                for cell in reversed(cells):
                    v = parse_br_number(cell)
                    if v > 0:
                        client_totals[cod_cli] = v
                        break
            cod_cli = None; nome_cli = None
            continue

        # Pula outras linhas de "Total" (total geral, etc.) para não
        # confundi-las com linhas de item.
        if any(c.strip().lower().startswith('total') for c in cells):
            continue

        # ── Linha de item (≥ 12 células, cliente já definido) ──────────────
        # Colunas: [0]=cod_item [1]=desc [2]=cod_fab [3]=fornec
        #          [4]=peso [5]=qtd [6]=preco_tab [7]=vlr_venda ...
        # IMPORTANTE: cells[0] deve ser NÃO-VAZIO (código do item).
        # Linhas "Descrição" têm cells[0]='' e 12+ células → devem ser puladas.
        # Linhas com vlr_venda=0 (cabeçalhos/resumos do Movere) também são puladas.
        if cod_cli and len(cells) >= 12 and first:
            try:
                vlr = parse_br_number(cells[7])
                if vlr <= 0:
                    continue  # Pula itens sem valor de venda (cabeçalhos/resumos)
                records.append({
                    'codigo_cliente': cod_cli,
                    'nome_cliente':   nome_cli or '',
                    'codigo_item':    cells[0],
                    'descricao_item': cells[1],
                    'quantidade':     parse_br_number(cells[5]),
                    'vlr_venda':      vlr,
                })
            except Exception:
                pass

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

# ─── Correção de vlr_venda inflado ───────────────────────────────────────────

def _normalizar_desc_lado(desc: str) -> str:
    """Remove sufixos de lado (LD / LE) para comparar itens 'irmãos'."""
    return desc.upper().rstrip().removesuffix(' LD').removesuffix(' LE')


def _corrigir_vlr_inflado(items: list, client_totals: dict) -> list:
    """
    Detecta e corrige itens onde vlr_venda é múltiplo inteiro (≥ 2×) do valor
    de um item 'irmão' (mesma descrição, apenas LD↔LE diferente no final).

    Isso ocorre quando o Movere insere o total da nota fiscal em cells[7]
    em vez do valor individual do item — ex.: COXIM DT LD = 332,31 = 3× 110,77.

    A correção só é aplicada quando a soma dos itens do cliente REALMENTE supera
    o 'Total Cliente:' extraído do HTML (client_totals), evitando falsos positivos.
    """
    if not client_totals:
        return items

    from collections import defaultdict

    # Mapeia índice global → codigo_cliente
    por_cliente: dict[str, list[int]] = defaultdict(list)
    for i, it in enumerate(items):
        por_cliente[it['codigo_cliente']].append(i)

    corrected: dict[int, float] = {}  # índice → novo vlr_venda correto

    for cod_cli, indices in por_cliente.items():
        total_correto = client_totals.get(cod_cli, 0.0)
        if not total_correto:
            continue

        soma = sum(items[i]['vlr_venda'] for i in indices)

        # Só corrige se houver inflação real (tolerância de 0,5 %)
        if soma <= total_correto * 1.005:
            continue

        # Detectar pares LD/LE onde um valor é múltiplo inteiro do outro
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
                # ratio ≥ 2 e próximo de inteiro → v_i é o total da nota
                if ratio >= 1.9 and abs(ratio - round(ratio)) < 0.03:
                    corrected[idx_i] = v_j
                    print(
                        f"    ⚠️  VLR INFLADO CORRIGIDO [{cod_cli}] "
                        f"'{it_i['descricao_item']}': "
                        f"R${v_i:.2f} → R${v_j:.2f} "
                        f"(era {round(ratio):.0f}× '{it_j['descricao_item']}')"
                    )
                    break  # um par encontrado por item é suficiente

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

    override_total:  se > 0, usa esse valor no dashboard em vez de somar
                     vlr_venda dos itens (que pode estar inflado).
    client_totals:   dict {codigo_cliente: total_correto} extraído das linhas
                     'Total Cliente:' do HTML — usado para detectar e corrigir
                     itens com vlr_venda inflado (total da nota em vez do item).

    Retorna (status_code, total_valor, qtd_itens).
    """
    # Filtro de segurança: descarta itens com vlr_venda = 0 antes de salvar
    items = [it for it in items if (it.get('vlr_venda') or 0) > 0]

    # Corrige itens inflados (cells[7] = total da nota) usando pares LD/LE
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

    # ── Valor correto para o dashboard ───────────────────────────────────────────
    # Prioridade: override_total (vindo de "Total Cliente:" ou parser resumo CSS)
    # Fallback:   soma de vlr_venda dos itens (pode estar inflado se cells[7]
    #             contiver o valor total da nota em vez do valor do item)
    if override_total and override_total > 0:
        total_valor = override_total
    else:
        total_valor = sum(r['vlr_venda'] for r in payload)

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
            'qtd_itens':       len(payload),   # após dedup
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
                # O Movere exige esse clique para validar o código antes de Executar
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

                # Fallback JS: clica no primeiro botão após o campo operador
                if not lupa_clicada:
                    try:
                        lupa_clicada = await page.evaluate("""() => {
                            const inp = document.querySelector(
                                '[id*="idcliforoperador"],[id*="operador"],[id*="Operador"]'
                            );
                            if (!inp) return false;
                            // Busca botão irmão ou próximo input[type=button]
                            let el = inp.nextElementSibling;
                            while (el) {
                                if (el.tagName === 'INPUT' && (el.type === 'button' || el.type === 'submit')) {
                                    el.click(); return true;
                                }
                                if (el.tagName === 'BUTTON') { el.click(); return true; }
                                el = el.nextElementSibling;
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

# URLs de login/portal — não queremos capturar essas páginas como relatório
# NOTA: rotina553.aspx NÃO está aqui — o relatório pode ser uma POST-response
# da mesma URL depois de clicar Executar.
_URL_EXCLUIR = ('default.aspx', '/login', '/Login', 'LoginPage')

def _e_html_relatorio(url: str, body: str) -> bool:
    """Verifica se um HTML grande do Movere é o relatório (não o login)."""
    if MOVERE_BASE not in url:
        return False
    for excl in _URL_EXCLUIR:
        if excl in url:
            return False
    # Aceita qualquer HTML do domínio Movere com conteúdo substancial
    return len(body) > 2000

def _frame_e_relatorio(url: str, body: str) -> bool:
    """Verifica se um frame é o relatório (não o login)."""
    for excl in _URL_EXCLUIR:
        if excl in url:
            return False
    return len(body) > 2000

async def buscar_relatorio(page, operador: dict, data_iso: str,
                           debug_ss: bool = False) -> str | None:
    html_cap  = []
    popup_pgs = []
    data_fmt  = datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')
    context   = page.context

    # ── Listener de resposta na página principal ──────────────────────────────
    async def on_resp(response):
        url = response.url
        # Ignora recursos de outros domínios (CDN, analytics, etc.)
        if MOVERE_BASE not in url:
            return
        # Ignora recursos estáticos
        url_path = url.split('?')[0].lower()
        for ext in ('.css', '.js', '.png', '.jpg', '.gif', '.ico', '.woff', '.woff2', '.svg', '.map'):
            if url_path.endswith(ext):
                return

        ct   = response.headers.get('content-type', '')
        clen = response.headers.get('content-length', '?')
        st   = response.status
        # v10: loga TODAS as respostas dinâmicas do Movere para diagnóstico
        print(f"        🌐 [{st}] ...{url[-60:]} | {ct[:30]} | {clen}b")

        if html_cap:
            return  # já capturou

        if st != 200:
            return

        # Verifica se não é página de login/portal
        for excl in _URL_EXCLUIR:
            if excl in url:
                print(f"        ↳ ignorado (excluído: {excl})")
                return

        # v10: aceita qualquer tipo de conteúdo (não filtra por 'html')
        # Movere pode retornar text/html, text/plain, application/xhtml+xml, etc.
        try:
            body = await response.text()
            if len(body) > 2000:
                html_cap.append(body)
                print(f"        ✅ Capturado: {len(body)} bytes")
        except Exception as e:
            print(f"        ⚠️ Erro ao ler resposta: {e}")

    # ── Handler de popup/nova janela ──────────────────────────────────────────
    def on_new_page(popup):
        popup_pgs.append(popup)

    await preencher_formulario(page, operador, data_fmt)

    print(f"        (URL após form-fill: ...{page.url[-60:]})")

    # Screenshot 1: formulário preenchido (apenas para os 2 primeiros pares)
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

    # Fallback JS 1: clica qualquer botão submit visível na página
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

    # Fallback JS 2: __doPostBack para ASP.NET WebForms
    # (form.submit() genérico não envia o __EVENTTARGET correto)
    if not executar_clicado:
        try:
            clicou = await page.evaluate("""() => {
                // Tenta encontrar o ID do botão Executar no DOM
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
                // Último recurso: __doPostBack com IDs comuns do Movere
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

    # Aguarda resposta na página principal ou abertura de popup
    for _ in range(30):
        if html_cap or popup_pgs:
            break
        await page.wait_for_timeout(400)

    # Screenshot 2: resultado após espera (apenas para os 2 primeiros pares)
    if debug_ss and DEBUG_HTML:
        try:
            ss2 = f"/tmp/movere_ss_{operador['codigo']}_{data_iso}_2result.png"
            await page.screenshot(path=ss2)
            print(f"        📸 Screenshot resultado: {ss2}")
        except Exception as e:
            print(f"        ⚠️ Screenshot resultado falhou: {e}")

    # ── Tenta capturar HTML de popup, se abriu ────────────────────────────────
    if not html_cap and popup_pgs:
        for popup in popup_pgs:
            try:
                await popup.wait_for_load_state('domcontentloaded', timeout=12000)
                await popup.wait_for_timeout(1500)
                content = await popup.content()
                if len(content) > 2000:
                    html_cap.append(content)
                    break
                # Se ainda pequeno, aguarda mais um pouco
                await popup.wait_for_timeout(2000)
                content = await popup.content()
                if len(content) > 2000:
                    html_cap.append(content)
                    break
            except Exception:
                pass
            finally:
                try:
                    await popup.close()
                except Exception:
                    pass

    # ── Fallback de frames: lê todos os frames sem filtro de string ───────────
    if not html_cap:
        for frame in [page, *page.frames]:
            try:
                content = await frame.content()
                if _frame_e_relatorio(frame.url, content):
                    html_cap.append(content)
                    break
            except Exception:
                pass

    # ── Debug: salva HTML capturado ───────────────────────────────────────────
    if html_cap and DEBUG_HTML:
        dbg = f"/tmp/movere_debug_{operador['codigo']}_{data_iso}.html"
        try:
            with open(dbg, 'w', encoding='utf-8') as f:
                f.write(html_cap[-1])
        except Exception:
            pass

    if html_cap:
        try:
            await page.wait_for_load_state('networkidle', timeout=6000)
        except Exception:
            pass
        await page.wait_for_timeout(500)

    page.remove_listener('response', on_resp)
    context.remove_listener('page', on_new_page)
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
    print(f"\n🔄  Sync Televendas v10 — {agora_sp.strftime('%d/%m/%Y %H:%M')} (Brasília)")
    print(f"    Modo: {modo_txt}\n")

    fila = []

    if bool(MES_RETRO_ANO and MES_RETRO_MES):
        # Modo retroativo manual: processa mês inteiro indicado
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

        # Junta: mês anterior (últimos 5) + mês atual (todos)
        dias_janela = dias_mes_ant + dias_mes_atual

        # Range para buscar_existentes abrange os dois meses
        janela_ini_str = dias_janela[0] if dias_janela else data_hoje
        janela_fim_str = data_hoje

        # Para o buscar_existentes precisamos cobrir os dois meses
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
                html = await buscar_relatorio(page, op, dia, debug_ss=(i < 2))

                if html:
                    if MODO_DETALHADO:
                        items, client_totals = parse_report_html_detalhado(html)

                        if items:
                            # ── Determina o melhor total para o dashboard ──────
                            # Método A: parser de resumo CSS (divs a5119/a5123)
                            dados_resumo  = parse_report_html(html)
                            VALOR_KEY     = 'Valor Total das Notas Emitidas'
                            valor_resumo  = parse_br_number(dados_resumo.get(VALOR_KEY, '0')) if dados_resumo else 0.0

                            # Método B: linhas "Total Cliente:" do HTML detalhado
                            valor_totais  = sum(client_totals.values()) if client_totals else 0.0

                            # Prioridade: resumo CSS > Total Cliente: > soma itens
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
    if DEBUG_HTML:
        import glob as _glob
        ss_files = _glob.glob('/tmp/movere_ss_*.png')
        if ss_files:
            print(f"  Screenshots     : {len(ss_files)} arquivo(s) em /tmp/movere_ss_*.png")
    print(f"{'─'*50}\n")


if __name__ == '__main__':
    asyncio.run(main())
