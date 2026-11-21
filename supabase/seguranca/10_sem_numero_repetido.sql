-- ════════════════════════════════════════════════════════════════════════
-- FOXNET · Passo 10: acabar com descontos de número repetido
--
-- 1. Guarda uma CÓPIA de segurança de cada cadastro repetido que vai sair
--    (tabela descontos_duplicados_apagados; dá para desfazer).
-- 2. Apaga só os repetidos. Fica 1 por número + tipo (Orçamento ou O.S.):
--    o que já foi LIBERADO; se nenhum (ou os dois) foi, o PRIMEIRO cadastrado.
-- 3. Trava no banco: a partir daqui nenhuma tela consegue cadastrar o mesmo
--    número duas vezes no mesmo tipo (maiúsculas e espaços não contam).
--
-- O registro de concorrência (#CONC...) não entra na trava.
-- Pode rodar mais de uma vez. No fim mostra o que foi apagado.
-- ════════════════════════════════════════════════════════════════════════

-- 1) Cópia de segurança (só o admin vê, pelo SQL Editor)
create table if not exists public.descontos_duplicados_apagados (
  id          uuid,
  numero      text,
  tipo        text,
  dados       jsonb not null,           -- o cadastro inteiro, como estava
  apagado_em  timestamptz not null default now()
);
alter table public.descontos_duplicados_apagados enable row level security;
revoke all on public.descontos_duplicados_apagados from anon, authenticated;

-- 2) Copia e apaga os repetidos
with ordem as (
  select id,
         row_number() over (
           partition by lower(btrim(numero)), coalesce(tipo, 'orcamento')
           order by coalesce(liberado, false) desc, criado_em asc, id
         ) as posicao
  from public.descontos
  where coalesce(tipo, 'orcamento') <> 'conc'
),
copia as (
  insert into public.descontos_duplicados_apagados (id, numero, tipo, dados)
  select d.id, d.numero, d.tipo, to_jsonb(d)
  from public.descontos d
  join ordem o on o.id = d.id
  where o.posicao > 1
  returning id
)
delete from public.descontos d
using copia c
where d.id = c.id;

-- 3) Trava: mesmo número + mesmo tipo não entra duas vezes
create unique index if not exists descontos_numero_tipo_unico
  on public.descontos (lower(btrim(numero)), coalesce(tipo, 'orcamento'))
  where coalesce(tipo, 'orcamento') <> 'conc';

-- Conferência: o que foi apagado (e quando)
select numero, tipo,
       to_char((dados->>'criado_em')::timestamptz at time zone 'America/Porto_Velho', 'DD/MM/YYYY HH24:MI') as cadastrado,
       dados->>'negociador_nome' as quem_cadastrou,
       to_char(apagado_em at time zone 'America/Porto_Velho', 'DD/MM/YYYY HH24:MI') as apagado_em
from public.descontos_duplicados_apagados
order by apagado_em desc, numero;
