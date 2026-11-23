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
- **Sem travessão (—) em nenhum texto da tela** (decisão do TI): usar vírgula, dois-pontos
  ou "·". Campo vazio fica em branco (sem "—"). Registros antigos de concorrência gravados
  com "—" (cba, loja, pgto) aparecem em branco no App e na Consulta.
- **Logo oficial**: raposa vermelha de traços (`public/logo-fox.png`, `public/favicon.png`).
  A Fernanda usa a mesma raposa em preto, de propósito.
- **Fernanda**: assistente sem IA externa (palavras-chave), não envia dados para fora.
  `public/fernanda.js` (busca no FOXNET) + `public/fernanda-ajuda.js` (ajuda de cada tela,
  carregado pelo fernanda.js; `feAnswer` chama `window.feAjuda` antes de `feAnswerBase`):
  · **Cadastrar desconto** (`cadastrardescontos.html` e aba Cadastrar do App — campos com
    `data-fe="..."`): entende os dados escritos no chat, lê o **PDF** do orçamento do Movere
    (pdf.js, por posição: valor embaixo do rótulo) ou **imagem** (Tesseract no navegador),
    preenche, pergunta o que falta, põe concorrência e anexo (App) e salva ao ouvir "salvar".
    Vendedor "Fernanda" no orçamento não é preenchido (pede o vendedor responsável).
    **CBA = coluna "Cód."** da tabela de produtos do orçamento; com vários produtos vale o **1º** (decisão do TI).
  · **Painel do televendas**: "sou a Kessya" fica guardado no navegador (`fe_tv_quem`) e ela
    responde só os números dessa pessoa (`window.FE_TV`, exposto no `render()` do mês).
    Não é segurança de verdade (qualquer um pode dizer que é a Kessya) — o painel já é aberto.
  · Contas: porcentagem, desconto, parcelas e contas simples. Botão 📎 no chat.
  · **Plano para a meta** (televendas): "o que preciso fazer para bater a meta?" → previsão no ritmo atual,
    quanto por dia (e % acima da média), vendas pelo ticket médio, chance (aproximação normal), dias que
    bateram o necessário, tendência, melhor dia da semana e até 3 dicas. Só com as vendas da própria pessoa.
  · **Erros de digitação**: Fuse.js 7.1.0 (Apache 2.0) copiado em `public/vendor/` (sem CDN, sem rede).
    Corrige só palavras desconhecidas por uma conhecida com a mesma 1ª letra (`FE_COMUNS` = palavras que
    nunca corrige) e avisa "Acho que você quis dizer…". O ECC (affaan-m/ECC) foi avaliado e **não** usado.
  · **Ligações das lojas** (`public/fernanda-ligacoes.js`, carregado pelo fernanda-ajuda.js só em
    `/ligacoes.html`; lê `window.FE_LIG`, a "ponte" no fim do ligacoes.html, evento `fe-lig`):
    chama a pessoa pelo primeiro nome; **um aviso por período** (manhã: clientes de ontem, agendados de
    hoje com quem agendou: "foi você", outra pessoa ou "o televendas pelo Kommo", atrasados; tarde:
    quanto falta, WhatsApp para quem não atendeu; noite: resumo do dia), guardado por pessoa+dia+período
    no navegador (`fe_lig_aviso_...`) e repetido na virada do período se a página ficar aberta.
    Chat: agendados de hoje/amanhã/atrasados/sem data, por onde começo (maior valor), quantos faltam,
    quem não atende, meu resumo, dicas de abordagem (nunca prometer pneu separado), como fazer.
    Botões "Ver na lista" (destaca a linha), Ligar e WhatsApp (os mesmos links da tela).
  · **Avisos no computador e no celular** (notificação push do navegador, grátis; SQL `17_avisos_push.sql`,
    robô `avisos_ligacoes.py`, workflow `avisos-ligacoes.yml`): **seg–sáb 8h, 10h, 14h e 16h30** (decisão do TI:
    2x de manhã, 2x à tarde). Cada pessoa liga no 🔔 do topo das Ligações ou pela Fernanda ("Sim, quero
    receber avisos"); a Fernanda oferece uma vez por aparelho. Vendedor: os números dele; gerente: a loja e
    quem tem mais sem contato; gerente de todas/admin: a rede. **Só números** (nada de cliente). Férias e
    desativado não recebem; sem nada a dizer não manda. Criptografia RFC 8291 + VAPID feita no próprio
    robô com `cryptography` (teste contra o exemplo oficial da RFC). A chave VAPID é criada pelo robô na
    1ª rodada e fica em `push_config` (sem regra de acesso: só a chave de serviço lê). iPhone: precisa
    "Adicionar à Tela de Início" (`ligacoes.webmanifest`, ícones `icone-192/512.png`). Service worker:
    `public/sw-avisos.js`. No /admin, coluna "🔔 Avisos". Tocar no aviso abre as Ligações (passa pela trava de IP).
    **Trava** (decisão do TI): o **vendedor** no computador ou no Android só usa as Ligações com os avisos
    ligados (tela por cima com "🔔 Ligar avisos"; se bloqueou no navegador, mostra o passo a passo).
    Não trava: **iPhone** (não cobrar), navegador sem avisos, gerente/Jonathan/admin, e enquanto o
    sistema de avisos não estiver pronto (sem SQL 17 ou sem a chave). `conferirTrava()` no ligacoes.html.
  · **Nome de quem está logado** em todas as telas (`feNomeLogado()`: perfil das Ligações ou a sessão
    `foxnet-auth` do navegador): "Oi, Felipe! Aqui é a Fernanda…".
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
- **Concorrentes** (`todasEmpresas` no App): a lista junta as padrão + as adicionadas no navegador +
  **todas as empresas já gravadas nos descontos do banco** (antes a empresa nova ficava só no navegador
  de quem criou e "sumia" nos outros). Sem repetir maiúscula/acento; a busca ignora acento.
- O App busca os descontos **em partes de 1000** (`supa.from().select()` em `src/App.jsx`; o banco entrega
  no máximo 1000 por vez; em 23/11/2026 eram 736). Fotos da galeria numa ida só (`buscarFotos`, 40 por ida).

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

## Ligações das lojas — branch `ligacoes-lojas` + `ligacoes-vendedores`

- **Quem liga são os VENDEDORES DAS LOJAS** (não o televendas). Página `/ligacoes.html`
  (bloco "Ligações das lojas" do FOXNET).
- **Funções** (`perfis.papel_ligacoes`, SQL `15_ligacoes_vendedores.sql`), decisão do TI:
  · **Vendedor da loja**: vê SÓ os clientes dele (`ligacoes.responsavel_id`); só liga e preenche
    status, O.S., data do agendamento, motivo da perda e anotação. Sem Dashboard, sem histórico.
  · **Gerente da loja** (ex.: Wagner, MATRIZ): vê todos da loja, Dashboard e histórico; troca o
    responsável (`trocar_responsavel`, fica no histórico); põe vendedor de **férias** / volta
    (`vendedor_ferias`: os clientes em aberto dele vão para os outros; não recebe novos).
  · **Gerente de todas as lojas** (Jonathan, sem loja): vê tudo, só acompanha.
  · **Admin**: tudo; botão **👥 Usuários** (abre `/admin`) e aviso do robô no topo.
- **Férias com data de volta** (SQL `16_ferias_data_volta.sql`, `perfis.ferias_ate`): ao clicar em
  "Colocar de férias" o gerente escolhe o dia da volta (ou "Ainda não sei"). Na hora os clientes em
  aberto passam para os outros vendedores ativos e ele não recebe novos; no dia da volta
  `voltar_das_ferias()` (chamada pela divisão, o robô das 7h) o reativa sozinho. "Voltou: ativar" ativa antes.
- **Robô nunca dá ponto ao vendedor**: o que o robô muda (venda achada no Movere, agendado no Kommo)
  aparece como "🤖 Sistema (Movere)" / "🤖 Sistema (Kommo)", é atualizado na própria linha (não exclui),
  e no Dashboard fica na coluna "🤖 Venda pelo sistema" (fora das "Vendas ganhas" do vendedor).
  **Dashboard só conta trabalho de pessoas com o cliente** (`ehSistema` no ligacoes.html): ficam fora
  do "Trabalhados", "Sem contato", tentativas e ranking os registros dos robôs (Movere/Analytics, Kommo),
  a "Divisão automática", a troca de responsável e as férias (decisão do TI). Não é preciso apagar dados.
- **Dias da cotação em ordem crescente** (19/11, 20/11, 21/11, "Os N dias"), decisão do TI.
- **Divisão automática** (`distribuir_ligacoes`): clientes sem responsável são divididos por igual
  entre os vendedores ativos (não férias) da loja, maiores valores primeiro; a sobra roda
  (`ligacoes_rodizio`: 29/3 → 10,10,9 e quem ficou com 9 recebe o extra da próxima vez).
  O robô chama depois de importar. Loja sem vendedor ativo: fica sem responsável (gerente vê).
- Colunas **Cotou** (primeiro nome de quem cotou no televendas; nomes iguais ganham a inicial:
  "Sabrina R", "Sabrina D") e **Responsável** (`perfis.apelido`, primeiro nome; só gerente/admin muda).
- **Primeiro acesso**: login = e-mail, senha inicial = o próprio e-mail (minúsculas);
  `perfis.trocar_senha` obriga a criar senha nova (≥ 8, diferente do e-mail) → `senha_trocada()`.
- Lista por **dia da cotação** (abre no mais recente com pendentes), abas Pendentes / Já liguei /
  Agendou / Venda ganha (loja) / Venda televendas / Todas, busca, filtro por quem cotou e por
  responsável, botões Ligar e WhatsApp (iguais aos de antes, com a mensagem pronta; não mudar, decisão do TI), histórico.
  Status pela função `marcar_ligacao` (registra quem e quando; vendedor só nos clientes dele).
  **"Venda ganha" só salva com o status E o nº da O.S.** (os dois; decisão do TI).
  `ligacoes.tentativas` conta os "Não atendeu" (o vendedor não lê o histórico).
- **"Venda ganha televendas"** (só o robô): o cliente comprou e a loja NÃO marcou "Venda ganha"
  (mesmo que tenha ligado) — decisão do TI.
- **Agendou** exige a **data do agendamento** (`ligacoes.agendado_para`); o agendado do Kommo
  (robô) fica sem data. Na aba Agendou a lista é pela data do agendamento (Atrasados / Hoje /
  Amanhã / Próximos 7 dias / Sem data / Todos + calendário), não pelo dia da cotação.
  **Venda perdida** exige **motivo** (`motivo_perda`, lista fixa + "Outro motivo" com obs).
  Perdida que depois compra → "Venda ganha televendas". SQL: `13_ligacoes_agenda_perda.sql`.
- **Formato planilha** (computador ≥ 900 px): tabela com as colunas da planilha do TI. Salva sozinho
  ao mudar a célula, com "↶ Desfazer" por 8 s. **Regras automáticas**: data → Agendou; motivo →
  Venda perdida; "Outro motivo" exige a Anotação; O.S. sozinha fica anotada até escolher "Venda ganha".
  Tentativas "Não atendeu (2x)"; da 2ª em diante o WhatsApp fica em destaque.
  Pendentes ordenados pelo maior valor + total em aberto. Celular (< 900 px): cartões.
  **WhatsApp**: primeiro nome do vendedor + medida do pneu + "ontem/hoje/no dia" + convite para vir à loja.
  **Nunca prometer pneu separado nem horário reservado** (o estoque pode acabar; decisão do TI). Mensagens curtas.
- **Data do agendamento pelo Kommo**: o robô lê o campo **"Data da visita"** do lead e grava em
  `agendado_para` quando a lista está sem data ou com data mais antiga.
  **Medida do pneu** (`ligacoes.medida`, SQL `14_ligacoes_medida.sql`).
- **Nome do cliente** aparece sem o telefone que às vezes vem junto do Movere (`nomeCli`: tira
  sequências com 8+ dígitos; só na tela, o dado no banco não muda).
- **Histórico** na tela: só **admin** e **gerente da loja** (o gerente de todas as lojas não vê a
  coluna; o histórico só alimenta o Dashboard dele). Decisão do TI.
- **Paleta de cores** (🎨 ▾ no topo das Ligações): Claro / Escuro / Dispositivo + 15 cores + conta-gotas
  (cor própria). Guardada no navegador (`localStorage "lig_tema"`), sem login. Padrão = escuro com o
  vermelho Fox (igual a antes). As cores da página são variáveis CSS (`--bg`, `--s1`, `--ac`, `--th`...).
- **Na lista só ficam os 5 dias de cotação mais recentes** (`DIAS_NA_LISTA`), menos os **agendados**.
  O **Dashboard usa tudo** (decisão do TI) e tem a "Divisão por vendedor". Períodos: **1 dia** (a lista que
  entrou hoje = último dia de cotação), 7, 15, 30 dias e Este mês; botão "↻ Atualizar" com a hora da última busca.
- **`/admin`** (`public/admin.html`, só admin): cadastrar pessoa com função (vendedor / gerente da
  loja / gerente de todas), primeiro nome e loja; lote "Nome; e-mail; LOJA; função" com botão que
  preenche a equipe da Matriz + Jonathan; tabela para mudar função, primeiro nome, loja, férias e
  ativo (vendedor que sai da divisão passa os clientes para os outros); "Dividir clientes agora".
  Esquecer a senha: o admin manda o e-mail de recuperação pelo Supabase (Authentication → Users).
- Lojas = nomes do Estabelecimento no Movere: MATRIZ, C.AUTO PVH, ARIQUEMES, JI-PARANA,
  CACOAL, C.AUTO VLH, PARINTINS, XAPURI (= Rio Branco, Acre; Vilhena = C.AUTO VLH).
  As equipes de todas as lojas (vendedores e gerentes, 22/11/2026) estão em `EQUIPES` no `admin.html`
  (botão "Preencher com as equipes de todas as lojas").
- Robô `ligacoes_lojas.py` (workflow `ligacoes-lojas.yml`): **todo dia, inclusive sábado e domingo,
  7h, 10h, 15h e 18h** de Porto Velho (decisão do TI). Importa os dias ainda não importados
  (cotações de ontem: sábado → lista de domingo etc.; relatório 782403 com os filtros do dashboard
  782276), tira quem comprou no dia da cotação ou depois (vendas 742591), quem está nas 2 colunas
  de agendados do Kommo (etapas 6 e 7, com ou sem data) e telefone repetido; divide entre os
  vendedores; o dia D só entra **a partir das 6h de D+1** e só se tiver cotações (a data existe no
  calendário do Analytics mesmo sem dados; em 21/11 à 1h30 o 20/11 entrou com só 3 clientes);
  **confere de novo os últimos 5 dias** (`dias_para_revisar`, `DIAS_REVISAR`: cotações que chegaram
  atrasadas no Analytics ou dias que ficaram de fora entram depois, sem repetir); reconfere os últimos 30 dias (comprou → "venda_televendas"; pendente que aparece no
  Kommo → "agendou", a data vem depois).
  **Aviso de erro**: se na rodada das 18h algum dia ainda não chegou, a rodada termina com ERRO →
  o GitHub manda e-mail ao dono do repositório (só em erro) e o admin vê o aviso vermelho no topo
  das Ligações (`robo_execucoes`). Começa nas cotações de 17/11/2026 (`INICIO`; os 5 dias antes de 22/11, decisão do TI).
  Segredos: `ANALYTICS_LOGIN`, `ANALYTICS_SENHA`, `SUPABASE_SERVICE_KEY`, `KOMMO_TOKEN`.
- **As planilhas do Google (Apps Script) continuam funcionando** — decisão do TI.
- SQL: `12_ligacoes.sql` (tabelas, `minha_loja()`, `ve_todas_ligacoes()`, `marcar_ligacao()`,
  `senha_trocada()`), 13, 14 e **`15_ligacoes_vendedores.sql`** (funções, responsável, férias, divisão).
- Testes: `python tests/test_ligacoes_lojas.py` e `python tests/test_avisos_ligacoes.py`.
- `sb_get` busca em partes de 1000 (o banco entrega no máximo 1000 linhas por vez).

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
5. **Ligações das lojas** no FOXNET — feito (ver seção acima). Depois de um tempo em paralelo,
   o TI decide se desliga as planilhas.
6. Opcional: e-mail da empresa (SMTP) no Supabase para "esqueci minha senha".

## Pendências de informação do TI

- Significado das cores amarelo/vermelho nas cidades; gerente de cada loja; CNPJ,
  endereço e telefone da loja de Guajará-Mirim; frases do dia além das 64.
