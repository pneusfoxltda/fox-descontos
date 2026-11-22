-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Passo 15: Ligações por vendedor (divisão automática, gerente, férias)
--
-- Quem vê (decisão do TI, 22/11/2026):
--   vendedor da loja     → só os clientes que estão com ele (responsável);
--                          sem Dashboard e sem histórico.
--   gerente da loja      → todos os clientes da loja dele, Dashboard e histórico;
--                          troca o responsável e coloca vendedor de férias.
--   gerente de todas as lojas (papel gerente, sem loja) e admin → todas as lojas.
--
-- Divisão: os clientes novos de cada loja são divididos igualmente entre os
-- vendedores ATIVOS (não de férias). A sobra (ex.: 29 para 3 → 10, 10 e 9) vai
-- para quem ficou com menos da vez anterior (rodízio por loja).
-- Férias: os clientes em aberto do vendedor são divididos entre os outros e ele
-- não recebe novos até voltar.
--
-- Só cria/ajusta coisas novas. Pode rodar mais de uma vez.
-- ════════════════════════════════════════════════════════════════════════

-- 1) Perfis: função nas ligações, primeiro nome e férias
alter table public.perfis add column if not exists papel_ligacoes text;   -- 'vendedor' | 'gerente'
alter table public.perfis add column if not exists apelido text;          -- primeiro nome mostrado na lista
alter table public.perfis add column if not exists ferias boolean not null default false;
do $$ begin
  alter table public.perfis add constraint perfis_papel_ligacoes_ok
    check (papel_ligacoes is null or papel_ligacoes in ('vendedor', 'gerente'));
exception when duplicate_object then null;
end $$;

-- quem já usava as ligações continua igual
update public.perfis set papel_ligacoes = 'gerente'
 where papel_ligacoes is null and dash_ligacoes;
update public.perfis set papel_ligacoes = 'vendedor'
 where papel_ligacoes is null and loja is not null;
update public.perfis set apelido = initcap(split_part(trim(nome), ' ', 1))
 where coalesce(trim(apelido), '') = '' and coalesce(trim(nome), '') <> '';
-- gerente sempre tem o Dashboard
update public.perfis set dash_ligacoes = true where papel_ligacoes = 'gerente' and not dash_ligacoes;

-- 2) Ligações: quem é o responsável e quantas vezes não atendeu
alter table public.ligacoes add column if not exists responsavel_id   uuid references public.perfis(id) on delete set null;
alter table public.ligacoes add column if not exists responsavel_nome text;
alter table public.ligacoes add column if not exists distribuido_em   timestamptz;
alter table public.ligacoes add column if not exists tentativas       integer not null default 0;
create index if not exists ligacoes_loja_responsavel on public.ligacoes (loja, responsavel_id);

-- tentativas "não atendeu" que já estão no histórico
update public.ligacoes l
   set tentativas = h.n
  from (select ligacao_id, count(*)::int as n
          from public.ligacoes_historico where status = 'nao_atende' group by ligacao_id) h
 where h.ligacao_id = l.id and l.tentativas < h.n;

-- 3) Rodízio da sobra, por loja (só as funções mexem)
create table if not exists public.ligacoes_rodizio (
  loja          text primary key,
  proximo_extra uuid,
  atualizado_em timestamptz not null default now()
);
alter table public.ligacoes_rodizio enable row level security;

-- 4) Funções de apoio
-- Gerente de todas as lojas (sem loja) ou admin
create or replace function public.ve_todas_ligacoes()
returns boolean
language sql stable security definer
set search_path = public
as $$
  select exists (select 1 from public.perfis
                 where id = auth.uid() and ativo
                   and ('admin' = any(funcoes)
                        or ((papel_ligacoes = 'gerente' or dash_ligacoes) and loja is null)));
$$;

-- Gerente desta loja (ou de todas, ou admin)
create or replace function public.eh_gerente_da_loja(p_loja text)
returns boolean
language sql stable security definer
set search_path = public
as $$
  select public.ve_todas_ligacoes() or exists (
    select 1 from public.perfis
     where id = auth.uid() and ativo and loja = p_loja
       and (papel_ligacoes = 'gerente' or dash_ligacoes));
$$;

-- Quem pode mexer na loja (trocar responsável, férias): gerente DA loja ou admin.
-- O gerente de todas as lojas só acompanha.
create or replace function public.gerencia_loja(p_loja text)
returns boolean
language sql stable security definer
set search_path = public
as $$
  select public.eh_admin() or exists (
    select 1 from public.perfis
     where id = auth.uid() and ativo and loja = p_loja
       and (papel_ligacoes = 'gerente' or dash_ligacoes));
$$;

revoke execute on function public.ve_todas_ligacoes() from public, anon;
revoke execute on function public.eh_gerente_da_loja(text) from public, anon;
revoke execute on function public.gerencia_loja(text) from public, anon;
grant  execute on function public.ve_todas_ligacoes() to authenticated;
grant  execute on function public.eh_gerente_da_loja(text) to authenticated;
grant  execute on function public.gerencia_loja(text) to authenticated;

