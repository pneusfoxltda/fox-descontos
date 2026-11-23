-- =====================================================================
-- 18) 🩺 MONITOR (página /monitor, só o admin)
-- ---------------------------------------------------------------------
-- Uma função que junta, numa ida só, a saúde de tudo:
--   robôs (rodadas e detalhes), lista das ligações por dia, divisão por loja,
--   uso pelas lojas, avisos no celular, descontos, televendas, tabelas,
--   segurança (tabelas sem trava / abertas sem login) e o tamanho do banco.
-- Só contagens e datas: nada de nome ou telefone de cliente.
-- Só o admin consegue chamar (a função confere e recusa os outros).
-- Também cria a coluna "detalhes" nas rodadas dos robôs.
-- Pode rodar mais de uma vez.
-- =====================================================================

alter table public.robo_execucoes add column if not exists detalhes jsonb;

-- Linhas e data mais recente de uma tabela (sem quebrar se a tabela/coluna não existir)
create or replace function public.monitor_tabela(p_tabela text)
returns jsonb
language plpgsql stable security definer
set search_path = public
as $$
declare v_col text; v_n bigint; v_ult timestamptz;
begin
  if to_regclass('public.' || p_tabela) is null then return jsonb_build_object('existe', false); end if;
  execute format('select count(*) from public.%I', p_tabela) into v_n;
  select c.column_name into v_col
    from information_schema.columns c
   where c.table_schema = 'public' and c.table_name = p_tabela
     and c.data_type in ('timestamp with time zone', 'timestamp without time zone', 'date')
   order by array_position(array['atualizado_em','updated_at','criado_em','created_at','fim','inicio','quando','data','dia'], c.column_name::text) nulls last
   limit 1;
  if v_col is not null then
    execute format('select max(%I)::timestamptz from public.%I', v_col, p_tabela) into v_ult;
  end if;
  return jsonb_build_object('existe', true, 'linhas', v_n, 'coluna', v_col, 'ultima', v_ult);
exception when others then
  return jsonb_build_object('existe', true, 'erro', sqlerrm);
end;
$$;
revoke execute on function public.monitor_tabela(text) from public, anon, authenticated;

create or replace function public.monitor_resumo()
returns jsonb
language plpgsql stable security definer
set search_path = public
as $$
declare
  v_hoje date := (now() at time zone 'America/Porto_Velho')::date;
  r jsonb := '{}'::jsonb;
  v jsonb;
