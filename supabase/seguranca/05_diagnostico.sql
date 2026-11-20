-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Segurança · Passo 5: DIAGNÓSTICO (só lê, não muda nada)
--
-- Mostra, numa tabela só:
--   TABELA   → cada tabela, se a trava (RLS) está ligada e quantas linhas tem
--   REGRA    → cada regra de acesso que existe hoje
--   FUNCAO   → as funções do banco que o site chama (e se furam a trava)
--
-- Como rodar: Supabase → SQL Editor → New query → colar tudo → Run.
-- Depois: mande print do resultado (pode precisar de 2 ou 3 prints rolando).
-- ════════════════════════════════════════════════════════════════════════

select tipo, nome, detalhe
from (
  -- 1) Tabelas e situação da trava
  select 1 as ordem, 'TABELA' as tipo, c.relname::text as nome,
         'RLS ' || case when c.relrowsecurity then 'LIGADO' else 'DESLIGADO' end
         || ' · ~' || greatest(c.reltuples, 0)::bigint || ' linhas' as detalhe
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind in ('r', 'p', 'v')

  union all

  -- 2) Regras de acesso atuais
  select 2, 'REGRA', p.tablename || ' · ' || p.policyname,
         p.cmd || ' para ' || array_to_string(p.roles, ',')
         || ' · usa: ' || coalesce(p.qual, '-')
         || ' · grava: ' || coalesce(p.with_check, '-')
  from pg_policies p
  where p.schemaname = 'public'

  union all

  -- 3) Funções do banco (as do site e as de segurança)
  select 3, 'FUNCAO', p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')',
         case when p.prosecdef then 'FURA A TRAVA (security definer)' else 'respeita a trava' end
         || ' · anon pode chamar: '
         || case when has_function_privilege('anon', p.oid, 'execute') then 'SIM' else 'nao' end
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
) x
order by ordem, nome;
