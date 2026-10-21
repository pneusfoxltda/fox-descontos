# Painel Televendas — atualização automática pelo Google Apps Script

O Apps Script roda nos servidores do Google. Todo dia, por volta das **7h40**, ele entra no
Movere, busca o faturamento das 4 operadoras e entrega os números para o painel
https://fox-descontos.vercel.app/televendas.html. **Não precisa de computador ligado.**

A senha fica guardada nas **Propriedades do script**, que só o dono do projeto vê.
Ela nunca vai para o código nem para o GitHub.

---

## Antes de começar (recomendado)

1. **Troque a senha do Movere.** A senha antiga foi colada numa conversa.
2. Se a Movere permitir, **peça um usuário só para leitura**, para uso do painel,
   em vez de usar a sua conta pessoal.

---

## Passo 1 — Criar o projeto

1. Acesse https://script.google.com e clique em **Novo projeto**.
2. Dê o nome **Painel Televendas** (clique em "Projeto sem título", no topo).
3. Apague o conteúdo do arquivo `Código.gs` e **cole todo o conteúdo de
   [`Televendas.gs`](Televendas.gs)**.
4. Clique em ⚙️ **Configurações do projeto** e marque
   **"Mostrar arquivo de manifesto appsscript.json no editor"**.
5. Volte ao editor (`< >`), abra o `appsscript.json`, apague tudo e **cole o conteúdo de
   [`appsscript.json`](appsscript.json)**.
6. Salve (Ctrl+S).

## Passo 2 — Guardar o usuário e a senha

1. ⚙️ **Configurações do projeto** → role até **Propriedades do script** →
   **Adicionar propriedade do script**.
2. Crie estas duas propriedades (o nome tem que ser exatamente este):

   | Propriedade      | Valor                         |
   |------------------|-------------------------------|
   | `MOVERE_USUARIO` | o e-mail de login no Movere   |
   | `MOVERE_SENHA`   | a senha do Movere             |

3. Clique em **Salvar propriedades do script**.

## Passo 3 — Testar o login

1. No editor, escolha a função **`testarLogin`** na lista ao lado do botão ▶ e clique
   em **Executar**.
2. Na primeira vez, o Google pede autorização: **Revisar permissões** → escolha a sua conta.
   Se aparecer "O Google não verificou este app", clique em **Avançado** →
   **Acessar Painel Televendas (não seguro)** → **Permitir**. O aviso aparece porque o script
   foi criado por você e não passou pela verificação do Google, o que é normal.
3. Resultado esperado no registro de execução: **`Login no Movere OK.`**

   Se aparecer **"O Movere recusou o login"**, confira o usuário e a senha. Se estiverem
   certos, o Movere pode não aceitar login por API (por exemplo, por exigir verificação em
   duas etapas). Nesse caso, avise o Gilcimar/Claude.

## Passo 4 — Testar a atualização

1. Escolha a função **`atualizar`** e clique em **Executar**.
2. Resultado esperado: **`OK: vendas até AAAA-MM-DD (4 operadoras). GitHub: ...`**

## Passo 5 — Ligar o painel aos dados (escolha UMA opção)

### Opção A — App da Web (mais simples, não precisa de token)

1. Clique em **Implantar** → **Nova implantação** → ⚙️ → **App da Web**.
2. Preencha assim:
   - **Executar como:** Eu
   - **Quem pode acessar:** Qualquer pessoa
3. Clique em **Implantar** e **copie o endereço do App da Web**
   (começa com `https://script.google.com/macros/s/...`).
4. **Mande esse endereço para o Claude.** Ele coloca o endereço no painel (`FONTE_URL` no
   `televendas.html`) e publica.

> Se a opção **"Qualquer pessoa"** não aparecer (algumas contas de empresa bloqueiam),
> use a Opção B.

### Opção B — Arquivo no GitHub (funciona mesmo se a Opção A for bloqueada)

1. No GitHub, com a conta **pneusfoxltda**, acesse
   https://github.com/settings/personal-access-tokens/new
2. Preencha:
   - **Token name:** Painel Televendas
   - **Expiration:** 1 ano (anote para renovar)
   - **Repository access:** *Only select repositories* → **fox-descontos**
   - **Permissions → Repository permissions → Contents:** **Read and write**
     (deixe todo o resto como *No access*)
3. **Generate token** e copie o token (começa com `github_pat_`).
4. No Apps Script, crie a propriedade **`GITHUB_TOKEN`** com esse valor (como no Passo 2).
5. Rode **`atualizar`** de novo. O resultado deve terminar com **`GitHub: commit feito`**.
   Cerca de 1 minuto depois, o painel mostra os números novos.

Esse token só consegue mexer no repositório **fox-descontos**. Se precisar, é só apagar o
token no GitHub e ele deixa de funcionar na hora.

## Passo 6 — Agendar todos os dias às 7h40

1. Escolha a função **`criarGatilho`** e clique em **Executar** (uma vez só).
2. Confira em ⏰ **Acionadores** (menu da esquerda): deve aparecer `atualizar`, diário,
   entre 7h e 8h. O Google roda perto das 7h40, com até 15 minutos de variação.

Pronto. A partir daí não depende de computador nenhum.

---

## Se algo der errado

- **Você recebe um e-mail** "Painel Televendas: a atualização falhou" com o motivo do erro.
- O painel **continua mostrando os últimos números que deram certo**.
- O histórico de cada execução fica em **Execuções** (menu da esquerda do Apps Script).

| Problema | O que fazer |
|---|---|
| "O Movere recusou o login" | Senha trocada ou expirada: atualize `MOVERE_SENHA` |
| "GitHub recusou o commit (HTTP 401)" | Token vencido ou apagado: gere outro e atualize `GITHUB_TOKEN` |
| Painel não muda | Veja em **Execuções** se a última rodada deu certo |

## Virada de mês

- O script busca sempre o mês de **ontem**. No dia 1º ele ainda mostra o fechamento do mês
  anterior, e a partir do dia 2 já mostra o mês novo.
- Os **dias úteis** são calculados sozinhos (segunda a sábado, menos os feriados da lista
  `FERIADOS` no `televendas.html`). Já estão na lista: 12/10, 02/11, 20/11 e 25/12.
  **Confira se a loja abre ou fecha nesses dias.**
- As **metas** ficam no `televendas.html` (`OPERADORAS`). Se mudarem em algum mês, peça ao
  Claude para ajustar.