-- 5) Quem vê
drop policy if exists "ligacoes: ver (sua loja, gerente ou admin)" on public.ligacoes;
drop policy if exists "ligacoes: ver (seus clientes, gerente ou admin)" on public.ligacoes;
create policy "ligacoes: ver (seus clientes, gerente ou admin)" on public.ligacoes
  for select to authenticated
  using (public.eh_gerente_da_loja(loja) or responsavel_id = auth.uid());

drop policy if exists "ligacoes_historico: ver (sua loja, gerente ou admin)" on public.ligacoes_historico;
drop policy if exists "ligacoes_historico: ver (gerente ou admin)" on public.ligacoes_historico;
create policy "ligacoes_historico: ver (gerente ou admin)" on public.ligacoes_historico
  for select to authenticated
  using (exists (select 1 from public.ligacoes l
                  where l.id = ligacao_id and public.eh_gerente_da_loja(l.loja)));

-- 6) Divisão automática (o robô chama depois de importar; férias também)
--    Divide os clientes em aberto SEM responsável entre os vendedores ativos da loja.
create or replace function public.distribuir_ligacoes(p_loja text default null)
returns integer
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja   text;
  v_vend   uuid[];
  v_nomes  text[];
  v_k      int;
  v_n      int;
  v_r      int;
  v_ini    int;
  v_ptr    uuid;
  v_i      int;
  v_alvo   int;
  v_total  int := 0;
  rec      record;
begin
  -- só o robô (sem usuário logado), o admin ou o gerente da loja
  if auth.uid() is not null and not (public.eh_admin() or (p_loja is not null and public.gerencia_loja(p_loja))) then
    raise exception 'Sem permissão para dividir as ligações';
  end if;

  for v_loja in
    select distinct loja from public.ligacoes
     where responsavel_id is null and (p_loja is null or loja = p_loja)
  loop
    select array_agg(id order by lower(coalesce(apelido, nome)), id),
           array_agg(coalesce(nullif(trim(apelido), ''), initcap(split_part(trim(nome), ' ', 1)))
                     order by lower(coalesce(apelido, nome)), id)
      into v_vend, v_nomes
      from public.perfis
     where loja = v_loja and ativo and not ferias and papel_ligacoes = 'vendedor';
    v_k := coalesce(array_length(v_vend, 1), 0);
    continue when v_k = 0;   -- loja sem vendedor ativo: fica para o gerente

    select count(*) into v_n
      from public.ligacoes
     where loja = v_loja and responsavel_id is null
       and status in ('pendente', 'nao_atende', 'retornar', 'agendou')
       and (data_cotacao >= current_date - 7 or status = 'agendou');
    continue when v_n = 0;

    -- a sobra começa por quem ficou com menos na vez anterior
    select proximo_extra into v_ptr from public.ligacoes_rodizio where loja = v_loja;
    v_ini := coalesce(array_position(v_vend, v_ptr), 1) - 1;
    v_r := v_n % v_k;

    v_i := 0;
    for rec in
      select id, status from public.ligacoes
       where loja = v_loja and responsavel_id is null
         and status in ('pendente', 'nao_atende', 'retornar', 'agendou')
         and (data_cotacao >= current_date - 7 or status = 'agendou')
       order by valor desc nulls last, id
    loop
      v_alvo := ((v_ini + v_i) % v_k) + 1;
      update public.ligacoes
         set responsavel_id = v_vend[v_alvo], responsavel_nome = v_nomes[v_alvo], distribuido_em = now()
       where id = rec.id;
      insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
      values (rec.id, 'Divisão automática', rec.status, 'Responsável: ' || v_nomes[v_alvo]);
      v_i := v_i + 1;
    end loop;

    if v_r > 0 then
      insert into public.ligacoes_rodizio (loja, proximo_extra, atualizado_em)
      values (v_loja, v_vend[((v_ini + v_r) % v_k) + 1], now())
      on conflict (loja) do update set proximo_extra = excluded.proximo_extra, atualizado_em = now();
    end if;
    v_total := v_total + v_n;
  end loop;
  return v_total;
end;
$$;
revoke execute on function public.distribuir_ligacoes(text) from public, anon;
grant  execute on function public.distribuir_ligacoes(text) to authenticated, service_role;

-- 7) Gerente/admin troca o responsável de um cliente
create or replace function public.trocar_responsavel(p_id bigint, p_vendedor uuid)
returns void
language plpgsql security definer
set search_path = public
as $$
declare
  v_lig   record;
  v_novo  text;
  v_quem  text;
