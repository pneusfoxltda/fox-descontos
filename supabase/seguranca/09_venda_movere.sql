-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Passo 9: "Venda concluída (Movere)" nos descontos
--
-- O robô "Conferir vendas Movere" (GitHub) compara o telefone do cliente do
-- desconto com o relatório de vendas do Analytics. Se o cliente comprou no dia
-- do cadastro ou depois, marca a venda nestas colunas novas.
--
-- Rodar ANTES de publicar o site novo (o App passa a ler estas colunas).
-- Só ACRESCENTA colunas: não muda nem apaga nada. Pode rodar mais de uma vez.
-- Quem grava é só o robô (chave secreta). As telas só leem.
-- ════════════════════════════════════════════════════════════════════════

alter table public.descontos add column if not exists venda_movere              boolean not null default false;
alter table public.descontos add column if not exists venda_movere_em           date;
alter table public.descontos add column if not exists venda_movere_valor        numeric;
alter table public.descontos add column if not exists venda_movere_por          text;   -- 'telefone'
alter table public.descontos add column if not exists venda_movere_conferido_em timestamptz;

-- Só o robô (chave secreta) grava a venda do Movere: quem entra pelo site
-- (logado ou não) não consegue marcar nem desmarcar essas colunas.
create or replace function public.proteger_venda_movere()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if current_user in ('anon', 'authenticated') then
    if tg_op = 'INSERT' then
      new.venda_movere := false;
      new.venda_movere_em := null;
      new.venda_movere_valor := null;
      new.venda_movere_por := null;
      new.venda_movere_conferido_em := null;
    else
      new.venda_movere := old.venda_movere;
      new.venda_movere_em := old.venda_movere_em;
      new.venda_movere_valor := old.venda_movere_valor;
      new.venda_movere_por := old.venda_movere_por;
      new.venda_movere_conferido_em := old.venda_movere_conferido_em;
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists proteger_venda_movere on public.descontos;
create trigger proteger_venda_movere
  before insert or update on public.descontos
  for each row execute function public.proteger_venda_movere();

-- Consulta pública: passa a devolver também se o cliente já comprou
create or replace function public.consulta_publica(p_modo text, p_termo text, p_loja text default null)
returns jsonb
language sql stable security definer
set search_path = public
as $$
  select coalesce(jsonb_agg(to_jsonb(x) order by x.criado_em desc), '[]'::jsonb)
  from (
    select d.numero, d.tipo, d.cba, d.medida, d.loja, d.valor, d.pgto, d.validade,
           d.obs, d.liberado, d.vendedor, d.criado_em, d.telefone_cliente,
           d.venda_movere, d.venda_movere_em
    from public.descontos d
    where trim(coalesce(p_termo, '')) <> ''
      and case p_modo
        when 'med' then d.medida ilike '%' || trim(p_termo) || '%'
                    and d.obs ilike '%CONCORRENTES%'
                    and d.criado_em >= current_date - 60
                    and (coalesce(p_loja, '') = '' or d.loja = p_loja)
        when 'tel' then d.telefone_cliente ilike '%' || trim(p_termo) || '%'
                    or (regexp_replace(p_termo, '\D', '', 'g') <> ''
                        and d.telefone_cliente ilike '%' || regexp_replace(p_termo, '\D', '', 'g') || '%')
        when 'num' then d.numero ilike '%' || trim(p_termo) || '%'
        else false
      end
    order by d.criado_em desc
    limit 200
  ) x;
$$;
revoke execute on function public.consulta_publica(text, text, text) from public;
grant  execute on function public.consulta_publica(text, text, text) to anon, authenticated;


-- Avisa a API do Supabase das colunas novas
notify pgrst, 'reload schema';

-- Conferência: quantos descontos existem e quantos já estão marcados como venda
select count(*) as descontos, count(*) filter (where venda_movere) as com_venda_movere
from public.descontos;
