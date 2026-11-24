/* ═════════════════════════════════════════════════════════════════════════
   FERNANDA · Conhecimento de pneus (estudo "Pneus" da Fox, enviado pelo TI em 24/11/2026)

   Carregado pelo fernanda-ajuda.js em todas as telas. Sem IA externa: respostas prontas,
   escolhidas por palavras-chave, e contas feitas aqui no navegador.
   · Segmentos (liso, HT, AT, TA, MUD/MT, carga) e qual indicar pelo uso do cliente;
   · Ler a medida (ex.: 205/55R16 91V): largura, altura, radial, aro, carga, velocidade e diâmetro;
   · Medida alternativa (ex.: 175/65R14 → 175/70R14, sempre conferindo na loja) e diferença de diâmetro;
   · Medidas que a Fox tem em A/T;
   · Quando trocar (sulco, TWI), validade e DOT (idade do pneu), etiqueta do INMETRO, run-flat,
     válvula, balanceamento, torque e alinhamento.
   Responde só quando a mensagem é sobre pneu (para não atrapalhar o cadastro de desconto).
   ═════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  const N = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  const bot = t => window.feBot(t);
  const chips = l => window.feRenderChips && window.feRenderChips(l);
  const fmt = (v, d = 0) => Number(v).toLocaleString("pt-BR", {maximumFractionDigits: d, minimumFractionDigits: d});

  // ── Tabelas ──
  const VELOCIDADE = {J: 100, K: 110, L: 120, M: 130, N: 140, P: 150, Q: 160, R: 170, S: 180, T: 190, U: 200, H: 210, V: 240, W: 270, Y: 300};
  const CARGA = {60: 250, 61: 257, 62: 265, 63: 272, 64: 280, 65: 290, 66: 300, 67: 307, 68: 315, 69: 325, 70: 335, 71: 345, 72: 355, 73: 365,
    74: 375, 75: 387, 76: 400, 77: 412, 78: 425, 79: 437, 80: 450, 81: 462, 82: 475, 83: 487, 84: 500, 85: 515, 86: 530, 87: 545, 88: 560,
    89: 580, 90: 600, 91: 615, 92: 630, 93: 650, 94: 670, 95: 690, 96: 710, 97: 730, 98: 750, 99: 775, 100: 800, 101: 825, 102: 850, 103: 875,
    104: 900, 105: 925, 106: 950, 107: 975, 108: 1000, 109: 1030, 110: 1060, 111: 1090, 112: 1120, 113: 1150, 114: 1180, 115: 1215, 116: 1250,
    117: 1285, 118: 1320, 119: 1360, 120: 1400, 121: 1450, 122: 1500, 123: 1550, 124: 1600, 125: 1650, 126: 1700};
  // Medidas em que a Fox tem pneu misto (A/T). Outras medidas que começam com 1 não têm A/T.
  const AT_FOX = ["175/70R14", "175/75R14", "175/80R14", "205/60R15", "205/65R15", "205/70R15"];
  // Situações do estudo: cliente quer X → podemos oferecer Y (sempre com o cliente conferindo na loja)
  const ALTERNATIVA = {"175/65R14": "175/70R14", "175/70R14": "175/75R14"};

  const SEGMENTOS = [
    ["Liso (asfalto)", /\bliso\b/, "indicado para quem roda 100% no asfalto."],
    ["HT", /\bht\b/, "uso misto leve: para quem roda mais no asfalto, mas às vezes pega estrada de chão. 70% asfalto e 30% chão."],
    ["AT", /\bat\b|a\/t/, "para quem roda tanto no asfalto quanto na estrada de terra, com desempenho equilibrado. 50% asfalto e 50% chão."],
    ["TA (All Terrain)", /segmento ta\b|pneu ta\b|all ?terrain/, "para os fãs de off-road que querem o melhor desempenho em terreno irregular, com visual arrojado e agressivo. 40% asfalto e 60% chão."],
    ["MUD (M/T)", /\bmud\b|m\/t/, "os famosos M/T: ideais para quem ama trilha e lugares quase inexplorados. 20% asfalto e 80% chão."],
  ];
  const TXT_SEG = "🛞 Segmentos de pneu (do mais asfalto ao mais terra):\n" +
    SEGMENTOS.map(([n, , t]) => `· ${n}: ${t}`).join("\n") +
    "\n· CARGA: para veículos que levam mais peso ou trabalham com carga (ex.: Doblô, Strada, Fiorino)." +
    "\n\nMe diga quanto o cliente roda na terra (ex.: \"roda 40% na terra\") que eu indico o segmento.";

  // ── Ler a medida ──
  // Aceita 205/55R16 91V · 205/55 R16 · 175/70/14 · P215/65R15 89H · 195/75R16C 107/105R
  const RE_MEDIDA = /\b(p|lt|st)?\s*(\d{3})\s*\/\s*(\d{2})\s*(?:z?r|\/|-|\s)\s*(\d{2})(?:\s*(c|lt))?(?:\s+(\d{2,3})(?:\/(\d{2,3}))?\s*([a-z])\b)?/i;
  function lerMedida(t) {
    const m = String(t).match(RE_MEDIDA); if (!m) return null;
    const md = {cat: (m[1] || "").toUpperCase(), larg: +m[2], perfil: +m[3], aro: +m[4], c: (m[5] || "").toUpperCase(),
      carga: m[6] ? +m[6] : null, carga2: m[7] ? +m[7] : null, vel: m[8] ? m[8].toUpperCase() : null};
    if (md.larg < 125 || md.larg > 355 || md.perfil < 25 || md.perfil > 95 || md.aro < 12 || md.aro > 24) return null;
    md.nome = `${md.larg}/${md.perfil}R${md.aro}${md.c}`;
    md.altura = md.larg * md.perfil / 100;
    md.diam = md.aro * 25.4 + 2 * md.altura;
    return md;
  }
  const CATEG = {P: "P = pneu de passeio.", LT: "LT = caminhões leves e alguns SUVs maiores.", ST: "ST = reboques e motor-homes.",
    C: "C = caminhões, vans e picapes de maior porte (pneu de carga)."};
  function explicarMedida(md) {
    const l = [`📏 ${md.cat}${md.nome}${md.carga ? " " + md.carga + (md.carga2 ? "/" + md.carga2 : "") + (md.vel || "") : ""}:`];
    if (md.cat) l.push("· " + CATEG[md.cat]);
    l.push(`· ${md.larg} = largura: ${md.larg} mm, medida de lado a lado no costado (a lateral do pneu), não na banda que encosta no chão.`);
    l.push(`· ${md.perfil} = altura: ${md.perfil}% da largura, cerca de ${fmt(md.altura)} mm.`);
    l.push("· R = construção radial.");
    l.push(`· ${md.aro} = aro (diâmetro da roda) de ${md.aro} polegadas.`);
    if (md.c) l.push("· " + CATEG[md.c === "LT" ? "LT" : "C"]);
    if (md.carga) l.push(`· ${md.carga}${md.carga2 ? "/" + md.carga2 : ""} = índice de carga: ${CARGA[md.carga] ? "até " + fmt(CARGA[md.carga]) + " kg por pneu" : "veja a tabela do fabricante"}${md.carga2 ? " (montado sozinho; o 2º número vale para rodado duplo)" : ""}.`);
    if (md.vel) l.push(`· ${md.vel} = índice de velocidade: ${VELOCIDADE[md.vel] ? "até " + VELOCIDADE[md.vel] + " km/h" : "veja a tabela do fabricante"}.`);
    l.push(`\nAltura total do pneu (diâmetro): cerca de ${fmt(md.diam)} mm.`);
    if (md.carga || md.vel) l.push("Na troca, respeite pelo menos o índice de carga e o de velocidade do pneu original (pode ser maior, nunca menor).");
    if (AT_FOX.includes(md.nome)) l.push("✅ Nessa medida a Fox tem pneu misto (A/T).");
    if (ALTERNATIVA[md.nome]) l.push(`💡 Se faltar essa medida, dá para oferecer ${ALTERNATIVA[md.nome]}, mas o cliente precisa ir à loja para conferir se serve no carro dele.`);
    return l.join("\n");
  }
  function compararMedidas(a, b) {
    const dif = (b.diam - a.diam) / a.diam * 100;
    const txt = `📐 ${a.nome}: cerca de ${fmt(a.diam)} mm de altura total.\n📐 ${b.nome}: cerca de ${fmt(b.diam)} mm.\n\nDiferença: ${dif >= 0 ? "+" : ""}${fmt(dif, 1)}%` +
      (Math.abs(dif) < 3.05 ? " (pequena)." : Math.abs(dif) < 5 ? " (um pouco maior: confira com mais cuidado na loja)." : " (grande: normalmente não é recomendada).") +
      (b.aro !== a.aro ? `\n⚠️ O aro é diferente (${a.aro} → ${b.aro}): precisa trocar a roda.` : "") +
      "\n\nRegra da Fox: pode oferecer a medida parecida, mas sempre avise o cliente que ele precisa ir à loja para conferir se serve no carro dele (folga na caixa de roda, suspensão, velocímetro).";
    return txt;
  }

  // ── Respostas prontas (do estudo) ──
  const TEMAS = [
    {re: /(quando|hora de|preciso|devo|tem que)\s*(trocar|substituir)|troca do pneu|sulco|twi|treadwear|profundidade|careca|gasto|desgast(e|ado) .*pneu|1[,.]6 ?mm/,
     txt: "🔧 Quando trocar o pneu:\n· Pneu novo tem cerca de 8 mm de sulco (varia pelo segmento).\n· Troca preventiva: com 3 mm.\n· Troca obrigatória: com 1,6 mm. Nesse ponto o pneu ainda parece pneu, mas já não escoa a água: risco alto de aquaplanagem e desempenho muito comprometido.\n\nComo medir: no meio dos sulcos tem uns \"calombinhos\", o TWI (indicador de desgaste da banda). Quando a borracha chega na altura dele, é hora de trocar. Dá para medir com profundímetro ou paquímetro: meça todos os sulcos e considere o MENOR, sempre no lugar onde fica o TWI.\n\nMe diga quantos mm o pneu tem (ex.: \"sulco 2 mm\") que eu te digo se já precisa trocar."},
    {re: /validade|vence|venc(e|ido)|idade do pneu|quanto tempo dura|pneu velho|ressecad|fissura|rachad|ozonio|garantia/,
     txt: "📅 Pneu tem validade?\nPneu é de borracha, e a borracha sofre oxidação pelo ozônio do ar. Com o tempo, a estrutura muda: o pneu fica duro, faz mais barulho (\"ronca\"), aparecem microfissuras e ele perde aderência.\n\nOs fabricantes dão garantia de 5 anos contra defeito de fabricação (ex.: problema de construção, descolamento da banda, \"aneurisma\"/bolha que surge com o tempo).\n\nPara saber a idade, veja o código DOT na lateral: os 4 últimos números são a semana e o ano de fabricação. Me mande os 4 números (ex.: \"DOT 2324\") que eu calculo a idade."},
    {re: /\bdot\b|data de fabrica|fabricacao do pneu|semana .*ano/,
     txt: "🔎 DOT: é um registro obrigatório (vem de uma lei do Departamento de Transporte dos Estados Unidos) gravado na lateral de todo pneu. Os 4 últimos números são a semana e o ano de fabricação: \"2324\" = semana 23 de 2024. Me mande os 4 números que eu calculo a idade do pneu."},
    {re: /etiqueta|inmetro|selo|resistencia ao rolamento|economia de combustivel|aderencia no molhado|ruido|decibe|\bdb\b|barulho do pneu|qualidade do pneu|pneu (e )?bom/,
     txt: "🏷️ Etiqueta do INMETRO (obrigatória em todo pneu no Brasil), com 3 critérios:\n· ⛽ Resistência ao rolamento (bomba de combustível): de A (mais eficiente, menos combustível) a G. Pode economizar até 2% de combustível.\n· 💧 Aderência no molhado (nuvem com gotas): frenagem no piso molhado. Um carro com pneu A pode frear até 4 metros antes que um com pneu E.\n· 🔊 Ruído externo (ondas sonoras): 1 onda = menos barulho; 3 ondas (em vermelho) = mais barulho. Mostra também os decibéis (ex.: 72 dB). Limite para carro de passeio: 75 dB.\n\nPneu de qualidade tem a etiqueta com boas notas, dura mais (até 30% mais que outros) e mantém frenagem, curva e tração boas até o fim da vida."},
    {re: /run ?flat|rodar furado|anda furado|pneu que roda vazio|sem estepe/,
     txt: "🛞 Pneu run-flat: tem laterais reforçadas que seguram o peso do carro mesmo sem ar. Furou? Dá para seguir até um lugar seguro.\n\n✅ Vantagens:\n· Segurança: roda até 80 km a no máximo 80 km/h depois do furo (dado da Bridgestone), sem parar em lugar perigoso.\n· Conveniência: dispensa o estepe (mais espaço no porta-malas e menos peso).\n· Conforto: condução mais suave mesmo perdendo pressão.\n\n⚠️ Desvantagens:\n· Preço: geralmente mais caro.\n· Menos confortável em piso irregular (lateral mais rígida).\n· Nem toda medida existe em run-flat.\n· Exige TPMS (sensor de pressão) no carro, para avisar quando perder ar.\n\nUma pesquisa da Michelin mostrou que 70% de quem usa run-flat se sente mais seguro em caso de furo."},
    {re: /valvula|tpms|sensor de pressao|bico do pneu/,
     txt: "🔧 Válvula: troque sempre que trocar o pneu, porque válvula velha pode comprometer o pneu novo. Se o carro tem TPMS (sensor de pressão dos pneus), cuidado ao desmontar para não danificar a válvula/sensor."},
    {re: /balancea|vibra|trepid|volante (tremendo|treme|vibra)/,
     txt: "⚖️ Balanceamento: é essencial para evitar vibração e desgaste irregular. Faça sempre que trocar ou consertar pneu."},
    {re: /alinhament|converg|camb(er|agem)|puxando|carro puxa|desgaste (irregular|de um lado|na borda)/,
     txt: "📐 Alinhamento: verifique com regularidade. Garante desgaste por igual dos pneus e segurança. Os ângulos de convergência, cambagem (camber) e a posição do volante afetam a estabilidade e o desgaste dos pneus. Carro puxando para um lado ou pneu gastando só numa borda são sinais de que precisa alinhar."},
    {re: /torque|aperto (dos|da) (parafuso|roda)|apertar (os )?parafuso/,
     txt: "🔩 Torque: ao apertar os parafusos da roda, siga a especificação de torque do fabricante, para não danificar os componentes."},
    {re: /indice de velocidade|letra .*velocidade|velocidade (do|no) pneu|tabela de velocidade/,
     txt: "🏁 Índice de velocidade (a letra no fim da medida):\n" + Object.entries(VELOCIDADE).map(([k, v]) => `${k} = ${v} km/h`).join(" · ") +
          "\n\nNa troca, use no mínimo o índice do pneu original (pode ser maior)."},
    {re: /indice de carga|carga (do|no) pneu|quanto (de )?peso (o pneu|aguenta)|tabela de carga/,
     txt: "🏋️ Índice de carga (o número antes da letra, ex.: 91 em 205/55R16 91V): é o peso máximo por pneu. Exemplos: 82 = 475 kg · 86 = 530 kg · 88 = 560 kg · 91 = 615 kg · 94 = 670 kg · 98 = 750 kg · 102 = 850 kg · 107 = 975 kg · 112 = 1.120 kg.\nNa troca, use no mínimo o índice do pneu original (pode ser maior). Me diga um número que eu te falo o peso."},
    {re: /como (saber|ler|entender|descobrir) (a )?medida|como (e|funciona) a (medida|numeracao)|numeracao do pneu|o que significa (a )?medida|como medir (o )?pneu|largura do pneu|altura do pneu/,
     txt: "📏 Como ler a medida (ex.: P 215/65 R15 89H):\n· P = categoria (P passeio · LT caminhão leve/SUV grande · ST reboque e motor-home · C caminhão, van e picape grande).\n· 215 = largura em mm, medida no costado (lateral), não na banda de rodagem. Para medir, o pneu tem que estar montado no aro e suspenso (sem o peso do carro), senão a largura muda.\n· 65 = altura: 65% da largura.\n· R = radial.\n· 15 = aro, em polegadas.\n· 89 = índice de carga (peso por pneu).\n· H = índice de velocidade.\n\nMe mande uma medida (ex.: 205/55R16 91V) que eu explico parte por parte."},
    {re: /pneu original|veio de fabrica|mesmo pneu de fabrica|melhor pneu|qual pneu (comprar|escolher|indicar)/,
     txt: "🤝 Qual pneu indicar: o melhor pneu é o que dá o melhor desempenho para o USO e o ORÇAMENTO do cliente. Não se prenda ao que veio no carro: não é porque veio de fábrica que é o melhor para o uso dele. Pergunte onde ele roda (asfalto/terra), quanto quer investir e o que espera do pneu. Só respeite pelo menos o índice de carga e de velocidade do original."},
  ];

  const ehSobrePneu = n => /pneu|carro puxa|puxando para|volante (treme|tremendo|vibra)|medida|aro\b|sulco|twi|\bdot\b|run ?flat|etiqueta|inmetro|segment|\bht\b|a\/t|\bat\b|m\/t|\bmud\b|all ?terrain|balancea|alinhament|valvula|tpms|indice de (carga|velocidade)|aquaplana|desgaste|calibr/.test(n);
  const ehPergunta = (q, n) => /\?|^(o que|oq|como|qual|quais|quando|quanto|pode|posso|serve|tem |da pra|explica|me explica|significa|diferenca|vale a pena|e bom|devo|preciso)/.test(n) || /\?\s*$/.test(q);

  function resposta(q) {
    const n = N(q);
    const naTelaDeCadastro = !!document.querySelector("[data-fe]");
    const medidas = [...String(q).matchAll(new RegExp(RE_MEDIDA.source, "gi"))].map(m => lerMedida(m[0])).filter(Boolean);

    // DOT com 4 números: idade do pneu
    const dot = n.match(/\bdot\b[^\d]*(?:[a-z0-9]{2,}\s+)*?(\d{2})(\d{2})\b/) || (/(fabrica|semana)/.test(n) && n.match(/\b(\d{2})(\d{2})\b/));
    if (dot) {
      const sem = +dot[1], ano = 2000 + +dot[2], hoje = new Date();
      if (sem >= 1 && sem <= 53 && ano <= hoje.getFullYear()) {
        const fab = new Date(ano, 0, 1 + (sem - 1) * 7), anos = (hoje - fab) / (365.25 * 864e5);
        bot(`📅 DOT ${dot[1]}${dot[2]}: fabricado na semana ${sem} de ${ano}, tem cerca de ${anos < 1 ? fmt(anos * 12) + " meses" : fmt(anos, 1).replace(",0", "") + " anos"}.` +
            (anos > 5 ? "\n⚠️ Já passou dos 5 anos da garantia de fabricação. Confira se a borracha está dura, com fissuras ou ressecada." : anos > 3 ? "\nAinda dentro dos 5 anos da garantia de fabricação, mas fique de olho no ressecamento." : "\n✅ Pneu novo, dentro da garantia de fabricação."));
        return true;
      }
    }
    // Sulco em mm: precisa trocar?
    const sulco = n.match(/(sulco|profundidade|borracha|banda|twi)[^\d]{0,25}(\d+(?:[.,]\d+)?)\s*(mm|milimetro)?/) || (/pneu/.test(n) && n.match(/(\d+(?:[.,]\d+)?)\s*(mm|milimetro)/));
    if (sulco) {
      const mm = parseFloat((sulco[2] && /\d/.test(sulco[2]) ? sulco[2] : sulco[1]).replace(",", "."));
      if (mm > 0 && mm <= 20) {
        bot(mm <= 1.6 ? `🚨 Com ${fmt(mm, 1)} mm a troca é OBRIGATÓRIA (limite: 1,6 mm). O pneu já não escoa a água: risco de aquaplanagem.` :
            mm <= 3 ? `⚠️ Com ${fmt(mm, 1)} mm já é hora da troca preventiva (a partir de 3 mm). A obrigatória é com 1,6 mm.` :
            `✅ Com ${fmt(mm, 1)} mm ainda dá para rodar (pneu novo tem cerca de 8 mm). A troca preventiva é com 3 mm e a obrigatória com 1,6 mm. Meça sempre o menor sulco, onde fica o TWI.`);
        return true;
      }
    }
    // Índice de carga ou de velocidade pedido direto
    const ic = n.match(/indice de carga\D{0,10}(\d{2,3})|carga (\d{2,3})\b/);
    if (ic && CARGA[+(ic[1] || ic[2])]) { const k = +(ic[1] || ic[2]); bot(`🏋️ Índice de carga ${k}: até ${fmt(CARGA[k])} kg por pneu (${fmt(CARGA[k] * 4)} kg nos 4 pneus).`); return true; }
    const iv = n.match(/(?:indice de velocidade|letra)\s*([a-z])\b/);
    if (iv && VELOCIDADE[iv[1].toUpperCase()]) { bot(`🏁 Índice de velocidade ${iv[1].toUpperCase()}: até ${VELOCIDADE[iv[1].toUpperCase()]} km/h.`); return true; }

    // Medidas escritas: no cadastro, só responde se for pergunta (senão é o cadastro preenchendo)
    if (medidas.length && (!naTelaDeCadastro || ehPergunta(q, n))) {
      if (medidas.length >= 2) { bot(compararMedidas(medidas[0], medidas[1])); return true; }
      const md = medidas[0];
      if (/(alternativ|no lugar|substitu|parecid|outra medida|nao tem|faltou|em falta|similar|equivalente)/.test(n)) {
        bot(ALTERNATIVA[md.nome] ? `💡 Para quem quer ${md.nome}, dá para oferecer ${ALTERNATIVA[md.nome]}. Mas avise o cliente: ele precisa ir à loja para conferir se essa medida serve no carro dele.\n\n` + compararMedidas(md, lerMedida(ALTERNATIVA[md.nome]))
          : `Para ${md.nome} eu não tenho uma alternativa no estudo. Me mande as duas medidas (ex.: \"${md.nome} ou ${md.larg}/${md.perfil + 5}R${md.aro}\") que eu comparo o tamanho. E o cliente sempre confere na loja. 😊`);
        return true;
      }
      if (/\b(at|a\/t|misto|mista)\b/.test(n)) {
        bot(AT_FOX.includes(md.nome) ? `✅ Sim! Na medida ${md.nome} a Fox tem pneu misto (A/T).` :
            String(md.larg).startsWith("1") ? `❌ Na medida ${md.nome} a Fox não tem A/T. Em medidas que começam com 1, só temos A/T em: ${AT_FOX.filter(m => m.startsWith("1")).join(", ")}.` :
            `Na medida ${md.nome} eu não tenho essa informação. As medidas com A/T que eu conheço são: ${AT_FOX.join(", ")}. Confira o estoque. 😊`);
        return true;
      }
      if (!naTelaDeCadastro || /significa|explica|o que e|como ler|entender|quer dizer/.test(n)) { bot(explicarMedida(md)); return true; }
    }
    if (!ehSobrePneu(n)) return false;
    if (naTelaDeCadastro && !ehPergunta(q, n)) return false;

    // Medidas A/T da Fox
    if (/(quais|que|tem|lista).*(medida|pneu).*(a\/t|\bat\b|misto)|(a\/t|\bat\b|misto).*(medida|temos|tem)/.test(n) && !/segmento|o que e|diferenca/.test(n)) {
      bot(`🛞 Medidas em que a Fox tem pneu misto (A/T): ${AT_FOX.join(" · ")}.\nTodas as outras medidas que começam com 1 não têm A/T.`);
      return true;
    }
    // Segmento: indica pelo uso (% de terra) ou mostra todos
    if (/segment|\bliso\b|\bht\b|\bat\b|a\/t|segmento ta\b|all ?terrain|\bmud\b|m\/t|off ?road|trilha|\bmisto\b|pneu de carga|estrada de chao|\bterra\b|\blama\b|doblo|strada|fiorino/.test(n)) {
      const pct = n.match(/(\d{1,3})\s*%?\s*(?:por cento)?\s*(?:na |de |em )?(terra|chao|estrada de chao|asfalto)/);
      if (pct) {
        let chao = +pct[1]; if (/asfalto/.test(pct[2])) chao = 100 - chao;
        const seg = chao <= 5 ? SEGMENTOS[0] : chao <= 35 ? SEGMENTOS[1] : chao <= 55 ? SEGMENTOS[2] : chao <= 70 ? SEGMENTOS[3] : SEGMENTOS[4];
        bot(`🛞 Para quem roda ${chao}% na terra e ${100 - chao}% no asfalto, o indicado é o segmento ${seg[0]}: ${seg[2]}`);
        return true;
      }
      if (/carga|doblo|strada|fiorino|furgao|van\b/.test(n)) { bot("🚚 Segmento CARGA: pneus para veículos de maior carga, porque são mais pesados ou trabalham levando carga. Veículos que geralmente usam: Doblô, Strada, Fiorino."); return true; }
      const so = !/segmentos|todos|quais|diferenca/.test(n) && SEGMENTOS.find(([, re]) => re.test(n));
      if (so) { bot(`🛞 Segmento ${so[0]}: ${so[2]}`); chips(["Quais os segmentos de pneu?", "Quais medidas têm A/T?"]); return true; }
      bot(TXT_SEG); chips(["Roda 50% na terra", "Quais medidas têm A/T?", "Como ler a medida do pneu?"]); return true;
    }
    for (const t of TEMAS) if (t.txt && t.re.test(n)) { bot(t.txt); return true; }
    if (/pneu/.test(n) && ehPergunta(q, n)) {
      bot("Sobre pneus eu sei: segmentos (liso, HT, AT, TA, MUD, carga), ler a medida, medida alternativa, quando trocar (sulco/TWI), validade e DOT, etiqueta do INMETRO, run-flat, válvula, balanceamento, alinhamento e torque. O que você quer saber? 🛞");
      chips(["Como ler a medida do pneu?", "Quando trocar o pneu?", "Quais os segmentos de pneu?", "O que é run-flat?"]);
      return true;
    }
    return false;
  }

  window.fePneus = {resposta, lerMedida, explicarMedida, compararMedidas};
})();
