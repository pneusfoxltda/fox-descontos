-- ═════════════════════════════════════════════════════════════════════════
-- 29) Metas do Resultado Varejo: o GERENTE DE TODAS AS LOJAS (Jonathan) também edita (pode rodar duas vezes)
--
--   Antes: só o admin gravava em varejo_metas (meta em R$, metas de pneus Meta/Super/Mega e feriados).
--   Agora: admin OU "Gerente de todas as lojas" (papel das Ligações sem loja: o mesmo de ve_todas_ligacoes()).
--   Decisão do TI, 25/11/2026. Vendedor e gerente de uma loja continuam só vendo.
-- ═════════════════════════════════════════════════════════════════════════
create or replace function public.edita_metas_varejo()
returns boolean
language sql stable security definer
set search_path = public
as $$
  select public.ve_todas_ligacoes();   -- admin, ou gerente sem loja (gerente de todas as lojas)
$$;
revoke execute on function public.edita_metas_varejo() from public, anon;
grant  execute on function public.edita_metas_varejo() to authenticated;

drop policy if exists "varejo_metas: admin grava" on public.varejo_metas;
drop policy if exists "varejo_metas: admin muda" on public.varejo_metas;
drop policy if exists "varejo_metas: admin apaga" on public.varejo_metas;
drop policy if exists "varejo_metas: admin ou gerente de todas grava" on public.varejo_metas;
drop policy if exists "varejo_metas: admin ou gerente de todas muda" on public.varejo_metas;
drop policy if exists "varejo_metas: admin ou gerente de todas apaga" on public.varejo_metas;
create policy "varejo_metas: admin ou gerente de todas grava" on public.varejo_metas
  for insert to authenticated with check (public.edita_metas_varejo());
create policy "varejo_metas: admin ou gerente de todas muda" on public.varejo_metas
  for update to authenticated using (public.edita_metas_varejo()) with check (public.edita_metas_varejo());
create policy "varejo_metas: admin ou gerente de todas apaga" on public.varejo_metas
  for delete to authenticated using (public.edita_metas_varejo());

notify pgrst, 'reload schema';

-- Conferência: quem pode editar as metas do Varejo (deve aparecer você e o Jonathan)
select nome, case when 'admin' = any(funcoes) then 'admin' else 'gerente de todas as lojas' end as como
  from public.perfis
 where ativo and ('admin' = any(funcoes) or ((papel_ligacoes = 'gerente' or dash_ligacoes) and loja is null))
 order by 2, 1;
