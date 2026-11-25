-- ═════════════════════════════════════════════════════════════════════════
-- 27) Resultado Varejo: coluna "Pneus" + metas de novembro/2026 (pode rodar duas vezes)
--
--   · pneus        = quantos pneus a loja (ou o vendedor) vendeu no mês (só as famílias de pneu)
--   · pneus_vendas = em quantas vendas teve pneu
--   · Metas de novembro/2026 por loja, enviadas pelo TI em 24/11/2026 (total R$ 4.500.000,00).
--     Rodar de novo regrava os mesmos valores. As metas também podem ser mudadas na página (✏️ Metas).
-- ═════════════════════════════════════════════════════════════════════════
alter table public.varejo_lojas      add column if not exists pneus        numeric;
alter table public.varejo_lojas      add column if not exists pneus_vendas int;
alter table public.varejo_vendedores add column if not exists pneus        numeric;
alter table public.varejo_vendedores add column if not exists pneus_vendas int;

insert into public.varejo_metas (mes, loja, meta, alterado_por, alterado_em) values
  ('2026-11-01', 'ARIQUEMES',  410000, 'TI (SQL 27)', now()),
  ('2026-11-01', 'C.AUTO PVH', 680000, 'TI (SQL 27)', now()),
  ('2026-11-01', 'C.AUTO VLH', 300000, 'TI (SQL 27)', now()),
  ('2026-11-01', 'CACOAL',     620000, 'TI (SQL 27)', now()),
  ('2026-11-01', 'JI-PARANA',  680000, 'TI (SQL 27)', now()),
  ('2026-11-01', 'MATRIZ',     800000, 'TI (SQL 27)', now()),
  ('2026-11-01', 'PARINTINS',  530000, 'TI (SQL 27)', now()),
  ('2026-11-01', 'XAPURI',     480000, 'TI (SQL 27)', now())
on conflict (mes, loja) do update set meta = excluded.meta, alterado_por = excluded.alterado_por, alterado_em = excluded.alterado_em;

notify pgrst, 'reload schema';

-- Conferência: 8 lojas e o total de R$ 4.500.000
select loja, to_char(meta, 'FM9G999G999') as meta from public.varejo_metas where mes = '2026-11-01'
union all
select 'TOTAL', to_char(sum(meta), 'FM9G999G999') from public.varejo_metas where mes = '2026-11-01';
