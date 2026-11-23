-- ═════════════════════════════════════════════════════════════════════════
-- 19) Anotação NÃO conta como ligação (pode rodar duas vezes)
--
-- Antes: salvar uma anotação num cliente "Não atendeu" chamava marcar_ligacao de novo e somava
-- uma tentativa (e um "Não atendeu" no histórico, que entrava no Dashboard).
-- Agora:
--   · anotar_ligacao() grava só a anotação (histórico com status 'anotacao', sem tentativa);
--   · corrige o que já foi gravado: "Não atendeu" repetido em seguida pela mesma pessoa e com a
--     anotação diferente vira 'anotacao'; e a coluna tentativas é recontada pelo histórico.
--   · Cópia do que foi mudado em ligacoes_historico_ajuste_19 (só admin pelo SQL Editor).
-- ═════════════════════════════════════════════════════════════════════════

-- 1) Gravar só a anotação
create or replace function public.anotar_ligacao(p_id bigint, p_obs text)
returns void
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja text;
  v_resp uuid;
  v_nome text;
  v_obs  text := nullif(trim(coalesce(p_obs, '')), '');
begin
  select loja, responsavel_id into v_loja, v_resp from public.ligacoes where id = p_id;
  if v_loja is null then
    raise exception 'Ligação não encontrada';
  end if;
  if not (public.gerencia_loja(v_loja) or coalesce(v_resp = auth.uid(), false)) then
    raise exception 'Este cliente não está com você';
  end if;
  select coalesce(nullif(trim(apelido), ''), nullif(trim(nome), ''), email) into v_nome
    from public.perfis where id = auth.uid() and ativo;
  if v_nome is null then
    raise exception 'Usuário sem perfil ativo';
  end if;
  if v_obs is null then
    return;
  end if;
  update public.ligacoes set obs = left(v_obs, 300) where id = p_id;
  insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
  values (p_id, v_nome, 'anotacao', left(v_obs, 300));
end;
$$;
revoke execute on function public.anotar_ligacao(bigint, text) from public, anon;
grant  execute on function public.anotar_ligacao(bigint, text) to authenticated;

-- 2) Cópia de segurança do que o passo 3 muda
create table if not exists public.ligacoes_historico_ajuste_19 (
  historico_id bigint primary key,
  ligacao_id   bigint,
  quem         text,
  quando       timestamptz,
  status_antes text,
  obs          text,
  ajustado_em  timestamptz default now()
);
alter table public.ligacoes_historico_ajuste_19 enable row level security;   -- sem regra: só o SQL Editor lê

-- 3) "Não atendeu" repetido logo em seguida, pela mesma pessoa, com anotação diferente = foi só anotação
with h as (
  select id, ligacao_id, quem, quando, status, obs,
         lag(status) over w as st_ant, lag(quem) over w as quem_ant, lag(obs) over w as obs_ant
    from public.ligacoes_historico
  window w as (partition by ligacao_id order by quando, id)
), alvo as (
  select * from h
   where status = 'nao_atende' and st_ant = 'nao_atende' and quem = quem_ant
     and obs is not null and obs is distinct from obs_ant
), copia as (
  insert into public.ligacoes_historico_ajuste_19 (historico_id, ligacao_id, quem, quando, status_antes, obs)
  select id, ligacao_id, quem, quando, status, obs from alvo
  on conflict (historico_id) do nothing
  returning historico_id
)
update public.ligacoes_historico g set status = 'anotacao'
  from copia c where g.id = c.historico_id;

-- 4) Tentativas = quantos "Não atendeu" de verdade no histórico
update public.ligacoes l
   set tentativas = coalesce(x.n, 0)
  from (select l2.id, (select count(*) from public.ligacoes_historico g
                        where g.ligacao_id = l2.id and g.status = 'nao_atende') as n
          from public.ligacoes l2) x
 where x.id = l.id and l.tentativas is distinct from coalesce(x.n, 0);

notify pgrst, 'reload schema';

-- Conferência: quantos registros viraram anotação e quem mais tinha "tentativas" a mais
select count(*) as registros_corrigidos from public.ligacoes_historico_ajuste_19;
select quem, count(*) as anotacoes_que_contavam_como_ligacao
  from public.ligacoes_historico_ajuste_19 group by quem order by 2 desc;
