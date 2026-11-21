-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Passo 11: registro das rodadas dos robôs
--
-- Cada vez que o robô "Conferir vendas Movere" roda, ele grava aqui um
-- resumo: quando, se deu certo, quantos descontos conferiu, quantas vendas
-- achou e, se falhou, o motivo. O App mostra a última rodada para o admin.
--
-- Quem grava: só o robô (chave secreta). Quem vê: só o admin.
-- O próprio robô apaga as rodadas com mais de 90 dias.
-- Só cria coisas novas. Pode rodar mais de uma vez.
-- ════════════════════════════════════════════════════════════════════════

create table if not exists public.robo_execucoes (
  id           bigserial primary key,
  robo         text not null,                 -- ex.: 'conferir_vendas_movere'
  inicio       timestamptz not null default now(),
  fim          timestamptz,
  ok           boolean not null,
  teste        boolean not null default false, -- rodada "só mostrar, sem gravar"
  conferidos   integer,                       -- descontos conferidos
  encontrados  integer,                       -- vendas encontradas
  mensagem     text                           -- motivo do erro (sem dados de cliente)
);

create index if not exists robo_execucoes_robo_inicio on public.robo_execucoes (robo, inicio desc);

alter table public.robo_execucoes enable row level security;

drop policy if exists "robo_execucoes: ver (admin)" on public.robo_execucoes;
create policy "robo_execucoes: ver (admin)" on public.robo_execucoes
  for select to authenticated
  using (public.eh_admin());

-- Avisa a API do Supabase da tabela nova
notify pgrst, 'reload schema';

-- Conferência
select count(*) as rodadas_registradas from public.robo_execucoes;
