-- ═════════════════════════════════════════════════════════════════════════
-- 23) Mensagens da Fernanda na página das Ligações (pode rodar duas vezes)
--     O robô dos avisos (avisos_ligacoes.py) guarda aqui a mensagem de cada pessoa em cada turno
--     (manhã, meio da manhã, tarde, fim do dia). A raposa da página mostra a mais nova do dia.
--     Cada pessoa só lê as DELA. Só o robô (chave de serviço) grava. Ficam 15 dias.
-- ═════════════════════════════════════════════════════════════════════════
create table if not exists public.avisos_fernanda (
  id        bigserial primary key,
  perfil_id uuid not null references public.perfis(id) on delete cascade,
  dia       date not null,
  turno     text not null,
  titulo    text,
  texto     text not null,
  criado_em timestamptz not null default now(),
  unique (perfil_id, dia, turno)
);
alter table public.avisos_fernanda enable row level security;

drop policy if exists "avisos_fernanda: cada um lê as suas" on public.avisos_fernanda;
create policy "avisos_fernanda: cada um lê as suas" on public.avisos_fernanda
  for select to authenticated using (perfil_id = auth.uid());

revoke all on public.avisos_fernanda from anon;
grant select on public.avisos_fernanda to authenticated;

notify pgrst, 'reload schema';

-- Conferência: deve mostrar "sim"
select case when relrowsecurity then 'sim' else 'NÃO' end as tabela_trancada
  from pg_class where oid = 'public.avisos_fernanda'::regclass;
