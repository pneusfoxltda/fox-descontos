-- 35 · Funil do televendas: quadro "Pelo Kommo (Trackeamento)" (TI, 28/11/2026)
-- Acrescenta 3 colunas em funil_leads (só o robô lê e grava; nenhuma regra de acesso muda):
--   campos  = campos do Trackeamento que estão "Sim" no cartão: '1' Contato Inicial, '2' Fez cotação, '3' Cotação IA,
--             '4' Negociação, '5' Recuperação Inicial, '6' Agendamento IA, '7' Agendamento
--   etapa   = etapa do cartão agora: 'aberto', 'ganha' (VENDA GANHA) ou 'perdida' (venda perdida)
--   entrou  = false para o cartão "adicionado" (sem Contato Inicial nem etapa): só conta no quadro "Pelo Kommo"
--   perda_auto = venda perdida AUTOMÁTICA (motivo só no campo "Motivo de perda"; com motivo na etapa = a equipe marcou)
--   respondeu / disparo = grupo "Disparos" do Kommo: se respondeu ao disparo e o que respondeu (texto da opção)
-- Pode rodar mais de uma vez.

alter table public.funil_leads add column if not exists campos text[];
alter table public.funil_leads add column if not exists etapa  text;
alter table public.funil_leads add column if not exists entrou boolean;
alter table public.funil_leads add column if not exists respondeu text;
alter table public.funil_leads add column if not exists disparo text;
alter table public.funil_leads add column if not exists perda_auto boolean;

-- Conferência: as 6 respostas devem ser "sim"
select c as coluna,
       case when exists (select 1 from information_schema.columns
                         where table_schema = 'public' and table_name = 'funil_leads' and column_name = c)
            then 'sim' else 'NÃO' end as ok
from unnest(array['campos', 'etapa', 'entrou', 'respondeu', 'disparo', 'perda_auto']) as c;
