-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Segurança · Passo 2: criar os logins seguros (Supabase Auth)
--
-- O que faz:
--   1. Cria a tabela "perfis" (nome, e-mail, funções e loja de cada pessoa).
--   2. Para cada pessoa da tabela "usuarios" (App de descontos), cria um login
--      no Supabase Auth com a MESMA senha de hoje, guardada criptografada.
--
-- O que NÃO faz:
--   · Não altera nem apaga nada que já existe. O sistema atual continua
--     funcionando exatamente igual.
--   · Pode rodar mais de uma vez sem problema: quem já tem login é pulado.
--
-- Como rodar: Supabase → SQL Editor → New query → colar tudo → Run.
-- ════════════════════════════════════════════════════════════════════════

-- 1) Perfis: quem é cada pessoa e o que ela pode acessar
create table if not exists public.perfis (
  id         uuid primary key references auth.users(id) on delete cascade,
  nome       text not null,
  email      text not null unique,
  funcoes    text[] not null default '{}',   -- ex.: {admin}, {gerente,comercial}, {televendas}
  loja       text,                            -- loja da pessoa (para Resultados e Ligações)
  vendedor_bi text,                           -- nome exato no Movere/BI (para Resultados)
  ativo      boolean not null default true,
  criado_em  timestamptz not null default now()
);

alter table public.perfis enable row level security;

-- Diz se quem está logado é admin (usada nas regras de acesso)
create or replace function public.eh_admin()
returns boolean
language sql stable security definer
set search_path = public
as $$
  select exists (
    select 1 from public.perfis
    where id = auth.uid() and ativo and 'admin' = any(funcoes)
  );
$$;

-- Diz se quem está logado tem uma função (ex.: tem_funcao('gerente'))
create or replace function public.tem_funcao(f text)
returns boolean
language sql stable security definer
set search_path = public
as $$
  select exists (
    select 1 from public.perfis
    where id = auth.uid() and ativo and (f = any(funcoes) or 'admin' = any(funcoes))
  );
$$;

drop policy if exists "perfis: cada um le o seu, admin le todos" on public.perfis;
create policy "perfis: cada um le o seu, admin le todos" on public.perfis
  for select to authenticated
  using (id = auth.uid() or public.eh_admin());

drop policy if exists "perfis: so admin altera" on public.perfis;
create policy "perfis: so admin altera" on public.perfis
  for all to authenticated
  using (public.eh_admin())
  with check (public.eh_admin());

-- 2) Cria os logins com a mesma senha de hoje
do $$
declare
  u   record;
  uid uuid;
begin
  for u in
    select nome, lower(trim(email)) as email, senha, role
    from public.usuarios
    where coalesce(trim(email), '') <> '' and coalesce(senha, '') <> ''
  loop
    select id into uid from auth.users where lower(email) = u.email;

    if uid is null then
      uid := gen_random_uuid();

      insert into auth.users (
        instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
        raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
        confirmation_token, recovery_token, email_change_token_new, email_change
      ) values (
        '00000000-0000-0000-0000-000000000000', uid, 'authenticated', 'authenticated',
        u.email, extensions.crypt(u.senha, extensions.gen_salt('bf')), now(),
        '{"provider":"email","providers":["email"]}', jsonb_build_object('nome', u.nome),
        now(), now(), '', '', '', ''
      );

      insert into auth.identities (
        id, user_id, provider_id, identity_data, provider, last_sign_in_at, created_at, updated_at
      ) values (
        gen_random_uuid(), uid, uid::text,
        jsonb_build_object('sub', uid::text, 'email', u.email, 'email_verified', true),
        'email', now(), now(), now()
      );
    end if;

    insert into public.perfis (id, nome, email, funcoes)
    values (
      uid, u.nome, u.email,
      array_remove(string_to_array(replace(coalesce(u.role, ''), ' ', ''), ','), '')
    )
    on conflict (id) do nothing;
  end loop;
end $$;

-- 3) Conferência: lista quem ficou com login (não mostra senhas)
select p.nome, p.email, array_to_string(p.funcoes, ', ') as funcoes,
       (u.encrypted_password like '$2%') as senha_criptografada
from public.perfis p
join auth.users u on u.id = p.id
order by p.nome;
