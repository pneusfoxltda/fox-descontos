-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Segurança · Passo 8: tirar a gravação pública das vendas
--
-- Rodar SÓ DEPOIS que:
--   1. o segredo SUPABASE_SERVICE_KEY foi criado no GitHub, e
--   2. o robô "Sync Televendas" rodou com sucesso usando esse segredo.
-- O robô com a chave secreta não depende destas regras (a chave secreta
-- passa por cima da trava). Depois deste passo, ninguém mais consegue
-- gravar vendas pelo site, só o robô.
--
-- Pode rodar mais de uma vez. Para desfazer, é só recriar as duas regras.
-- ════════════════════════════════════════════════════════════════════════

drop policy if exists "insercao_script"   on public.vendas_televendas;
drop policy if exists "atualizacao_script" on public.vendas_televendas;

-- Conferência: só deve sobrar a regra de leitura
select policyname as regra, cmd as acao, array_to_string(roles, ',') as para
from pg_policies
where schemaname = 'public' and tablename in ('vendas_televendas', 'vendas_televendas_clientes')
order by tablename, policyname;
