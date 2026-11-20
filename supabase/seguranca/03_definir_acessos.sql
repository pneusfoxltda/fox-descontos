-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Segurança · Passo 3: definir o nível de acesso de cada pessoa
--
-- Níveis (decididos com o TI):
--   admin      → tudo (somente o TI)
--   comercial  → cadastrar, consultar e liberar descontos
--   gerente    → somente ver relatórios
--   televendas → cadastrar pedidos de desconto e ver os seus
--
-- Rodar DEPOIS do passo 2. Só altera a tabela "perfis" (nova);
-- o sistema atual continua funcionando igual.
-- ════════════════════════════════════════════════════════════════════════

update public.perfis set funcoes = '{admin}'
 where email in ('gilcimar.freitass21@gmail.com', 'ti@redefox.com.br');

update public.perfis set funcoes = '{comercial}'
 where email in ('lorhanny.beatriz@redefox.com.br', 'luigi.ribeiro@redefox.com.br',
                 'safira.brito@redefox.com.br',     'sara.gomes@redefox.com.br');

update public.perfis set funcoes = '{gerente}'
 where email = 'kazan.felipe@redefox.com.br';

update public.perfis set funcoes = '{televendas}'
 where email = 'jonathan.lemes@redefox.com.br';

-- Conferência
select nome, email, array_to_string(funcoes, ', ') as nivel, ativo
from public.perfis
order by array_to_string(funcoes, ','), nome;
