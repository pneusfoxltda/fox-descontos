-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Passo 12: Ligações das lojas
--
-- Lista de clientes que fizeram cotação e ainda não compraram nem agendaram,
-- para os VENDEDORES DAS LOJAS ligarem. Quem preenche é o robô "Ligações das
-- lojas" (GitHub). As planilhas do Google continuam funcionando como hoje.
--
-- Quem vê:   vendedor → só a lista da SUA loja (campo "loja" do perfil);
--            gerente com dashboard (perfis.dash_ligacoes) → todas as lojas (só olha);
--            admin → tudo.
-- Quem muda: o vendedor muda o status da SUA loja pela função marcar_ligacao
--            (fica registrado quem e quando). "Venda ganha" exige o nº da O.S.
--            "Venda ganha televendas" só o robô marca (comprou e a loja não
--            registrou venda ganha).
-- Primeiro acesso: perfis.trocar_senha = true obriga a criar uma senha nova.
--
-- Só cria/ajusta coisas novas. Pode rodar mais de uma vez.
-- ════════════════════════════════════════════════════════════════════════

-- 1) Perfis: troca de senha obrigatória e acesso ao dashboard das ligações
alter table public.perfis add column if not exists trocar_senha   boolean not null default false;
alter table public.perfis add column if not exists dash_ligacoes  boolean not null default false;

-- 2) A lista
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
  os_venda      text,                          -- nº da O.S. informado na "Venda ganha"
  comprou_em    date,                          -- data da compra achada pelo robô
  criado_em     timestamptz not null default now()
);
alter table public.ligacoes add column if not exists os_venda text;
alter table public.ligacoes drop constraint if exists ligacoes_status_valido;
alter table public.ligacoes add constraint ligacoes_status_valido check (status in
  ('pendente', 'nao_atende', 'retornar', 'sem_interesse', 'agendou',
   'venda_ganha', 'venda_televendas', 'comprou'));
create index if not exists ligacoes_loja_data on public.ligacoes (loja, data_cotacao desc);
create index if not exists ligacoes_tel_chave on public.ligacoes (tel_chave);

-- 3) O histórico de cada cliente (quem marcou o quê e quando)
create table if not exists public.ligacoes_historico (
  id          bigserial primary key,
  ligacao_id  bigint not null references public.ligacoes(id) on delete cascade,
  quando      timestamptz not null default now(),
  quem        text not null,
  status      text not null,
  obs         text
);
create index if not exists ligacoes_historico_ligacao on public.ligacoes_historico (ligacao_id, quando);
create index if not exists ligacoes_historico_quando on public.ligacoes_historico (quando);

-- 4) Funções de apoio
create or replace function public.minha_loja()
returns text
language sql stable security definer
set search_path = public
as $$
  select loja from public.perfis where id = auth.uid() and ativo;
$$;

create or replace function public.ve_todas_ligacoes()
returns boolean
language sql stable security definer
set search_path = public
as $$
  select exists (select 1 from public.perfis
                 where id = auth.uid() and ativo and (dash_ligacoes or 'admin' = any(funcoes)));
$$;

-- 5) Regras de leitura (ninguém grava direto pelo site)
alter table public.ligacoes enable row level security;
alter table public.ligacoes_historico enable row level security;

drop policy if exists "ligacoes: ver (sua loja ou admin)" on public.ligacoes;
drop policy if exists "ligacoes: ver (sua loja, gerente ou admin)" on public.ligacoes;
create policy "ligacoes: ver (sua loja, gerente ou admin)" on public.ligacoes
  for select to authenticated
  using (public.ve_todas_ligacoes() or loja = public.minha_loja());

drop policy if exists "ligacoes_historico: ver (sua loja ou admin)" on public.ligacoes_historico;
drop policy if exists "ligacoes_historico: ver (sua loja, gerente ou admin)" on public.ligacoes_historico;
create policy "ligacoes_historico: ver (sua loja, gerente ou admin)" on public.ligacoes_historico
  for select to authenticated
  using (public.ve_todas_ligacoes()
         or exists (select 1 from public.ligacoes l where l.id = ligacao_id and l.loja = public.minha_loja()));

-- 6) O vendedor marca o status da SUA loja (admin: qualquer loja).
--    "venda_ganha" exige o nº da O.S. "venda_televendas" só o robô marca.
drop function if exists public.marcar_ligacao(bigint, text, text);
create or replace function public.marcar_ligacao(p_id bigint, p_status text, p_obs text default null, p_os text default null)
returns void
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja text;
  v_nome text;
begin
  if p_status not in ('pendente', 'nao_atende', 'retornar', 'sem_interesse', 'agendou', 'venda_ganha') then
    raise exception 'Status inválido: %', p_status;
  end if;
  if p_status = 'venda_ganha' and coalesce(trim(p_os), '') = '' then
    raise exception 'Informe o nº da O.S. da venda';
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
         os_venda = case when p_status = 'venda_ganha' then trim(p_os) else os_venda end
   where id = p_id;

  insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
  values (p_id, v_nome, p_status,
          nullif(trim(concat_ws(' · ', nullif(trim(p_obs), ''),
                 case when p_status = 'venda_ganha' then 'O.S. ' || trim(p_os) end)), ''));
end;
$$;
revoke execute on function public.marcar_ligacao(bigint, text, text, text) from public, anon;
grant  execute on function public.marcar_ligacao(bigint, text, text, text) to authenticated;

-- 7) Primeiro acesso: depois de criar a senha nova, a pessoa desliga o aviso
create or replace function public.senha_trocada()
returns void
language sql security definer
set search_path = public
as $$
  update public.perfis set trocar_senha = false where id = auth.uid();
$$;
revoke execute on function public.senha_trocada() from public, anon;
grant  execute on function public.senha_trocada() to authenticated;

-- Avisa a API do Supabase das tabelas e funções novas
notify pgrst, 'reload schema';

-- Conferência
select (select count(*) from public.ligacoes) as ligacoes,
       (select count(*) from public.perfis where loja is not null) as vendedores_com_loja,
       (select count(*) from public.perfis where dash_ligacoes) as gerentes_com_dashboard;
