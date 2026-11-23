-- ═════════════════════════════════════════════════════════════════════════
-- 20) Novo status nas Ligações: "Aguardando retorno WhatsApp" (pode rodar duas vezes)
--     Código no banco: 'aguardando_wa'. Conta como cliente EM ABERTO (igual a "Retornar depois"):
--     entra na divisão, nas férias, nos números do vendedor e do Monitor.
-- ═════════════════════════════════════════════════════════════════════════

-- 1) O status passa a ser aceito na tabela
alter table public.ligacoes drop constraint if exists ligacoes_status_valido;
alter table public.ligacoes add constraint ligacoes_status_valido check (status in
  ('pendente', 'nao_atende', 'retornar', 'aguardando_wa', 'sem_interesse', 'agendou',
   'venda_ganha', 'venda_perdida', 'venda_televendas', 'comprou'));

-- 2) As funções que já existem no banco ganham o status novo onde aparece "retornar"
--    (marcar_ligacao, divisão, férias, vendedores da loja e Monitor). Só troca se ainda não tiver.
do $$
declare
  f record;
  def text;
  novo text;
begin
  for f in
    select p.oid from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.proname in ('marcar_ligacao', 'distribuir_ligacoes', 'vendedor_ferias', 'voltar_das_ferias',
                         'vendedores_da_loja', 'monitor_resumo')
  loop
    def := pg_get_functiondef(f.oid);
    if position('aguardando_wa' in def) > 0 then continue; end if;
    novo := replace(def,  '''retornar'', ''agendou''',       '''retornar'', ''aguardando_wa'', ''agendou''');
    novo := replace(novo, '''retornar'',''agendou''',         '''retornar'',''aguardando_wa'',''agendou''');
    novo := replace(novo, '''retornar'', ''sem_interesse''', '''retornar'', ''aguardando_wa'', ''sem_interesse''');
    if novo <> def then
      execute novo;
      raise notice 'atualizada: %', f.oid::regprocedure;
    end if;
  end loop;
end $$;

notify pgrst, 'reload schema';

-- Conferência: todas as funções abaixo devem mostrar "sim"
select p.oid::regprocedure as funcao,
       case when position('aguardando_wa' in pg_get_functiondef(p.oid)) > 0 then 'sim' else 'NÃO' end as tem_o_status_novo
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('marcar_ligacao', 'distribuir_ligacoes', 'vendedor_ferias', 'vendedores_da_loja', 'monitor_resumo')
 order by 1;
