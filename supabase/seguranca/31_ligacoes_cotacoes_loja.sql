-- ═════════════════════════════════════════════════════════════════════════
-- 31) Ligações: as COTAÇÕES DOS VENDEDORES DAS LOJAS também entram (pode rodar duas vezes)
--
-- Decisão do TI (25/11/2026):
--   · Além das cotações do televendas, entram as cotações feitas pelos vendedores nas 8 lojas
--     (coluna "Vendedor" do relatório do Analytics). Quem cotou é quem liga (não entra na divisão).
--   · Cotação do gerente, de vendedor de férias/desativado ou de quem não está cadastrado → divisão automática.
--   · ligacoes.origem: 'televendas' (como sempre) ou 'loja'. Preço garantido: televendas 7 dias, loja 3 dias.
--   · perfis.nome_movere: o nome da pessoa no Movere, quando o robô não reconhece sozinho.
--   · ligacoes_nomes_movere: nomes de vendedores que apareceram nas cotações (o /admin avisa os sem ligação).
-- ═════════════════════════════════════════════════════════════════════════
alter table public.ligacoes add column if not exists origem text not null default 'televendas';
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'ligacoes_origem_check') then
    alter table public.ligacoes add constraint ligacoes_origem_check check (origem in ('televendas', 'loja'));
  end if;
end $$;
create index if not exists ligacoes_origem_idx on public.ligacoes (origem);

alter table public.perfis add column if not exists nome_movere text;

create table if not exists public.ligacoes_nomes_movere (
  loja          text not null,
  nome          text not null,                 -- nome do vendedor como vem do Movere
  cotacoes      integer not null default 0,    -- cotações vistas na última rodada
  ultima        date,                          -- dia da cotação mais recente
  perfil_id     uuid references public.perfis(id) on delete set null,   -- com quem o robô ligou (null = não reconheceu)
  atualizado_em timestamptz not null default now(),
  primary key (loja, nome)
);
alter table public.ligacoes_nomes_movere enable row level security;
drop policy if exists "nomes_movere: admin lê" on public.ligacoes_nomes_movere;
create policy "nomes_movere: admin lê" on public.ligacoes_nomes_movere for select to authenticated using (public.eh_admin());
revoke all on public.ligacoes_nomes_movere from anon;
grant select on public.ligacoes_nomes_movere to authenticated;

notify pgrst, 'reload schema';

-- Conferência: as 3 linhas devem dizer "ok"
select 'coluna ligacoes.origem' as item, case when exists (select 1 from information_schema.columns
       where table_schema = 'public' and table_name = 'ligacoes' and column_name = 'origem') then 'ok' else 'FALTA' end as situacao
union all
select 'coluna perfis.nome_movere', case when exists (select 1 from information_schema.columns
       where table_schema = 'public' and table_name = 'perfis' and column_name = 'nome_movere') then 'ok' else 'FALTA' end
union all
select 'tabela ligacoes_nomes_movere (trancada)', case when (select relrowsecurity from pg_class
       where oid = 'public.ligacoes_nomes_movere'::regclass) then 'ok' else 'FALTA' end;
