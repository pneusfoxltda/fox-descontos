-- ═════════════════════════════════════════════════════════════════════════
-- 25) O que as pessoas escrevem para a Fernanda (para o 🩺 Monitor) (pode rodar duas vezes)
--     · Guarda o TEXTO que a pessoa digitou no chat da Fernanda (até 300 letras), quem (nome e loja,
--       se estiver logada), a tela e se a Fernanda achou resposta.
--     · Telefones, CPF e qualquer número grande são escondidos (••••) ANTES de gravar.
--     · Arquivos (PDF e imagem do orçamento) NÃO são enviados: ficam só no computador da pessoa.
--     · Só o admin lê (pelo Monitor). Ficam 90 dias.
-- ═════════════════════════════════════════════════════════════════════════
create table if not exists public.fernanda_conversas (
  id        bigserial primary key,
  quando    timestamptz not null default now(),
  perfil_id uuid references public.perfis(id) on delete set null,
  nome      text,
  loja      text,
  tela      text,
  texto     text not null,
  achou     boolean
);
create index if not exists fernanda_conversas_quando on public.fernanda_conversas (quando);
alter table public.fernanda_conversas enable row level security;   -- sem regra: ninguém lê direto
revoke all on public.fernanda_conversas from anon, authenticated;

-- Gravar (todas as telas; quem não está logado entra como "sem login")
create or replace function public.fernanda_registrar(p_texto text, p_tela text default null, p_achou boolean default null)
returns void
language plpgsql security definer
set search_path = public
as $$
declare
  v_txt  text := left(regexp_replace(trim(coalesce(p_texto, '')), '\d[\d\s().-]{6,}\d', '••••', 'g'), 300);
  v_nome text; v_loja text;
begin
  if length(v_txt) < 1 then return; end if;
  -- trava contra exagero: no máximo 120 mensagens por pessoa (ou por "sem login") por hora
  if (select count(*) from public.fernanda_conversas
       where quando > now() - interval '1 hour'
         and perfil_id is not distinct from auth.uid()) >= 120 then
    return;
  end if;
  select coalesce(nullif(trim(apelido), ''), nullif(trim(nome), ''), email), loja into v_nome, v_loja
    from public.perfis where id = auth.uid();
  insert into public.fernanda_conversas (perfil_id, nome, loja, tela, texto, achou)
  values (auth.uid(), v_nome, v_loja, left(coalesce(p_tela, ''), 60), v_txt, p_achou);
  if random() < 0.02 then
    delete from public.fernanda_conversas where quando < now() - interval '90 days';
  end if;
end;
$$;
revoke execute on function public.fernanda_registrar(text, text, boolean) from public;
grant  execute on function public.fernanda_registrar(text, text, boolean) to anon, authenticated;

-- Ler (só o admin, pelo Monitor)
create or replace function public.monitor_fernanda(p_dias int default 1)
returns jsonb
language plpgsql stable security definer
set search_path = public
as $$
declare
  v_desde timestamptz := ((now() at time zone 'America/Porto_Velho')::date - greatest(coalesce(p_dias, 1), 1) + 1)::timestamp at time zone 'America/Porto_Velho';
begin
  if not public.eh_admin() then raise exception 'Só o administrador'; end if;
  return jsonb_build_object(
    'total', (select count(*) from public.fernanda_conversas where quando >= v_desde),
    'pessoas', (select count(distinct coalesce(perfil_id::text, 'anon')) from public.fernanda_conversas where quando >= v_desde),
    'nao_achou', (select count(*) from public.fernanda_conversas where quando >= v_desde and achou = false),
    'por_pessoa', coalesce((select jsonb_agg(x order by x.n desc) from (
        select coalesce(nome, 'Sem login (FOXNET)') as nome, loja, count(*) as n, max(quando) as ultima
          from public.fernanda_conversas where quando >= v_desde group by 1, 2 order by n desc limit 30) x), '[]'::jsonb),
    'por_loja', coalesce((select jsonb_agg(x order by x.n desc) from (
        select coalesce(loja, '(sem loja)') as loja, count(*) as n
          from public.fernanda_conversas where quando >= v_desde group by 1) x), '[]'::jsonb),
    'mais_perguntado', coalesce((select jsonb_agg(x order by x.n desc) from (
        select lower(texto) as texto, count(*) as n, count(distinct coalesce(perfil_id::text, 'anon')) as pessoas
          from public.fernanda_conversas where quando >= v_desde group by lower(texto) order by count(*) desc limit 15) x), '[]'::jsonb),
    'sem_resposta', coalesce((select jsonb_agg(x order by x.n desc) from (
        select lower(texto) as texto, count(*) as n
          from public.fernanda_conversas where quando >= v_desde and achou = false group by lower(texto) order by count(*) desc limit 15) x), '[]'::jsonb),
    'ultimas', coalesce((select jsonb_agg(x order by x.quando desc) from (
        select quando, coalesce(nome, 'Sem login (FOXNET)') as nome, loja, tela, texto, achou
          from public.fernanda_conversas where quando >= v_desde order by quando desc limit 150) x), '[]'::jsonb)
  );
end;
$$;
revoke execute on function public.monitor_fernanda(int) from public, anon;
grant  execute on function public.monitor_fernanda(int) to authenticated;

notify pgrst, 'reload schema';

-- Conferência: deve mostrar as 2 funções
select p.oid::regprocedure as funcao_criada from pg_proc p join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public' and p.proname in ('fernanda_registrar', 'monitor_fernanda') order by 1;
