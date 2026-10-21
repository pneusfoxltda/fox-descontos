/**
 * Televendas Fox Pneus — atualização automática do painel
 * https://fox-descontos.vercel.app/televendas.html
 *
 * Roda no Google Apps Script (servidores do Google), sem depender de computador ligado.
 * Todo dia, perto das 7h40 (horário de Brasília):
 *   1. faz login no Movere (GoodData) pela API, com usuário e senha guardados nas
 *      Propriedades do script (nunca no código);
 *   2. busca o faturamento do mês por operadora e por dia
 *      (o mesmo do dashboard "Gil - Vendas que já estão validadas - Televendas");
 *   3. guarda o resultado e o publica para o painel:
 *        - pelo endereço do App da Web (doGet), e/ou
 *        - no arquivo public/televendas-dados.json do GitHub, se houver GITHUB_TOKEN.
 *   Se der erro, manda um e-mail para o dono do script.
 *
 * Propriedades do script (Configurações do projeto > Propriedades do script):
 *   MOVERE_USUARIO  e-mail de login no Movere            (obrigatório)
 *   MOVERE_SENHA    senha do Movere                      (obrigatório)
 *   GITHUB_TOKEN    token do GitHub com acesso "Contents: Read and write"
 *                   somente ao repositório fox-descontos (opcional)
 *
 * Funções para rodar manualmente pelo editor:
 *   testarLogin()   confere se o Movere aceita o login (não grava nada)
 *   atualizar()     faz a atualização completa
 *   criarGatilho()  agenda a atualização diária às 7h40 (rodar uma vez)
 */

const CONFIG = {
  BASE: 'https://analytics.moveresoftware.com',
  PROJETO: 'uljodb77ez5d22jaim5mks2y36n5xvr4',
  OBJ_OPERADOR: 410826,     // NomeOperador
  OBJ_DIA: 1303,            // dd/mm/yyyy (dtaemissao)
  OBJ_FATURAMENTO: 2160,    // métrica Faturamento
  OBJ_DATASET_DATA: 1146,   // dataset Date (dtaemissao)
  OPERADORAS: [
    'KESSYA DIAS MARQUES',
    'ANA CLARA MARTINS HENRIQUE',
    'SABRINA ROCHA PARDO',
    'GRAZIELE MACHADO GARCIA'
  ],
  FUSO: 'America/Sao_Paulo',
  HORA: 7,
  MINUTO: 40,
  GITHUB_REPO: 'pneusfoxltda/fox-descontos',
  GITHUB_ARQUIVO: 'public/televendas-dados.json',
  GITHUB_BRANCH: 'main',
  // a Vercel só publica commits com este autor
  GITHUB_AUTOR: { name: 'pneusfoxltda', email: 'gilcimar.freitass21@gmail.com' }
};

/* ======================= funções principais ======================= */

function atualizar() {
  try {
    const dados = buscarDados_();
    PropertiesService.getScriptProperties().setProperty('DADOS_JSON', JSON.stringify(dados));
    const github = publicarNoGitHub_(dados);
    console.log(`OK: vendas até ${dados.dadosAte} (${Object.keys(dados.vendas).length} operadoras). GitHub: ${github}`);
    return dados;
  } catch (e) {
    avisarErro_(e);
    throw e;
  }
}

function testarLogin() {
  const sessao = login_();
  logout_(sessao);
  console.log('Login no Movere OK.');
}

function criarGatilho() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'atualizar')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('atualizar')
    .timeBased()
    .everyDays(1)
    .atHour(CONFIG.HORA)
    .nearMinute(CONFIG.MINUTO)
    .inTimezone(CONFIG.FUSO)
    .create();
  console.log(`Gatilho criado: todo dia por volta das ${CONFIG.HORA}h${CONFIG.MINUTO}.`);
}

// Endereço do App da Web: devolve os últimos dados em JSON para o painel.
function doGet() {
  const json = PropertiesService.getScriptProperties().getProperty('DADOS_JSON') || '{}';
  return ContentService.createTextOutput(json).setMimeType(ContentService.MimeType.JSON);
}

/* ======================= Movere (GoodData) ======================= */

