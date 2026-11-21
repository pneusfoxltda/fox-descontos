-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Passo 13: Ligações — data do agendamento e venda perdida
--
-- · "Agendou" passa a guardar a DATA do agendamento (obrigatória quando o
--   vendedor marca; o "agendou" que vem do Kommo pelo robô fica sem data).
-- · Novo status "venda_perdida", com MOTIVO obrigatório.
--
-- Rodar ANTES de publicar o site novo. Pode rodar mais de uma vez.
-- ════════════════════════════════════════════════════════════════════════

alter table public.ligacoes add column if not exists agendado_para date;
alter table public.ligacoes add column if not exists motivo_perda  text;

alter table public.ligacoes drop constraint if exists ligacoes_status_valido;
alter table public.ligacoes add constraint ligacoes_status_valido check (status in
  ('pendente', 'nao_atende', 'retornar', 'sem_interesse', 'agendou',
   'venda_ganha', 'venda_perdida', 'venda_televendas', 'comprou'));

create index if not exists ligacoes_agendado_para on public.ligacoes (loja, agendado_para);

-- O vendedor marca o status da SUA loja (admin: qualquer loja).
--   agendou       → exige a data do agendamento (p_data)
--   venda_ganha   → exige o nº da O.S. (p_os)
--   venda_perdida → exige o motivo (p_motivo)
drop function if exists public.marcar_ligacao(bigint, text, text, text);
create or replace function public.marcar_ligacao(
  p_id bigint, p_status text, p_obs text default null, p_os text default null,
  p_data date default null, p_motivo text default null)
returns void
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja text;
  v_nome text;
begin
  if p_status not in ('pendente', 'nao_atende', 'retornar', 'sem_interesse', 'agendou', 'venda_ganha', 'venda_perdida') then
    raise exception 'Status inválido: %', p_status;
  end if;
  if p_status = 'venda_ganha' and coalesce(trim(p_os), '') = '' then
    raise exception 'Informe o nº da O.S. da venda';
  end if;
  if p_status = 'agendou' and p_data is null then
    raise exception 'Informe a data do agendamento';
  end if;
  if p_status = 'venda_perdida' and coalesce(trim(p_motivo), '') = '' then
    raise exception 'Informe o motivo da venda perdida';
  end if;

  select loja into v_loja from public.ligacoes where id = p_id;
  if v_loja is null then
    raise exception 'Ligação não encontrada';
  end if;
  if not (public.eh_admin() or coalesce(v_loja = public.minha_loja(), false)) then
    raise exception 'Sem permissão para esta loja';
  end if;

  select coalesce(nullif(trim(nome), ''), email) into v_nome
    from public.perfis where id = auth.uid() and ativo;
  if v_nome is null then
    raise exception 'Usuário sem perfil ativo';
  end if;

  update public.ligacoes
     set status = p_status,
         status_em = now(),
         status_por = v_nome,
         obs = coalesce(nullif(trim(p_obs), ''), obs),
         os_venda = case when p_status = 'venda_ganha' then trim(p_os) else os_venda end,
         agendado_para = case when p_status = 'agendou' then p_data else agendado_para end,
         motivo_perda = case when p_status = 'venda_perdida' then trim(p_motivo) else motivo_perda end
   where id = p_id;

  insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
  values (p_id, v_nome, p_status,
          nullif(trim(concat_ws(' · ',
            case when p_status = 'agendou' then 'Agendado para ' || to_char(p_data, 'DD/MM/YYYY') end,
            case when p_status = 'venda_ganha' then 'O.S. ' || trim(p_os) end,
            case when p_status = 'venda_perdida' then 'Motivo: ' || trim(p_motivo) end,
            nullif(trim(p_obs), ''))), ''));
end;
$$;
revoke execute on function public.marcar_ligacao(bigint, text, text, text, date, text) from public, anon;
grant  execute on function public.marcar_ligacao(bigint, text, text, text, date, text) to authenticated;

notify pgrst, 'reload schema';

-- Conferência
select count(*) filter (where status = 'agendou') as agendados,
       count(*) filter (where status = 'venda_perdida') as vendas_perdidas
from public.ligacoes;
