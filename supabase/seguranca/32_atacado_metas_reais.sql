-- ═════════════════════════════════════════════════════════════════════════
-- 32 · Metas REAIS do Atacado de novembro/2026 (planilha do TI, 26/11/2026)
-- Meta PRIME de cada vendedora (a página calcula Master = Prime + 10% e Suprema = Master + 10%).
-- Troca as metas de exemplo do SQL 30. Kleber fica SEM META; a Sara sai (não é da equipe do Atacado).
-- Pode rodar duas vezes. Os feriados (chave 'feriado_DD') não são mexidos.
-- ═════════════════════════════════════════════════════════════════════════
delete from public.atacado_metas
 where mes = '2026-11-01' and chave like 'v:%'
   and chave not in ('v:303101', 'v:309110', 'v:322540', 'v:318707', 'v:291608', 'v:324865');

insert into public.atacado_metas (mes, chave, nome, meta, alterado_por, alterado_em) values
  ('2026-11-01', 'v:303101', 'NAYZA',         920000, 'metas reais (SQL 32)', now()),
  ('2026-11-01', 'v:309110', 'CAMILA SILVA',  980000, 'metas reais (SQL 32)', now()),
  ('2026-11-01', 'v:322540', 'ALYSSANDRA',    550000, 'metas reais (SQL 32)', now()),
  ('2026-11-01', 'v:318707', 'CAMILA RAMOS',  900000, 'metas reais (SQL 32)', now()),
  ('2026-11-01', 'v:291608', 'NIORRANA',     1010000, 'metas reais (SQL 32)', now()),
  ('2026-11-01', 'v:324865', 'RAFAELA',       470000, 'metas reais (SQL 32)', now())
on conflict (mes, chave) do update
  set nome = excluded.nome, meta = excluded.meta, alterado_por = excluded.alterado_por, alterado_em = excluded.alterado_em;

-- Conferência: 6 vendedoras · Prime R$ 4.830.000 · Master R$ 5.313.000 · Suprema R$ 5.844.300
select count(*) as vendedoras,
       to_char(sum(meta), 'FM9G999G999')        as prime,
       to_char(sum(meta) * 1.1, 'FM9G999G999')  as master,
       to_char(sum(meta) * 1.21, 'FM9G999G999') as suprema
  from public.atacado_metas where mes = '2026-11-01' and chave like 'v:%';
