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

- Abas: **Todos** · **Válidos** (no prazo e não liberados) · **Liberados** · **Vencidas**
  (vencidos e não liberados, inclusive os que a rotina `auto_perdida` marcou como perdida).
  Válidos + Liberados + Vencidas = Todos. A aba "Pendentes" foi removida (igual a Válidos).
- A lista mostra 60 por vez ("Mostrar mais") e é memorizada para não travar ao digitar.

## Próximos passos (em ordem)

1. **Trancar o banco (RLS)**: hoje `descontos`, `usuarios`, `usuarios_televendas`,
   `logs_*` têm políticas "acesso total" para `anon`/`public`. Trocar por regras por
   nível (`public.tem_funcao()`, `public.eh_admin()` já existem). A Consulta pública deve
   ler só por uma view/RPC com as colunas necessárias. O robô do GitHub Actions e os
   Apps Scripts que gravam no banco precisam continuar funcionando (verificar a chave que usam).
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
