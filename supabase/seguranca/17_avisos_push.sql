-- =====================================================================
-- 17) Ligações das lojas: AVISOS NO COMPUTADOR E NO CELULAR (notificação push)
-- ---------------------------------------------------------------------
-- O vendedor clica em "Quero receber avisos" (Fernanda ou 🔔 no topo das Ligações)
-- e o navegador guarda aqui o "endereço" do aparelho. O robô avisos_ligacoes.py manda
-- os avisos (8h, 10h, 14h e 16h30) com SÓ OS NÚMEROS (nada de nome ou telefone de cliente).
--  · push_inscricoes: aparelhos de cada pessoa (cada um vê/apaga os seus; o admin vê todos).
--  · push_config: a chave dos avisos. O robô cria sozinho na 1ª vez; ninguém lê pelo site
--    (sem regra de acesso = só o robô, com a chave de serviço).
-- Grátis: quem entrega o aviso é o serviço do próprio navegador (Google, Apple, Microsoft).
-- Pode rodar mais de uma vez.
-- =====================================================================

create table if not exists public.push_inscricoes (
  id           bigserial primary key,
  perfil_id    uuid not null references public.perfis(id) on delete cascade,
  endpoint     text not null unique,
  p256dh       text not null,
  auth         text not null,
  aparelho     text,
  criado_em    timestamptz not null default now(),
  ultimo_envio timestamptz,
  falhas       integer not null default 0
);
create index if not exists push_inscricoes_perfil on public.push_inscricoes (perfil_id);
alter table public.push_inscricoes enable row level security;

drop policy if exists "push: ver os seus (admin vê todos)" on public.push_inscricoes;
create policy "push: ver os seus (admin vê todos)" on public.push_inscricoes
  for select to authenticated using (perfil_id = auth.uid() or public.eh_admin());
drop policy if exists "push: apagar os seus (admin apaga todos)" on public.push_inscricoes;
create policy "push: apagar os seus (admin apaga todos)" on public.push_inscricoes
  for delete to authenticated using (perfil_id = auth.uid() or public.eh_admin());
-- gravar só pela função salvar_push (abaixo)

create table if not exists public.push_config (
  id            integer primary key default 1 check (id = 1),
  chave_publica text not null,
  chave_privada text not null,
  criado_em     timestamptz not null default now()
);
alter table public.push_config enable row level security;
-- sem regras: só o robô (chave de serviço) lê e grava

-- Chave pública (o navegador precisa dela para se inscrever; não é segredo)
create or replace function public.push_chave_publica()
returns text
language sql stable security definer
set search_path = public
as $$ select chave_publica from public.push_config where id = 1 $$;
revoke execute on function public.push_chave_publica() from public, anon;
grant  execute on function public.push_chave_publica() to authenticated;

-- Guarda (ou atualiza) o aparelho de quem está logado. Se o mesmo aparelho for usado
-- por outra pessoa depois, passa a ser dessa pessoa.
create or replace function public.salvar_push(p_endpoint text, p_p256dh text, p_auth text, p_aparelho text default null)
returns void
language plpgsql security definer
set search_path = public
as $$
begin
  if auth.uid() is null then raise exception 'Entre com o seu login'; end if;
  if coalesce(p_endpoint, '') !~ '^https://' or coalesce(p_p256dh, '') = '' or coalesce(p_auth, '') = '' then
    raise exception 'Inscrição inválida';
  end if;
  insert into public.push_inscricoes (perfil_id, endpoint, p256dh, auth, aparelho)
  values (auth.uid(), p_endpoint, p_p256dh, p_auth, left(p_aparelho, 200))
  on conflict (endpoint) do update
     set perfil_id = auth.uid(), p256dh = excluded.p256dh, auth = excluded.auth,
         aparelho = excluded.aparelho, falhas = 0;
end;
$$;
revoke execute on function public.salvar_push(text, text, text, text) from public, anon;
grant  execute on function public.salvar_push(text, text, text, text) to authenticated;

create or replace function public.remover_push(p_endpoint text)
returns void
language sql security definer
set search_path = public
as $$ delete from public.push_inscricoes where endpoint = p_endpoint and perfil_id = auth.uid() $$;
revoke execute on function public.remover_push(text) from public, anon;
grant  execute on function public.remover_push(text) to authenticated;

notify pgrst, 'reload schema';

-- Conferência
select (select count(*) from public.push_inscricoes) as aparelhos_com_aviso,
       (select count(*) from public.push_config)     as chave_criada;
