-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Segurança · Passo 7: TRANCAR O BANCO (regras por nível)
--
-- IMPORTANTE: rodar SÓ DEPOIS do passo 6 E depois que o site novo (página
-- Consulta usando a função "consulta_publica") estiver publicado.
-- Antes disso a Consulta das lojas para de achar os descontos.
--
-- Quem pode o quê depois deste passo:
--   descontos ........ ver: quem tem nível (admin, comercial, gerente, televendas)
--                      cadastrar: comercial e televendas · editar/liberar: comercial
--                      excluir: só admin
--   Consulta pública . só pela função consulta_publica (sem login, só as colunas
--                      que a tela mostra, no máximo 200 resultados)
--   configuracoes .... ver: quem está logado · alterar: só admin
--   logs_consulta .... gravar: qualquer um (a Consulta registra as buscas)
--                      ver/apagar: só admin
--   logs_usuarios .... gravar: quem está logado · ver: só admin
--   metas_televendas . ver: todos (o painel mostra sem login) · alterar: só admin
--   vendas_televendas  ver: todos (painel sem login) · gravação do robô continua
--                      igual por enquanto (o passo 8 tranca isso)
--   vendas_televendas_clientes  ver: só logado com nível televendas ou gerente
--   usuarios, usuarios_televendas  ninguém pelo site (tabelas antigas, com senhas)
--   Funções antigas (fox_login, fox_criar_usuario, update_usuario): desligadas
--
-- Não apaga nenhum dado. Pode rodar mais de uma vez.
-- Como rodar: Supabase (janela anônima) → SQL Editor → New query → colar → Run.
-- ════════════════════════════════════════════════════════════════════════

-- Confere se o passo 6 já rodou (senão para aqui, sem mudar nada)
do $$ begin
  if to_regprocedure('public.consulta_publica(text, text, text)') is null then
    raise exception 'Rode primeiro o passo 6 (06_consulta_publica.sql).';
  end if;
end $$;

-- 0) Apaga TODAS as regras antigas destas tabelas (as de "acesso total")
do $$
declare r record;
begin
  for r in
    select tablename, policyname from pg_policies
    where schemaname = 'public'
      and tablename in ('descontos', 'configuracoes', 'logs_consulta', 'logs_usuarios',
                        'metas_televendas', 'vendas_televendas_clientes',
                        'usuarios', 'usuarios_televendas')
  loop
    execute format('drop policy %I on public.%I', r.policyname, r.tablename);
  end loop;

  -- vendas_televendas: só tira as leituras repetidas; a gravação do robô fica (passo 8)
  for r in
    select policyname from pg_policies
    where schemaname = 'public' and tablename = 'vendas_televendas' and cmd = 'SELECT'
  loop
    execute format('drop policy %I on public.vendas_televendas', r.policyname);
  end loop;
end $$;

-- Garante a trava ligada em todas
alter table public.descontos                  enable row level security;
alter table public.configuracoes              enable row level security;
alter table public.logs_consulta              enable row level security;
alter table public.logs_usuarios              enable row level security;
alter table public.metas_televendas           enable row level security;
alter table public.vendas_televendas          enable row level security;
alter table public.vendas_televendas_clientes enable row level security;
alter table public.usuarios                   enable row level security;
alter table public.usuarios_televendas        enable row level security;

-- 1) descontos
create policy "descontos: ver (quem tem nivel)" on public.descontos
  for select to authenticated
  using (public.tem_funcao('comercial') or public.tem_funcao('gerente')
         or public.tem_funcao('televendas'));

create policy "descontos: cadastrar (comercial, televendas)" on public.descontos
  for insert to authenticated
  with check (public.tem_funcao('comercial') or public.tem_funcao('televendas'));

create policy "descontos: editar e liberar (comercial)" on public.descontos
  for update to authenticated
  using (public.tem_funcao('comercial'))
  with check (public.tem_funcao('comercial'));

create policy "descontos: excluir (admin)" on public.descontos
  for delete to authenticated
  using (public.eh_admin());

