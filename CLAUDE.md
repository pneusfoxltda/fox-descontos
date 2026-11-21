# FOXNET · Sistema Integrado Rede Fox Pneus

Memória do projeto. Quem abrir este repositório no Claude Code começa por aqui.
Converse sempre em **português do Brasil**, com linguagem simples e passo a passo:
o responsável é o TI da Fox Pneus, não programador. Ele manda prints; peça print
quando precisar ver uma tela.

⚠️ **O repositório é PÚBLICO.** Nunca grave aqui senhas, chaves (service_role,
tokens), dados bancários nem a lista de IPs das lojas.

---

## O que existe

| Sistema | Endereço | Arquivo |
|---|---|---|
| **FOXNET** (intranet) | https://foxnet-intranet.vercel.app/ (também `/foxnet/` em qualquer domínio) | `public/foxnet/index.html`, `public/foxnet/frases.js` |
| App de descontos | https://fox-descontos.vercel.app/ e `/descontos` | `src/App.jsx` (React + Vite), `src/supabase.js` |
| Cadastrar desconto | `/cadastrardescontos.html` | `public/cadastrardescontos.html` |
| Consulta (pública p/ lojas) | `/consulta.html` | `public/consulta.html` |
| Painel do televendas | `/televendas.html` | `public/televendas.html` (dados de `televendas-dados.json` e Supabase) |
| Fernanda (assistente) | aparece em todas as páginas | `public/fernanda.js` |
| Trava por IP + domínios | todas as requisições | `middleware.js` (Vercel Routing Middleware) |

Hospedagem: **Vercel** (projeto `fox-descontos`, plano Hobby, publica a branch `main`).
Banco e login: **Supabase** (projeto `dxwkiaxpygibzmwzvcuz`).
Robôs: GitHub Actions `sync-televendas.yml` (Movere → Supabase, de hora em hora) e
Google Apps Scripts fora do repositório (planilhas de ligações das lojas; e-mail de
vendas para o televendas; `apps-script/` tem o do painel).

## Como trabalhamos

- Toda mudança: **branch → teste → pull request → merge** (o merge publica no Vercel).
  O TI aprova; quando ele disser "pode publicar", o merge pode ser feito pela API.
- Link de teste da branch: `fox-descontos-git-<branch>-gilcimarfreitass21-5566s-projects.vercel.app`
  (o Vercel encurta nomes longos; o link certo aparece no comentário do Vercel no PR).
  Links de teste pedem login do Vercel e também passam pela trava de IP.
- Esta sessão não acessa Supabase nem Vercel. Testes são feitos imitando as respostas
  do Supabase no navegador (Playwright) e com um Postgres local para os SQL.
- SQL novo vai em `supabase/seguranca/NN_nome.sql`, sempre **idempotente** (pode rodar
  duas vezes) e testado antes; o TI cola no SQL Editor do Supabase e manda print.
- O painel do Supabase às vezes não salva no navegador normal do TI (extensão):
  usar **janela anônima**.

## Decisões já tomadas (não refazer)

- **FOXNET** (`public/foxnet/`): página no estilo Canva — frase do dia (64 frases em
  `frases.js`, troca à meia-noite de Porto Velho, igual para todos), blocos de
  "Explorar sistemas" com filtros, **favoritos sem login** salvos no navegador
  (a barra lateral só aparece com os favoritos), busca que filtra ou pergunta à Fernanda.
  **Sem botão "Entrar"** na intranet. Fundo com vídeo de pneus foi testado e **rejeitado**.
- **Domínio da intranet**: qualquer host que comece com `foxnet` mostra só o FOXNET;
  outros caminhos redirecionam para `https://fox-descontos.vercel.app`.
  `foxnet.vercel.app` é de outra empresa; `foxnet.foxpneu.com.br` foi desistido.
- **Trava por IP**: só abre nas internets das lojas e da casa do TI. Lista na variável
  `FOXNET_IPS_LIBERADOS` (Vercel → Settings → Environments → Production). Lista vazia =
  nada bloqueado. `/meu-ip` sempre mostra o IP público. Após mudar a lista, é preciso
  publicar de novo (um commit vazio em `main` serve).
- **Logo oficial**: raposa vermelha de traços (`public/logo-fox.png`, `public/favicon.png`).
  A Fernanda usa a mesma raposa em preto, de propósito.
- **Fernanda**: assistente sem IA externa (palavras-chave), não envia dados para fora.
- **Informações rápidas** (no FOXNET): lojas, CNPJ, cidades → loja mais próxima, veículos
  com 2 alinhamentos. **Dados bancários/Pix ficam fora** (repositório público).

## Login e níveis (Supabase Auth) — publicado

- Login por e-mail e senha no Supabase Auth; sessão única (`storageKey: "foxnet-auth"`)
  para App, Cadastrar e Televendas. A senha fixa antiga do admin foi removida do código.
- Tabela `perfis` (id = auth.users.id): `nome, email, funcoes[], loja, vendedor_bi, ativo, foto`.
  Níveis: **admin** (tudo, só o TI) · **comercial** (cadastrar, consultar, liberar) ·
  **gerente** (só relatórios/Dashboard) · **televendas** (cadastrar).
  No App, `papelLegado()` em `src/supabase.js` converte para os papéis antigos das telas.
- Cadastro de pessoas: aba Usuários do App (admin). "Confirm email" está **desligado**
  no Supabase (o e-mail gratuito do Supabase não entrega para os funcionários).
  Site URL e Redirect URLs já apontam para `https://fox-descontos.vercel.app`.
