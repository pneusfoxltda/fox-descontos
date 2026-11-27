-- ═════════════════════════════════════════════════════════════════════════
-- 33) Funil do televendas · Kommo → cotação → negociação → agendamento → compra (pode rodar duas vezes)
--
-- Carga desde 01/2025 aos poucos (decisão do TI): a 1ª rodada lê os últimos 4 meses; cada rodada seguinte atualiza o que
-- mudou e volta mais 2 meses no histórico, até janeiro de 2025.
-- O robô funil_televendas.py junta o Kommo (marcações 1 a 7 do cartão do lead, motivos de perda) com o Movere
-- (cotação, O.S. e nota fiscal pelo telefone) e grava:
--   · funil_resumo : as contas prontas do painel (funil, tempos, velocidade, coortes, ranking justo, sobrevivência,
--                    controle semanal, previsão), uma linha por período ('mes', '30d', '90d'), em jsonb
--   · funil_abertos: oportunidades em aberto para o follow-up (aging) e o lead scoring. SEM nome e SEM telefone:
--                    só o nº do lead no Kommo (o link abre o cartão), a operadora, a etapa, os dias parados e a chance.
-- Quem lê: login ATIVO com televendas, gerente ou admin (o mesmo do painel), e o gerente de todas as lojas.
-- Só o robô (chave de serviço) grava.
-- ═════════════════════════════════════════════════════════════════════════
create table if not exists public.funil_resumo (
  periodo       text primary key,                 -- 'mes' (mês atual), '30d', '90d'
  dados         jsonb not null,
  atualizado_em timestamptz not null default now()
);

create table if not exists public.funil_abertos (
  lead_id       bigint primary key,               -- nº do lead no Kommo
  operadora     text,
  etapa         text not null,                    -- entrou | cotou | negociou | agendou
  desde         date,                             -- dia em que entrou na etapa
  dias_parado   integer,
  p75_etapa     numeric,                          -- percentil 75 do tempo daquela etapa (acima = vermelho)
  atrasado      boolean not null default false,
  valor_cotacao numeric,
  chance        numeric,                          -- lead scoring: chance de compra (0 a 1)
  origem        text,
  loja          text,
  atualizado_em timestamptz not null default now()
);
create index if not exists funil_abertos_operadora on public.funil_abertos (operadora);

-- Uma linha por lead (a base das contas). SEM nome e SEM telefone: o telefone vira um código embaralhado (HMAC com
-- a chave do robô), que só serve para cruzar com as vendas do Movere e não dá para voltar ao número.
-- Só o robô lê e grava (sem regra de acesso para quem está logado).
create table if not exists public.funil_leads (
  id            bigint primary key,               -- nº do lead no Kommo
  operadora     text,
  origem        text,
  loja          text,
  perdido       boolean not null default false,
  motivo        text,
  d_entrou      date not null,
  d_cotou       date,
  d_negociou    date,
  d_agendou     date,
  d_visita      date,
  d_comprou     date,
  valor_compra  numeric,
  valor_cotacao numeric,
  tel_hash      text[],
  atualizado_em timestamptz not null default now()
);
create index if not exists funil_leads_entrou on public.funil_leads (d_entrou);
create table if not exists public.funil_estado (
  chave text primary key,                         -- 'carga_desde' (até onde o histórico já foi carregado), 'ultima_rodada'
  valor text,
  atualizado_em timestamptz not null default now()
);
alter table public.funil_leads  enable row level security;
alter table public.funil_estado enable row level security;
revoke all on public.funil_leads, public.funil_estado from anon, authenticated;

alter table public.funil_resumo  enable row level security;
alter table public.funil_abertos enable row level security;

create or replace function public.ve_funil()
returns boolean
language sql stable security definer
set search_path = public
as $$
  select public.tem_funcao('televendas') or public.tem_funcao('gerente') or public.ve_todas_ligacoes();
$$;
revoke execute on function public.ve_funil() from public, anon;
grant  execute on function public.ve_funil() to authenticated;

drop policy if exists "funil_resumo: televendas lê" on public.funil_resumo;
create policy "funil_resumo: televendas lê" on public.funil_resumo for select to authenticated using (public.ve_funil());
drop policy if exists "funil_abertos: televendas lê" on public.funil_abertos;
create policy "funil_abertos: televendas lê" on public.funil_abertos for select to authenticated using (public.ve_funil());

revoke all on public.funil_resumo, public.funil_abertos from anon;
grant select on public.funil_resumo, public.funil_abertos to authenticated;

notify pgrst, 'reload schema';

-- Conferência: as 4 tabelas trancadas ("sim")
select c.relname as tabela, case when c.relrowsecurity then 'sim' else 'NÃO' end as trancada
  from pg_class c where c.oid in ('public.funil_resumo'::regclass, 'public.funil_abertos'::regclass,
                                  'public.funil_leads'::regclass, 'public.funil_estado'::regclass);
