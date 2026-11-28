-- 35 · Funil do televendas: quadro "Pelo Kommo (Trackeamento)" (TI, 28/11/2026)
-- Acrescenta 3 colunas em funil_leads (só o robô lê e grava; nenhuma regra de acesso muda):
--   campos  = campos do Trackeamento que estão "Sim" no cartão: '1' Contato Inicial, '2' Fez cotação, '3' Cotação IA,
--             '4' Negociação, '5' Recuperação Inicial, '6' Agendamento IA, '7' Agendamento
--   etapa   = etapa do cartão agora: 'aberto', 'ganha' (VENDA GANHA) ou 'perdida' (venda perdida)
--   entrou  = false para o cartão "adicionado" (sem Contato Inicial nem etapa): só conta no quadro "Pelo Kommo"
-- Pode rodar mais de uma vez.

alter table public.funil_leads add column if not exists campos text[];
alter table public.funil_leads add column if not exists etapa  text;
alter table public.funil_leads add column if not exists entrou boolean;

-- Conferência: as 3 respostas devem ser "sim"
select c as coluna,
       case when exists (select 1 from information_schema.columns
                         where table_schema = 'public' and table_name = 'funil_leads' and column_name = c)
            then 'sim' else 'NÃO' end as ok
from unnest(array['campos', 'etapa', 'entrou']) as c;