-- 2) configuracoes (lista de vendedores)
create policy "configuracoes: ver (logado)" on public.configuracoes
  for select to authenticated using (true);
create policy "configuracoes: alterar (admin)" on public.configuracoes
  for all to authenticated using (public.eh_admin()) with check (public.eh_admin());

-- 3) logs_consulta
create policy "logs_consulta: gravar (todos)" on public.logs_consulta
  for insert to anon, authenticated with check (true);
create policy "logs_consulta: ver (admin)" on public.logs_consulta
  for select to authenticated using (public.eh_admin());
create policy "logs_consulta: apagar (admin)" on public.logs_consulta
  for delete to authenticated using (public.eh_admin());

-- 4) logs_usuarios
create policy "logs_usuarios: gravar (logado)" on public.logs_usuarios
  for insert to authenticated with check (true);
create policy "logs_usuarios: ver (admin)" on public.logs_usuarios
  for select to authenticated using (public.eh_admin());

-- 5) metas_televendas
create policy "metas: ver (todos)" on public.metas_televendas
  for select to anon, authenticated using (true);
create policy "metas: alterar (admin)" on public.metas_televendas
  for all to authenticated using (public.eh_admin()) with check (public.eh_admin());

-- 6) vendas_televendas (leitura; a gravação do robô continua até o passo 8)
create policy "vendas: ver (todos)" on public.vendas_televendas
  for select to anon, authenticated using (true);

-- 7) vendas_televendas_clientes (dados de clientes)
create policy "vendas clientes: ver (televendas, gerente)" on public.vendas_televendas_clientes
  for select to authenticated
  using (public.tem_funcao('televendas') or public.tem_funcao('gerente'));

-- 8) usuarios e usuarios_televendas: sem regra = ninguém acessa pelo site

-- 9) Consulta pública: a função consulta_publica foi criada no passo 6.

-- 10) Editar desconto (App): a função agora RESPEITA a trava (só comercial/admin)
--     e só mexe nos campos que as telas usam.
drop function if exists public.update_desconto(text, text, jsonb);
create function public.update_desconto(p_numero text, p_tipo text, p_fields jsonb)
returns void
language plpgsql security invoker
set search_path = public
as $$
begin
  update public.descontos d
     set (cba, medida, segmento, loja, valor, pgto, validade, obs, erro_interno,
          perdida, motivo_perda, liberado, liberador_nome, liberador_email, liberado_em)
       = (select r.cba, r.medida, r.segmento, r.loja, r.valor, r.pgto, r.validade, r.obs,
                 r.erro_interno, r.perdida, r.motivo_perda, r.liberado, r.liberador_nome,
                 r.liberador_email, r.liberado_em
            from jsonb_populate_record(d, p_fields) r)
   where d.numero = p_numero and d.tipo = p_tipo;
end;
$$;
revoke execute on function public.update_desconto(text, text, jsonb) from public, anon;
grant  execute on function public.update_desconto(text, text, jsonb) to authenticated;

-- 11) Marcar vencidas como perdidas: só quem está logado pode chamar
revoke execute on function public.auto_perdida() from public, anon;
grant  execute on function public.auto_perdida() to authenticated;

-- 12) Funções antigas (login antigo com senha legível): desligadas para o site
do $$
declare f text;
begin
  foreach f in array array[
    'public.fox_login(text, text)',
    'public.fox_criar_usuario(text, text, text, text, text)',
    'public.update_usuario(text, jsonb)',
    'public.criar_perfil_novo_login()'
  ] loop
    if to_regprocedure(f) is not null then
      execute format('revoke execute on function %s from public, anon, authenticated', f);
    end if;
  end loop;
end $$;

-- Avisa a API do Supabase das funções novas
notify pgrst, 'reload schema';

-- Conferência: as regras que ficaram
select tablename as tabela, policyname as regra, cmd as acao, array_to_string(roles, ',') as para
from pg_policies
where schemaname = 'public'
order by tablename, policyname;
