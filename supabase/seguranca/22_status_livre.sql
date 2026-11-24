-- ═════════════════════════════════════════════════════════════════════════
-- 22) Ligações: o vendedor pode mudar o status à vontade (pode rodar duas vezes)
--     Ao sair de um status, o dado que era só dele sai junto:
--       · saiu de "Venda ganha"    → a O.S. é apagada
--       · saiu de "Agendou"        → a data do agendamento é apagada
--       · saiu de "Venda perdida"  → o motivo da perda é apagado
--     Também apaga O.S. que ficou presa em cliente que não está em "Venda ganha" (testes).
--     (Inclui o status "Aguardando retorno WhatsApp" do passo 20.)
-- ═════════════════════════════════════════════════════════════════════════
create or replace function public.marcar_ligacao(
  p_id bigint, p_status text, p_obs text default null, p_os text default null,
  p_data date default null, p_motivo text default null)
returns void
language plpgsql security definer
set search_path = public
as $$
declare
  v_loja text;
  v_resp uuid;
  v_nome text;
begin
  if p_status not in ('pendente', 'nao_atende', 'retornar', 'aguardando_wa', 'sem_interesse', 'agendou', 'venda_ganha', 'venda_perdida') then
    raise exception 'Status inválido: %', p_status;
  end if;
  if p_status = 'venda_ganha' and coalesce(trim(p_os), '') = '' then
    raise exception 'Informe o nº da O.S. da venda';
  end if;
  if p_status = 'agendou' and p_data is null then
    raise exception 'Informe a data do agendamento';
  end if;
  if p_status = 'venda_perdida' and coalesce(trim(p_motivo), '') = '' then
    raise exception 'Informe o motivo da venda perdida';
  end if;

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

  update public.ligacoes
     set status = p_status,
         status_em = now(),
         status_por = v_nome,
         obs = coalesce(nullif(trim(p_obs), ''), obs),
         os_venda      = case when p_status = 'venda_ganha'   then trim(p_os)     else null end,
         agendado_para = case when p_status = 'agendou'       then p_data         else null end,
         motivo_perda  = case when p_status = 'venda_perdida' then trim(p_motivo) else null end,
         tentativas = tentativas + case when p_status = 'nao_atende' then 1 else 0 end
   where id = p_id;

  insert into public.ligacoes_historico (ligacao_id, quem, status, obs)
  values (p_id, v_nome, p_status,
          nullif(trim(concat_ws(' · ',
            case when p_status = 'agendou' then 'Agendado para ' || to_char(p_data, 'DD/MM/YYYY') end,
            case when p_status = 'venda_ganha' then 'O.S. ' || trim(p_os) end,
            case when p_status = 'venda_perdida' then 'Motivo: ' || trim(p_motivo) end,
            nullif(trim(p_obs), ''))), ''));
end;
$$;
revoke execute on function public.marcar_ligacao(bigint, text, text, text, date, text) from public, anon;
grant  execute on function public.marcar_ligacao(bigint, text, text, text, date, text) to authenticated;

-- O.S. presa em cliente que não está em "Venda ganha" (só status das pessoas; os do robô ficam como estão)
update public.ligacoes set os_venda = null
 where os_venda is not null
   and status in ('pendente', 'nao_atende', 'retornar', 'aguardando_wa', 'sem_interesse', 'agendou', 'venda_perdida');

notify pgrst, 'reload schema';

-- Conferência: deve mostrar 0
select count(*) as os_presa_fora_de_venda_ganha
  from public.ligacoes
 where os_venda is not null
   and status in ('pendente', 'nao_atende', 'retornar', 'aguardando_wa', 'sem_interesse', 'agendou', 'venda_perdida');