function buscarDados_() {
  const agora = new Date();
  // mês de ONTEM: no dia 1º ainda mostra o fechamento do mês anterior
  const ontem = new Date(agora.getTime() - 24 * 3600 * 1000);
  const mes = Utilities.formatDate(ontem, CONFIG.FUSO, 'yyyy-MM');
  const [ano, m] = mes.split('-').map(Number);
  const ultimoDia = new Date(ano, m, 0).getDate();

  const sessao = login_();
  try {
    const linhas = consultarFaturamento_(sessao.tt, `${mes}-01`, `${mes}-${String(ultimoDia).padStart(2, '0')}`);
    const vendas = {};
    CONFIG.OPERADORAS.forEach(nome => { vendas[nome] = {}; });
    let dadosAte = null;
    linhas.forEach(([nome, dia, valor]) => {
      if (!vendas[nome]) return;                    // ignora outros operadores
      vendas[nome][dia] = Math.round(valor * 100) / 100;
      if (!dadosAte || dia > dadosAte) dadosAte = dia;
    });
    return {
      atualizadoEm: Utilities.formatDate(agora, CONFIG.FUSO, 'yyyy-MM-dd'),
      atualizadoAs: Utilities.formatDate(agora, CONFIG.FUSO, 'HH:mm'),
      mes: mes,
      dadosAte: dadosAte,
      vendas: vendas
    };
  } finally {
    logout_(sessao);
  }
}

function login_() {
  const props = PropertiesService.getScriptProperties();
  const usuario = props.getProperty('MOVERE_USUARIO');
  const senha = props.getProperty('MOVERE_SENHA');
  if (!usuario || !senha) {
    throw new Error('Faltam MOVERE_USUARIO e/ou MOVERE_SENHA nas Propriedades do script.');
  }

  const r = UrlFetchApp.fetch(CONFIG.BASE + '/gdc/account/login', {
    method: 'post',
    contentType: 'application/json',
    headers: { Accept: 'application/json' },
    payload: JSON.stringify({ postUserLogin: { login: usuario, password: senha, remember: 0, verify_level: 2 } }),
    muteHttpExceptions: true
  });
  if (r.getResponseCode() !== 200) {
    throw new Error(`O Movere recusou o login (HTTP ${r.getResponseCode()}): ${r.getContentText().slice(0, 300)}`);
  }
  const userLogin = JSON.parse(r.getContentText()).userLogin || {};
  const sst = userLogin.token;
  if (!sst) throw new Error('O Movere aceitou o login, mas não devolveu o token de sessão.');

  const t = UrlFetchApp.fetch(CONFIG.BASE + '/gdc/account/token', {
    headers: { Accept: 'application/json', 'X-GDC-AuthSST': sst },
    muteHttpExceptions: true
  });
  if (t.getResponseCode() !== 200) {
    throw new Error(`Não foi possível obter o token temporário do Movere (HTTP ${t.getResponseCode()}).`);
  }
  const tt = JSON.parse(t.getContentText()).userToken.token;
  return { sst: sst, tt: tt, perfil: userLogin.profile || '' };
}

function logout_(sessao) {
  try {
    const id = (sessao.perfil || '').split('/').pop();
    if (!id) return;
    UrlFetchApp.fetch(CONFIG.BASE + '/gdc/account/login/' + id, {
      method: 'delete',
      headers: { Accept: 'application/json', 'X-GDC-AuthSST': sessao.sst, 'X-GDC-AuthTT': sessao.tt },
      muteHttpExceptions: true
    });
  } catch (e) {
    // sair da sessão é só limpeza; não interrompe a atualização
  }
}

