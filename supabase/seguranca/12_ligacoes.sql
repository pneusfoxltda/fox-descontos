-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Passo 12: Ligações das lojas
--
-- Lista de clientes que fizeram cotação e ainda não compraram nem agendaram,
-- para cada loja ligar. Quem preenche é o robô "Ligações das lojas" (GitHub),
-- toda manhã. As planilhas do Google continuam funcionando como hoje.
--
-- Quem vê:   cada pessoa só a lista da SUA loja (campo "loja" do perfil);
--            o admin vê todas.
-- Quem muda: a loja só muda o status/observação, pela função marcar_ligacao
--            (fica registrado quem e quando). O robô grava o resto.
--
-- Só cria coisas novas. Pode rodar mais de uma vez.
-- ════════════════════════════════════════════════════════════════════════

-- 1) A lista
create table if not exists public.ligacoes (
  id            bigserial primary key,
  cotacao       text not null unique,          -- nº da cotação no Movere
  cliente       text,
  telefone      text,
  tel_chave     text,                          -- últimos 8 dígitos (para comparar)
  loja          text not null,                 -- estabelecimento do Movere (ex.: CACOAL)
  operador      text,
  valor         numeric,
  data_cotacao  date not null,
  status        text not null default 'pendente',
  status_em     timestamptz,
  status_por    text,
  obs           text,
  comprou_em    date,
  criado_em     timestamptz not null default now(),
  constraint ligacoes_status_valido check (status in
    ('pendente', 'nao_atende', 'retornar', 'sem_interesse', 'agendou', 'comprou'))
);
create index if not exists ligacoes_loja_data on public.ligacoes (loja, data_cotacao desc);
create index if not exists ligacoes_tel_chave on public.ligacoes (tel_chave);

-- 2) O histórico de cada cliente (quem marcou o quê e quando)
create table if not exists public.ligacoes_historico (
  id          bigserial primary key,
  ligacao_id  bigint not null references public.ligacoes(id) on delete cascade,
  quando      timestamptz not null default now(),
  quem        text not null,
  status      text not null,
  obs         text
);
create index if not exists ligacoes_historico_ligacao on public.ligacoes_historico (ligacao_id, quando);

-- 3) A loja de quem está logado
create or replace function public.minha_loja()
returns text
language sql stable security definer
set search_path = public
as $$
  select loja from public.perfis where id = auth.uid() and ativo;
$$;

-- 4) Regras: cada um vê a sua loja; admin vê tudo; ninguém grava direto pelo site
alter table public.ligacoes enable row level security;
alter table public.ligacoes_historico enable row level security;

drop policy if exists "ligacoes: ver (sua loja ou admin)" on public.ligacoes;
create policy "ligacoes: ver (sua loja ou admin)" on public.ligacoes
  for select to authenticated
  using (public.eh_admin() or loja = public.minha_loja());

drop policy if exists "ligacoes_historico: ver (sua loja ou admin)" on public.ligacoes_historico;
create policy "ligacoes_historico: ver (sua loja ou admin)" on public.ligacoes_historico
  for select to authenticated
  using (exists (select 1 from public.ligacoes l
                 where l.id = ligacao_id
                   and (public.eh_admin() or l.loja = public.minha_loja())));

-- 5) A loja marca o status (e a observação). Fica registrado quem e quando.
--    "comprou" só o robô marca (conferido no Movere).
create or replace function public.marcar_ligacao(p_id bigint, p_status text, p_obs text default null)
returns void
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja text;
  v_nome text;
begin
  if p_status not in ('pendente', 'nao_atende', 'retornar', 'sem_interesse', 'agendou') then
    raise exception 'Status inválido: %', p_status;
  end if;

  select loja into v_loja from public.ligacoes where id = p_id;
  if v_loja is null then
    raise exception 'Ligação não encontrada';
  end if;
  if not (public.eh_admin() or v_loja = public.minha_loja()) then
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
         obs = coalesce(nullif(trim(p_obs), ''), obs)
   where id = p_id;

  insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
  values (p_id, v_nome, p_status, nullif(trim(p_obs), ''));
end;
$$;
revoke execute on function public.marcar_ligacao(bigint, text, text) from public, anon;
grant  execute on function public.marcar_ligacao(bigint, text, text) to authenticated;

-- Avisa a API do Supabase das tabelas e funções novas
notify pgrst, 'reload schema';

-- Conferência
select (select count(*) from public.ligacoes) as ligacoes,
       (select count(*) from public.perfis where loja is not null) as pessoas_com_loja;
