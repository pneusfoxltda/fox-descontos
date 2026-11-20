-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Segurança · Passo 4: preparar o banco para o login novo
--
-- Rodar ANTES de publicar o login novo nas telas.
-- Não altera nem apaga nada que já existe. Pode rodar mais de uma vez.
--
--   1. perfis ganha a coluna "foto" (copiada da tabela antiga "usuarios").
--   2. Quem for cadastrado (tela Usuários do App) ganha um perfil automático,
--      SEM nível de acesso; só o admin define o nível depois.
-- ════════════════════════════════════════════════════════════════════════

-- 1) Foto de cada pessoa
alter table public.perfis add column if not exists foto text;

update public.perfis p
   set foto = u.foto
  from public.usuarios u
 where lower(trim(u.email)) = p.email
   and p.foto is null
   and u.foto is not null;

-- 2) Perfil automático para cada login novo (sem nível: ninguém se dá acesso sozinho)
create or replace function public.criar_perfil_novo_login()
returns trigger
language plpgsql security definer
set search_path = public
as $$
begin
  insert into public.perfis (id, nome, email, funcoes)
  values (
    new.id,
    coalesce(nullif(trim(new.raw_user_meta_data->>'nome'), ''), split_part(new.email, '@', 1)),
    lower(new.email),
    '{}'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists criar_perfil_novo_login on auth.users;
create trigger criar_perfil_novo_login
  after insert on auth.users
  for each row execute function public.criar_perfil_novo_login();

-- Conferência
select nome, email, array_to_string(funcoes, ', ') as nivel, ativo,
       (foto is not null) as tem_foto
from public.perfis
order by nome;
