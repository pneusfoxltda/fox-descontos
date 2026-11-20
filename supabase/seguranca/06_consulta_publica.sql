-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Segurança · Passo 6: função da Consulta pública das lojas
--
-- Cria a função "consulta_publica": a página /consulta.html passa a buscar
-- por ela, sem ler a tabela de descontos direto. Ela devolve só as colunas
-- que a tela mostra, e no máximo 200 resultados.
--
-- Não muda nenhuma regra nem dado: o site atual continua funcionando igual.
-- Rodar ANTES de publicar o site novo. Pode rodar mais de uma vez.
-- ════════════════════════════════════════════════════════════════════════

create or replace function public.consulta_publica(p_modo text, p_termo text, p_loja text default null)
returns jsonb
language sql stable security definer
set search_path = public
as $$
  select coalesce(jsonb_agg(to_jsonb(x) order by x.criado_em desc), '[]'::jsonb)
  from (
    select d.numero, d.tipo, d.cba, d.medida, d.loja, d.valor, d.pgto, d.validade,
           d.obs, d.liberado, d.vendedor, d.criado_em, d.telefone_cliente
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

-- Conferência: deve aparecer 1 linha com "consulta_publica"
select proname as funcao from pg_proc where proname = 'consulta_publica';
