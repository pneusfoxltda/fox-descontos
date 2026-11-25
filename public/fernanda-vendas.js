/* ═════════════════════════════════════════════════════════════════════════
   FERNANDA · Treinadora de vendas de alta performance (Base de Conhecimento Mestre da Fox,
   enviada pelo TI em 24/11/2026). Carregada pelo fernanda-ajuda.js em todas as telas.

   Sem IA externa: respostas prontas e avaliação por palavras-chave, aqui no navegador.
   3 modos (o vendedor escolhe):
     1. Simulação (roleplay): a Fernanda faz o papel de um cliente (produto × perfil × objeção × canal,
        mais de 500 combinações), o vendedor responde e ela dá nota de 0 a 10 em 4 pontos
        (diagnóstico, consciência técnica, armas da Fox, postura e fechamento) + a resposta modelo.
     2. Auditoria: o vendedor cola uma conversa de WhatsApp e ela aponta o que faltou.
     3. Resposta rápida: o vendedor conta a objeção ("cliente achou mais barato na internet") e ela
        entrega 2 respostas prontas.
   Também explica a filosofia (consciência gratuita, perguntar, medo × ambição, "desvender", escada de
   valor, estrada/carro/piloto), o protocolo de atendimento e os diferenciais da Fox.

   Regras da Fox nas respostas modelo (decisão do TI, 24/11/2026): nunca prometer pneu separado nem
   travar box/horário (pode não dar para cumprir); combinar o DIA da visita. A Fox NÃO faz entrega.
   Preço só fica garantido pela DATA DA COTAÇÃO: até 7 dias se a cotação foi do televendas, 3 dias se foi da loja.
   Módulo 2 (follow-up por ligação, resgate no WhatsApp, escada de condições, cobrir orçamento).
   Sem travessão nos textos da tela.
   ═════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  const N = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  const bot = t => window.feBot(t);
  const chips = l => window.feRenderChips && window.feRenderChips(l);
  const sorteia = a => a[Math.floor(Math.random() * a.length)];
  const ARMAS = "montagem gratuita + checklist preventivo completo gratuito";

  // ══════════════════════ PLAYBOOK DE OBJEÇÕES ══════════════════════
  // re: como o vendedor descreve a objeção · cliente: falas do cliente no treino · modelo: respostas Fox
  const OBJ = [
    {id: "internet", grupo: "preco", nome: "Achei mais barato na internet",
     re: /(internet|site|mercado livre|shopee|amazon|online|magalu)/,
     cliente: ["Vi esse {p} bem mais barato na internet. Consegue fazer o mesmo preço?", "No site tá mais em conta, viu? Por que aí é mais caro?"],
     modelo: ["Com certeza na internet você acha o preço seco do pneu. Mas quando soma o frete, os dias de espera e paga por fora para montar aqui na cidade, o valor final passa do nosso, e sem assistência local. Fechando aqui na Fox Pneus você já ganha a montagem totalmente gratuita e ainda leva um checklist preventivo completo gratuito do seu carro. Você sai rodando, com garantia presencial e sem surpresa na conta. Faz sentido garantir essa economia real?",
              "Pesquisar na internet é ótimo! Só me conta: nesse preço já está o frete e a montagem? Aqui na Fox a montagem é por nossa conta e você ainda ganha o checklist preventivo completo do carro. Somando tudo, normalmente sai igual ou melhor, e com garantia aqui do lado. Quer que eu te mostre a conta lado a lado?"]},
    {id: "concorrente", grupo: "preco", nome: "O concorrente fez mais barato",
     re: /(concorrente|outra loja|loja (ali|aqui|do lado)|orcamento menor|mais barato (no|na|em|ali)|fizeram (por )?menos)/,
     cliente: ["A loja aqui perto me passou um orçamento menor nesse {p}.", "O concorrente fez mais barato, vocês cobrem?"],
     modelo: ["Excelente você pesquisar! Só para a gente comparar laranja com laranja: o orçamento deles já inclui a montagem gratuita e um checklist técnico completo sem custo? Muitas vezes o preço parece menor porque cobram a montagem na hora que o carro sobe no elevador. Aqui na Fox Pneus a montagem é por nossa conta e você ainda sai com o diagnóstico preventivo gratuito. Se quiser, me manda o orçamento deles que a gente analisa junto para você não cair em pegadinha.",
              "Que bom que você comparou! Me mostra o que está incluso no orçamento deles? Aqui você não paga a montagem e ainda ganha o checklist preventivo completo. Comparando tudo, quero que você feche com quem te entrega mais."]},
    {id: "caro", grupo: "preco", nome: "Está muito caro",
     re: /((muito|ta|esta|achei|meio|bem) caro|preco alto|salgado|puxado|nao cabe no bolso)/,
     cliente: ["Nossa, achei esse {p} muito caro.", "Tá caro, hein. Não tem como melhorar?"],
     modelo: ["Entendo perfeitamente. Olhando só o valor da nota hoje parece um investimento maior, mas na ponta do lápis esse pneu roda muito mais quilômetros e entrega economia de combustível. E fechando aqui na Fox Pneus você não gasta um centavo com a montagem (é gratuita) e ainda ganha o checklist preventivo completo, para evitar gasto surpresa com suspensão e freios. Você prefere pagar menos hoje e trocar de novo logo ali na frente, ou resolver agora com tudo incluso?",
              "Te entendo! Vamos fazer a conta por quilômetro rodado? Um pneu mais barato que dura menos sai mais caro no fim. Aqui ainda tem a montagem gratuita e o checklist completo do carro. Prefere à vista no PIX com a melhor condição ou parcelado no cartão?"]},
    {id: "pesquisar", grupo: "adiamento", nome: "Vou pesquisar e depois te falo",
     re: /(vou (dar uma )?pesquis|vou ver (e|com calma)|depois te (falo|aviso|retorno|chamo)|vou pensar|vou analisar|deixa eu ver)/,
     cliente: ["Vou dar uma pesquisada e depois te falo.", "Deixa eu ver com calma e te retorno."],
     modelo: ["Claro, pesquisar faz parte! Só para te ajudar a comparar direito: lembre que na Fox Pneus você não paga pela montagem e ainda ganha o checklist completo do carro. O que ficou faltando na nossa proposta para a gente já combinar o dia da sua visita: foi a marca, a condição de parcelamento ou alguma dúvida sobre o serviço?",
              "Tranquilo! Para você comparar certo, compare com montagem e checklist inclusos, que aqui são gratuitos. Me conta: o que pesou mais, o preço, a marca ou o parcelamento? Assim eu já te mando a melhor opção."]},
    {id: "rodar", grupo: "adiamento", nome: "Ainda dá para rodar mais uns meses",
     re: /(da (pra|para) rodar|aguenta mais|ainda (da|roda|aguenta)|mais uns meses|mais um tempo)/,
     cliente: ["Acho que ainda dá pra rodar mais uns meses com esse pneu.", "Meu pneu ainda aguenta, vou deixar pra depois."],
     modelo: ["Visualmente no meio ele até engana, mas o indicador TWI já está no limite. Com o pneu nesse estágio, a frenagem na pista molhada piora muito, além do risco de multa na blitz. Fechando com a Fox Pneus você ganha a montagem gratuita e o checklist completo: vale muito mais resolver agora com segurança do que correr risco na pista.",
              "Posso te mostrar uma coisa? Esse calombinho no sulco é o TWI: quando a borracha chega nele, o pneu já não escoa água e o risco de aquaplanagem dispara. Que tal a gente medir junto? Se estiver no limite, resolve com montagem gratuita e checklist completo."]},
    {id: "cartao", grupo: "adiamento", nome: "Vou esperar o cartão virar",
     re: /(cartao (virar|fechar)|semana que vem|mes que vem|dia do pagamento|salario|quando (eu )?receber|fim do mes)/,
     cliente: ["Vou esperar o cartão virar semana que vem.", "Só consigo no mês que vem, quando receber."],
     modelo: ["Perfeito! Só um cuidado: o valor do seu orçamento fica garantido até [data: 3 dias da cotação na loja, 7 dias se foi pelo televendas]; depois disso o preço pode mudar, e o estoque gira rápido. Se quiser, já parcelamos no cartão de hoje (até 4x sem juros) e você ainda ganha a montagem gratuita e o checklist preventivo completo. Qual dia fica melhor para você passar aqui na Fox Pneus?",
              "Entendo! Uma opção: parcelar no cartão de hoje, aí a primeira parcela já cai depois do seu pagamento. E você ainda leva montagem gratuita e checklist completo. Quer que eu simule as parcelas?"]},
    {id: "dois", grupo: "quebragalho", nome: "Vou trocar só dois pneus agora",
     re: /((so|somente|apenas) (dois|2|um|1) pneus?|um par|so o par|os outros dois depois)/,
     cliente: ["Vou trocar só dois pneus agora e os outros dois depois.", "Me vê só um par por enquanto."],
     modelo: ["Tranquilo, podemos fazer os dois agora sem problema. Lembrando que, por segurança, os pneus novos vão sempre no eixo traseiro. Mas já que o seu carro vai entrar no box da Fox Pneus com montagem gratuita e checklist completo, deixa eu te mostrar a condição parcelada para levar o jogo todo: você deixa os quatro zerados de uma vez e aproveita o benefício completo numa única parada.",
              "Pode ser! Só te mostro a diferença: no parcelado, o jogo completo fica quanto por mês a mais? Assim você decide com tudo na mão. E a montagem é gratuita nos quatro."]},
    {id: "alinhar", grupo: "alinhamento", nome: "Não precisa alinhar, o carro não puxa",
     re: /(nao (precisa|preciso|quero) (de |fazer )?alinh|nao (esta|ta) puxando|nao puxa|alinhamento (nao|e besteira))/,
     cliente: ["Meu carro não está puxando, não preciso alinhar.", "Alinhamento não, só quero o pneu."],
     modelo: ["O carro puxar é só um dos sintomas. Muitas vezes a geometria está aberta por igual dos dois lados: o volante fica reto, mas vai lixando a borda interna do pneu novo. Aqui na Fox Pneus você já economizou na montagem gratuita e ainda ganha o checklist completo do carro. Vale muito investir no alinhamento agora para não perder um pneu zero em 5 mil km por desgaste irregular.",
              "Posso te mostrar no checklist gratuito como está a geometria? Se estiver tudo certo, ótimo. Se não, o alinhamento protege o pneu novo que você acabou de comprar."]},
    {id: "balancear", grupo: "alinhamento", nome: "Balanceamento é besteira",
     re: /(balance\w* (e|eh) besteira|nao (preciso|quero) (de )?balance|so ando na cidade|balanceamento nao)/,
     cliente: ["Balanceamento é besteira, só ando na cidade.", "Não precisa balancear não."],
     modelo: ["Mesmo na cidade, qualquer diferença de peso na roda gera vibração que desgasta terminais de direção e amortecedores, além de deixar o pneu escamoso. Como você já ganhou a montagem gratuita e o checklist preventivo fechando com a Fox Pneus, incluir o balanceamento agora é o que garante que o pneu novo rode liso e dure até 20% a mais.",
              "Na cidade é onde mais pega buraco e lombada, e qualquer peso diferente vira vibração no volante e desgaste no pneu novo. Vamos proteger o investimento?"]},
    {id: "alinhou", grupo: "alinhamento", nome: "Alinhei faz pouco tempo",
     re: /(fiz (o )?alinhamento|alinhei|ja alinhei|alinhamento (faz|ha|tem) (pouco|dois|2|um|1))/,
     cliente: ["Fiz alinhamento faz dois meses, não precisa fazer de novo.", "Já alinhei há pouco tempo."],
     modelo: ["Você fez com os pneus antigos já gastos, certo? Quando colocamos pneus novos, com a borracha na altura original, toda a geometria muda. Aqui na Fox Pneus a gente já te dá a montagem gratuita e o checklist completo: fazer o alinhamento agora é o que protege os pneus novos contra desgaste irregular.",
              "Ótimo que você cuida do carro! Só que com pneu novo a altura muda e o alinhamento antigo deixa de valer. É rapidinho e protege os pneus que você acabou de comprar."]},
    {id: "oleo_tempo", grupo: "oleo", nome: "O óleo ainda não venceu (km)",
     re: /(nao (atingi|chegou|deu|bateu) (a )?(quilometragem|km)|oleo (ainda )?nao venc|ainda nao (deu|chegou) (a )?(km|quilometragem))/,
     cliente: ["Não atingi a quilometragem da troca ainda, mas já faz 8 meses.", "Meu óleo ainda não venceu."],
     modelo: ["Muita gente olha só o hodômetro, mas o óleo vence por quilometragem OU por tempo (6 meses), o que vier primeiro. No anda e para da cidade, o óleo oxida e forma borra no motor. Fechando o serviço aqui na Fox Pneus você ganha um checklist preventivo completo gratuito: em 20 minutos o motor fica protegido e você ainda sai sabendo como está o resto do carro.",
              "O óleo envelhece mesmo parado: depois de 6 meses ele perde a proteção. Quer que eu veja a data da última troca e já te passo a condição?"]},
    {id: "completar", grupo: "oleo", nome: "Só completa o óleo",
     re: /((so|somente) complet|complet(a|ar) (o )?oleo|so (da|de) uma completada)/,
     cliente: ["Só completa o óleo pra mim, está um pouco baixo.", "Dá só uma completada no óleo."],
     modelo: ["Completar óleo velho com óleo novo mistura lubrificante contaminado com óleo limpo e derruba a proteção do motor na hora. Como o carro já está aqui na Fox Pneus, a troca completa com filtro novo resolve o problema na raiz, e você ainda ganha o checklist gratuito dos itens de segurança.",
              "Posso completar, mas te aviso: se está baixando, vale a gente entender o porquê no checklist gratuito. Óleo baixo pode ser vazamento ou consumo, e isso fica caro se não olhar agora."]},
    {id: "filtro", grupo: "oleo", nome: "Troca só o óleo, o filtro dá mais uma vez",
     re: /(filtro (da|aguenta|serve) (pra|para|mais)|nao (precisa|quero) (trocar )?(o )?filtro|so o oleo|sem (trocar )?(o )?filtro)/,
     cliente: ["Troca só o óleo, o filtro dá pra usar mais uma vez.", "Filtro não precisa, só o óleo."],
     modelo: ["Dentro do filtro antigo ficam retidos cerca de 300 a 500 ml de óleo velho sujo e limalhas. Se colocarmos óleo novo sem trocar o filtro, na primeira partida o óleo limpo já sai contaminado. Fechando a troca completa na Fox Pneus você garante a máxima vida útil do motor e ainda leva o checklist preventivo gratuito.",
              "O filtro é o que segura a sujeira: óleo novo com filtro velho vira óleo sujo na primeira partida. A diferença no valor é pequena perto do que protege."]},
    {id: "marca", grupo: "marca", nome: "Nunca ouvi falar dessa marca",
     re: /(nunca ouvi|marca (chinesa|importada|desconhecida|estranha)|essa marca|e boa mesmo|importad|chines)/,
     cliente: ["Nunca ouvi falar dessa marca importada, é boa mesmo?", "Pneu chinês? Tenho medo."],
     modelo: ["É super normal não conhecer de nome, porque essas marcas não gastam milhões em propaganda na TV, por isso o preço é tão competitivo. Mas o pneu tem selo do INMETRO, 5 anos de garantia de fábrica, e aqui na Fox Pneus você ainda ganha a montagem gratuita e o checklist preventivo fechando conosco.",
              "Pergunta justa! Olha a etiqueta do INMETRO: ela mostra a nota de frenagem no molhado, economia e ruído. Vamos comparar com a marca que você conhece, lado a lado?"]},
    {id: "empurrar", grupo: "desconfianca", nome: "Loja de pneu sempre inventa defeito",
     re: /(inventa(m)? (defeito|problema)|empurr|enganar|achismo|desconfi|sempre acham (um )?problema)/,
     cliente: ["Toda vez que levo o carro em loja de pneu inventam defeito na suspensão.", "Vocês não vão inventar problema, né?"],
     modelo: ["Aqui na Fox Pneus a gente não trabalha no achismo. Fechando conosco você ganha um checklist completo gratuito feito na sua frente: te chamamos no box para você ver com os próprios olhos o estado de cada peça. Você só aprova o que quiser fazer, com total transparência.",
              "Te entendo, muita gente passou por isso. Por isso o nosso checklist é feito com você do lado e com foto do que a gente encontrar. Você decide o que fazer."]},
    {id: "terceiro", grupo: "terceiro", nome: "Preciso falar com marido/esposa/sócio",
     re: /(falar com (meu|minha|o|a) (marido|esposa|mulher|socio|chefe|pai|mae|patrao)|consultar (meu|minha)|ver com (meu|minha))/,
     cliente: ["Preciso falar com meu marido antes.", "Vou ver com meu sócio e te falo."],
     modelo: ["Perfeito! Para facilitar a conversa, vou te mandar agora no WhatsApp um resumo pronto com a medida do pneu, a condição parcelada e destacando que fechando na Fox Pneus vocês já ganham a montagem gratuita e o checklist preventivo completo. Que horas vocês conversam, para eu te dar um retorno?",
              "Claro! Quer que eu monte um resumo com as duas opções (custo-benefício e premium) para vocês decidirem juntos? Que horário eu te chamo de volta?"]},
    {id: "tempo", grupo: "tempo", nome: "Estou sem tempo / não posso ficar sem carro",
     re: /((muito )?corrid|sem tempo|nao posso ficar sem (o )?carro|nao tenho tempo|correria)/,
     cliente: ["Estou muito corrido hoje, não posso ficar sem carro.", "Não tenho tempo de ficar na loja."],
     modelo: ["Na Fox Pneus a gente agiliza para não travar o seu dia: você combina o melhor horário comigo e a gente já deixa tudo organizado. Fazemos a montagem gratuita, o checklist completo e os serviços enquanto você toma um café no ar-condicionado. Fica melhor vir logo às 8h ou no horário do almoço?",
              "Entendo a correria! Me diz o melhor horário para você e eu já deixo tudo organizado para ser rápido. Cedinho ou no almoço?"]},
    {id: "manda_wpp", grupo: "ligacao", nome: "Na ligação: \"me manda no WhatsApp\"",
     re: /(me manda (no|pelo) (whats|zap|wpp)|manda (no|pelo) (whats|zap|wpp)|(pode|so) mandar (no|pelo) (whats|zap)|nao posso falar agora)/,
     cliente: ["Ah, me manda no WhatsApp que eu vejo depois.", "Agora não posso falar, me manda por mensagem."],
     modelo: ["Olha, eu só preciso de 30 segundos! Tenho uma notícia boa sobre o seu orçamento, pode ser? Jogo rápido, não vou tomar seu tempo… (Se insistir:) Mando agora mesmo! E já deixo a loja avisada do seu orçamento. Para qual dia fica melhor a sua vinda na loja, [dia A] ou [dia B]?",
              "Claro, te mando agora! Só pra eu já deixar tudo certo: você pretende passar na loja ainda essa semana, [dia A] ou [dia B]? (Regra: nunca desligue sem tentar cravar um dia.)"]},
    {id: "ml_ligacao", grupo: "ligacao", nome: "Na ligação: \"vi mais barato / no Mercado Livre\"",
     re: /(mercado livre|vi (mais )?barato|achei (mais )?barato).*(ligac|ligando|telefone)|cobrir (o )?orcamento|cobre (o )?orcamento|voces cobrem/,
     cliente: ["Ah, mas eu vi esse pneu mais barato no Mercado Livre.", "Achei mais barato em outro lugar, vocês cobrem?"],
     modelo: ["Quanto te passaram e de qual marca? (anote na hora) Me dá 30 segundos na linha que eu vejo agora mesmo com o meu gerente. (Volte NA MESMA ligação com a contraproposta, sem pedir print para depois.) Consegui! O gerente libera cobrir esse valor, com montagem gratuita e checklist completo, para você vir na loja. Fica melhor hoje à tarde ou amanhã de manhã?",
              "Ótimo você me falar! Me passa o valor e a marca que eu levo agora pro meu gerente. Se ele aprovar, você vem quando: [dia A] ou [dia B]? (Cobrir orçamento sempre com o gerente e com o dia da visita combinado.)"]},
  ];
  const GRUPO_NOME = {ligacao: "Ligação de follow-up", preco: "Preço / internet / concorrência", adiamento: "Adiamento (\"mês que vem\")", alinhamento: "Recusa de alinhamento/balanceamento",
    oleo: "Recusa de troca de óleo/filtro", marca: "Desconfiança de marca importada", desconfianca: "Medo de \"empurroterapia\"",
    terceiro: "Decisão de outra pessoa", tempo: "Falta de tempo", quebragalho: "Só 1 ou 2 pneus"};

  // ══════════════════════ MOTOR DE CENÁRIOS (ROLEPLAY) ══════════════════════
  const PRODUTOS = [["pneu aro 14", "pneu"], ["pneu aro 15/16", "pneu"], ["pneu de caminhonete A/T", "pneu"], ["pneu de van", "pneu"],
    ["alinhamento 3D", "alinhamento"], ["balanceamento", "alinhamento"], ["troca de óleo sintético", "oleo"], ["troca de óleo semissintético", "oleo"],
    ["kit de filtros", "oleo"], ["revisão de suspensão e freios", "revisao"]];
  const PERFIS = [
    ["Motorista de aplicativo", "Sou motorista de aplicativo, cada real conta e não posso ficar parado."],
    ["Pai/mãe de família", "Uso o carro para levar as crianças, me preocupo com chuva."],
    ["Dono de frota", "Tenho uma empresa com 5 carros, preciso de nota fiscal e prazo."],
    ["Pesquisador de internet", "Já pesquisei bastante na internet."],
    ["Cliente desconfiado", "Já fui enganado em oficina antes."],
    ["Cliente apressado", "Tô com pressa, vou direto ao ponto."],
    ["Cliente indeciso", "Não sei ainda, tô vendo opções."],
    ["Cliente quebra-galho", "Quero gastar o mínimo agora."],
  ];
  const OBJ_POR_PRODUTO = {pneu: ["internet", "concorrente", "caro", "pesquisar", "rodar", "cartao", "dois", "marca", "empurrar", "terceiro", "tempo"],
    alinhamento: ["alinhar", "balancear", "alinhou", "caro", "tempo", "empurrar"], oleo: ["oleo_tempo", "completar", "filtro", "caro", "tempo", "pesquisar"],
    revisao: ["empurrar", "caro", "terceiro", "tempo", "cartao", "pesquisar"]};
  const CANAIS = ["WhatsApp", "Balcão/telefone", "Ligação de follow-up"];

  function novoCenario() {
    const [prod, tipo] = sorteia(PRODUTOS), [perfil, fala] = sorteia(PERFIS), canal = sorteia(CANAIS);
    // Na ligação de follow-up também aparecem as objeções de telefone (Módulo 2)
    const idObj = sorteia(canal.startsWith("Ligação") && tipo === "pneu" ? [...OBJ_POR_PRODUTO[tipo], "manda_wpp", "ml_ligacao", "manda_wpp"] : OBJ_POR_PRODUTO[tipo]), o = OBJ.find(x => x.id === idObj);
    let frase = sorteia(o.cliente).replace("{p}", prod);
    if (canal === "WhatsApp") frase = frase.replace(/\.$/, "").replace(/^./, c => c.toLowerCase()).replace(/você/g, "vc").replace(/está/g, "tá");
    return {prod, perfil, fala, obj: o, canal, frase};
  }

  // ══════════════════════ AVALIAÇÃO (0 a 10, por palavras) ══════════════════════
  // "montagem gratuita", "a montagem é gratuita", "montagem por nossa conta", "não paga a montagem"…
  const MONTAGEM = /montagem.{0,20}(gratis|gratuit|por (nossa|conta da)|sem custo|de graca|inclusa|e nossa)|(nao paga|sem pagar|nao cobra(mos)?).{0,15}montagem/;
  const TECNICO = /(seguranc|aquaplan|sulco|twi|frenag|durabil|dura (mais|ate)|quilometr|\bkm\b|economia|combustivel|borra|desgast|geometri|vibra|garantia|inmetro|aderenc|estabilid|protege|vida util|risco|multa|blitz|contamin|oxida)/g;
  function avaliar(resp, cen) {
    const n = N(resp), notas = [], dicas = [];
    const perguntas = (resp.match(/\?/g) || []).length;
    const d = perguntas >= 1 && /(voce|vc|seu|sua|qual|como|quanto|onde|roda|usa|prefere|faz sentido|me conta|me diz)/.test(n) ? 2.5 : perguntas ? 1.5 : /(qual|como|quanto)/.test(n) ? 1 : 0;
    notas.push(["Diagnóstico (perguntou antes de defender o preço?)", d]);
    if (d < 2.5) dicas.push("Faça pelo menos uma pergunta: entender o uso, a urgência ou o que pesou na decisão. Quem pergunta melhor fecha.");
    const tec = new Set(n.match(TECNICO) || []).size;
    const c = tec >= 2 ? 2.5 : tec === 1 ? 1.5 : 0;
    notas.push(["Consciência técnica (o porquê: segurança, economia, durabilidade)", c]);
    if (c < 2.5) dicas.push("Explique o risco ou a economia ANTES de defender o valor (consciência gratuita, consequência paga).");
    const mont = MONTAGEM.test(n), chk = /check ?-?list/.test(n);
    const a = mont && chk ? 2.5 : mont || chk ? 1.5 : 0;
    notas.push(["Armas da Fox (montagem gratuita + checklist completo gratuito)", a]);
    if (a < 2.5) dicas.push(`Use as armas da Fox para fechar: ${ARMAS}.`);
    const fech = /(agend|horario|que dia|qual dia|hoje|amanha|passar aqui|vir aqui|encostar|as \d|prefere|fica melhor|fechamos|vamos fechar|posso (ja )?(lancar|fechar))/.test(n);
    const duas = /( ou )/.test(n) && fech;
    let f = duas ? 2.5 : fech ? 1.5 : 0;
    const desc = /(desconto|baixo o preco|faco por|abaixar|menor preco)/.test(n);
    if (desc) { f = Math.max(0, f - 1); dicas.push("Não comece pelo desconto: compare custo por km, segurança e garantia primeiro."); }
    if (resp.length > 700) { f = Math.max(0, f - 0.5); dicas.push("Resposta longa demais: cuidado para não \"desvender\". Seja claro e conduza para o fechamento."); }
    if (/(separo|separado|reservo|reservado|reservar|seguro (o pneu|pra voce)|garanto o (pneu|preco))/.test(n)) dicas.push("⚠️ Regra da Fox: nunca prometer pneu separado nem horário reservado (o estoque pode acabar). Combine o dia da visita.");
    notas.push(["Postura e fechamento (conduziu para o dia da visita com 2 opções?)", f]);
    if (f < 2.5 && !desc) dicas.push("Feche com duas opções: \"Fica melhor hoje à tarde ou amanhã cedo?\"");
    const total = Math.round(notas.reduce((s, [, v]) => s + v, 0) * 10) / 10;
    return {total, notas, dicas};
  }

  // ══════════════════════ AUDITORIA DE CONVERSA ══════════════════════
  // txt = o que o VENDEDOR escreveu (ou a conversa inteira, quando não dá para separar); txtCli = o que o cliente escreveu
  function auditar(txt, txtCli) {
    const n = N(txt), l = [];
    // Pergunta de diagnóstico (do vendedor): "você roda…?", "qual o carro…?" (a pergunta de preço do cliente não conta)
    const iPreco = n.search(/r\$\s*\d|\d+,\d{2}|\bvalor (e|fica|sai)\b/);
    const mp = n.match(/[^.?!\n]*(voce|vc|seu|sua|roda|usa|prefere|qual (o |a )?(carro|modelo|ano|medida|uso)|jogo|par\b|cidade|estrada)[^.?!\n]*\?/);
    const iPerg = mp ? n.indexOf(mp[0]) : -1;
    l.push(iPreco >= 0 && (iPerg < 0 || iPreco < iPerg) ? "❌ O preço apareceu antes de qualquer pergunta. Primeiro diagnostique (medida, uso, urgência), depois o preço." : iPerg >= 0 ? "✅ Teve pergunta de diagnóstico antes do preço." : "❌ Não vi perguntas de diagnóstico (uso, carro, urgência).");
    l.push(MONTAGEM.test(n) ? "✅ Falou da montagem gratuita." : "❌ Não falou da MONTAGEM GRATUITA.");
    l.push(/check ?-?list/.test(n) ? "✅ Falou do checklist preventivo." : "❌ Não falou do CHECKLIST PREVENTIVO COMPLETO GRATUITO.");
    l.push(/(alinhament|balanceament|oleo|filtro)/.test(n) ? "✅ Ofereceu serviço junto (alinhamento, balanceamento, óleo/filtro)." : "❌ Não ofereceu alinhamento/balanceamento/óleo: pneu novo nunca anda sozinho.");
    l.push(new Set(n.match(TECNICO) || []).size >= 2 ? "✅ Explicou o porquê técnico." : "❌ Pouca consciência técnica: explique segurança/economia/durabilidade antes de defender o valor.");
    l.push(/(que dia|qual dia|horario|amanha|hoje|passar aqui|vir aqui|agend)/.test(n) ? "✅ Tentou levar para a visita/agendamento." : "❌ Não conduziu para o fechamento: termine com duas opções de dia/horário.");
    if (/(desconto|abaixo|faco por)/.test(n)) l.push("⚠️ Apareceu desconto: só use depois de mostrar valor (custo por km, garantia, armas da Fox).");
    if (/(separo|separado|reservo|reservado|reservar)/.test(n)) l.push("⚠️ Regra da Fox: nunca prometer pneu separado nem horário reservado.");
    const achadas = OBJ.filter(o => o.re.test(txtCli != null ? N(txtCli) : n));
    let r = "🔎 Auditoria da conversa (automática, por palavras: confira com o seu olhar):\n\n" + l.join("\n");
    if (achadas.length) r += "\n\n💬 Objeções que apareceram e a resposta modelo Fox:\n" + achadas.slice(0, 2).map(o => `\n• ${o.nome}:\n"${o.modelo[0]}"`).join("\n");
    return r;
  }

  // ══════════════════════ CONVERSA LIDA DO PRINT (ou colada) ══════════════════════
  // msgs = [{quem: "cliente" | "vendedor" | "?", txt}] na ordem da conversa. Entende quem disse o quê,
  // onde a conversa parou e dá a PRÓXIMA MENSAGEM pronta para mandar + ideias para melhorar.
  const SIM = /\b(quero|pode ser|fechado|fechou|combinado|vou (passar|ai|la)|passo (ai|la|amanha|hoje)|bora|beleza|blz|ok|pode (marcar|agendar)|tenho interesse)\b/;
  const PERGUNTA_PRECO = /(quanto|valor|preco|r\$|parcel|a vista|pix|cartao|desconto|fica quanto|sai quanto)/;
  function proximaMensagem(msgs) {
    const ult = msgs[msgs.length - 1] || {quem: "?", txt: ""};
    const cli = msgs.filter(m => m.quem === "cliente");
    const ultCli = cli.length ? N(cli[cli.length - 1].txt) : "";
    const recente = N(cli.slice(-3).map(m => m.txt).join("\n"));
    const oUlt = OBJ.find(x => x.re.test(ultCli));
    const o = oUlt || (SIM.test(ultCli) || PERGUNTA_PRECO.test(ultCli) ? null : OBJ.find(x => x.re.test(recente)));
    if (ult.quem === "vendedor" && cli.length) {
      const objAntes = o ? `\n\nA última objeção dele foi "${o.nome}". Se ele responder, use:\n"${o.modelo[0]}"` : "";
      return "📍 A conversa parou em VOCÊ: o cliente não respondeu a sua última mensagem.\n\n📩 Mande agora (curta, para ele responder):\n\"[Nome], olha só… Tenho uma condição especial aqui sobre o seu orçamento. Quer ouvir?\"\n\nDepois do \"sim\": \"Para quem vier na loja em até 48 horas, a Fox Pneus libera o parcelamento em até 8x com desconto + montagem gratuita e checklist preventivo! Te explico melhor ou já combinamos o dia da sua visita?\"\n\n📞 Se não responder até amanhã, ligue (diga \"roteiro de ligação\")." + objAntes;
    }
    if (o) return `📍 A conversa parou no cliente, com a objeção "${o.nome}".\n\n📩 Responda assim (adapte com o nome e o pneu):\n"${o.modelo[0]}"\n\nOutra opção:\n"${o.modelo[1]}"`;
    if (SIM.test(ultCli) && PERGUNTA_PRECO.test(ultCli)) return "📍 O cliente está quase fechando e perguntou a condição. Responda e já feche o dia:\n\n📩 Mande:\n\"Fica em 4x de R$ [valor] sem juros, [Nome], com a montagem gratuita e o checklist preventivo completo do carro. Fica melhor você passar hoje à tarde ou amanhã logo cedo?\"\n\n(Não prometa pneu separado nem horário reservado: combine o dia da visita.)";
    if (SIM.test(ultCli)) return "📍 O cliente deu sinal de que quer comprar. PARE de argumentar e feche!\n\n📩 Mande:\n\"Perfeito! Fica melhor você passar hoje à tarde ou amanhã logo cedo?\"\n\n(Não prometa pneu separado nem horário reservado: combine o dia da visita.)";
    if (PERGUNTA_PRECO.test(ultCli)) return "📍 O cliente perguntou de preço/condição. Responda com valor + vantagens + dia:\n\n📩 Mande:\n\"[Nome], esse pneu sai por R$ [valor] cada, em até 4x sem juros. E comprando com a gente a montagem é gratuita e você ainda ganha o checklist preventivo completo do carro. Fica melhor passar hoje à tarde ou amanhã cedo?\"";
    if (/\?/.test(cli.length ? cli[cli.length - 1].txt : "")) return "📍 A conversa parou numa pergunta do cliente: responda de forma curta e termine puxando para o dia da visita:\n\n📩 \"…e se quiser, já combinamos: fica melhor hoje à tarde ou amanhã cedo?\"";
    return "📍 Próximo passo: leve para o dia da visita.\n\n📩 Mande:\n\"[Nome], consegui uma condição boa para o seu orçamento, com montagem gratuita e checklist preventivo completo. Fica melhor passar hoje à tarde ou amanhã cedo?\"";
  }
  function ideias(txtVend) {
    const n = N(txtVend), l = [];
    if (!MONTAGEM.test(n)) l.push("\"Comprando os pneus com a gente, a montagem é por nossa conta.\"");
    if (!/check ?-?list/.test(n)) l.push("\"E ainda faço um checklist preventivo completo do seu carro, sem custo.\"");
    if (!/(alinhament|balanceament)/.test(n)) l.push("\"Já aproveita e faz o alinhamento e o balanceamento, para o pneu novo durar mais.\"");
    if (new Set(n.match(TECNICO) || []).size < 2) l.push("\"Pneu com o sulco baixo perde aderência na chuva e aumenta o risco de aquaplanagem: é segurança da família.\"");
    if (!/\?/.test(txtVend)) l.push("\"Você roda mais na cidade ou pega estrada? É o jogo completo ou só o par?\"");
    return l.slice(0, 4);
  }
  function auditarConversa(msgs) {
    msgs = (msgs || []).filter(m => m && String(m.txt || "").trim());
    const separou = msgs.some(m => m.quem === "cliente") && msgs.some(m => m.quem === "vendedor");
    const txtVend = (separou ? msgs.filter(m => m.quem !== "cliente") : msgs).map(m => m.txt).join("\n");
    const txtCli = separou ? msgs.filter(m => m.quem === "cliente").map(m => m.txt).join("\n") : null;
    const leitura = separou ? "👀 Li assim (confira):\n" + msgs.slice(-6).map(m => (m.quem === "cliente" ? "👤 Cliente: " : "🧑‍💼 Você: ") + (m.txt.length > 90 ? m.txt.slice(0, 88) + "…" : m.txt)).join("\n") + "\n\n" : "";
    let r = leitura + proximaMensagem(separou ? msgs : [{quem: "cliente", txt: msgs.map(m => m.txt).join("\n")}]);
    const id = ideias(txtVend);
    if (id.length) r += "\n\n💡 Ideias para usar nessa conversa:\n· " + id.join("\n· ");
    r += "\n\n" + auditar(txtVend, txtCli);
    return r;
  }
  // Texto colado: separa "Cliente: …" / "Eu: …" ou o formato exportado do WhatsApp ("25/11/2026 10:32 - Nome: texto")
  function msgsDoTexto(txt) {
    const linhas = String(txt || "").split(/\n+/).map(l => l.replace(/^\[?\d{1,2}\/\d{1,2}(\/\d{2,4})?,? \d{1,2}:\d{2}(:\d{2})?\]?\s*-?\s*/, "").trim()).filter(Boolean);
    const out = [];
    for (const l of linhas) {
      const m = l.match(/^([^:]{1,30}):\s*(.+)$/);
      let quem = "?", t = l;
      if (m) { const k = N(m[1]); t = m[2];
        quem = /^(cliente|client)/.test(k) ? "cliente" : /^(eu|vendedor|vendedora|atendente|voce|fox)/.test(k) ? "vendedor" : "nome:" + k; }
      const ant = out[out.length - 1];
      if (ant && (quem === "?" || quem === ant.quem)) ant.txt += "\n" + t; else out.push({quem, txt: t});
    }
    // Exportado do WhatsApp: os dois nomes viram cliente/vendedor (o vendedor é quem fala de montagem, valor, loja…)
    const nomes = [...new Set(out.filter(m => m.quem.startsWith("nome:")).map(m => m.quem))];
    if (nomes.length === 2) {
      const pts = nomes.map(k => N(out.filter(m => m.quem === k).map(m => m.txt).join(" ")).match(/(fox|montagem|r\$|parcel|garantia|checklist|loja|orcamento|aqui e)/g)?.length || 0);
      const vend = pts[0] >= pts[1] ? nomes[0] : nomes[1];
      out.forEach(m => { if (m.quem.startsWith("nome:")) m.quem = m.quem === vend ? "vendedor" : "cliente"; });
    }
    out.forEach(m => { if (m.quem.startsWith("nome:")) m.quem = "?"; });
    return out;
  }

  // ══════════════════════ CONHECIMENTO (filosofia, protocolo, diferenciais) ══════════════════════
  const SABER = [
    {re: /escada (de )?(condic|parcel|preco)|condic(ao|oes) (posso|que posso|especial)|niveis? de (condic|parcel)|quantas vezes (posso|da pra) parcel|parcelamento|21x|8x|4x/,
     txt: "🪜 Escada de condições Fox (libere aos poucos, nunca tudo na primeira mensagem):\n· Autoridade: 30 anos de tradição + 5 anos de garantia de fábrica.\n· Benefícios: montagem gratuita, checklist completo, rodízio gratuito e desconto na avaliação do pneu usado.\n· Nível 1 (padrão): até 4x sem juros (ou 3x mantendo o valor à vista).\n· Nível 2 (campanha): até 8x com 5% de desconto, para quem marca a visita na loja em até 48 h.\n· Nível 3: até 21x no cartão (pequeno acréscimo da operadora), bom para serviços combinados.\n· Nível 4 (cartada final): cobrir o orçamento da concorrência, com validação do gerente e visita combinada.\n\n🏅 Regra de ouro: condição especial não se dá de graça. Toda liberação do gerente pede uma contrapartida: o cliente combinar o DIA da visita na loja.\n⏳ Preço garantido pela data da cotação: até 7 dias (televendas) ou 3 dias (loja). Nunca travar box nem separar pneu. A Fox não faz entrega."},
    {re: /(validade|vale ate|segurar|garantir|manter) (o |do )?(preco|valor|orcamento)|quanto tempo (vale|dura) (o )?(orcamento|preco)|orcamento vence/,
     txt: "⏳ Validade do preço: conta da DATA DA COTAÇÃO. Cotação do televendas: até 7 dias. Cotação da loja: só 3 dias. Depois disso, confirme o preço atual antes de prometer. E nunca prometa pneu separado nem box travado: pode não dar para cumprir."},
    {re: /(roteiro|script|como (fazer|faco) (a |uma )?liga|follow ?-?up|resgat(ar|e) (o |de )?orcamento|ligar para (o )?cliente|abordagem (na|por) ligac)/,
     txt: null, roteiro: true},
    {re: /(mensagem de resgate|cliente sumiu|cliente nao responde|vacuo|resgatar (no|pelo) whats|chamar de novo no whats|reativar cliente)/,
     txt: "💬 Resgate pelo WhatsApp (visita em 48 h):\n1️⃣ Curiosidade (curta): \"[Nome], olha só… Tenho uma condição especial aqui sobre o seu orçamento. Quer ouvir?\"\n2️⃣ Depois do \"sim\": \"Para quem vier na loja em até 48 horas, a Fox Pneus libera o parcelamento em até 8x com desconto + montagem gratuita e checklist preventivo! Te explico melhor ou já combinamos o dia da sua visita?\"\n\n(Não prometa box travado nem pneu separado. O preço vale pela data da cotação: 7 dias televendas, 3 dias loja.)"},
    {re: /cobrir (o )?orcamento|cobre (o )?orcamento|politica de cobrir|cartada final/,
     txt: "🥊 Cobrir orçamento da concorrência (cartada final):\n1. Pergunte na hora: \"Quanto te passaram e de qual marca?\" e anote.\n2. \"Me dá 30 segundos na linha que eu vejo agora com o meu gerente.\"\n3. Volte NA MESMA ligação com a contraproposta (não peça print para depois).\n4. Sempre com a validação do gerente e o dia da visita combinado."},
    {re: /(diferenc|vantage|beneficio|armas?).*(fox|loja)|por que (comprar|fechar) (na|com a) fox|montagem gratuita|checklist/,
     txt: "🏆 Armas de fechamento da Fox Pneus:\n1. Montagem gratuita: comprando os pneus com a gente, a montagem é por conta da Fox.\n2. Checklist preventivo completo gratuito: fechando o serviço, o cliente ganha uma inspeção técnica completa e transparente do carro.\n\nRegra: nunca trate como algo banal. Use para anular objeção de preço (internet/concorrente), gerar reciprocidade, quebrar a desconfiança e trazer o cliente para o box."},
    {re: /protocolo|passo a passo (do |de )?atendimento|como (devo )?atender|roteiro (de )?(atendimento|venda)|etapas da venda/,
     txt: "📋 Protocolo de atendimento Fox:\n1. Acolhimento e qualificação: confirme a medida (ou modelo/ano) e faça 1 ou 2 perguntas de uso (\"Roda mais na cidade ou pega estrada/chuva?\", \"Jogo completo ou o par?\").\n2. Consciência técnica: ligue a necessidade ao benefício (sulco, aderência no molhado, durabilidade, proteção do motor).\n3. Oferta estruturada: 2 opções claras (custo-benefício × premium), à vista/PIX × parcelado, e as armas da Fox: montagem gratuita + checklist completo gratuito.\n4. Venda complementar: alinhamento, balanceamento e óleo/filtros para proteger o pneu novo.\n5. Fechamento assumido: duas opções de dia/horário (\"Fica melhor hoje às 14h ou amanhã logo às 8h?\")."},
    {re: /consciencia gratuita|consequencia paga|elevar (a )?consciencia/,
     txt: "🧠 Consciência gratuita, consequência paga: o cliente bloqueia quem parece querer só o dinheiro dele. Nunca jogue o preço seco de cara. Primeiro mostre um risco técnico ou um prejuízo escondido (eleve a consciência), depois apresente a solução completa com as armas da Fox."},
    {re: /medo|ambicao|gatilho/,
     txt: "⚖️ Gatilhos de decisão:\n· MEDO: aquaplanagem na chuva, estourar pneu na viagem, multa e apreensão na blitz, perder pneu novo por falta de alinhamento, borra e motor fundido, ser enganado na oficina.\n· AMBIÇÃO: economia de combustível, mais km por real, conforto, silêncio, estabilidade e transparência no atendimento.\nDescubra qual dos dois move o cliente e fale com ele por aí."},
    {re: /desvender|falar demais|cliente ja (decidiu|quer comprar)|timing/,
     txt: "⏱️ Antídoto contra o \"desvender\": muita venda ganha se perde por ansiedade ou roteiro no piloto automático. Se o cliente já mostrou que quer comprar, PARE de argumentar e conduza para o fechamento: \"Perfeito! Fica melhor você passar hoje à tarde ou amanhã cedo?\""},
    {re: /escada de valor|frutas? baixas?|cross ?-?sell|venda casada|venda complementar|o que oferecer junto/,
     txt: "🪜 Escada de valor: pneu novo nunca anda sozinho. Todo orçamento de pneu leva a oferta consultiva de alinhamento, balanceamento e óleo/filtros, para proteger o investimento do cliente. E todo dia ative clientes antigos da base para recompra e revisão (\"ser interessante antes de ser interesseiro\")."},
    {re: /estrada.*carro.*piloto|piloto|controle emocional|levar (o )?nao para o pessoal/,
     txt: "🏎️ Estrada, carro e piloto:\n· Estrada (método): roteiro simples e claro; complexidade gera dúvida e trava a venda.\n· Carro (ferramenta): use o sistema (Ligações, histórico, números do funil) com disciplina.\n· Piloto (você): controle emocional, não leve o \"não\" para o lado pessoal, postura consultiva (sem afobação) e fome de resultado."},
    {re: /perguntar (em vez|ao inves)|quem fala primeiro|que perguntas? (fazer|devo)|como diagnosticar|qualificar/,
     txt: "❓ Perguntar em vez de afirmar: quem pergunta melhor diagnostica e fecha. Antes do orçamento descubra: medida ou modelo/ano do carro, uso (cidade, estrada, aplicativo, carga), urgência e se é o jogo completo ou o par."},
    {re: /guerra de preco|cliente (achou|acha) caro|so quer (saber )?(o )?preco|dar desconto/,
     txt: "💰 Não entre em guerra de preço: quando o cliente achar caro, compare custo por quilômetro rodado, segurança e garantia, e use as armas da Fox (montagem gratuita + checklist), antes de pensar em desconto."},
  ];

  // ══════════════════════ ROTEIRO DE LIGAÇÃO (Módulo 2) ══════════════════════
  // Nas Ligações, monta o roteiro com o cliente de maior valor sem contato (nome, medida, dia da cotação,
  // validade do preço pela data da cotação: televendas 7 dias, loja 3 dias).
  const fmtD = iso => iso ? iso.slice(8, 10) + "/" + iso.slice(5, 7) : "";
  const somaDias = (iso, d) => new Date(new Date(iso + "T12:00:00").getTime() + d * 864e5).toISOString().slice(0, 10);
  function roteiro() {
    const F = window.FE_LIG; let cli = "[Nome]", med = "[medida]", dia = "[dia X]", eu = "[Seu Nome]", cargo = "executivo(a)", validade = "", onde = "com a gente";
    if (F && F.pronto && F.pronto()) {
      const e = F.eu(); if (e.nome) eu = e.nome;
      cargo = e.artigo === "o" ? "executivo" : e.artigo === "a" ? "executiva" : "executivo(a)";
      const l = (F.meus() || []).filter(x => x.status === "pendente").sort((a, b) => Number(b.valor || 0) - Number(a.valor || 0))[0];
      if (l) {
        cli = F.primeiro(F.nomeCli(l)) || cli; med = l.medida || med; dia = "dia " + fmtD(l.data_cotacao);
        onde = l.origem === "loja" ? "aqui na loja" : "no nosso WhatsApp";
        const nd = l.origem === "loja" ? 3 : 7, ate = somaDias(l.data_cotacao, nd), venceu = ate < F.hoje();
        validade = venceu ? `\n\n⚠️ A cotação de ${cli} é de ${fmtD(l.data_cotacao)}: o preço garantido (${nd} dias) venceu em ${fmtD(ate)}. Confirme o valor atual com o gerente antes de ligar.`
                          : `\n\n⏳ Preço garantido até ${fmtD(ate)} (${nd} dias da cotação ${nd === 3 ? "da loja" : "do televendas"}).`;
      }
    }
    return `📞 Roteiro de ligação (resgate de orçamento)${cli !== "[Nome]" ? ": " + cli + ", o de maior valor sem contato" : ""}\n\n` +
      `A) Abertura: "Fala, ${cli}! Tudo bem? Aqui é ${eu}, ${cargo} da Fox Pneus. Tá lembrado de mim? Você fez um orçamento do pneu ${med} ${onde} no ${dia}, certo?"\n` +
      `   Se pedir para mandar no WhatsApp: "Eu só preciso de 30 segundos! Tenho uma notícia boa sobre o seu orçamento…" Se insistir: "Mando agora! Para qual dia fica melhor sua vinda na loja, [dia A] ou [dia B]?" (nunca desligue sem tentar um dia)\n\n` +
      `B) Descobrir o que trava: "Quero entender o que preciso fazer para te ajudar a fechar esses pneus aqui com a gente. Você me ajuda? O que está te impedindo de fechar comigo hoje?"\n` +
      `   Dúvida/benefício → montagem gratuita + checklist gratuito + rodízio gratuito. Concorrência → cobrir orçamento (com o gerente).\n\n` +
      `C) Oferta com prazo: "Te liguei porque consegui com meu gerente uma condição especial: o [marca] sai por R$ [valor] cada, em até 4x sem juros, com montagem gratuita, checklist preventivo e 5 anos de garantia. Esse valor vale até [data da validade]. Fica melhor passar hoje à tarde ou amanhã de manhã?"` + validade;
  }

  // ══════════════════════ CONVERSA ══════════════════════
  let modo = null, cenario = null;
  const MENU = ["🎭 Simulação (roleplay)", "🔎 Auditar uma conversa", "⚡ Resposta rápida a objeção"];
  function menu() {
    bot("🎯 Bora treinar! Como você quer treinar hoje?\n1. 🎭 Simulação: eu faço o papel do cliente, você responde e eu dou nota de 0 a 10.\n2. 🔎 Auditoria: cole uma conversa de WhatsApp que travou e eu mostro onde dava para melhorar.\n3. ⚡ Resposta rápida: me conte a objeção que você acabou de ouvir e eu te dou 2 respostas prontas.");
    chips(MENU);
  }
  function lancarCenario() {
    cenario = novoCenario(); modo = "roleplay";
    bot(`🎭 Cenário: ${cenario.perfil} · ${cenario.prod} · ${cenario.canal}\nObjeção: ${GRUPO_NOME[cenario.obj.grupo]}\n\n👤 Cliente: "${cenario.fala} ${cenario.frase}"\n\nSua vez: responda como responderia de verdade.`);
    chips(["Pular cenário", "Sair do treino"]);
  }
  function respostaRapida(o) {
    bot(`⚡ "${o.nome}": 2 respostas prontas para adaptar e enviar:\n\n1️⃣ ${o.modelo[0]}\n\n2️⃣ ${o.modelo[1]}`);
    chips(["Outra objeção", "🎭 Simulação (roleplay)", "Sair do treino"]);
  }

  function resposta(q) {
    const n = N(q), naTelaDeCadastro = !!document.querySelector("[data-fe]");
    // Sair / trocar de modo
    if (modo && /^(sair( do treino)?|parar|chega|encerrar|fim do treino)$/.test(n)) { modo = null; cenario = null; bot("Treino encerrado. Mandou bem! 💪 Quando quiser de novo, é só dizer \"treinar vendas\"."); return true; }
    if (/(treinar|treino|treinamento|simula|roleplay|role play|me treina)/.test(n) && !/(cadastr|desconto)/.test(n)) {
      if (/simula|roleplay|role play|cliente dificil/.test(n)) { lancarCenario(); return true; }
      if (/audit|analis|avali/.test(n)) { modo = "auditoria"; bot("🔎 Mande o PRINT da conversa de WhatsApp (📎 ou Ctrl+V) ou cole o texto. Eu leio, digo onde a conversa parou e te dou a próxima mensagem pronta."); chips(["Sair do treino"]); return true; }
      menu(); return true;
    }
    if (/^🎭|^simulacao/.test(n) || /^(proximo cenario|pular cenario|outro cenario|mais um)$/.test(n) || (/^(sim|bora|vamos|pronto|estou pronto)!?$/.test(n) && modo === "roleplay")) { lancarCenario(); return true; }
    if (/^🔎|^auditar/.test(n)) { modo = "auditoria"; bot("🔎 Mande o PRINT da conversa de WhatsApp (📎 ou Ctrl+V) ou cole o texto. Eu leio, digo onde a conversa parou e te dou a próxima mensagem pronta."); chips(["Sair do treino"]); return true; }
    if (/^⚡|^resposta rapida|^outra objecao$/.test(n)) {
      modo = "rapida"; bot("⚡ Me conte a objeção que o cliente fez. Ex.: \"achou mais barato na internet\", \"não quer alinhar\", \"vai falar com a esposa\"."); chips(["Sair do treino"]); return true;
    }
    // Modo simulação: a mensagem é a resposta do vendedor
    if (modo === "roleplay" && cenario && q.trim().length >= 15) {
      const a = avaliar(q, cenario);
      bot(`📝 Nota: ${String(a.total).replace(".", ",")}/10\n\n` + a.notas.map(([nome, v]) => `${v >= 2.5 ? "✅" : v > 0 ? "🟡" : "❌"} ${nome}: ${String(v).replace(".", ",")}/2,5`).join("\n") +
          (a.dicas.length ? "\n\n💡 Para melhorar:\n· " + a.dicas.join("\n· ") : "\n\n🔥 Excelente, resposta de consultor de elite!") +
          `\n\n🏆 Resposta modelo Fox Pneus:\n"${cenario.obj.modelo[0]}"\n\n(A nota é automática, por palavras-chave: use como guia.) Pronto para o próximo cenário?`);
      chips(["Próximo cenário", "Sair do treino"]);
      return true;
    }
    // Modo auditoria (ou conversa longa colada pedindo análise)
    if ((modo === "auditoria" && q.length >= 60) || (q.length >= 80 && /(analis|audit|avali|onde errei|o que (eu )?errei)/.test(n) && /(conversa|atendimento|cliente:|vendedor:|\n)/.test(n))) {
      bot(auditarConversa(msgsDoTexto(q))); modo = null; chips(["🎭 Simulação (roleplay)", "⚡ Resposta rápida a objeção", "Sair do treino"]); return true;
    }
    // Resposta rápida: o vendedor conta a objeção
    const pediuAjuda = modo === "rapida" || /(cliente (disse|falou|fala|diz|achou|acha|quer|vai|esta|ta)|objecao|como (eu )?respondo|o que (eu )?respondo|o que (eu )?falo|como contorn|como rebat|me ajuda (a|com) (responder|fechar))/.test(n);
    if (pediuAjuda || (!naTelaDeCadastro && /^(achei|acho|ta|esta|nao|vou|preciso|toda vez|nunca|so|meu|fiz|estou)\b/.test(n) && n.split(" ").length <= 18)) {
      const o = OBJ.find(x => x.re.test(n));
      if (o) { respostaRapida(o); return true; }
      if (modo === "rapida") { bot("Não reconheci essa objeção. Tente com outras palavras, ex.: \"achou caro\", \"vai pesquisar\", \"não quer trocar o filtro\"."); return true; }
    }
    // Conhecimento
    if (!naTelaDeCadastro || /\?/.test(q)) for (const s of SABER) if (s.re.test(n) && (s.roteiro || /(venda|vender|cliente|atendimento|fox|fechar|fechamento|objecao|gatilho|desvender|consciencia|protocolo|escada|piloto|preco|valor|orcamento|montagem|checklist|diferencia|parcel|condic|whats|ligac|cobrir|\d+x)/.test(n))) {
      bot(s.roteiro ? roteiro() : s.txt); chips(["🎯 Treinar vendas", "📞 Roteiro de ligação", "🪜 Escada de condições"]); return true;
    }
    if (/(dica|dicas) de venda|como vender (mais|melhor)|vender mais/.test(n)) {
      bot("💡 Dicas de venda Fox:\n· Pergunte antes de orçar (uso, urgência, jogo ou par).\n· Eduque sobre o risco antes do preço.\n· Use as armas: montagem gratuita + checklist completo gratuito.\n· Pneu nunca anda sozinho: ofereça alinhamento, balanceamento e óleo.\n· Cliente decidiu? Pare de argumentar e feche com duas opções de dia.\n\nQuer treinar agora?"); chips(MENU); return true;
    }
    return false;
  }

  window.feVendas = {resposta, avaliar, auditar, auditarConversa, msgsDoTexto, novoCenario, OBJ, modo: () => modo, sairAuditoria: () => { if (modo === "auditoria") modo = null; }};
})();
