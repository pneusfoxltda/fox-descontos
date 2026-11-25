-- ═════════════════════════════════════════════════════════════════════════
-- 30) Resultados Fox Pneus · ATACADO (pode rodar duas vezes)
--
-- O robô resultados_atacado.py (rotina 553 do Movere, Tabela de Preço 2 ATACADO + 5 ATACADO PREMIUM, todas as
-- lojas, frete compõe os valores) grava aqui, de hora em hora:
--   · atacado_vendedores : venda, clientes, itens (e pneus no mês) por vendedor; periodo 'mes' (mês até hoje)
--                          ou 'dia' (cada um dos últimos dias úteis, para as colunas "Últimos 5 dias úteis")
--   · atacado_lojas      : o mesmo por loja
--   · atacado_metas      : meta do mês por vendedor (chave 'v:COD') e feriados (chave 'feriado_DD')
-- Quem lê: login ATIVO. Metas: admin e gerente de todas as lojas (Jonathan). Nada de cliente.
-- ═════════════════════════════════════════════════════════════════════════
create table if not exists public.atacado_vendedores (
  mes           date    not null,              -- 1º dia do mês
  periodo       text    not null check (periodo in ('mes', 'dia')),
  dia           date    not null,              -- 'mes': até que dia · 'dia': o dia
  cod           text    not null,
  nome          text    not null,
  venda         numeric not null default 0,
  clientes      int     not null default 0,
  itens         numeric not null default 0,
  pneus         numeric,
  pneus_vendas  int,
  atualizado_em timestamptz not null default now(),
  primary key (mes, periodo, dia, cod)
);

create table if not exists public.atacado_lojas (
  mes           date    not null,
  periodo       text    not null check (periodo in ('mes', 'dia')),
  dia           date    not null,
  loja          text    not null,
  cod           int,
  venda         numeric not null default 0,
  clientes      int     not null default 0,
  itens         numeric not null default 0,
  pneus         numeric,
  pneus_vendas  int,
  atualizado_em timestamptz not null default now(),
  primary key (mes, periodo, dia, loja)
);

create table if not exists public.atacado_metas (
  mes          date    not null,
  chave        text    not null,               -- 'v:COD' (meta do vendedor) ou 'feriado_DD'
  nome         text,
  meta         numeric not null default 0 check (meta >= 0),
  alterado_por text,
  alterado_em  timestamptz not null default now(),
  primary key (mes, chave)
);

alter table public.atacado_vendedores enable row level security;
alter table public.atacado_lojas      enable row level security;
alter table public.atacado_metas      enable row level security;

drop policy if exists "atacado_vendedores: login ativo lê" on public.atacado_vendedores;
create policy "atacado_vendedores: login ativo lê" on public.atacado_vendedores for select to authenticated using (public.perfil_ativo());
drop policy if exists "atacado_lojas: login ativo lê" on public.atacado_lojas;
create policy "atacado_lojas: login ativo lê" on public.atacado_lojas for select to authenticated using (public.perfil_ativo());
drop policy if exists "atacado_metas: login ativo lê" on public.atacado_metas;
create policy "atacado_metas: login ativo lê" on public.atacado_metas for select to authenticated using (public.perfil_ativo());

-- Metas: admin ou gerente de todas as lojas (mesma regra de ve_todas_ligacoes)
drop policy if exists "atacado_metas: grava" on public.atacado_metas;
create policy "atacado_metas: grava" on public.atacado_metas for insert to authenticated with check (public.ve_todas_ligacoes());
drop policy if exists "atacado_metas: muda" on public.atacado_metas;
create policy "atacado_metas: muda" on public.atacado_metas for update to authenticated using (public.ve_todas_ligacoes()) with check (public.ve_todas_ligacoes());
drop policy if exists "atacado_metas: apaga" on public.atacado_metas;
create policy "atacado_metas: apaga" on public.atacado_metas for delete to authenticated using (public.ve_todas_ligacoes());

revoke all on public.atacado_vendedores, public.atacado_lojas, public.atacado_metas from anon;
grant select on public.atacado_vendedores, public.atacado_lojas to authenticated;
grant select, insert, update, delete on public.atacado_metas to authenticated;

-- Metas de EXEMPLO de novembro/2026 (para começar; mude pela página em "Editar metas")
insert into public.atacado_metas (mes, chave, nome, meta, alterado_por) values
  ('2026-11-01', 'v:303101', 'NAYZA MINELLI PEREIRA OLIVEIRA',   1100000, 'exemplo (SQL 30)'),
  ('2026-11-01', 'v:309110', 'CAMILA DA SILVA FEITOZA',            850000, 'exemplo (SQL 30)'),
  ('2026-11-01', 'v:318707', 'CAMILA RAMOS BRILHANTE',             850000, 'exemplo (SQL 30)'),
  ('2026-11-01', 'v:291608', 'NIORRANA CARRIÇO GHISLERI',          800000, 'exemplo (SQL 30)'),
  ('2026-11-01', 'v:233260', 'SARA DE ARAUJO GOMES',               600000, 'exemplo (SQL 30)'),
  ('2026-11-01', 'v:322540', 'ALYSSANDRA SALES MARINHO',           500000, 'exemplo (SQL 30)'),
  ('2026-11-01', 'v:324865', 'RAFAELA FERNANDES DA SILVA',         350000, 'exemplo (SQL 30)'),
  ('2026-11-01', 'v:107560', 'KLEBER CAZUZA SILVA',                150000, 'exemplo (SQL 30)')
on conflict (mes, chave) do nothing;   -- não sobrescreve meta que já foi mudada pela página

notify pgrst, 'reload schema';

-- Conferência: 3 tabelas com "sim" e as metas de exemplo (total R$ 5.200.000)
select c.relname as tabela, case when c.relrowsecurity then 'sim' else 'NÃO' end as trancada
  from pg_class c where c.oid in ('public.atacado_vendedores'::regclass, 'public.atacado_lojas'::regclass, 'public.atacado_metas'::regclass)
union all
select 'metas nov/2026: ' || count(*) || ' vendedores', to_char(sum(meta), 'FM9G999G999')
  from public.atacado_metas where mes = '2026-11-01' and chave like 'v:%';
