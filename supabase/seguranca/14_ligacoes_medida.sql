-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Passo 14: Ligações — medida do pneu da cotação
--
-- O robô passa a guardar a medida do pneu (ex.: 255/50R20), tirada da
-- descrição do item no relatório de cotações. Ela aparece na lista e entra
-- na mensagem pronta do WhatsApp. Na próxima rodada o robô completa a medida
-- das cotações que já estão na lista.
--
-- Só cria a coluna. Pode rodar mais de uma vez.
-- ════════════════════════════════════════════════════════════════════════

alter table public.ligacoes add column if not exists medida text;

notify pgrst, 'reload schema';

-- Conferência
select count(*) as ligacoes, count(medida) as com_medida from public.ligacoes;