begin
  select id, loja, status, responsavel_nome into v_lig from public.ligacoes where id = p_id;
  if v_lig.id is null then raise exception 'Ligação não encontrada'; end if;
  if not public.gerencia_loja(v_lig.loja) then
    raise exception 'Só o gerente da loja ou o admin pode trocar o responsável';
  end if;
  select coalesce(nullif(trim(apelido), ''), initcap(split_part(trim(nome), ' ', 1))) into v_novo
    from public.perfis
   where id = p_vendedor and ativo and loja = v_lig.loja and papel_ligacoes = 'vendedor';
  if v_novo is null then raise exception 'Vendedor não encontrado nesta loja'; end if;
  select coalesce(nullif(trim(apelido), ''), nullif(trim(nome), ''), email) into v_quem
    from public.perfis where id = auth.uid();

  update public.ligacoes
     set responsavel_id = p_vendedor, responsavel_nome = v_novo, distribuido_em = now()
   where id = p_id;
  insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
  values (p_id, v_quem, v_lig.status,
          'Responsável: ' || coalesce(v_lig.responsavel_nome, 'ninguém') || ' → ' || v_novo);
end;
$$;
revoke execute on function public.trocar_responsavel(bigint, uuid) from public, anon;
grant  execute on function public.trocar_responsavel(bigint, uuid) to authenticated;

-- 8) Férias: o vendedor para de receber e os clientes em aberto dele vão para os outros
create or replace function public.vendedor_ferias(p_vendedor uuid, p_ferias boolean)
returns integer
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja text;
  v_nome text;
  v_quem text;
  v_n    int := 0;
begin
  select loja, coalesce(nullif(trim(apelido), ''), initcap(split_part(trim(nome), ' ', 1)))
    into v_loja, v_nome
    from public.perfis where id = p_vendedor and papel_ligacoes = 'vendedor';
  if v_loja is null then raise exception 'Vendedor não encontrado'; end if;
  if not public.gerencia_loja(v_loja) then
    raise exception 'Só o gerente da loja ou o admin pode mudar';
  end if;
  select coalesce(nullif(trim(apelido), ''), nullif(trim(nome), ''), email) into v_quem
    from public.perfis where id = auth.uid();

  update public.perfis set ferias = p_ferias where id = p_vendedor;

  if p_ferias then
    with soltos as (
      update public.ligacoes
         set responsavel_id = null, responsavel_nome = null
       where responsavel_id = p_vendedor
         and status in ('pendente', 'nao_atende', 'retornar', 'agendou')
      returning id, status)
    insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
    select id, v_quem, status, v_nome || ' de férias: cliente vai para outro vendedor' from soltos;
    get diagnostics v_n = row_count;
    perform public.distribuir_ligacoes(v_loja);
  end if;
  return v_n;
end;
$$;
revoke execute on function public.vendedor_ferias(uuid, boolean) from public, anon;
grant  execute on function public.vendedor_ferias(uuid, boolean) to authenticated;

-- 9) Vendedores da loja (painel do gerente e lista de responsáveis)
drop function if exists public.vendedores_da_loja(text);
create or replace function public.vendedores_da_loja(p_loja text default null)
returns table (id uuid, loja text, apelido text, nome text, ferias boolean, abertos integer)
language sql stable security definer
set search_path = public
as $$
  select p.id, p.loja,
         coalesce(nullif(trim(p.apelido), ''), initcap(split_part(trim(p.nome), ' ', 1))),
         p.nome, p.ferias,
         (select count(*)::int from public.ligacoes l
           where l.responsavel_id = p.id and l.status in ('pendente', 'nao_atende', 'retornar', 'agendou'))
    from public.perfis p
   where p.ativo and p.papel_ligacoes = 'vendedor' and p.loja is not null
     and (p_loja is null or p.loja = p_loja)
     and public.eh_gerente_da_loja(p.loja)
   order by p.loja, lower(coalesce(p.apelido, p.nome));
$$;
revoke execute on function public.vendedores_da_loja(text) from public, anon;
grant  execute on function public.vendedores_da_loja(text) to authenticated;

-- 10) Marcar status: o vendedor só nos clientes dele; gerente na loja dele; admin em todas.
--     "Venda ganha" só com o nº da O.S.; "Não atende" conta uma tentativa.
create or replace function public.marcar_ligacao(
  p_id bigint, p_status text, p_obs text default null, p_os text default null,
  p_data date default null, p_motivo text default null)
returns void
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja text;
  v_resp uuid;
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

  select loja, responsavel_id into v_loja, v_resp from public.ligacoes where id = p_id;
  if v_loja is null then
    raise exception 'Ligação não encontrada';
  end if;
  if not (public.gerencia_loja(v_loja) or coalesce(v_resp = auth.uid(), false)) then
    raise exception 'Este cliente não está com você';
  end if;

  select coalesce(nullif(trim(apelido), ''), nullif(trim(nome), ''), email) into v_nome
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
         motivo_perda = case when p_status = 'venda_perdida' then trim(p_motivo) else motivo_perda end,
         tentativas = tentativas + case when p_status = 'nao_atende' then 1 else 0 end
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

-- 11) Divide agora os clientes que já estão na lista (se a loja já tiver vendedores)
select public.distribuir_ligacoes(null) as clientes_divididos_agora;

notify pgrst, 'reload schema';

-- Conferência
select loja,
       count(*) filter (where responsavel_id is not null) as com_responsavel,
       count(*) filter (where responsavel_id is null)     as sem_responsavel
  from public.ligacoes
 group by loja order by loja;
