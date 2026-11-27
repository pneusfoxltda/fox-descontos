/* ═════════════════════════════════════════════════════════════════════════
   FERNANDA · Ligações das lojas (carregada pelo fernanda-ajuda.js só em /ligacoes.html)

   Uma "amiga" do vendedor na tela de ligações:
   · chama a pessoa pelo nome, com bom dia / boa tarde / boa noite;
   · de manhã: quantos clientes de ontem ela recebeu e quem está agendado para hoje
     (e quem agendou: ela mesma, outra pessoa ou o televendas pelo Kommo);
   · à tarde: quanto falta para concluir; à noite: o resumo do dia;
   · responde no chat: agendados, por onde começar, quem não atende, resumo, dicas…

   Lê só o que a tela já carregou (window.FE_LIG, em ligacoes.html). Sem IA externa:
   nada do que aparece aqui sai do navegador.
   ═════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  const L = () => window.FE_LIG;
  const N = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  const bot = t => window.feBot(t);
  const html = h => window.feHtml(h);
  const chips = l => window.feRenderChips(l);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const sorteia = a => a[Math.floor(Math.random() * a.length)];
  const plural = (n, um, varios) => n + " " + (n === 1 ? um : varios);

  // ── Hora de Porto Velho e período do dia ──
  const horaPVH = () => Number(new Date().toLocaleString("en-US", {timeZone: "America/Porto_Velho", hour: "numeric", hour12: false})) % 24;
  const periodo = () => { const h = horaPVH(); return h >= 5 && h < 12 ? "manha" : h >= 12 && h < 18 ? "tarde" : "noite"; };
  const saudacao = () => ({manha: "Bom dia", tarde: "Boa tarde", noite: "Boa noite"})[periodo()];

  // ── Os números da pessoa ──
  const ABERTO = ["pendente", "nao_atende", "retornar", "aguardando_wa", "agendou"];
  function numeros() {
    const F = L(), meus = F.meus(), hoje = F.hoje(), ontem = F.ontem();
    const deOntem = meus.filter(l => l.data_cotacao === ontem);
    const semContato = meus.filter(l => l.status === "pendente");
    const agHoje = meus.filter(l => l.status === "agendou" && l.agendado_para === hoje);
    const agAtras = meus.filter(l => F.atrasado(l));
    const agSemData = meus.filter(l => l.status === "agendou" && !l.agendado_para);
    const naoAtende = meus.filter(l => l.status === "nao_atende").sort((a, b) => F.tentativas(b) - F.tentativas(a));
    const retornar = meus.filter(l => l.status === "retornar");
    const fizHoje = meus.filter(l => String(l.status_em || "").slice(0, 10) === hoje && F.ehMeu(l));
    const ganhas = meus.filter(l => l.status === "venda_ganha");
    const sistema = meus.filter(l => F.ehTv(l.status));
    const trabalhados = meus.filter(l => l.status !== "pendente" && !F.ehRobo(l.status_por)).length;   // robô (Movere/Kommo) não conta
    return {meus, deOntem, deOntemFalta: deOntem.filter(l => l.status === "pendente"), semContato, agHoje, agAtras, agSemData,
            naoAtende, retornar, fizHoje, ganhas, sistema, trabalhados,
            valorAberto: meus.filter(l => ABERTO.includes(l.status)).reduce((t, l) => t + Number(l.valor || 0), 0)};
  }

  // Quem agendou: a própria pessoa, outra pessoa ou o televendas (robô do Kommo)
  function quemAgendou(l) {
    const F = L();
    if (F.ehRobo(l.status_por)) return "o televendas agendou pelo Kommo";
    if (F.ehMeu(l)) return "foi você que agendou";
    const p = F.primeiro(l.status_por);
    return p ? `quem agendou foi ${p}` : "";
  }
  const cli = l => L().nomeCli(l) || "Cliente sem nome";
  const primeiroCli = l => L().primeiro(cli(l));

  // Botões de ação para um cliente: ver na lista, ligar, WhatsApp
  function botoesCliente(l, extra) {
    const F = L(), wa = F.linkWa(l), wa2 = F.linkWa2 ? F.linkWa2(l) : "", tel = l.telefone ? F.linkTel(l) : "";
    return `<div class="fe-lig-cli"><b>${esc(cli(l))}</b><small>${esc(extra || "")}</small><span>` +
      `<button onclick="FE_LIG.abrirCliente(${l.id})">Ver na lista</button>` +
      (tel ? `<a href="${esc(tel)}">📞 Ligar</a>` : "") +
      (wa ? `<a href="${esc(wa)}" target="_blank" rel="noopener">WhatsApp</a>` : "") +
      (wa2 ? `<a href="${esc(wa2)}" target="_blank" rel="noopener" title="2ª mensagem: endereço e mapa da loja">📍 Endereço</a>` : "") + `</span></div>`;
  }
  function listaClientes(lista, extra, max = 5) {
    if (!lista.length) return;
    html(lista.slice(0, max).map(l => botoesCliente(l, extra(l))).join("") +
      (lista.length > max ? `<div class="fe-lig-mais">e mais ${lista.length - max}…</div>` : ""));
  }

  // ── Mensagem do período (manhã / tarde / noite) ──
  function mensagemDoPeriodo(curta) {
    const F = L(), eu = F.eu(), n = numeros(), nome = eu.nome ? ", " + eu.nome : "";
    const p = periodo(), gerente = eu.papel !== "vendedor";
    const quemTem = gerente ? (eu.papel === "gerente" ? "A loja tem" : "As lojas têm") : "Você tem";
    if (p === "manha") {
      const partes = [`${saudacao()}${nome}! ☀️`];
      if (n.deOntem.length) partes.push(`${gerente ? (eu.papel === "gerente" ? "A loja recebeu" : "As lojas receberam") : "Você recebeu"} ${plural(n.deOntem.length, "cliente que cotou", "clientes que cotaram")} ontem${n.deOntemFalta.length ? ` e ${n.deOntemFalta.length === n.deOntem.length ? (n.deOntem.length === 1 ? "ainda não teve contato" : "nenhum teve contato ainda") : (n.deOntemFalta.length === 1 ? "falta 1" : "faltam " + n.deOntemFalta.length) + " sem contato"}` : ", e já falou com todos 👏"}.`);
      else if (n.semContato.length) partes.push(`${quemTem} ${plural(n.semContato.length, "cliente", "clientes")} esperando o primeiro contato.`);
      if (n.agHoje.length === 1) {
        const l = n.agHoje[0];
        partes.push(`📅 Já falou com ${primeiroCli(l)} hoje? ${eu.papel === "vendedor" ? "Ficou" : "Está"} agendado para vir na loja hoje, e ${quemAgendou(l)}.`);
      } else if (n.agHoje.length) partes.push(`📅 Hoje tem ${n.agHoje.length} clientes agendados para vir na loja: ${n.agHoje.slice(0, 3).map(l => `${primeiroCli(l)} (${quemAgendou(l).replace(/^foi você que agendou$/, "você agendou").replace(/^o televendas agendou pelo Kommo$/, "televendas pelo Kommo").replace(/^quem agendou foi /, "agendado por ")})`).join(", ")}${n.agHoje.length > 3 ? "…" : ""}.`);
      if (n.agAtras.length) partes.push(`⚠️ ${plural(n.agAtras.length, "agendamento passou", "agendamentos passaram")} da data e ainda ${n.agAtras.length === 1 ? "precisa" : "precisam"} de resultado.`);
      if (curta) return partes.slice(0, 2).join(" ");
      partes.push(n.semContato.length ? sorteia(["Bora começar? Eu te mostro por qual cliente ir primeiro. 💪", "Vamos começar agora? Comece pelos de maior valor! 💪", "Partiu ligar? Um café e vamos nessa! ☕"]) : "Que tal confirmar os agendados de hoje pelo WhatsApp? 😊");
      return partes.join("\n\n");
    }
    if (p === "tarde") {
      const partes = [`${saudacao()}${nome}! 🌤️`];
      if (n.semContato.length || n.naoAtende.length) {
        partes.push(`Vamos concluir as ligações de hoje? ${quemTem} ${plural(n.semContato.length, "cliente sem contato", "clientes sem contato")}` +
          (n.naoAtende.length ? ` e ${plural(n.naoAtende.length, "que não atendeu", "que não atenderam")} (que tal uma mensagem no WhatsApp?)` : "") + ".");
      } else partes.push("Você já falou com todos os seus clientes. Mandou bem! 👏");
      if (n.agHoje.length) partes.push(`📅 ${plural(n.agHoje.length, "cliente está agendado", "clientes estão agendados")} para hoje: ${n.agHoje.slice(0, 3).map(cli).join(", ")}${n.agHoje.length > 3 ? "…" : ""}. Já ${n.agHoje.length === 1 ? "veio" : "vieram"}?`);
      if (curta) return partes.slice(0, 2).join(" ");
      if (n.semContato.length) partes.push("Bora? Eu te mostro por onde continuar. 💪");
      return partes.join("\n\n");
    }
    const partes = [`${saudacao()}${nome}! 🌙`];
    partes.push(n.fizHoje.length ? `Hoje você registrou ${plural(n.fizHoje.length, "contato", "contatos")}. Obrigada pelo empenho! 🙌` : "Hoje ainda não vi nenhum contato registrado por você.");
    if (n.semContato.length) partes.push(n.semContato.length === 1 ? "Ficou 1 cliente para amanhã cedo." : `Ficaram ${n.semContato.length} clientes para amanhã cedo.`);
    if (curta) return partes.slice(0, 2).join(" ");
    return partes.join("\n\n");
  }
  const CHIPS = ["Agendados de hoje", "Por onde começo?", "Quantos faltam?", "Quem não atende?", "Meu resumo", "Dica para ligar", "📞 Roteiro de ligação", "🎯 Treinar vendas", "🔔 Avisos no celular"];

  // ── Respostas no chat ──
  function resposta(q) {
    const F = L(); if (!F || !F.pronto()) return false;
    const n0 = N(q), eu = F.eu();
    const tem = re => re.test(n0);

    if (tem(/^(oi|ola|bom dia|boa tarde|boa noite|e ai|opa|tudo bem)\b/) && n0.split(" ").length <= 4) {
      bot(mensagemDoPeriodo(false)); chips(CHIPS); return true;
    }
    if (tem(/agend/) && tem(/hoje|vem|vir|vao/) || tem(/quem vem hoje|vem hoje/)) {
      const n = numeros();
      if (!n.agHoje.length) { bot("Hoje não tem nenhum cliente agendado para vir na loja. 😊" + (n.agAtras.length ? `\n\nMas ${plural(n.agAtras.length, "agendamento passou", "agendamentos passaram")} da data. Quer ver?` : "")); chips(n.agAtras.length ? ["Agendados atrasados", "Por onde começo?"] : CHIPS); return true; }
      bot(`📅 ${plural(n.agHoje.length, "cliente agendado", "clientes agendados")} para hoje. Que tal mandar um WhatsApp confirmando?`);
      listaClientes(n.agHoje, l => quemAgendou(l) + (l.responsavel_nome && eu.papel !== "vendedor" && !quemAgendou(l).endsWith(l.responsavel_nome) ? " · cliente de " + l.responsavel_nome : ""));
      html(`<button class="fe-lig-bt" onclick="FE_LIG.abrirAgenda('hoje')">Abrir os agendados de hoje →</button>`);
      return true;
    }
    if (tem(/agend/) && tem(/atras|passou|venceu|esquec/)) {
      const n = numeros();
      if (!n.agAtras.length) { bot("Nenhum agendamento atrasado. 👏"); return true; }
      bot(`⚠️ ${plural(n.agAtras.length, "cliente estava agendado", "clientes estavam agendados")} e a data já passou. Ligue para saber se ainda vem, ou marque o resultado (Venda ganha com a O.S., ou Venda perdida com o motivo).`);
      listaClientes(n.agAtras, l => "era " + F.fmtData(l.agendado_para) + " · " + quemAgendou(l));
      html(`<button class="fe-lig-bt" onclick="FE_LIG.abrirAgenda('atrasados')">Abrir os atrasados →</button>`);
      return true;
    }
    if (tem(/agend/) && tem(/amanha/)) {
      const am = numeros().meus.filter(l => l.status === "agendou" && l.agendado_para === somaDias(F.hoje(), 1));
      bot(am.length ? `📅 Amanhã: ${plural(am.length, "cliente agendado", "clientes agendados")}.` : "Amanhã ainda não tem ninguém agendado.");
      listaClientes(am, l => quemAgendou(l)); if (am.length) html(`<button class="fe-lig-bt" onclick="FE_LIG.abrirAgenda('amanha')">Abrir os de amanhã →</button>`);
      return true;
    }
    if (tem(/agend/) && tem(/sem data|kommo/)) {
      const n = numeros();
      bot(n.agSemData.length ? `${plural(n.agSemData.length, "cliente foi agendado", "clientes foram agendados")} pelo televendas no Kommo e ainda sem a data da visita. Vale ligar e combinar o dia!` : "Não tem agendado sem data. 👍");
      listaClientes(n.agSemData, () => "o televendas agendou pelo Kommo");
      return true;
    }
    if (tem(/por onde|comeco|comecar|proximo|qual (cliente )?ligar|quem ligar|ligo pra quem|ligar primeiro|prioridade/)) {
      const n = numeros();
      const fila = n.semContato.slice().sort((a, b) => Number(b.valor || 0) - Number(a.valor || 0));
      if (!fila.length) {
        if (n.naoAtende.length) { bot("Todos já tiveram contato! 👏 Agora vale tentar de novo quem não atendeu, de preferência pelo WhatsApp:"); listaClientes(n.naoAtende, l => `não atendeu ${F.tentativas(l)}x`, 3); return true; }
        bot("Você já falou com todos os seus clientes. Mandou bem! 👏"); return true;
      }
      const l = fila[0];
      bot(`Comece por ${cli(l)}: é a cotação de maior valor (${F.fmtR0(l.valor)})${l.medida ? `, pneu ${l.medida}` : ""}, cotou em ${F.fmtData(l.data_cotacao)}. 💪` +
          (fila.length > 1 ? `\n\nDepois: ${fila.slice(1, 3).map(x => `${cli(x)} (${F.fmtR0(x.valor)})`).join(" e ")}.` : ""));
      listaClientes(fila.slice(0, 3), x => F.fmtR0(x.valor) + (x.medida ? " · " + x.medida : ""), 3);
      chips(["Dica para ligar", "Quantos faltam?", "Agendados de hoje"]);
      return true;
    }
    // "faltou algum?", "ficou faltando alguém?", "esqueci de ligar para alguém?" (Monitor, 27/11/2026)
    if (tem(/quantos|falt(a|am|ou|ando)|pendente|sem contato|em aberto|ainda tenho|esqueci|ficou (algum|alguem)|deixei (de|algum)/)) {
      const n = numeros();
      bot(`${eu.papel === "vendedor" ? "Seus números" : "Os números" + (eu.loja ? " da " + eu.loja : "")}:\n` +
        `· ${plural(n.semContato.length, "cliente sem contato", "clientes sem contato")}\n` +
        `· ${plural(n.naoAtende.length, "não atendeu", "não atenderam")} (tentar WhatsApp)\n` +
        (n.retornar.length ? `· ${plural(n.retornar.length, "pediu retorno", "pediram retorno")}\n` : "") +
        `· ${plural(n.agHoje.length, "agendado", "agendados")} para hoje` + (n.agAtras.length ? ` e ${n.agAtras.length} atrasado(s)` : "") + "\n" +
        `· ${F.fmtR0(n.valorAberto)} em cotações abertas`);
      if (n.semContato.length) html(`<button class="fe-lig-bt" onclick="FE_LIG.abrirAba('pendentes')">Abrir os pendentes →</button>`);
      chips(["Por onde começo?", "Quem não atende?", "Agendados de hoje"]);
      return true;
    }
    if (tem(/nao atende|nao atendeu|nao atendem|caixa postal|nao responde|whats|zap/)) {
      const n = numeros();
      if (!n.naoAtende.length) { bot("Ninguém na lista de \"não atendeu\" agora. 👍"); return true; }
      bot(`${plural(n.naoAtende.length, "cliente não atendeu", "clientes não atenderam")}. Da 2ª tentativa em diante, o WhatsApp funciona melhor: o botão já abre com a mensagem pronta. 😉`);
      listaClientes(n.naoAtende, l => `${F.tentativas(l)}x sem atender`);
      return true;
    }
    if (tem(/resumo|como (eu )?estou|meu dia|desempenho|minhas vendas|quanto (eu )?vendi|como foi/)) {
      const n = numeros(), tot = n.meus.length;
      bot(`${eu.papel === "vendedor" ? "Seu resumo" : "Resumo"} (últimos dias na lista):\n` +
        `· ${plural(tot, "cliente recebido", "clientes recebidos")}, ${n.trabalhados} com contato (${tot ? Math.round(n.trabalhados * 100 / tot) : 0}%)\n` +
        `· ${plural(n.ganhas.length, "venda ganha", "vendas ganhas")} ${eu.papel === "vendedor" ? "por você" : "pela loja"}` +
        (n.ganhas.length ? ` (${F.fmtR0(n.ganhas.reduce((t, l) => t + Number(l.valor || 0), 0))})` : "") + "\n" +
        `· ${n.sistema.length} compraram sem ser marcadas pela loja (🤖 Sistema)\n` +
        `· hoje: ${plural(n.fizHoje.length, "contato registrado", "contatos registrados")}`);
      if (n.sistema.length > n.ganhas.length) bot("Dica: quando o cliente comprar com você, marque \"Venda ganha\" com o nº da O.S. Assim a venda conta para você! 🏆");
      return true;
    }
    if (tem(/dica|o que (eu )?falo|o que falar|como (eu )?falo|como abordar|script|argumento|objec|ta caro|achou caro|vou pensar/)) {
      bot(sorteia([
        "Dica: comece pelo nome e lembre a cotação: \"Oi, Lúcia! Aqui é da Fox Pneus. Você fez um orçamento ontem do pneu 175/65R14, ficou alguma dúvida?\". Pergunte, não empurre. 😊",
        "Se o cliente disser \"vou pensar\": pergunte o que ficou de dúvida (preço, prazo, medida?) e convide para passar na loja para ver o pneu de perto. Combine o dia e marque \"Agendou\" com a data. 📅",
        "Se achar caro: mostre o valor (garantia, montagem, alinhamento) e, se tiver desconto autorizado, consulte no FOXNET. Nunca prometa pneu separado nem horário reservado. 😉",
        "Não atendeu duas vezes? Mande WhatsApp: é mais fácil para o cliente responder quando puder. O botão já abre com a mensagem pronta. 📲",
        "Ligue nos horários que o cliente costuma atender: no fim da manhã e no fim da tarde costuma funcionar melhor. ☎️",
      ]));
      chips(["Outra dica", "Por onde começo?", "Agendados de hoje"]);
      return true;
    }
    if (tem(/outra dica/)) return resposta("dica");
    // Avisos no computador e no celular
    if (tem(/desliga|parar|nao quero/) && tem(/aviso|notifica|lembrete/)) {
      F.avisos.desativar().then(() => bot("Pronto, desliguei os avisos neste aparelho. Se quiser de volta, é só pedir! 🔕"));
      return true;
    }
    if (tem(/aviso|notifica|lembrete|me avisa|me lembra|celular/)) {
      bot("Um instante, vou ligar os avisos… Se o navegador perguntar, clique em \"Permitir\". 🔔");
      F.avisos.ativar().then(r => { bot(F.avisos.texto(r)); if (r === "ativo") chips(CHIPS); });
      return true;
    }
    // Como fazer (ajuda da tela)
    if (tem(/como/) && tem(/venda ganha|ganhei|vendi|marcar venda|o\.?s/)) { bot("Para marcar a venda: escolha \"Venda ganha\" no Status E digite o nº da O.S. A venda só é salva com os dois. ✅"); return true; }
    if (tem(/como/) && tem(/agend|marcar visita/)) { bot("Para agendar: escolha a data na coluna \"Data agendamento\". O status muda para \"Agendou\" sozinho. No dia, eu te lembro! 📅"); return true; }
    if (tem(/como/) && tem(/perdid|perdi|desist|motivo/)) { bot("Para venda perdida: escolha o motivo na coluna \"Motivo da perda\". Se for \"Outro motivo\", escreva na Anotação. ❌"); return true; }
    if (tem(/desfaz|errei|marquei errado/)) { bot("Marcou errado? Logo depois de salvar aparece \"↶ Desfazer\" por alguns segundos, embaixo na tela. Se já passou, é só escolher o status certo de novo. 😉"); return true; }
    if (tem(/ferias/)) {
      bot(eu.papel === "gerente" || eu.papel === "admin" ? "Para férias: no painel \"Vendedores\" no alto da lista, clique em \"Colocar de férias\" e escolha o dia que a pessoa volta. Os clientes dela passam na hora para os outros. 🏖️"
        : "Férias quem marca é o gerente da loja. Avise ele(a) para os seus clientes irem para os colegas enquanto você estiver fora. 🏖️");
      return true;
    }
    if (tem(/trocar|passar|transferir/) && tem(/cliente|responsavel|vendedor/)) {
      bot(eu.papel === "gerente" || eu.papel === "admin" ? "Para passar um cliente para outro vendedor: na coluna \"Responsável\", escolha o nome. Fica registrado no histórico." : "Só o gerente da loja troca o responsável de um cliente. Fale com ele(a). 😊");
      return true;
    }
    if (tem(/robo|sistema|televendas|kommo/) && tem(/o que|quem|significa|por que|porque/)) {
      bot("Quando aparece \"🤖 Sistema\" é o robô: \"Sistema (Movere)\" quer dizer que o cliente comprou e a loja não marcou a venda; \"Sistema (Kommo)\" quer dizer que o televendas agendou pelo Kommo. Isso não conta ponto para ninguém. Marque você a venda com a O.S. para contar para você! 🏆");
      return true;
    }
    return false;
  }
  const somaDias = (iso, d) => new Date(new Date(iso + "T12:00:00").getTime() + d * 864e5).toISOString().slice(0, 10);

  // ── Boas-vindas ao abrir a conversa ──
  function boasVindas() {
    if (!L() || !L().pronto()) { bot("Oi! Aqui é a Fernanda. 🦊 Entre com o seu e-mail que eu te ajudo com as ligações."); return; }
    // A mensagem do robô dos avisos (a mesma do computador/celular) vale mais que a conta feita aqui
    if (ultimoRobo) bot((ultimoRobo.titulo ? ultimoRobo.titulo + "\n\n" : "") + ultimoRobo.texto);
    else bot(mensagemDoPeriodo(false));
    const n = numeros();
    if (periodo() !== "noite" && n.agHoje.length > 1) listaClientes(n.agHoje, quemAgendou, 3);
    chips(CHIPS);
    // Oferece os avisos no computador/celular (uma vez por aparelho, enquanto estiverem desligados)
    const F = L(); let ofereceu = false; try { ofereceu = !!localStorage.getItem("fe_lig_avisos_oferta"); } catch (e) {}
    if (F.avisos && !ofereceu) F.avisos.estado().then(st => {
      if (st !== "desligado" && st !== "iphone_instalar") return;
      try { localStorage.setItem("fe_lig_avisos_oferta", "1"); } catch (e) {}
      bot("Quer que eu te avise aqui no " + (/Mobi|Android|iPhone/.test(navigator.userAgent) ? "celular" : "computador") +
          ", mesmo com a página fechada? 🔔 De segunda a sábado, 2 vezes de manhã e 2 à tarde, só com os seus números.");
      chips(["Sim, quero receber avisos", ...CHIPS.slice(0, 3)]);
    });
  }

  // ── Mensagens do robô dos avisos (as mesmas do computador/celular), guardadas no banco (SQL 23) ──
  // Quem está com a página aberta recebe também aqui, na raposa: a cada 5 minutos a Fernanda confere se chegou
  // mensagem nova (manhã, meio da manhã, tarde, fim do dia).
  let ultimoRobo = null;
  async function conferirRobo() {
    const F = L(); if (!F || !F.pronto() || !F.avisoRobo) return false;
    const m = await F.avisoRobo(); if (!m) return false;
    ultimoRobo = m;
    const eu = F.eu(), chave = `fe_lig_robo_${eu.id || eu.email}_${F.hoje()}_${m.turno}`;
    let ja = false; try { ja = !!localStorage.getItem(chave); } catch (e) {}
    if (ja) return true;
    const bub = document.getElementById("feBub"), painel = document.getElementById("fePanel");
    const txt = (m.titulo ? m.titulo + " " : "") + m.texto;
    if (painel && painel.classList.contains("on")) { bot((m.titulo ? m.titulo + "\n\n" : "") + m.texto); chips(CHIPS); }
    else if (bub) { const fx = bub.querySelector(".fx"); bub.textContent = ""; if (fx) bub.appendChild(fx); bub.appendChild(document.createTextNode(txt)); bub.style.display = ""; }
    try { localStorage.setItem(chave, "1"); localStorage.setItem(chaveAviso(), "1"); } catch (e) {}
    return true;
  }
  setInterval(conferirRobo, 5 * 60 * 1000);

  // ── Balão perto da Fernanda: um aviso por período do dia, para quem está logado ──
  function chaveAviso() { const F = L(), eu = F.eu(); return `fe_lig_aviso_${eu.id || eu.email}_${F.hoje()}_${periodo()}`; }
  async function mostrarBalao(force) {
    const F = L(), bub = document.getElementById("feBub"), painel = document.getElementById("fePanel");
    if (!F || !F.pronto() || !bub) return;
    if (!force && await conferirRobo()) return;          // já tem a mensagem do robô de hoje
    const chave = chaveAviso();
    let ja = false; try { ja = !!localStorage.getItem(chave); } catch (e) {}
    if (ja && !force) return;
    const txt = mensagemDoPeriodo(true);
    const fx = bub.querySelector(".fx");
    bub.textContent = ""; if (fx) bub.appendChild(fx); bub.appendChild(document.createTextNode(txt));
    if (painel && painel.classList.contains("on")) { bot(mensagemDoPeriodo(false)); chips(CHIPS); }
    else bub.style.display = "";
    try { localStorage.setItem(chave, "1"); } catch (e) {}
  }
  let periodoVisto = null;
  window.addEventListener("fe-lig", () => {
    if (periodoVisto === null) { periodoVisto = periodo(); setTimeout(() => mostrarBalao(false), 600); }
  });
  // A página fica aberta o dia todo: na virada da manhã → tarde → noite, a Fernanda dá o novo aviso
  setInterval(() => { if (periodoVisto !== null && periodo() !== periodoVisto) { periodoVisto = periodo(); mostrarBalao(false); } }, 5 * 60 * 1000);

  // Estilo dos cartões de cliente dentro da conversa
  const st = document.createElement("style");
  st.textContent = ".fe-lig-cli{background:#F7F8FA;border:1px solid #E4E7EB;border-radius:10px;padding:8px 10px;margin:4px 0;font-size:13px;color:#1F2937}" +
    ".fe-lig-cli b{display:block}.fe-lig-cli small{display:block;color:#6B7280;margin:2px 0 6px}" +
    ".fe-lig-cli span{display:flex;gap:6px;flex-wrap:wrap}.fe-lig-cli button,.fe-lig-cli a,.fe-lig-bt{background:#fff;border:1px solid #D1D5DB;border-radius:8px;padding:4px 9px;font-size:12px;font-weight:600;color:#1F2937;cursor:pointer;text-decoration:none}" +
    ".fe-lig-cli a[target]{background:#DCFCE7;border-color:#86EFAC;color:#166534}.fe-lig-bt{display:block;margin:6px 0;background:#1F2937;color:#fff;border-color:#1F2937}" +
    ".fe-lig-mais{font-size:12px;color:#6B7280;margin:2px 0 6px}";
  document.head.appendChild(st);

  window.feLig = {resposta, boasVindas, mostrarBalao, mensagemDoPeriodo, numeros};
})();
