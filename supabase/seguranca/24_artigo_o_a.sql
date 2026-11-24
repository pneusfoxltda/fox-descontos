-- ═════════════════════════════════════════════════════════════════════════
-- 24) "Aqui é O Gilcimar" / "Aqui é A Fernanda" na mensagem do WhatsApp (pode rodar duas vezes)
--     O admin escolhe no /admin, para cada pessoa (coluna "Aqui é"). Sem escolha, a mensagem
--     fica sem o artigo ("Aqui é Gilcimar"), como antes. O sistema não adivinha pelo nome.
-- ═════════════════════════════════════════════════════════════════════════
alter table public.perfis add column if not exists artigo text;
alter table public.perfis drop constraint if exists perfis_artigo_valido;
alter table public.perfis add constraint perfis_artigo_valido check (artigo is null or artigo in ('o', 'a'));

notify pgrst, 'reload schema';

-- Conferência: deve mostrar 1 linha com "artigo"
select column_name from information_schema.columns
 where table_schema = 'public' and table_name = 'perfis' and column_name = 'artigo';
