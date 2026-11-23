-- ═════════════════════════════════════════════════════════════════════════
-- 21) Ligações: corrigir o NOME do cliente pela tela (pode rodar duas vezes)
--     Quem pode: o vendedor responsável pelo cliente, o gerente da loja e o admin
--     (as mesmas regras do status). Fica no histórico ("Nome corrigido"), que NÃO conta como
--     ligação nem como trabalho no Dashboard. O robô não apaga a correção (ele só insere clientes novos).
-- ═════════════════════════════════════════════════════════════════════════
create or replace function public.renomear_cliente(p_id bigint, p_nome text)
returns void
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja  text;
  v_resp  uuid;
  v_antes text;
  v_quem  text;
  v_nome  text := left(regexp_replace(trim(coalesce(p_nome, '')), '\s+', ' ', 'g'), 120);
begin
  if length(v_nome) < 2 then
    raise exception 'Escreva o nome do cliente';
  end if;
  select loja, responsavel_id, cliente into v_loja, v_resp, v_antes from public.ligacoes where id = p_id;
  if v_loja is null then
    raise exception 'Ligação não encontrada';
  end if;
  if not (public.gerencia_loja(v_loja) or coalesce(v_resp = auth.uid(), false)) then
    raise exception 'Este cliente não está com você';
  end if;
  select coalesce(nullif(trim(apelido), ''), nullif(trim(nome), ''), email) into v_quem
    from public.perfis where id = auth.uid() and ativo;
  if v_quem is null then
    raise exception 'Usuário sem perfil ativo';
  end if;
  if v_nome is not distinct from v_antes then
    return;
  end if;
  update public.ligacoes set cliente = v_nome where id = p_id;
  insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
  values (p_id, v_quem, 'nome_cliente', left('Nome: ' || coalesce(v_antes, '(sem nome)') || ' → ' || v_nome, 300));
end;
$$;
revoke execute on function public.renomear_cliente(bigint, text) from public, anon;
grant  execute on function public.renomear_cliente(bigint, text) to authenticated;

notify pgrst, 'reload schema';

-- Conferência: deve mostrar 1 linha
select p.oid::regprocedure as funcao_criada
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public' and p.proname = 'renomear_cliente';