begin
  if not public.eh_admin() then raise exception 'Só o administrador'; end if;
  r := r || jsonb_build_object('agora', now(), 'hoje', v_hoje);

  -- Robôs: as últimas 8 rodadas de cada um
  select coalesce(jsonb_object_agg(robo, rodadas), '{}'::jsonb) into v from (
    select robo, jsonb_agg(jsonb_build_object('ok', ok, 'teste', teste, 'inicio', inicio, 'fim', fim, 'conferidos', conferidos,
                                              'encontrados', encontrados, 'mensagem', mensagem, 'detalhes', detalhes) order by inicio desc) rodadas
      from (select *, row_number() over (partition by robo order by inicio desc) n from public.robo_execucoes) x
     where n <= 8 group by robo) y;
  r := r || jsonb_build_object('robos', v);

  -- Ligações: clientes por dia de cotação (14 dias) e quantos estão sem responsável
  begin
    select coalesce(jsonb_agg(jsonb_build_object('dia', data_cotacao, 'total', total, 'sem_resp', sem_resp, 'pendentes', pend) order by data_cotacao), '[]')
      into v from (
      select data_cotacao, count(*) total,
             count(*) filter (where responsavel_id is null and status in ('pendente','nao_atende','retornar','agendou')) sem_resp,
             count(*) filter (where status = 'pendente') pend
        from public.ligacoes where data_cotacao >= v_hoje - 14 group by data_cotacao) d;
    r := r || jsonb_build_object('ligacoes_dias', v);

    -- Por loja: vendedores, divisão e uso (só o trabalho de pessoas com o cliente)
    select coalesce(jsonb_agg(l order by l->>'loja'), '[]') into v from (
      select jsonb_build_object(
        'loja', lj.loja,
        'abertos', (select count(*) from public.ligacoes g where g.loja = lj.loja and g.status in ('pendente','nao_atende','retornar','agendou')),
        'sem_resp', (select count(*) from public.ligacoes g where g.loja = lj.loja and g.responsavel_id is null
                                                              and g.status in ('pendente','nao_atende','retornar','agendou')),
        'vendedores', (select count(*) from public.perfis p where p.loja = lj.loja and p.ativo and p.papel_ligacoes = 'vendedor' and not p.ferias),
        'ferias', (select count(*) from public.perfis p where p.loja = lj.loja and p.ativo and p.papel_ligacoes = 'vendedor' and p.ferias),
        'menor', (select min(c) from (select count(g.id) c from public.perfis p left join public.ligacoes g on g.responsavel_id = p.id
                                         and g.status in ('pendente','nao_atende','retornar','agendou')
                                       where p.loja = lj.loja and p.ativo and p.papel_ligacoes = 'vendedor' and not p.ferias group by p.id) m),
        'maior', (select max(c) from (select count(g.id) c from public.perfis p left join public.ligacoes g on g.responsavel_id = p.id
                                         and g.status in ('pendente','nao_atende','retornar','agendou')
                                       where p.loja = lj.loja and p.ativo and p.papel_ligacoes = 'vendedor' and not p.ferias group by p.id) m),
        'ultimo_contato', (select max(h.quando) from public.ligacoes_historico h join public.ligacoes g on g.id = h.ligacao_id
                            where g.loja = lj.loja and h.quem not like 'Robô%' and h.quem <> 'Divisão automática'
                              and coalesce(h.obs, '') not like 'Responsável: %' and coalesce(h.obs, '') not like '% de férias%'),
        'contatos_hoje', (select count(*) from public.ligacoes_historico h join public.ligacoes g on g.id = h.ligacao_id
                           where g.loja = lj.loja and (h.quando at time zone 'America/Porto_Velho')::date = v_hoje
                             and h.quem not like 'Robô%' and h.quem <> 'Divisão automática'
                             and coalesce(h.obs, '') not like 'Responsável: %' and coalesce(h.obs, '') not like '% de férias%')
      ) l
      from (select distinct loja from public.ligacoes where loja is not null) lj) z;
    r := r || jsonb_build_object('ligacoes_lojas', v);
  exception when others then
    r := r || jsonb_build_object('ligacoes_erro', sqlerrm);
  end;

  -- Avisos no celular
  begin
    select jsonb_build_object('aparelhos', count(*), 'pessoas', count(distinct perfil_id), 'ultimo_envio', max(ultimo_envio),
                              'com_falha', count(*) filter (where falhas > 0),
                              'chave', (select count(*) from public.push_config))
      into v from public.push_inscricoes;
    r := r || jsonb_build_object('avisos', v);
  exception when others then r := r || jsonb_build_object('avisos', jsonb_build_object('erro', sqlerrm));
  end;

  -- Descontos: total, hoje, 7 dias, último cadastro, liberados hoje
  begin
    execute $q$
      select jsonb_build_object(
        'total', count(*),
        'hoje', count(*) filter (where (criado_em::timestamptz at time zone 'America/Porto_Velho')::date = $1),
        'semana', count(*) filter (where (criado_em::timestamptz at time zone 'America/Porto_Velho')::date > $1 - 7),
        'ultimo', max(criado_em::timestamptz),
        'liberados_hoje', count(*) filter (where liberado and (liberado_em::timestamptz at time zone 'America/Porto_Velho')::date = $1),
        'venda_movere', count(*) filter (where coalesce(venda_movere, false) and not coalesce(liberado, false)))
      from public.descontos $q$ into v using v_hoje;
    r := r || jsonb_build_object('descontos', v);
  exception when others then r := r || jsonb_build_object('descontos', jsonb_build_object('erro', sqlerrm));
  end;

  -- Tabelas: linhas e data mais recente
  select jsonb_object_agg(t, public.monitor_tabela(t)) into v
    from unnest(array['descontos','ligacoes','ligacoes_historico','perfis','vendas_televendas','vendas_televendas_clientes',
                      'metas_televendas','configuracoes','logs_usuarios','logs_consulta','robo_execucoes','push_inscricoes',
                      'usuarios','usuarios_televendas']) t;
  r := r || jsonb_build_object('tabelas', v);

  -- Segurança: tabelas sem trava (RLS) e regras que deixam ler/gravar SEM login
  select coalesce(jsonb_agg(c.relname order by c.relname), '[]') into v
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity;
  r := r || jsonb_build_object('sem_rls', v);
  select coalesce(jsonb_agg(jsonb_build_object('tabela', tablename, 'regra', policyname, 'acao', cmd) order by tablename, policyname), '[]') into v
    from pg_policies
   where schemaname = 'public' and (roles @> array['anon']::name[] or roles @> array['public']::name[]);
  r := r || jsonb_build_object('abertas_sem_login', v);
  -- Senhas legíveis nas tabelas antigas (passo 2 dos próximos passos)
  begin
    execute 'select count(*) filter (where coalesce(senha, '''') <> '''') from public.usuarios' into v;
    r := r || jsonb_build_object('senhas_usuarios', v);
  exception when others then null;
  end;
  begin
    execute 'select count(*) filter (where coalesce(senha, '''') <> '''') from public.usuarios_televendas' into v;
    r := r || jsonb_build_object('senhas_televendas', v);
  exception when others then null;
  end;

  -- Tamanho do banco (plano grátis: 500 MB)
  r := r || jsonb_build_object('banco_bytes', pg_database_size(current_database()));
  return r;
end;
$$;
revoke execute on function public.monitor_resumo() from public, anon;
grant  execute on function public.monitor_resumo() to authenticated;

notify pgrst, 'reload schema';

-- Conferência (no SQL Editor você é o dono do banco: mostra só que a função existe)
select 'monitor pronto' as resultado, pg_size_pretty(pg_database_size(current_database())) as tamanho_do_banco;