- Gatilho `criar_perfil_novo_login`: todo login novo nasce **sem nível**.

## Consultar (App de descontos)

- Abas (cada desconto em UMA só; decisão do TI): **Todos** · **Válidos** (no prazo, não
  liberado, sem venda no Movere) · **Liberados** (a equipe liberou; o robô não mexe) ·
  **Vencidas** (fora do prazo, não liberado, sem venda no Movere; inclui as `auto_perdida`) ·
  **✅ Venda concluída (Movere)** (não liberado e o robô achou a venda).
  Válidos + Liberados + Vencidas + Venda concluída = Todos. A aba "Pendentes" foi removida.
- A lista mostra 60 por vez ("Mostrar mais") e é memorizada para não travar ao digitar.

## Venda concluída (Movere) — branch `venda-movere`

- Robô `conferir_vendas_movere.py` (workflow `conferir-vendas-movere.yml`, seg–sáb 7h50,
  12h50 e 17h50 de Porto Velho): baixa o relatório de vendas do **Analytics Movere**
  (relatório 742591, mesmo login do Apps Script das planilhas) e compara os **últimos 8
  dígitos do telefone** com `descontos.telefone_cliente`. Venda no dia do cadastro ou
  depois → `venda_movere = true` (vale mesmo vencido). Só pelo telefone (decisão do TI).
  **Só descontos PENDENTES de liberação** (decisão do TI): o robô ignora os liberados e as
  telas só mostram "Venda concluída" quando `venda_movere && !liberado` (`vendeuSemLib` no App);
  se a equipe liberar depois, o desconto sai do filtro e fica só em Liberados.
- Segredos no GitHub: `ANALYTICS_LOGIN`, `ANALYTICS_SENHA`, `SUPABASE_SERVICE_KEY`.
  Rodar à mão com "teste" marcado mostra o que faria sem gravar.
- O registro do GitHub Actions é **público**: o robô nunca imprime telefone nem nome.
- `09_venda_movere.sql`: colunas novas + gatilho `proteger_venda_movere` (só o robô
  grava essas colunas) + `consulta_publica` devolve `venda_movere`. Rodar ANTES de publicar.
- Filtros do dashboard 744813 (só operadoras do televendas) ficam **desligados** para
  conferir vendas de todas as lojas (`USAR_FILTRO_DASH=1` liga).
  O TI confirmou que o relatório 742591 traz vendas de **todas as lojas**.
- Testes: `python tests/test_conferir_vendas_movere.py` (rede imitada).
- Registro das rodadas: `11_robo_execucoes.sql` (tabela `robo_execucoes`; grava só o robô,
  lê só o admin; o robô apaga as com mais de 90 dias). No App, aba Consultar, abaixo das abas,
  o admin vê a última rodada: verde (ok), vermelho (falhou + última certa), amarelo (sem rodar
  há mais de 40 h). A "Venda concluída" ainda NÃO entra no Dashboard (ideia futura).

## Número repetido — branch `cadastro-sem-duplicado`

- `10_sem_numero_repetido.sql`: guarda cópia dos repetidos em `descontos_duplicados_apagados`
  (coluna `dados` jsonb, só admin pelo SQL Editor), apaga os repetidos (fica o liberado; senão
  o 1º cadastrado) e cria o índice único `descontos_numero_tipo_unico`
  (`lower(btrim(numero))` + tipo; `conc` fica de fora). Orçamento e O.S. com o mesmo nº podem.
- `cadastrardescontos.html` confere antes de salvar e mostra quem cadastrou e quando;
  App e página tratam o erro 23505 com aviso amigável.
- ⚠️ No App, "Excluir" apaga por número + tipo (apagaria os dois repetidos).

## Próximos passos (em ordem)

1. ✅ **Trancar o banco (RLS)** — CONCLUÍDO em 21/11/2026. Passos 06, 07 e 08 rodados no
   Supabase; segredo `SUPABASE_SERVICE_KEY` no GitHub (o robô do televendas voltou a gravar
   `vendas_televendas_clientes`, que antes dava 401). Regras: ver `07_trancar_banco.sql`.
   Painel do televendas: resumo e metas continuam sem login (aguardando decisão do TI).
   **Editar metas / dias úteis** aparece para quem está logado como **admin** em qualquer link
   do painel (mesmo login do App). É o comportamento desejado (decisão do TI, 21/11/2026).
2. **Apagar as senhas legíveis** das tabelas `usuarios` e `usuarios_televendas`.
3. Remontar **liberação, consultas e relatórios** com as ideias do TI (ele vai trazer).
   Ideias já sugeridas: recusar com motivo, histórico de quem liberou, aviso ao vendedor,
   alçada do gerente, relatórios por período/loja/vendedor/concorrente.
4. **Resultados** (aba principal desejada): Resultado Rede Fox (vendido hoje / mês),
   Resultado por loja → vendedores da loja, Resultado televendas. Fazer **junto com o TI**.
   Fonte provável: o mesmo caminho do `sync_televendas.py` (Movere, de hora em hora).
   Só depois do banco trancado (dados sensíveis).
5. **Ligações das lojas** no FOXNET (hoje "em breve"): Apps Script também grava no
   Supabase; lojas marcam o status no portal.
6. Opcional: e-mail da empresa (SMTP) no Supabase para "esqueci minha senha".

## Pendências de informação do TI

- Significado das cores amarelo/vermelho nas cidades; gerente de cada loja; CNPJ,
  endereço e telefone da loja de Guajará-Mirim; frases do dia além das 64.
