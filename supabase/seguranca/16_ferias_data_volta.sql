-- =====================================================================
-- 16) Ligações das lojas: FÉRIAS COM DATA DE VOLTA
-- ---------------------------------------------------------------------
-- O gerente (ou o admin) coloca o vendedor de férias e diz o dia que ele volta.
--  · Na hora: os clientes em aberto dele passam para os outros vendedores ativos
--    da loja e ele para de receber clientes novos.
--  · No dia da volta: ele volta a receber sozinho (o robô das 7h já divide com ele).
--  · O gerente pode ativar antes, pelo botão "Voltou: ativar".
-- Pode rodar mais de uma vez. Rodar DEPOIS do 15.
-- =====================================================================

alter table public.perfis add column if not exists ferias_ate date;

-- 1) Volta das férias: quem chegou na data volta a ficar ativo
create or replace function public.voltar_das_ferias()
returns integer
language plpgsql security definer
set search_path = public
as $$
declare v_n int;
begin
  update public.perfis
     set ferias = false, ferias_ate = null
   where ferias and ferias_ate is not null
     and ferias_ate <= (now() at time zone 'America/Porto_Velho')::date;
  get diagnostics v_n = row_count;
  return v_n;
end;
$$;
revoke execute on function public.voltar_das_ferias() from public, anon;
grant  execute on function public.voltar_das_ferias() to authenticated, service_role;

-- 2) Divisão (igual ao passo 15, agora devolvendo quem voltou das férias antes de dividir)
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

  -- quem chegou na data de volta das férias volta a receber clientes (a partir deste dia)
  perform public.voltar_das_ferias();

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

-- 3) Férias com data de volta (a função antiga, sem data, é trocada por esta)
drop function if exists public.vendedor_ferias(uuid, boolean);
create or replace function public.vendedor_ferias(p_vendedor uuid, p_ferias boolean, p_volta date default null)
returns integer
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja text;
  v_nome text;
  v_quem text;
  v_hoje date := (now() at time zone 'America/Porto_Velho')::date;
  v_n    int := 0;
begin
  select loja, coalesce(nullif(trim(apelido), ''), initcap(split_part(trim(nome), ' ', 1)))
    into v_loja, v_nome
    from public.perfis where id = p_vendedor and papel_ligacoes = 'vendedor';
  if v_loja is null then raise exception 'Vendedor não encontrado'; end if;
  if not public.gerencia_loja(v_loja) then
    raise exception 'Só o gerente da loja ou o admin pode mudar';
  end if;
  if p_ferias and p_volta is not null and p_volta <= v_hoje then
    raise exception 'A data de volta precisa ser depois de hoje';
  end if;
  select coalesce(nullif(trim(apelido), ''), nullif(trim(nome), ''), email) into v_quem
    from public.perfis where id = auth.uid();

  update public.perfis
     set ferias = p_ferias, ferias_ate = case when p_ferias then p_volta end
   where id = p_vendedor;

  if p_ferias then
    with soltos as (
      update public.ligacoes
         set responsavel_id = null, responsavel_nome = null
       where responsavel_id = p_vendedor
         and status in ('pendente', 'nao_atende', 'retornar', 'agendou')
      returning id, status)
    insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
    select id, v_quem, status, v_nome || ' de férias'
           || coalesce(' até ' || to_char(p_volta - 1, 'DD/MM'), '')
           || ': cliente vai para outro vendedor' from soltos;
    get diagnostics v_n = row_count;
    perform public.distribuir_ligacoes(v_loja);
  end if;
  return v_n;
end;
$$;
revoke execute on function public.vendedor_ferias(uuid, boolean, date) from public, anon;
grant  execute on function public.vendedor_ferias(uuid, boolean, date) to authenticated;

-- 4) Vendedores da loja: agora com a data de volta
drop function if exists public.vendedores_da_loja(text);
create or replace function public.vendedores_da_loja(p_loja text default null)
returns table (id uuid, loja text, apelido text, nome text, ferias boolean, abertos integer, ferias_ate date)
language sql stable security definer
set search_path = public
as $$
  select p.id, p.loja,
         coalesce(nullif(trim(p.apelido), ''), initcap(split_part(trim(p.nome), ' ', 1))),
         p.nome, p.ferias,
         (select count(*)::int from public.ligacoes l
           where l.responsavel_id = p.id and l.status in ('pendente', 'nao_atende', 'retornar', 'agendou')),
         p.ferias_ate
    from public.perfis p
   where p.ativo and p.papel_ligacoes = 'vendedor' and p.loja is not null
     and (p_loja is null or p.loja = p_loja)
     and public.eh_gerente_da_loja(p.loja)
   order by p.loja, lower(coalesce(p.apelido, p.nome));
$$;
revoke execute on function public.vendedores_da_loja(text) from public, anon;
grant  execute on function public.vendedores_da_loja(text) to authenticated;

notify pgrst, 'reload schema';

-- Conferência: vendedores de férias e quando voltam
select loja, coalesce(apelido, nome) as vendedor, ferias, ferias_ate as volta_em
  from public.perfis
 where papel_ligacoes = 'vendedor'
 order by loja, 2;