// Devolve [[nomeOperador, 'AAAA-MM-DD', valor], ...]
function consultarFaturamento_(tt, de, ate) {
  const P = `/gdc/md/${CONFIG.PROJETO}/obj/`;
  const corpo = {
    execution: {
      afm: {
        attributes: [
          { displayForm: { uri: P + CONFIG.OBJ_OPERADOR }, localIdentifier: 'op' },
          { displayForm: { uri: P + CONFIG.OBJ_DIA }, localIdentifier: 'd' }
        ],
        measures: [{ localIdentifier: 'm', definition: { measure: { item: { uri: P + CONFIG.OBJ_FATURAMENTO } } } }],
        filters: [{ absoluteDateFilter: { dataSet: { uri: P + CONFIG.OBJ_DATASET_DATA }, from: de, to: ate } }]
      },
      resultSpec: { dimensions: [{ itemIdentifiers: ['op', 'd'] }, { itemIdentifiers: ['measureGroup'] }] }
    }
  };
  const cab = { Accept: 'application/json', 'X-GDC-AuthTT': tt };

  const ex = UrlFetchApp.fetch(`${CONFIG.BASE}/gdc/app/projects/${CONFIG.PROJETO}/executeAfm`, {
    method: 'post', contentType: 'application/json', headers: cab,
    payload: JSON.stringify(corpo), muteHttpExceptions: true
  });
  if (ex.getResponseCode() !== 201 && ex.getResponseCode() !== 200) {
    throw new Error(`Consulta ao Movere falhou (HTTP ${ex.getResponseCode()}): ${ex.getContentText().slice(0, 300)}`);
  }
  // buscar o resultado SEM parâmetros de limit/offset
  const link = CONFIG.BASE + JSON.parse(ex.getContentText()).executionResponse.links.executionResult;

  for (let i = 0; i < 30; i++) {
    const r = UrlFetchApp.fetch(link, { headers: cab, muteHttpExceptions: true });
    const code = r.getResponseCode();
    if (code === 204) return [];                    // mês ainda sem vendas
    if (code === 200) {
      const res = JSON.parse(r.getContentText()).executionResult;
      const H = res.headerItems[0];
      return res.data.map((v, k) => [
        H[0][k].attributeHeaderItem.name,
        H[1][k].attributeHeaderItem.name.split('/').reverse().join('-'),   // dd/mm/aaaa -> aaaa-mm-dd
        Number(v[0]) || 0
      ]);
    }
    if (code !== 202) throw new Error(`Resultado da consulta falhou (HTTP ${code}).`);
    Utilities.sleep(1000);
  }
  throw new Error('O Movere demorou demais para devolver o resultado.');
}

/* ======================= publicação ======================= */

function publicarNoGitHub_(dados) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) return 'sem GITHUB_TOKEN (só App da Web)';

  const url = `https://api.github.com/repos/${CONFIG.GITHUB_REPO}/contents/${CONFIG.GITHUB_ARQUIVO}`;
  const cab = {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };

  const atual = UrlFetchApp.fetch(`${url}?ref=${CONFIG.GITHUB_BRANCH}`, { headers: cab, muteHttpExceptions: true });
  let sha = null;
  if (atual.getResponseCode() === 200) {
    const j = JSON.parse(atual.getContentText());
    sha = j.sha;
    const antigo = JSON.parse(Utilities.newBlob(Utilities.base64Decode(j.content.replace(/\n/g, ''))).getDataAsString('UTF-8'));
    if (antigo.mes === dados.mes && antigo.dadosAte === dados.dadosAte &&
        JSON.stringify(antigo.vendas) === JSON.stringify(dados.vendas)) {
      return 'sem mudança nos números';
    }
  } else if (atual.getResponseCode() !== 404) {
    throw new Error(`GitHub: não consegui ler o arquivo (HTTP ${atual.getResponseCode()}).`);
  }

  const dd = (dados.dadosAte || dados.mes + '-01').slice(8, 10) + '/' + (dados.dadosAte || dados.mes).slice(5, 7);
  const corpo = {
    message: `dados: televendas ate ${dd}`,
    content: Utilities.base64Encode(JSON.stringify(dados, null, 2) + '\n', Utilities.Charset.UTF_8),
    branch: CONFIG.GITHUB_BRANCH,
    author: CONFIG.GITHUB_AUTOR,
    committer: CONFIG.GITHUB_AUTOR
  };
  if (sha) corpo.sha = sha;

  const r = UrlFetchApp.fetch(url, {
    method: 'put', contentType: 'application/json', headers: cab,
    payload: JSON.stringify(corpo), muteHttpExceptions: true
  });
  if (r.getResponseCode() !== 200 && r.getResponseCode() !== 201) {
    throw new Error(`GitHub recusou o commit (HTTP ${r.getResponseCode()}): ${r.getContentText().slice(0, 300)}`);
  }
  return 'commit feito';
}

function avisarErro_(e) {
  try {
    const email = Session.getEffectiveUser().getEmail();
    if (!email) return;
    MailApp.sendEmail(email, 'Painel Televendas: a atualização falhou',
      'A atualização automática do painel Televendas falhou.\n\n' +
      'Erro: ' + (e && e.message ? e.message : e) + '\n\n' +
      'O painel continua mostrando os últimos números que deram certo.\n' +
      'Se o erro for de login, confira MOVERE_USUARIO e MOVERE_SENHA nas Propriedades do script.');
  } catch (ignorado) {
    // sem e-mail, o erro continua aparecendo em Execuções no Apps Script
  }
}
