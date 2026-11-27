-- 34 · Funil do televendas: cotação que virou O.S. = venda (TI, 27/11/2026)
-- Acrescenta 2 colunas em funil_leads (só o robô lê e grava; nenhuma regra de acesso muda).
--   cotacoes      = números das cotações do Movere ligadas ao cliente (para saber se viraram O.S.)
--   compra_fonte  = de onde veio a compra: 'os' (cotação virou O.S.), 'movere' (nota pelo telefone),
--                   'venda_ganha' (coluna VENDA GANHA do Kommo) ou '1a_venda' (campo 1ª Venda)
-- Pode rodar mais de uma vez.

alter table public.funil_leads add column if not exists cotacoes     text[];
alter table public.funil_leads add column if not exists compra_fonte text;

-- Conferência: as 2 respostas devem ser "sim"
select 'coluna cotacoes' as item,
       case when exists (select 1 from information_schema.columns
                         where table_schema = 'public' and table_name = 'funil_leads' and column_name = 'cotacoes')
            then 'sim' else 'NÃO' end as ok
union all
select 'coluna compra_fonte',
       case when exists (select 1 from information_schema.columns
                         where table_schema = 'public' and table_name = 'funil_leads' and column_name = 'compra_fonte')
            then 'sim' else 'NÃO' end;
