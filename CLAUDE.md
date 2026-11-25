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
**Horário dos robôs**: o horário agendado do GitHub atrasa horas ou pula (23/11: a rodada das 7h não
aconteceu). O `sync-televendas.yml` é disparado de fora, em ponto (seg–sáb, :45), e no fim acorda os
outros (job `acordar-robos`, pela hora de Porto Velho em que o Sync COMEÇOU, não a de quando terminou; em 24/11 ele passou das 7h e pulou as Ligações): 6h45 Ligações · 7h45 Avisos + Vendas Movere ·
9h45 Ligações + Avisos · 12h45 Vendas · 13h45 Avisos · 14h45 Ligações · 16h45 Avisos · 17h45 Ligações + Vendas.
Os crons de cada robô ficam como reserva (e valem no domingo). Avisos não repetem o turno no dia (`ja_enviado`).
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
  **Paleta de cores** (🎨 ▾ no topo, `public/foxnet/tema.js`), igual à das Ligações: Claro / Escuro /
  Dispositivo + 15 cores + conta-gotas. Padrão = claro com o roxo do FOXNET, idêntico a antes (conferido
  ponto a ponto). Cores da página em variáveis CSS no `:root`.
- **Paleta ÚNICA para todos os sistemas** (`public/tema-comum.js`, `window.FoxTema`; decisão do TI): quem
  nunca escolheu vê cada tela com a sua cor de sempre; escolheu em qualquer tela, vale em todas (abas
  abertas mudam na hora). Guardado em `localStorage "fox_tema"` {modo, cor, em}. O FOXNET
  (foxnet-intranet) e os sistemas (fox-descontos) são endereços diferentes: ao abrir um sistema pelo FOXNET
  a escolha vai no link (`?tema=modo.COR.hora`, a mais nova vale) e sai do endereço. "Voltar ao padrão" =
  cada tela com a sua cor. **Todas as páginas têm o 🎨**: FOXNET e Ligações (paleta própria) e App de
  descontos (🎨 no canto de cima à direita, faixa `#topo-acoes` do App), Cadastrar, Consulta, Televendas, /admin e Monitor (`public/paleta.js`, carregado depois do
  tema-comum.js com `data-padrao="modo,#cor"` e `data-antes`/`data-dentro` para o lugar do botão).
  Nessas páginas cada cor fixa virou `var(--fx-PAPEL, cor de sempre)` (fundo bg/s1/s2, borda bd, texto
  tx/tx0/tx2/tx3/tx4, destaque ac/ac2/ac3/acbg, faixa hd/hd2 do Televendas e situação okbg/oktx,
  avbg/avtx, inbg/intx, erbg/ertx): sem escolha nenhuma --fx-* existe e a página fica **idêntica** (conferido
  ponto a ponto nas 7 páginas). Padrões: Televendas claro azul-marinho (#0F1F3D); as outras escuras vermelho Fox.
  No App, RED/CARD/TEXT/MUTED/BORDER são variáveis e RED+"22"/"44" viraram RED22/RED44 (color-mix).
  Cor nova escrita no código dessas páginas: use `var(--fx-..., #cor)` para seguir a paleta.
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
  **Clicar na raposa de qualquer sistema volta para a intranet** (FOXNET), inclusive nas telas de login
  (`tema-comum.js`; em produção vai para foxnet-intranet.vercel.app levando a cor escolhida; nos links de teste, /foxnet/).
  A Fernanda usa a mesma raposa em preto, de propósito.
- **Fernanda**: assistente sem IA externa (palavras-chave). Arquivos (PDF/imagem) nunca saem do computador; o **texto
  digitado no chat** é registrado para o 🩺 Monitor (`feRegistrar` no fernanda.js → `fernanda_registrar`, SQL
  `25_fernanda_conversas.sql`: até 300 letras, números grandes/telefones viram ••••, nome e loja de quem está logado,
  tela, se achou resposta; 90 dias; só o admin lê por `monitor_fernanda(p_dias)`). Seção "🦊 Conversas com a
  Fernanda" no fim do Monitor: hoje / 7 / 30 dias, filtro por loja, quem mais conversou, o que mais perguntaram, o que
  ela não soube responder (para ensinar) e as últimas 150 mensagens.
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
    robô `avisos_ligacoes.py`, workflow `avisos-ligacoes.yml`): **seg–sáb 8h, 9h45, 13h45 e 16h45** (decisão do TI:
    2x de manhã, 2x à tarde). Cada pessoa liga no 🔔 do topo das Ligações ou pela Fernanda ("Sim, quero
    receber avisos"); a Fernanda oferece uma vez por aparelho. Vendedor: os números dele; gerente: a loja e
    quem tem mais sem contato; gerente de todas/admin: a rede. **Só números** (nada de cliente). Férias e
    desativado não recebem; sem nada a dizer não manda. Criptografia RFC 8291 + VAPID feita no próprio
    robô com `cryptography` (teste contra o exemplo oficial da RFC). A chave VAPID é criada pelo robô na
    1ª rodada e fica em `push_config` (sem regra de acesso: só a chave de serviço lê). iPhone: precisa
    "Adicionar à Tela de Início" (`ligacoes.webmanifest`, ícones `icone-192/512.png`). Service worker:
    `public/sw-avisos.js`. No /admin, coluna "🔔 Avisos". Tocar no aviso abre as Ligações (passa pela trava de IP).
    **Trava** (decisão do TI, 24/11/2026: vale para **todos**: vendedor, gerente da loja, Jonathan e admin): no
    computador ou no Android só usa as Ligações com os avisos ligados (tela por cima com "🔔 Ligar avisos", logo
    depois de criar a senha; se bloqueou no navegador, mostra o passo a passo e o botão "Já liberei, atualizar a página":
    o Edge/Chrome só aplicam a liberação do cadeado depois de recarregar; com a permissão já dada, liga sozinho; sininho
    riscado 🔕 do Edge = "dispensado", com a dica).
    Não trava: **iPhone** (não cobrar), navegador sem avisos, e enquanto o
    sistema de avisos não estiver pronto (sem SQL 17 ou sem a chave). `conferirTrava()` no ligacoes.html.
    **Fernanda coordenadora** (`montar_aviso` no `avisos_ligacoes.py`, decisão do TI 24/11/2026): **sempre 4 mensagens por
    dia para cada pessoa** (só não manda para quem não tem cliente na lista), 4 turnos
    (manha1 = bom dia às **8h** em ponto: acordado às 7h45 e espera; manha2 9h45, tarde1 13h45, tarde2 = fim do dia 16h45): vendedor (quantos recebeu hoje, o de maior
    valor com valor e nº da cotação, quantos faltam, "mudar a estratégia", até as 17h, resumo do dia); gerente da
    loja (cada vendedor: quem falou com quantos, quem não falou com nenhum, quem não entrou hoje, para cobrar);
    Jonathan/admin (resumo de todas as lojas "falaram com / receberam", lojas sem contato com o nome do gerente,
    abaixo de 30%, resumo da rede).
    **Nunca nome nem telefone de cliente.** A mesma mensagem fica em `avisos_fernanda` (SQL `23_avisos_fernanda.sql`,
    cada um lê só as suas, 15 dias) e a raposa mostra na página (`FE_LIG.avisoRobo`, confere a cada 5 min).
  · **Conhecimento de pneus** (`public/fernanda-pneus.js`, estudo "Pneus" da Fox enviado pelo TI em 24/11/2026; carregado
    pelo fernanda-ajuda.js em todas as telas, `window.fePneus`, chamado antes das contas): segmentos (liso 100% asfalto,
    HT 70/30, AT 50/50, TA 40/60, MUD 20/80, carga: Doblô/Strada/Fiorino) e indicação pelo % de terra; lê a medida
    (largura no costado, altura %, R, aro, índice de carga em kg, velocidade, diâmetro); compara 2 medidas (diferença
    %); alternativas do estudo (175/65R14 → 175/70R14, 175/70R14 → 175/75R14, sempre "o cliente confere na loja");
    medidas com A/T na Fox (175/70R14, 175/75R14, 175/80R14, 205/60R15, 205/65R15, 205/70R15; outras com 1 não têm);
    troca (novo ~8 mm, preventiva 3 mm, obrigatória 1,6 mm, TWI) e "sulco X mm"; validade/garantia 5 anos e "DOT 2324"
    (idade); etiqueta INMETRO; run-flat; válvula/TPMS, balanceamento, torque, alinhamento. No Cadastrar só responde
    se for pergunta (a medida digitada continua indo para o formulário).
  · **Treinadora de vendas** (`public/fernanda-vendas.js`, "Base de Conhecimento Mestre" enviada pelo TI em 24/11/2026;
    todas as telas, `window.feVendas`, chamada ANTES dos pneus): "treinar vendas" abre 3 modos: 🎭 simulação (cliente
    sorteado: 10 produtos × 8 perfis × objeções × WhatsApp/balcão; nota 0–10 por palavras em diagnóstico, consciência
    técnica, armas da Fox e fechamento + resposta modelo), 🔎 auditoria de conversa colada, ⚡ resposta rápida
    ("cliente achou mais barato na internet" → 2 respostas). Playbook com 17 objeções (`OBJ`), filosofia, protocolo e
    diferenciais (**montagem gratuita + checklist preventivo completo gratuito**).
    **Print da conversa** (TI, 25/11/2026): fora do Cadastrar (ex.: Ligações) ou no modo "🔎 Auditar", a imagem colada/📎
    é lida como conversa de WhatsApp (`lerConversa` no fernanda-ajuda.js, Tesseract; balão à direita = vendedor, à esquerda
    = cliente; modo escuro invertido; cabeçalho, horas e chip de data saem). `auditarConversa` (fernanda-vendas.js) mostra
    "Li assim", onde a conversa parou e a **próxima mensagem pronta** (objeção do cliente, sinal de compra, pergunta de
    preço ou cliente sumiu → resgate), ideias de frases e a auditoria. Texto exportado do WhatsApp também é separado. **Perguntas ensinadas** (Monitor "não soube responder", 25/11/2026): "venda" (o que ela sabe de vendas),
    "insistir no contato é ruim para a imagem da Fox" (`INSISTIR`: até 3 ligações, cada contato com algo novo, respeitar o não),
    "quero aprender a vender" (abre o treino), "ok/obrigado" (confirma) e "1/2/3" logo depois do menu de treino (`ultimoMenu`). Respostas modelo ADAPTADAS à regra do
    TI: sem "reservar box", sem "segurar condição 48 h", sem "pronta entrega" (nunca prometer pneu separado nem horário
    reservado); combinar o dia da visita. No Cadastrar só responde se a pessoa pedir ("cliente disse…", "treinar").
    **Módulo 2** (TI, 24/11/2026): roteiro de ligação de resgate (etapas A/B/C; nas Ligações já vem preenchido com o
    cliente de maior valor sem contato, a medida, o dia e a validade do preço), "me manda no WhatsApp" (30 segundos,
    nunca desligar sem tentar um dia), resgate no WhatsApp (visita em 48 h), escada de condições (4x sem juros · 8x
    com 5% para visita em 48 h · 21x · cobrir orçamento com o gerente; regra de ouro: contrapartida = dia da visita),
    cobrir orçamento na mesma ligação. **Regras da Fox**: não faz entrega; **preço garantido pela data da cotação:
    7 dias (cotação do televendas) ou 3 dias (cotação da loja)**; nunca travar box nem separar pneu.
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

## 🛰️ API oficial do Movere — branch `venda-api`

- Documentação pública no Swagger (`api.moveresoftware.com/swagger/docs/movere-api` e `.../movere-inteligente`; esta sessão
  não alcança o site, os testes rodam no GitHub). Login `POST /api/LoginComAmbiente` {ambiente, usuario, senha} → token
  (vale ~5 dias). **Um login novo NÃO derruba o token anterior** (testado em 25/11/2026; o mesmo usuário é usado por outra IA
  do TI). Segredos: `MOVERE_API_AMBIENTE`, `MOVERE_API_USUARIO`, `MOVERE_API_SENHA` (o `MOVERE_API_TOKEN` fixo estava vencido).
- `NotasFiscaisEmitidas` (por loja e período, 100 por página): nota em `NF` com `Cliente` (fonecelular/fonecom),
  `Comercial` (idorcamento; sem vendedor nem tabela de preço), `Produtos` (descrição com a medida), `descricaoentradaesaida`
  (VENDA / DEVOLUÇÃO DE VENDA / transferência / carcaça). Conferido 24/11: as vendas batem centavo com a 553 (MATRIZ,
  PARINTINS, C.AUTO PVH líquido, ARIQUEMES varejo+atacado). **Sem tabela de preço**: Varejo/Atacado continuam pela 553.
  `ConsultaOrcamentos`: cotações (cotação pura vem sem cliente/telefone: a lista das Ligações continua pelo Analytics).
- `movere_api.py`: vendas na hora por telefone e por nº do orçamento (só VENDA; últimos `DIAS_API` = 10 dias, o Analytics
  cobre os mais antigos). Usado em `conferir_vendas_movere.py` (descontos: 1º pelo NÚMERO, 2º pelo telefone; `venda_movere_por`). **Nos descontos,
  "Orçamento" = nº da COTAÇÃO e "O.S." = nº da ordem de serviço** (TI, 25/11/2026). Na API: nota `Comercial.idorcamento` = nº da
  O.S.; `ConsultaOrcamentos` (status 2) liga `idcotacao` → `idorcamento` (conferido com 2 exemplos do TI) e em `ligacoes_lojas.py` (comprou → venda televendas). Se a API falhar, segue só com o Analytics.
  Testes: `python tests/test_movere_api.py`. **Monitor**: seção "🛰️ API do Movere" (a última rodada dos descontos e das Ligações
  grava `movere_api.ESTADO` em `robo_execucoes.detalhes`: respondeu / falhou / não configurada). Horários = os dos dois robôs.

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
  Tentativas "Não atendeu (2x)"; da 2ª em diante o WhatsApp fica em destaque. Nova tentativa: opção "📞 Liguei de novo,
  não atendeu" no Status. **Máximo de 3 tentativas por ligação** (`MAX_TENT`, decisão do TI): depois o 📞 fica apagado e
  só vale o WhatsApp. **Anotação não conta como ligação** (`anotar_ligacao`, SQL `19_anotacao_sem_tentativa.sql`, que
  também corrigiu as tentativas a mais gravadas antes; cópia em `ligacoes_historico_ajuste_19`). Botão WA com o símbolo do WhatsApp.
  Status **"Aguardando retorno WhatsApp"** (`aguardando_wa`, SQL `20_aguardando_whatsapp.sql`): em aberto como "Retornar
  depois" (aba Já liguei, divisão, férias, Monitor, robôs). O SQL 20 acrescenta o status nas funções que já estão no banco.
  **Status livre** (decisão do TI): o vendedor muda qualquer status a qualquer hora, inclusive sair de "Venda ganha",
  "Venda perdida" e "Agendou" (salva sozinho, como planilha). Só o que o robô marcou (Venda televendas) fica travado.
  Ao sair de um status, o dado dele sai junto (O.S., data do agendamento, motivo): `marcar_ligacao` do SQL `22_status_livre.sql`.
  Pendentes ordenados pelo maior valor + total em aberto. Celular (< 900 px): cartões.
  **WhatsApp em 2 mensagens** (texto do TI, 24/11/2026): botão WA = mensagem 1 ("Olá, {cliente}! Aqui é {vendedor},
  da Fox Pneus {loja}. Vi que você fez um orçamento ontem/antes de ontem/no dia X do pneu {medida}… o que faltou para
  fecharmos…"; "Aqui é **o** Gilcimar / **a** Sabrina" pela coluna "Aqui é" do /admin, `perfis.artigo`, SQL `24_artigo_o_a.sql`;
  sem escolha fica sem artigo: o sistema NÃO adivinha pelo nome); botão (ícone do WhatsApp + alfinete de localização, meio a meio) = mensagem 2 com endereço e link do mapa da loja (`ENDERECO_LOJA`; PARINTINS = Manaus,
  XAPURI = Rio Branco, C.AUTO VLH = Vilhena), pisca depois da 1ª. O link do WhatsApp só leva 1 mensagem e
  precisa do clique em enviar (o botão WA é só o símbolo do WhatsApp; links por `api.whatsapp.com/send`, porque o `wa.me` estragava os emojis 📍 👇🏼): envio automático só com a API oficial do WhatsApp Business (paga) ou pelo Kommo.
  **Nunca prometer pneu separado nem horário reservado** (o estoque pode acabar; decisão do TI). Mensagens curtas.
- **Data do agendamento pelo Kommo**: o robô lê o campo **"Data da visita"** do lead e grava em
  `agendado_para` quando a lista está sem data ou com data mais antiga.
  **Medida do pneu** (`ligacoes.medida`, SQL `14_ligacoes_medida.sql`).
- **Nome do cliente** aparece sem o telefone que às vezes vem junto do Movere (`nomeCli`: tira
  sequências com 8+ dígitos; só na tela, o dado no banco não muda).
  **Corrigir o nome** pela tela: ✏️ ao lado do nome (vendedor responsável, gerente da loja, admin),
  `renomear_cliente` (SQL `21_editar_nome_cliente.sql`); fica no histórico como "Nome corrigido" e não conta
  como trabalho no Dashboard. O robô não sobrescreve (só insere clientes novos).
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
- **Cotações dos VENDEDORES DAS LOJAS** (decisão do TI, 25/11/2026; SQL **`31_ligacoes_cotacoes_loja.sql`**): além das do
  televendas, entram as cotações feitas nas **8 lojas** (FOX-GM, MANAUS, RECAP-PVH, RECAP-VLH e ATACADO ficam fora), **todas**,
  desde `INICIO_LOJA` (24/11/2026). O robô roda o relatório 782403 também SEM o filtro do dashboard 782276; nas cotações da
  loja o "NomeOperador" vem "Não informado" e quem cotou vem na coluna **"Vendedor"** (nome completo do Movere).
  **Quem cotou é o responsável** (Cotou: Edileia · Responsável: Edileia), sem divisão. Cotação do **gerente**, de vendedor de
  férias/desativado ou de nome **não reconhecido** → divisão automática. Reconhecer: `casar_vendedor` (1º `perfis.nome_movere`,
  escolhido no /admin; senão todas as palavras do nome cadastrado estão no nome do Movere e só 1 pessoa da loja bate).
  Mesmo telefone nas duas: fica a da loja. `ligacoes.origem` ('televendas' | 'loja'): coluna **Origem** e filtro
  "Origem: Loja / Origem: Televendas" na lista e no Dashboard (cartão "Origem das cotações" com as duas separadas). Venda achada
  pelo robô numa cotação da loja aparece como "Venda pelo sistema (Movere)". Preço garantido: **loja 3 dias, televendas 7 dias**
  (roteiro da Fernanda). Nomes vistos ficam em `ligacoes_nomes_movere` (só admin lê): o **/admin** mostra "⚠️ Vendedores do
  Movere que o sistema não reconheceu" com "É quem?", a coluna "Nome no Movere", e as Ligações do admin mostram uma faixa amarela.
  Sem o SQL 31 o robô segue só com o televendas.
- **As planilhas do Google (Apps Script) continuam funcionando** — decisão do TI.
- SQL: `12_ligacoes.sql` (tabelas, `minha_loja()`, `ve_todas_ligacoes()`, `marcar_ligacao()`,
  `senha_trocada()`), 13, 14 e **`15_ligacoes_vendedores.sql`** (funções, responsável, férias, divisão).
- Testes: `python tests/test_ligacoes_lojas.py` e `python tests/test_avisos_ligacoes.py`.
- `sb_get` busca em partes de 1000 (o banco entrega no máximo 1000 linhas por vez).

## 🏆 Resultados Fox Pneus — branch `resultados-fox`

- Página **`/resultados`** (`public/resultados.html`, rewrite no `middleware.js`; bloco "Resultados Fox Pneus" no FOXNET).
  Pede o login (o mesmo das Ligações e do App; qualquer perfil **ativo** lê; decisão: o repositório é público, sem
  login qualquer um leria os números com a chave anon). Abas: **Resultado Televendas** (abre `/televendas.html`),
  **Resultado Varejo · Geral**, **Resultado Atacado** (`/atacado`) e **Truck** ("em breve").
  **Barra de abas única** (`public/resultados-abas.js`, pedido do TI 25/11/2026): a mesma em /resultados, /atacado e no
  Televendas (só quando veio de Resultados: `?resultados=1`, guardado na aba), presa no topo. Aba nova: só mexer na lista `ABAS`.
- **Varejo** (decisão do TI: base = **rotina 553**, com o dia de hoje): Vendido hoje, no mês, meta, falta (e por dia,
  contando seg–sáb), ticket médio; **ranking das lojas** (hoje, clientes, mês, meta, %, falta, clientes, ticket, itens);
  clicar na loja mostra os **vendedores** (a soma bate com a loja: ✅). **Metas**: admin e **gerente de todas as lojas** (Jonathan;
  SQL `29_metas_varejo_jonathan.sql`, `edita_metas_varejo()` = `ve_todas_ligacoes()`; decisão do TI 25/11/2026), botão ✏️ Metas na página
  (`varejo_metas`). Sem metas, mostra "sem meta". **Dias úteis** igual ao Televendas: no ✏️ Metas, calendário do mês;
  clicar no dia marca feriado (domingo nunca conta). Feriados gravados em `varejo_metas` com `loja = 'feriado_DD'`.
  **% desejado do dia** (regra única do TI, 25/11/2026, vale para Televendas, Varejo e Atacado) = dias úteis **já fechados**
  (até ontem) ÷ dias úteis do mês; ex.: 23 dias úteis, em 24/11 fecharam 17 → 17/23 = 73,9%; mês fechado = 100%.
  % meta **verde** se ≥ desejado, **vermelho** abaixo.
  Ícone de pneu em SVG (`PNEU`; o emoji 🛞 não aparece no Windows). Em cima só "Atualizado em…"; as explicações
  ficam em "🔻 Mais informações sobre atualização", lá embaixo (pedido do TI, 25/11/2026). Página até 1700 px de largura.
- **Seta vermelha lá embaixo** (pedido do TI): a 553 até ontem (mês − hoje) comparada com o Analytics
  "Jonathan - Faturamento Varejo" (1111480), por loja, com os motivos: **REVENDA** (o Analytics tira, a 553 não tem o
  filtro) com o código do cliente, nota, dia e vendedor; o que sobrar vira "Diferença sem explicação automática".
  Tudo batendo: "✅ Conferido com o Analytics".
- Robô **`resultados_varejo.py`** (workflow `resultados-varejo.yml`): acordado pelo sync-televendas **7h45 às 17h45**
  (seg–sáb) + cron 19h10. Gera a 553 **loja por loja** (assim os vendedores somam a loja), mês e hoje (≈ 15 min).
  Filtros em `varejo_filtros.py`: 8 lojas, 13 tabelas de preço (`TABELAS_VAREJO`; ATACADO, ATACADO PREMIUM, AMAGGI e
  GK fora), 11 famílias, **"Frete compõe valores totais"** marcado (assim bate com o Analytics). O Movere lembra os
  filtros do login: o `sync_televendas.py` limpa lojas/tabelas/famílias/frete antes de cada relatório (não afetar o
  televendas). Registro público só com contagens. `DRY_RUN=1` testa sem gravar.
- **🛞 Pneus** (pedido do TI, 24/11/2026; coluna ao lado de "Clientes mês", na loja e no vendedor): mais uma 553 por loja
  só com as famílias de pneu (`FAMILIAS_PNEUS`: DUNLOP, FAMÍLIA PASSEIO PIRELLI, MULTIMARCAS CAR, PASSEIO BRIDGESTONE,
  PNEUS IMPORTADOS CAR) → pneus vendidos no mês (`pneus`) e em quantas vendas (`pneus_vendas`). Conferido em 25/11/2026 com a regra do TI
  ("pneu = item com medida no nome", ex.: 175/75R14, 185/65R15, 205/60R17, LT265/70R16, 31X10.50R15) no Analytics, item por
  item: **igual nas 8 lojas** (nenhum item de pneu fora dessas famílias e nenhum item dessas famílias sem medida). O filtro
  de aros da 553 NÃO serve (deu números negativos). A rodada passa a
  levar ≈ 20 min. SQL **`27_varejo_pneus_metas.sql`**: colunas de pneus + metas de nov/2026 (total R$ 4.500.000;
  MATRIZ 800 mil, C.AUTO PVH 680, JI-PARANA 680, CACOAL 620, PARINTINS 530, XAPURI 480, ARIQUEMES 410, C.AUTO VLH 300).
  Sem o SQL 27 o robô grava sem os pneus (não quebra).
  **Metas de pneus** (TI, 25/11/2026; SQL **`28_varejo_metas_pneus.sql`**: `varejo_metas.meta_pneus/super_pneus/mega_pneus`;
  nov/2026: total Meta 7.840 · Super 8.970 · Mega 9.720): na coluna Pneus "vendidos / Meta", % (verde no ritmo do dia,
  vermelho abaixo), barrinha com 3 marcas, "faltam N p/ Meta|Super|Mega" e selo da faixa (✅ Meta · ⭐ Super · 🏆 Mega);
  mouse em cima: vendas e projeção "no ritmo de hoje". Cartão "Pneus no mês" com o total da rede. Lançadas no ✏️ Metas
  (3 caixinhas por loja). Vendedor: só o número (sem meta por vendedor).
- SQL **`26_resultados_varejo.sql`**: `varejo_lojas`, `varejo_vendedores` (periodo `mes`/`hoje`), `varejo_conferencia`,
  `varejo_metas`, `perfil_ativo()`. Testes: `python tests/test_resultados_varejo.py`.
- Conferido em 24/11/2026 (01 a 21/11): 6 lojas batem no centavo com o Analytics; a diferença das outras é REVENDA
  (devoluções/vendas de clientes com segmento REVENDA). Segmento REVENDA não existe como filtro na 553 (procurado nas 21 listas).

## 📦 Resultado Atacado — branch `resultado-atacado`

- Página **`/atacado`** (`public/atacado.html`; aba e cartão "Resultado Atacado" em /resultados). **Visual copiado do painel
  do Televendas** (mesmo CSS, pedido do TI 25/11/2026): Meta 1 / Meta 2 (+10%) / Meta 3 (+20%), KPIs (faturamento do setor,
  % da meta, % desejado do dia, falta, setor precisa por dia) + "Pneus no mês"; tabela **por vendedor** (principal) com Meta,
  **últimos 5 dias úteis** (passar o mouse mostra clientes, itens e o valor; sem nome de cliente), faturamento do mês, pneus,
  precisa por dia e % atingido; linha verde no ritmo / vermelha abaixo; TOTAL
  SETOR; tabela **Por loja** (hoje, mês, % do setor, clientes, itens, pneus, ticket). Seletor de mês. Pede login.
  Vendedores sem meta (quase sempre devoluções, valor negativo) ficam lá embaixo: 🔻 Mais informações → "↩️ Devoluções e
  outros vendedores" (pedido do TI, 25/11/2026); o TOTAL SETOR já desconta.
  **Editar metas** (admin e gerente de todas as lojas): meta 1 de cada vendedor + feriados (dias úteis igual ao Televendas).
- Robô **`resultados_atacado.py`** (workflow `resultados-atacado.yml`, acordado com o Varejo 7h45–17h45 + cron 19h20; grupo
  de concorrência **`movere-553`** igual ao Varejo: nunca os dois ao mesmo tempo no mesmo login): rotina 553 com
  `TABELAS_ATACADO` (2 ATACADO + 5 ATACADO PREMIUM), **todas as lojas** (`gerar(..., lojas=[])`), todas as famílias, frete;
  mês (+ pneus do mês com `FAMILIAS_PNEUS_ATACADO`: inclui TRUCK, MULTIMARCAS TRUCK, TRUCK/AGRO e TRUCK PROMETEON, que tem
  câmaras; RECAPAGEM fica fora) e os últimos 5 dias úteis (hoje e o dia anterior sempre; os outros só se faltarem;
  linha `TOTAL` em `atacado_lojas` marca o dia lido). Nos dias 1–3 fecha o mês anterior. ≈ 2–5 min.
  Conferido em 25/11/2026: o total do mês bateu com o relatório 553 do TI (soma dos vendedores = total).
- SQL **`30_resultados_atacado.sql`**: `atacado_vendedores`, `atacado_lojas` (periodo `mes`/`dia`), `atacado_metas`
  (`v:COD` e `feriado_DD`; metas de EXEMPLO de nov/2026, 8 vendedores, R$ 5,2 mi). Testes: `python tests/test_resultados_atacado.py`.

## 🩺 Monitor (só o admin) — branch `monitor`

- Página **`/monitor`** (`public/monitor.html`, rewrite no `middleware.js`). Pede o login de admin; o banco
  só responde ao admin (`monitor_resumo()`, SQL `18_monitor.sql`, que também cria `robo_execucoes.detalhes`).
- Botão **"🩺 Monitor"** no topo do FOXNET só no navegador do admin: marcado ao entrar no /monitor
  (`localStorage fox_monitor`). Também é marcado sozinho quando o admin entra no App, Ligações, /admin ou
  Televendas (`FoxTema.admin()`), e a raposa leva a marca para a intranet (`?monitor=1`). À mão:
  `foxnet-intranet.vercel.app/?monitor=1` (`?monitor=0` tira). Sem botão "Entrar" na intranet (decisão mantida).
- Mostra (🟢/🟡/🔴, atualiza a cada 5 min): robôs no GitHub (API pública, últimas rodadas, atraso, erro);
  passo a passo da última rodada da lista (login no Analytics, vendas 742591, Kommo, cotações por dia,
  cruzamento e motivos, novos por loja, divisão, reconferência) a partir de `robo_execucoes.detalhes`;
  clientes por dia (14 dias); lojas (vendedores, férias, sem responsável, divisão desigual, contatos hoje,
  último contato só de pessoas); avisos no celular; descontos; televendas; páginas no ar; segurança
  (tabelas sem RLS, regras para quem não está logado, senhas antigas legíveis) e espaço do banco (500 MB).
- Robôs que gravam detalhes: `ligacoes_lojas.py` (`DETALHES`) e `avisos_ligacoes.py` (`rodar()`).
  Se o SQL 18 não rodou, gravam sem os detalhes (não quebram). Só contagens: nada de cliente.
- Seção **🏆 Resultados Fox Pneus (rotina 553)**: última rodada dos robôs do Varejo e do Atacado (detalhes, erros, bolinhas) e
  se os números chegaram na página (`varejo_lojas` / `atacado_lojas`; amarelo se parados há mais de 2 h em horário de loja).
- Próximas etapas combinadas: backup diário trancado com senha (segredo no GitHub), 3 linhas nos
  Apps Scripts para o monitor ver os e-mails, e anotar erros das telas.

## 🛡️ Segurança (os 8 ataques comuns de sistemas feitos com IA) — conferido em 23/11/2026

- ✅ Rotas expostas (RLS confere o dono), chaves expostas (só a anon no histórico do repositório),
  banco aberto (Monitor: 0 tabelas sem RLS), SQL injection (tudo pelo PostgREST/RPC com parâmetros),
  prompt injection (Fernanda sem IA externa), pacotes (poucos e conhecidos; `npm audit` 0).
- **XSS**: todo texto do banco/Movere entra na tela com `esc()` (Consulta, Televendas, Ligações, /admin,
  Monitor; o App é React). Cabeçalhos de segurança em `vercel.json` (nosniff, SAMEORIGIN, Referrer-Policy,
  Permissions-Policy, CSP `frame-ancestors 'self'; object-src 'none'; base-uri 'self'`). Texto novo na tela: use `esc()`.
- **Limite de tentativas de login** (`FoxLogin.entrar` em `tema-comum.js`, usado nas 6 telas de login):
  5 senhas erradas seguidas no mesmo e-mail travam 5 min (depois 15 e 30); aviso a partir da 3ª.
  O Supabase também limita por internet (deixar o padrão: todos de uma loja saem pela mesma internet).
- Ponto fraco conhecido: senha inicial = e-mail. O Monitor lista quem ainda não trocou (🔴 após 3 dias).
- Pendentes: apagar senhas antigas (`usuarios`, `usuarios_televendas`) e tirar o "👥 Usuários" antigo do
  Televendas; Dependabot; travar versões dos pacotes dos robôs.

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
4. **Resultados** — Varejo feito (ver "🏆 Resultados Fox Pneus"). Futuro: Atacado e Truck.
5. **Ligações das lojas** no FOXNET — feito (ver seção acima). Depois de um tempo em paralelo,
   o TI decide se desliga as planilhas.
6. Opcional: e-mail da empresa (SMTP) no Supabase para "esqueci minha senha".

## Pendências de informação do TI

- Significado das cores amarelo/vermelho nas cidades; gerente de cada loja; CNPJ,
  endereço e telefone da loja de Guajará-Mirim; frases do dia além das 64.
