-- ═════════════════════════════════════════════════════════════════════════
-- 26) Resultados Fox Pneus · Varejo (pode rodar duas vezes)
--
-- O robô resultados_varejo.py (rotina 553 do Movere, filtros do Varejo) grava aqui, de hora em hora:
--   · varejo_lojas       : venda, clientes, itens e ticket de cada loja (no mês e hoje)
--   · varejo_vendedores  : o mesmo por vendedor de cada loja (a soma dos vendedores = a loja)
--   · varejo_conferencia : a 553 comparada com o Analytics ("Jonathan - Faturamento Varejo"), por loja,
--                          com os motivos da diferença (ex.: REVENDA, com o código do cliente). É a setinha
--                          vermelha lá embaixo na página.
--   · varejo_metas       : a meta do mês de cada loja (só o admin muda, pela própria página)
-- Quem lê: qualquer pessoa com login ATIVO (o mesmo login das Ligações e do App).
-- Só o robô (chave de serviço) grava vendas e conferência. Nada de nome de cliente.
-- ═════════════════════════════════════════════════════════════════════════

-- Quem está logado tem perfil ativo?
create or replace function public.perfil_ativo()
returns boolean
language sql stable security definer
set search_path = public
as $$
  select exists (select 1 from public.perfis where id = auth.uid() and ativo);
$$;
revoke execute on function public.perfil_ativo() from public, anon;
grant  execute on function public.perfil_ativo() to authenticated;

create table if not exists public.varejo_lojas (
  mes           date    not null,              -- 1º dia do mês
  periodo       text    not null check (periodo in ('mes', 'hoje')),
  dia           date    not null,              -- até que dia (o "hoje" da rodada)
  loja          text    not null,
  cod           int,
  venda         numeric not null default 0,    -- venda líquida (venda - devolução)
  clientes      int     not null default 0,    -- vendas realizadas (clientes atendidos)
  itens         numeric not null default 0,
  ticket        numeric not null default 0,
  atualizado_em timestamptz not null default now(),
  primary key (mes, periodo, loja)
);

create table if not exists public.varejo_vendedores (
  mes           date    not null,
  periodo       text    not null check (periodo in ('mes', 'hoje')),
  dia           date    not null,
  loja          text    not null,
  cod           text    not null,
  nome          text    not null,
  venda         numeric not null default 0,
  clientes      int     not null default 0,
  itens         numeric not null default 0,
  ticket        numeric not null default 0,
  atualizado_em timestamptz not null default now(),
  primary key (mes, periodo, loja, cod)
);

create table if not exists public.varejo_conferencia (
  mes           date    not null,
  loja          text    not null,
  ate           date    not null,              -- comparado até este dia (o Analytics vai até ontem)
  v553          numeric,
  analytics     numeric,
  diferenca     numeric,
  motivos       jsonb   not null default '[]', -- [{motivo, cod_cliente, vendedor, dia, nota, valor}]
  atualizado_em timestamptz not null default now(),
  primary key (mes, loja)
);

create table if not exists public.varejo_metas (
  mes          date    not null,
  loja         text    not null,
  meta         numeric not null check (meta >= 0),
  alterado_por text,
  alterado_em  timestamptz not null default now(),
  primary key (mes, loja)
);

alter table public.varejo_lojas       enable row level security;
alter table public.varejo_vendedores  enable row level security;
alter table public.varejo_conferencia enable row level security;
alter table public.varejo_metas       enable row level security;

-- Leitura: quem tem login ativo
drop policy if exists "varejo_lojas: login ativo lê" on public.varejo_lojas;
create policy "varejo_lojas: login ativo lê" on public.varejo_lojas
  for select to authenticated using (public.perfil_ativo());
drop policy if exists "varejo_vendedores: login ativo lê" on public.varejo_vendedores;
create policy "varejo_vendedores: login ativo lê" on public.varejo_vendedores
  for select to authenticated using (public.perfil_ativo());
drop policy if exists "varejo_conferencia: login ativo lê" on public.varejo_conferencia;
create policy "varejo_conferencia: login ativo lê" on public.varejo_conferencia
  for select to authenticated using (public.perfil_ativo());
drop policy if exists "varejo_metas: login ativo lê" on public.varejo_metas;
create policy "varejo_metas: login ativo lê" on public.varejo_metas
  for select to authenticated using (public.perfil_ativo());

-- Metas: só o admin grava (pela página)
drop policy if exists "varejo_metas: admin grava" on public.varejo_metas;
create policy "varejo_metas: admin grava" on public.varejo_metas
  for insert to authenticated with check (public.eh_admin());
drop policy if exists "varejo_metas: admin muda" on public.varejo_metas;
create policy "varejo_metas: admin muda" on public.varejo_metas
  for update to authenticated using (public.eh_admin()) with check (public.eh_admin());
drop policy if exists "varejo_metas: admin apaga" on public.varejo_metas;
create policy "varejo_metas: admin apaga" on public.varejo_metas
  for delete to authenticated using (public.eh_admin());

revoke all on public.varejo_lojas, public.varejo_vendedores, public.varejo_conferencia, public.varejo_metas from anon;
grant select on public.varejo_lojas, public.varejo_vendedores, public.varejo_conferencia to authenticated;
grant select, insert, update, delete on public.varejo_metas to authenticated;

notify pgrst, 'reload schema';

-- Conferência: as 4 tabelas devem aparecer com "sim"
select c.relname as tabela, case when c.relrowsecurity then 'sim' else 'NÃO' end as trancada
  from pg_class c
 where c.oid in ('public.varejo_lojas'::regclass, 'public.varejo_vendedores'::regclass,
                 'public.varejo_conferencia'::regclass, 'public.varejo_metas'::regclass)
 order by 1;
