-- ═════════════════════════════════════════════════════════════════════════
-- 28) Resultado Varejo: metas de PNEUS por loja (Meta · Super · Mega) (pode rodar duas vezes)
--
--   Na página /resultados a coluna "Pneus" mostra vendidos / Meta, o % (verde no ritmo do dia, vermelho abaixo),
--   a barrinha com as 3 marcas e a faixa alcançada (✅ Meta · ⭐ Super · 🏆 Mega).
--   Valores de novembro/2026 enviados pelo TI em 25/11/2026 (total: Meta 7.840 · Super 8.970 · Mega 9.720).
--   A meta em R$ de cada loja NÃO muda. Também dá para mudar pela página (✏️ Metas).
-- ═════════════════════════════════════════════════════════════════════════
alter table public.varejo_metas add column if not exists meta_pneus  int;
alter table public.varejo_metas add column if not exists super_pneus int;
alter table public.varejo_metas add column if not exists mega_pneus  int;

insert into public.varejo_metas (mes, loja, meta, meta_pneus, super_pneus, mega_pneus, alterado_por, alterado_em) values
  ('2026-11-01', 'ARIQUEMES',   0,  930, 1080, 1180, 'TI (SQL 28)', now()),
  ('2026-11-01', 'C.AUTO PVH',  0,  920, 1070, 1170, 'TI (SQL 28)', now()),
  ('2026-11-01', 'C.AUTO VLH',  0,  520,  600,  650, 'TI (SQL 28)', now()),
  ('2026-11-01', 'CACOAL',      0,  980, 1130, 1230, 'TI (SQL 28)', now()),
  ('2026-11-01', 'JI-PARANA',   0, 1080, 1230, 1330, 'TI (SQL 28)', now()),
  ('2026-11-01', 'MATRIZ',      0, 1180, 1330, 1430, 'TI (SQL 28)', now()),
  ('2026-11-01', 'PARINTINS',   0, 1180, 1330, 1430, 'TI (SQL 28)', now()),
  ('2026-11-01', 'XAPURI',      0, 1050, 1200, 1300, 'TI (SQL 28)', now())
on conflict (mes, loja) do update set   -- a meta em R$ que já existe fica como está
  meta_pneus = excluded.meta_pneus, super_pneus = excluded.super_pneus, mega_pneus = excluded.mega_pneus,
  alterado_por = excluded.alterado_por, alterado_em = excluded.alterado_em;

notify pgrst, 'reload schema';

-- Conferência: 8 lojas + TOTAL (Meta 7840 · Super 8970 · Mega 9720) e a meta em R$ de antes
select loja, meta_pneus as meta, super_pneus as super, mega_pneus as mega, to_char(meta, 'FM9G999G999') as meta_reais
  from public.varejo_metas where mes = '2026-11-01' and loja not like 'feriado_%'
union all
select 'TOTAL', sum(meta_pneus)::int, sum(super_pneus)::int, sum(mega_pneus)::int, to_char(sum(meta), 'FM9G999G999')
  from public.varejo_metas where mes = '2026-11-01' and loja not like 'feriado_%';
