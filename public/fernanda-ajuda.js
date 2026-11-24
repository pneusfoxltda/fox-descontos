/* ════════════════════════════════════════════════════════════════════════
   FERNANDA · ajuda de cada tela (carregada pelo fernanda.js)

   Funciona 100% no navegador, sem IA externa: nada do que a pessoa escreve
   ou envia sai do computador. Os leitores de PDF (pdf.js) e de imagem
   (Tesseract) são baixados só quando alguém manda um arquivo.

   · Cadastrar desconto (/cadastrardescontos.html e aba Cadastrar do App):
     entende os dados escritos no chat, lê o PDF ou a imagem do orçamento
     do Movere, preenche a tela, pergunta o que falta, coloca concorrência
     e anexo, e salva quando a pessoa pedir.
   · Painel do televendas: a pessoa diz quem é ("sou a Kessya"); a Fernanda
     guarda neste navegador e responde só sobre os números dela.
   · Contas: porcentagem e contas simples.
   ════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  const N = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  const brl = v => Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const espera = ms => new Promise(r => setTimeout(r, ms));
  const bot = t => window.feBot(t);
  const chips = l => window.feRenderChips(l);
  const sorteia = a => a[Math.floor(Math.random() * a.length)];

  // Número em formato brasileiro: "7.495,99" → 7495.99 · "7200" → 7200 · "7.200" → 7200
  function numBR(s) {
    s = String(s || "").replace(/[^\d.,-]/g, "");
    if (!s) return NaN;
    if (s.includes(",")) return parseFloat(s.replace(/\./g, "").replace(",", "."));
    if (/^\d{1,3}(\.\d{3})+$/.test(s)) return parseFloat(s.replace(/\./g, ""));
    return parseFloat(s);
  }

  // ══════════════════════ CADASTRAR DESCONTO ══════════════════════
  const CAMPOS = {
    numero: "nº do orçamento/O.S.", loja: "loja", vendedor: "vendedor responsável", telefone: "telefone do cliente",
    cba: "CBA", medida: "medida do pneu", segmento: "segmento", valor: "valor com desconto",
    pgto: "forma de pagamento", validade: "validade", obs: "observação",
  };
  const OBRIGATORIOS = ["numero", "loja", "vendedor", "cba", "medida", "segmento", "valor", "pgto", "validade"];
  const IDS_HTML = { numero: "f-numero", loja: "f-loja", vendedor: "f-vendedor", telefone: "f-telefone", cba: "f-cba",
    medida: "f-medida", segmento: "f-segmento", valor: "f-valor", pgto: "f-pgto", validade: "f-validade", obs: "f-obs" };

  function setValor(el, v) {
    const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype
                : el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const set = Object.getOwnPropertyDescriptor(proto, "value").set;
    set.call(el, v);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }
  const visivel = el => el && el.offsetParent !== null;

  // Adaptadores: a página Cadastrar (HTML) e a aba Cadastrar do App (React)
  const CAD_HTML = {
    el: c => document.getElementById(IDS_HTML[c]),
    tipo: t => typeof window.setTipo === "function" && window.setTipo(t),
    tipoAtual: () => (typeof window.tipo !== "undefined" ? window.tipo : null),
    salvar: () => typeof window.salvar === "function" && window.salvar(),
    temConc: false, temAnexo: false,
  };
  const CAD_APP = {
    el: c => document.querySelector(`[data-fe="${c}"]`),
    tipo: t => { const b = document.querySelector(`[data-fe="tipo-${t}"]`); if (b) b.click(); },
    tipoAtual: () => { const b = document.querySelector('[data-fe="tipo-os"]'); return b && b.classList.contains("sel") ? "os" : "orcamento"; },
    salvar: () => { const b = document.querySelector('[data-fe="salvar"]'); if (b) b.click(); },
    temConc: true, temAnexo: true,
  };
  function telaCadastro() {
    if (/cadastrardescontos/.test(location.pathname) && document.getElementById("f-numero") && visivel(document.getElementById("main-screen"))) return CAD_HTML;
    const n = document.querySelector('[data-fe="numero"]');
    if (visivel(n)) return CAD_APP;
    return null;
  }

  // Lojas (cidades) → o que procurar no nome da opção
  const CIDADES = [
    [/porto velho|\bpvh\b|matriz/, "matriz"], [/ariquemes/, "ariquemes"], [/ji[\s-]?parana|jipa/, "jipar"],
    [/cacoal/, "cacoal"], [/vilhena|\bvlh\b/, "vilhena"], [/manaus|parintins/, "manaus"], [/rio branco|xapuri/, "rio branco"],
  ];
  const lojaDoTexto = t => { const n = N(t); for (const [re, k] of CIDADES) if (re.test(n)) return k; return null; };

  const SEGMENTOS = [
    [/liso\s*misto/, "LISO MISTO"], [/a\s*\/\s*t\s*\+|\bat\s*\+|\bat plus/, "A/T+"], [/a\s*\/\s*t\b|\ball\s*terrain|\bat\b/, "A/T"],
    [/t\s*\/\s*a\b/, "T/A"], [/carga/, "CARGA"], [/\bliso\b/, "Liso"],
  ];
  const segmentoDoTexto = t => { const n = N(t); for (const [re, s] of SEGMENTOS) if (re.test(n)) return s; return null; };

  function pgtoDoTexto(t) {
    const n = N(t);
    const x = n.match(/(\d{1,2})\s*(?:x|vezes|parcelas?)/);
    if (x && +x[1] >= 2) return `${+x[1]}x no cartão`;
    if (/a\s*vista|avista|\bpix\b|dinheiro|debito|\b1\s*x\b/.test(n)) return "À vista";
    return null;
  }

  function dataDoTexto(t) {
    const n = N(t), hoje = new Date();
    const iso = d => d.toLocaleDateString("sv-SE");
    let m = n.match(/(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/);
    if (m) {
      let a = m[3] ? +m[3] : hoje.getFullYear(); if (a < 100) a += 2000;
      const d = new Date(a, +m[2] - 1, +m[1]);
      if (!m[3] && d < new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate())) d.setFullYear(a + 1);
      return isNaN(d) ? null : iso(d);
    }
    m = n.match(/(\d{1,3})\s*dias?/);
    if (m) return iso(new Date(hoje.getTime() + +m[1] * 864e5));
    if (/amanha/.test(n)) return iso(new Date(hoje.getTime() + 864e5));
    if (/\bhoje\b/.test(n)) return iso(hoje);
    if (/fim do mes|final do mes/.test(n)) return iso(new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0));
    return null;
  }

  function medidaDoTexto(t) {
    const s = String(t || "").toUpperCase();
    let m = s.match(/(\d{3})\s*\/\s*(\d{2})\s*Z?R\s*(\d{2}(?:[.,]5)?)/);
    if (m) return `${m[1]}/${m[2]}R${m[3].replace(",", ".")}`;
    m = s.match(/(\d{1,2}[.,]\d{2})\s*[-–]\s*(\d{2})/);
    if (m) return `${m[1].replace(",", ".")}-${m[2]}`;
    m = s.match(/(\d{2,3})\s*[Xx]\s*(\d{1,2}[.,]\d{2})\s*R\s*(\d{2})/);
    if (m) return `${m[1]}X${m[2].replace(",", ".")}R${m[3]}`;
    return null;
  }

  function telefoneDoTexto(t, rotulado) {
    const re = rotulado
      ? /(?:tel(?:efone)?|cel(?:ular)?|fone|whats(?:app)?|contato)\s*(?:do cliente)?\s*[:=]?\s*(\+?[\d() \t.-]{8,20})/i
      : /(\(?\d{2}\)?\s*9?\d{4}[\s.-]?\d{4})/;
    const m = String(t || "").match(re);
    if (!m) return null;
    const d = m[1].replace(/\D/g, "").replace(/^55(?=\d{10,11}$)/, "");
    return d.length >= 8 && d.length <= 11 ? m[1].trim() : null;
  }

  // ── Leitura por posição: o valor fica EMBAIXO do rótulo, na mesma coluna ──
  // itens = [{s: texto, x0, x1, y}] (y cresce para baixo)
  function montarLinhas(itens) {
    const ord = itens.filter(i => String(i.s).trim()).sort((a, b) => a.y - b.y || a.x0 - b.x0);
    const linhas = [];
    ord.forEach(i => {
      const alt = Math.max(4, (i.h || 10) * 0.6);
      const l = linhas.find(l => Math.abs(l.y - i.y) <= alt);
      if (l) l.itens.push(i); else linhas.push({ y: i.y, itens: [i] });
    });
    linhas.forEach(l => l.itens.sort((a, b) => a.x0 - b.x0));
    return linhas.sort((a, b) => a.y - b.y);
  }
  const ROTULOS = /^(c[l1i][il1]?ente|telefone|vendedor|celular|canal|campanha|cota[cç][aã]o|condi[cç][aã]o|parcelas|total|c[oó]d|descri[cç][aã]o|marca|qtd|pre[cç]o|data)\b/i;
  function abaixoDe(linhas, reRotulo) {
    for (let li = 0; li < linhas.length; li++) {
      const its = linhas[li].itens;
      for (let k = 0; k < its.length; k++) {
        const it = its[k];
        if (!reRotulo.test(it.s)) continue;
        // valor na mesma "caixa" (ex.: "Cliente: 0 - PABLO")
        const resto = String(it.s).replace(reRotulo, "").replace(/^\s*[:.]?\s*/, "").trim();
        if (resto) return resto;
        const prox = its.slice(k + 1).find(o => ROTULOS.test(String(o.s).trim()));
        const xMin = it.x0 - 20, xMax = prox ? prox.x0 - 4 : Infinity;
        for (let lj = li + 1; lj < Math.min(linhas.length, li + 4); lj++) {
          const col = linhas[lj].itens.filter(o => o.x1 >= xMin && o.x0 < xMax);
          const txt = col.map(o => o.s).join(" ").trim();
          if (txt) return txt;
        }
      }
    }
    return null;
  }

  // Lê o texto do orçamento do Movere (PDF ou imagem)
  // Na imagem, a leitura troca número por letra dentro da medida ("255/SOR20" → 255/50R20)
  function corrigeMedidaOcr(t) {
    const fix = v => v.replace(/[Oo]/g, "0").replace(/[Ss]/g, "5").replace(/[Il|]/g, "1").replace(/B/g, "8");
    return t.replace(/\b([0-9OoSsIl|B]{3})\s*\/\s*([0-9OoSsIl|B]{2})(\s*Z?R\s*)([0-9OoSsIl|B]{2})\b/g,
      (m, a, b, r, c) => (a + b + c).replace(/\D/g, "").length >= 4 ? fix(a) + "/" + fix(b) + r + fix(c) : m);
  }
  function lerOrcamento(texto, itens) {
    const t = corrigeMedidaOcr(String(texto || "").replace(/\r/g, ""));
    const d = {};
    if (itens && itens.length) {
      const L = montarLinhas(itens);
      const so = (re, v) => { const m = String(v || "").match(re); return m ? m[1] : null; };
      const juntaNum = v => v && String(v).replace(/(\d)\s+(?=\d)/g, "$1");   // "95 1 290" → "951290"
      const cot = juntaNum(abaixoDe(L, /^cota[cç][aã]o\b/i));
      if (so(/(\d{3,})/, cot)) { d.numero = so(/(\d{3,})/, cot); d.tipo = "orcamento"; }
      const os = juntaNum(abaixoDe(L, /^(ordem de servi[cç]o|o\.?s\.?)\b/i));
      if (!d.numero && so(/(\d{3,})/, os)) { d.numero = so(/(\d{3,})/, os); d.tipo = "os"; }
      const cli = abaixoDe(L, /^c[l1i][il1]?ente\s*:?/i);
      if (cli) d.cliente = cli.replace(/^\d+\s*-\s*/, "").trim();
      const tel = abaixoDe(L, /^telefone\s*:?/i) || abaixoDe(L, /^celular\s*:?/i);
      if (tel && tel.replace(/\D/g, "").length >= 8) d.telefone = so(/(\+?[\d() \t.-]{8,20})/, tel).trim();
      const ven = abaixoDe(L, /^vendedor\s*:?/i);
      if (ven) d.vendedor = ven.replace(/^\d+\s*-\s*/, "").trim().split(/\s+/)[0];
      // CBA = coluna "Cód." da tabela de produtos (o 1º produto, se tiver vários)
      const cod = abaixoDe(L, /^c[oóòôeé]d\.?:?\s*$/i);
      if (so(/^\s*(\d{3,})\b/, cod)) d.cba = so(/^\s*(\d{3,})\b/, cod);
      const pg = abaixoDe(L, /^condi[cç][aã]o(\s*de)?\s*pagamento\s*:?/i);
      if (pg) d.pgtoOrcamento = pg.split(/\s{2,}|\d/)[0].trim() || pg;
    }

    let m = t.match(/Cota[cç][aã]o\s*[:nº°]*\s*\n?\s*(\d{3,})/i) || t.match(/Or[cç]amento\s*[:nº°]*\s*\n?\s*(\d{3,})/i);
    if (m && !d.numero) { d.numero = m[1]; d.tipo = "orcamento"; }
    m = t.match(/(?:Ordem de Servi[cç]o|\bO\.?S\.?)\s*[:nº°]*\s*\n?\s*(\d{3,})/i);
    if (!d.numero && m) { d.numero = m[1]; d.tipo = "os"; }
    const ini = t.search(/Cliente\s*:/i);
    d.loja = lojaDoTexto(ini > 0 ? t.slice(0, ini) : t.slice(0, 600));
    if (!d.cliente) { m = t.match(/Cliente\s*:\s*(?:\d+\s*-\s*)?([^\n]+)/i); if (m && !/telefone|vendedor/i.test(m[1])) d.cliente = m[1].trim(); }
    if (!d.telefone) { m = t.match(/(?:Telefone|Celular)\s*:\s*(\+?[\d() \t.-]{8,20})/i); if (m && m[1].replace(/\D/g, "").length >= 8) d.telefone = m[1].trim(); }
    if (!d.vendedor) { m = t.match(/Vendedor\s*:\s*(?:\d+\s*-\s*)?([A-Za-zÀ-ú]+)/i); if (m) d.vendedor = m[1].trim(); }
    if (!d.cba) {
      // Sem posição (texto corrido): 1ª linha que começa com número logo depois do cabeçalho "Cód. Descrição"
      const linhas = t.split("\n"), h = linhas.findIndex(l => /c[oó]d\.?\s+descri[cç][aã]o/i.test(l));
      if (h >= 0) for (const l of linhas.slice(h + 1, h + 6)) { m = l.match(/^\s*(\d{3,})\s+\S/); if (m) { d.cba = m[1]; break; } }
    }
    d.medida = medidaDoTexto(t);
    if (d.medida) {
      const i = t.toUpperCase().search(/\d{3}\s*\/\s*\d{2}\s*Z?R|\d{1,2}[.,]\d{2}\s*[-–]\s*\d{2}/);
      d.segmento = segmentoDoTexto(t.slice(i, i + 60).replace(/\b(USO|L1SO|LIS0|IISO|LlSO|LIS O)\b/gi, "LISO"));
    }
    m = t.match(/Valor Total\s*:?\s*R?\$?\s*([\d.]+,\d{2})/i);
    if (m) d.valorOrcamento = numBR(m[1]);

    return d;
  }

  // Lê os dados escritos no chat ("orçamento 951290, loja Ariquemes, CBA 1234...")
  function lerMensagem(texto) {
    const t = String(texto || ""), n = N(t), d = {};
    let m = n.match(/\b(?:o\.?\s?s\.?|ordem de servico)\s*(?:n[o°º.]*)?\s*[:=]?\s*(\d{3,})/);
    if (m) { d.tipo = "os"; d.numero = m[1]; }
    m = n.match(/\b(?:orcamento|cotacao|numero)\s*(?:n[o°º.]*)?\s*[:=]?\s*(\d{3,})/);
    if (m && !d.numero) { d.tipo = "orcamento"; d.numero = m[1]; }
    const loja = lojaDoTexto(n); if (loja) d.loja = loja;
    m = n.match(/vendedor(?:a)?(?:\s*responsavel)?\s*[:=]?\s*([a-z]+(?:\s+[a-z]+)?)/);
    if (m) d.vendedor = m[1];
    m = n.match(/\bcba\s*[:=]?\s*([a-z0-9-]+)/); if (m) d.cba = m[1].toUpperCase();
    const med = medidaDoTexto(t); if (med) d.medida = med;
    m = n.match(/segmento\s*[:=]?\s*([a-z/+ ]{2,12})/);
    const seg = segmentoDoTexto(m ? m[1] : (med ? n : "")); if (seg && (m || /segmento|liso|carga|a\/t|t\/a/.test(n))) d.segmento = seg;
    const tel = telefoneDoTexto(t, true); if (tel) d.telefone = tel;
    // valor com desconto (sem confundir com o valor do concorrente)
    const semConc = n.replace(/concorr\w*[^;\n]*/g, "");
    // número que NÃO é parcela (4x), data (30/11), prazo (7 dias) nem medida
    const NUM = "(\\d[\\d.]*(?:,\\d{1,2})?)(?![\\d.,]*\\s*(?:x\\b|vezes|\\/|dias?\\b|r\\s*\\d))";
    m = semConc.match(/valor(?:\s*(?:com desconto|negociado|final|do desconto|de venda))?\s*(?:e|de|:|=)?\s*(?:r\$\s*)?(\d[\d.]*(?:,\d{1,2})?)/) ||
        semConc.match(/\bpor\s*r\$\s*(\d[\d.]*(?:,\d{1,2})?)/) ||
        semConc.match(/r\$\s*(\d[\d.]*(?:,\d{1,2})?)/) ||
        semConc.match(new RegExp(NUM + "\\s*(?:reais|real|conto|contos|pila)\\b")) ||
        semConc.match(new RegExp("\\b(?:vai ser|vai sair|vai ficar|vai fechar|fica|ficou|sai|saiu|fechar|fechou|fechado|preco|desconto para)\\s*(?:em|por|a|de|para)?\\s*(?:r\\$\\s*)?" + NUM));
    if (m) d.valor = numBR(m[1]);
    m = semConc.match(/(?:forma de pagamento|pagamento|pgto|pagar)\s*[:=]?\s*([^,;\n]+)/);
    const pg = pgtoDoTexto(m ? m[1] : (/\b(a vista|avista|pix|\d{1,2}\s*x)\b/.test(semConc) ? semConc : ""));
    if (pg) d.pgto = pg;
    m = n.match(/validade\s*(?:ate|de|:|=)?\s*([^,;\n]+)/) || n.match(/\bvale\s*(?:ate|por)\s*([^,;\n]+)/);
    if (m) { const dt = dataDoTexto(m[1]); if (dt) d.validade = dt; }
    m = t.match(/(?:obs(?:erva[cç][aã]o)?|motivo)\s*[:=]\s*([^;\n]+)/i);
    if (m) d.obs = m[1].trim();
    m = t.match(/concorr[eê]n(?:cia|te)\s*[:=]?\s*([A-Za-zÀ-ú0-9 .&'-]+?)\s*(?:R\$\s*)?(\d[\d.]*(?:,\d{1,2})?)(?:\s*[,-]?\s*(à vista|a vista|pix|\d{1,2}\s*x[^,;\n]*))?(?=[,;\n]|$)/i);
    if (m) d.conc = { nome: m[1].trim(), valor: numBR(m[2]), pgto: m[3] ? pgtoDoTexto(m[3]) : null };
    return d;
  }

  function escolherOpcao(el, alvo, campo) {
    const ops = [...el.options].filter(o => o.value);
    const a = N(alvo);
    let op;
    if (campo === "loja") op = ops.find(o => N(o.textContent).includes(a));
    else if (campo === "vendedor") {
      const p = a.split(/\s+/)[0];
      op = ops.find(o => N(o.textContent) === a) || ops.find(o => N(o.textContent).split(/\s+/)[0] === p);
    } else op = ops.find(o => N(o.textContent) === a) || ops.find(o => N(o.textContent).startsWith(a));
    return op ? op.value || op.textContent : null;
  }

  async function preencher(tela, d) {
    const ok = [], avisos = [];
    if (d.tipo && d.tipo !== tela.tipoAtual()) { tela.tipo(d.tipo); await espera(60); }
    for (const c of Object.keys(CAMPOS)) {
      if (d[c] == null || d[c] === "" || (typeof d[c] === "number" && isNaN(d[c]))) continue;
      const el = tela.el(c); if (!el) continue;
      let v = d[c];
      if (el.tagName === "SELECT") {
        if (c === "vendedor" && N(v) === "fernanda") { avisos.push("No orçamento o vendedor aparece como “Fernanda”. Escolha o vendedor responsável na lista (ou me diga, ex.: “vendedor Kessya”)."); continue; }
        const op = escolherOpcao(el, v, c);
        if (!op) { avisos.push(`Não achei “${v}” na lista de ${CAMPOS[c]}. Escolha na tela.`); continue; }
        v = op;
      }
      if (c === "valor") v = String(Math.round(Number(v) * 100) / 100);
      if (c === "medida") v = String(v).toUpperCase();
      setValor(el, v);
      ok.push(c);
      await espera(20);
    }
    return { ok, avisos };
  }

  function lerTela(tela) {
    const v = {};
    for (const c of Object.keys(CAMPOS)) { const el = tela.el(c); v[c] = el ? String(el.value || "").trim() : ""; }
    if (tela === CAD_HTML && Number(v.valor) <= 0) v.valor = "";
    return v;
  }
  const faltando = tela => { const v = lerTela(tela); return OBRIGATORIOS.filter(c => !v[c]); };

  function resumoTela(tela) {
    const v = lerTela(tela), fmt = (c, x) => c === "valor" ? brl(x) : c === "validade" ? x.split("-").reverse().join("/") : x;
    return Object.keys(CAMPOS).filter(c => v[c]).map(c => `• ${CAMPOS[c]}: ${fmt(c, v[c])}`).join("\n");
  }

  function pedirOQueFalta(tela) {
    const f = faltando(tela);
    if (!f.length) {
      bot("Tudo pronto por aqui! ✅\n\n" + resumoTela(tela) + "\n\nConfere para mim? Se estiver certo, é só dizer “salvar”." +
        (tela.temConc ? "\n\nSe tiver concorrência, me mande antes: “concorrente Pneu Fácil R$ 7.200 à vista”." : ""));
      chips(tela.temConc ? ["Salvar", "Adicionar concorrência", "O que falta?"] : ["Salvar", "O que falta?"]);
      return;
    }
    const ex = {
      numero: "orçamento 951290", loja: "loja Ariquemes", vendedor: "vendedor Kessya", cba: "CBA 1234",
      medida: "medida 255/50R20", segmento: "segmento liso", valor: "valor 7.200", pgto: "pagamento à vista ou 3x",
      validade: "validade 30/11 (ou “7 dias”)",
    };
    bot("Para salvar, ainda falta:\n" + f.map(c => `• ${CAMPOS[c]}, ex.: “${ex[c]}”`).join("\n") +
      "\n\nPode mandar tudo numa mensagem só, separado por vírgula. 😉" +
      "\nSe quiser, inclua também a observação (“motivo: cliente achou mais barato”)" + (tela.temConc ? " e a concorrência." : "."));
  }

  async function adicionarConc(tela, c) {
    if (!tela.temConc) return false;
    const nome = tela.el("conc-nome"), val = tela.el("conc-valor"), pg = tela.el("conc-pgto"), add = tela.el("conc-add");
    if (!nome || !add) return false;
    setValor(nome, c.nome); await espera(40);
    if (val && !isNaN(c.valor)) { setValor(val, String(c.valor)); await espera(40); }
    if (pg && c.pgto) { const op = escolherOpcao(pg, c.pgto, "pgto"); if (op) { setValor(pg, op); await espera(40); } }
    await espera(80);
    add.click();
    return true;
  }

  async function anexar(tela, arquivo) {
    const inp = tela.el("anexo");
    if (!inp) return false;
    const dt = new DataTransfer(); dt.items.add(arquivo);
    inp.files = dt.files;
    inp.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function contarPreenchidos(r, d) {
    const nomes = r.ok.map(c => CAMPOS[c]);
    let txt = nomes.length ? sorteia(["Prontinho! ", "Feito! ", "Deixa comigo! "]) + "Preenchi: " + nomes.join(", ") + "." : "";
    if (d.valorOrcamento) txt += `\nO orçamento soma ${brl(d.valorOrcamento)}${d.pgtoOrcamento ? " (" + d.pgtoOrcamento.toLowerCase() + ")" : ""}. Qual é o valor com desconto?`;
    if (r.avisos.length) txt += (txt ? "\n\n" : "") + r.avisos.join("\n");
    return txt;
  }

  // ── Leitura de arquivos (tudo no navegador) ──
  function carregarScript(src) {
    return new Promise((ok, erro) => {
      if ([...document.scripts].some(s => s.src === src)) return ok();
      const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => erro(new Error("não consegui carregar o leitor")); document.head.appendChild(s);
    });
  }
  async function textoDoPdf(arquivo) {
    await carregarScript("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js");
    const lib = window.pdfjsLib;
    lib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    const pdf = await lib.getDocument({ data: await arquivo.arrayBuffer() }).promise;
    const todos = [];
    let deslocY = 0;
    for (let p = 1; p <= Math.min(pdf.numPages, 3); p++) {
      const pag = await pdf.getPage(p), alt = pag.getViewport({ scale: 1 }).height;
      (await pag.getTextContent()).items.forEach(i => {
        if (!String(i.str).trim()) return;
        todos.push({ s: i.str, x0: i.transform[4], x1: i.transform[4] + (i.width || 0), y: deslocY + alt - i.transform[5], h: i.height || 10 });
      });
      deslocY += alt;
    }
    const texto = montarLinhas(todos).map(l => l.itens.map(i => i.s).join(" ")).join("\n");
    return { texto, itens: todos };
  }
  // Print pequeno lê mal: amplia (até 3x, no máximo 3000 px) e deixa preto e branco (limiar de Otsu)
  async function prepararImagem(arquivo) {
    const url = URL.createObjectURL(arquivo);
    try {
      const img = new Image(); img.src = url; await img.decode();
      const k = Math.max(1, Math.min(3, 3000 / img.width));
      const c = document.createElement("canvas"); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      const g = c.getContext("2d"); g.imageSmoothingEnabled = true; g.imageSmoothingQuality = "high";
      g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0, c.width, c.height);
      const d = g.getImageData(0, 0, c.width, c.height), a = d.data, hist = new Array(256).fill(0);
      for (let i = 0; i < a.length; i += 4) { const y = (0.299 * a[i] + 0.587 * a[i + 1] + 0.114 * a[i + 2]) | 0; a[i] = y; hist[y]++; }
      let tot = a.length / 4, soma = 0, sB = 0, wB = 0, melhor = 0, lim = 160;
      for (let i = 0; i < 256; i++) soma += i * hist[i];
      for (let i = 0; i < 256; i++) { wB += hist[i]; if (!wB) continue; const wF = tot - wB; if (!wF) break; sB += i * hist[i];
        const mB = sB / wB, mF = (soma - sB) / wF, v = wB * wF * (mB - mF) ** 2; if (v > melhor) { melhor = v; lim = i; } }
      for (let i = 0; i < a.length; i += 4) { const v = a[i] <= lim ? 0 : 255; a[i] = a[i + 1] = a[i + 2] = v; }
      g.putImageData(d, 0, 0);
      return await new Promise(r => c.toBlob(r, "image/png"));
    } catch (e) { return null; } finally { URL.revokeObjectURL(url); }
  }
  async function textoDaImagem(arquivo, semPreparo) {
    await carregarScript("https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js");
    const pronta = semPreparo ? null : await prepararImagem(arquivo);
    const r = await window.Tesseract.recognize(pronta || arquivo, "por");
    const itens = [];
    (r.data.lines || []).forEach(l => {
      // junta palavras próximas numa "caixa" (ex.: "0 - PABLO"), separa colunas distantes
      let atual = null;
      (l.words || []).forEach(w => {
        const b = w.bbox;
        if (atual && b.x0 - atual.x1 < (b.y1 - b.y0) * 1.2) { atual.s += " " + w.text; atual.x1 = b.x1; }
        else { atual = { s: w.text, x0: b.x0, x1: b.x1, y: (b.y0 + b.y1) / 2, h: b.y1 - b.y0 }; itens.push(atual); }
      });
    });
    return { texto: r.data.text || "", itens };
  }

  let arquivoPendente = null;
  async function receberArquivo(arquivo) {
    const tela = telaCadastro();
    window.feMe("📎 " + arquivo.name);
    if (!tela) {
      bot("Para eu preencher um desconto, abra a tela de Cadastrar e me mande o arquivo lá. 😉");
      return;
    }
    const ehPdf = /pdf$/i.test(arquivo.type) || /\.pdf$/i.test(arquivo.name);
    const ehImg = /^image\//.test(arquivo.type);
    if (!ehPdf && !ehImg) { bot("Consigo ler PDF ou imagem (print/foto) do orçamento. Esse tipo de arquivo eu não sei abrir. 😕"); return; }
    if (ehImg && tela.temAnexo) {
      arquivoPendente = arquivo;
      bot("Recebi a imagem! Ela é:");
      chips(["📄 O orçamento (preencher a tela)", "🏢 Da concorrência (colocar no anexo)"]);
      return;
    }
    await lerArquivoOrcamento(tela, arquivo, ehPdf);
  }

  async function lerArquivoOrcamento(tela, arquivo, ehPdf) {
    bot(ehPdf ? "Lendo o orçamento… 📄" : "Lendo a imagem… 🔎 Isso leva alguns segundos (tudo aqui no seu computador).");
    let lido;
    try { lido = ehPdf ? await textoDoPdf(arquivo) : await textoDaImagem(arquivo); }
    catch (e) { bot("Não consegui ler esse arquivo (" + e.message + "). Pode me escrever os dados que eu preencho. 🙏"); return; }
    let d = lerOrcamento(lido.texto, lido.itens);
    const nota = x => ["numero", "telefone", "cba", "medida", "cliente"].filter(c => x[c]).length;
    if (!ehPdf && nota(d) < 3) {
      try { const l2 = await textoDaImagem(arquivo, true), d2 = lerOrcamento(l2.texto, l2.itens); if (nota(d2) > nota(d)) d = d2; } catch (e) {}
    }
    if (!d.numero && !d.medida && !d.telefone) {
      bot(ehPdf ? "Abri o PDF, mas não reconheci um orçamento do Movere nele. 🤔 Pode me escrever os dados?"
                : "Não consegui ler bem essa imagem. 🤔 Tente um print mais nítido (sem cortar) ou me escreva os dados.");
      return;
    }
    const r = await preencher(tela, d);
    const quem = d.cliente ? ` do cliente ${d.cliente.split(" ").map(p => p[0] + p.slice(1).toLowerCase()).join(" ")}` : "";
    bot(`Li o orçamento${d.numero ? " nº " + d.numero : ""}${quem}. ` + contarPreenchidos(r, d) +
      (ehPdf ? "" : "\nComo veio de imagem, dá uma conferida nos campos, tá? 👀"));
    pedirOQueFalta(tela);
  }

  async function ajudaCadastro(q, tela) {
    const n = N(q);
    if (arquivoPendente) {
      const arq = arquivoPendente;
      if (/orcamento|preencher/.test(n)) { arquivoPendente = null; await lerArquivoOrcamento(tela, arq, false); return true; }
      if (/concorr|anexo/.test(n)) {
        arquivoPendente = null;
        const ok = await anexar(tela, arq);
        bot(ok ? "Coloquei a imagem no anexo do desconto. 📎✅\nMe diga também o concorrente, o valor e a forma de pagamento deles (ex.: “concorrente Pneu Fácil R$ 7.200 à vista”)." : "Não achei o campo de anexo nesta tela. 😕");
        return true;
      }
    }
    if (/^(o que falta|falta (o que|algo)|faltou)/.test(n) || n === "falta") { pedirOQueFalta(tela); return true; }
    if (/^adicionar concorrencia$/.test(n)) { bot("Me diga assim: “concorrente Pneu Fácil R$ 7.200 à vista”. Se tiver o print do concorrente, mande pelo 📎 que eu coloco no anexo."); return true; }
    if (/^(salvar|salva|pode salvar|salve|confirmo|confirmar|pode cadastrar|cadastra|cadastrar desconto agora)\b/.test(n) || /^(sim|isso|ok)[, ]*(pode )?salva/.test(n)) {
      const f = faltando(tela);
      if (f.length) { bot("Antes de salvar preciso de: " + f.map(c => CAMPOS[c]).join(", ") + ". 🙏"); return true; }
      tela.salvar();
      await espera(900);
      const toast = document.querySelector(".toast,#toast");
      const msg = toast && getComputedStyle(toast).display !== "none" ? toast.textContent.trim() : "";
      if (document.querySelector(".modal-bg, [class*=modal]") && /concorr/i.test(document.body.innerText) && !msg)
        bot("A tela perguntou sobre a concorrência, é só responder lá. 😉");
      else bot(msg ? "Pronto! A tela respondeu: “" + msg + "”" : "Mandei salvar! Confira a mensagem na tela. ✅");
      return true;
    }
    const d = lerMensagem(q);
    // Vendedor escrito sem a palavra "vendedor" ("SABRINA, produto vai ser 245 reais…"): procura o nome na lista
    if (!d.vendedor) {
      const sel = tela.el("vendedor");
      if (sel && sel.options) {
        const pal = new Set(N(q).split(/[^a-z]+/));
        const op = [...sel.options].filter(o => o.value).find(o => {
          const p = N(o.textContent).split(/\s+/)[0];
          return p.length >= 3 && p !== "fernanda" && pal.has(p);
        });
        if (op) d.vendedor = op.textContent.trim();
      }
    }
    const temDados = Object.keys(d).length > 0;
    if (temDados) {
      const r = await preencher(tela, d);
      let txt = contarPreenchidos(r, d);
      if (d.conc) {
        const okc = await adicionarConc(tela, d.conc);
        txt += (txt ? "\n" : "") + (okc ? `Adicionei a concorrência: ${d.conc.nome}${isNaN(d.conc.valor) ? "" : " " + brl(d.conc.valor)}${d.conc.pgto ? " (" + d.conc.pgto + ")" : ""}. 🏢`
                                         : `Anotei a concorrência na observação: ${d.conc.nome} ${brl(d.conc.valor)}.`);
        if (!okc) {
          const obs = tela.el("obs");
          if (obs) setValor(obs, (obs.value ? obs.value + "\n\n" : "") + `📊 CONCORRENTES:\n• ${d.conc.nome}: ${brl(d.conc.valor)}${d.conc.pgto ? " (" + d.conc.pgto + ")" : ""}`);
        }
      }
      if (txt) bot(txt);
      pedirOQueFalta(tela);
      return true;
    }
    if (/cadastr|preench|desconto|orcamento|negociacao/.test(n)) {
      bot("Posso preencher o desconto para você! 🦊\n\n• Mande o PDF pelo 📎, cole um print do orçamento aqui (Ctrl+V), ou\n• Escreva os dados, por exemplo:\n“orçamento 951290, loja Ariquemes, vendedor Kessya, telefone 69 98152-5711, medida 255/50R20 liso, CBA 1234, valor 7.200, pagamento à vista, validade 7 dias, motivo: cobrir a concorrência”");
      return true;
    }
    return false;
  }

  // ══════════════════════ PAINEL DO TELEVENDAS ══════════════════════
  const CHAVE_QUEM = "fe_tv_quem";
  const lerQuem = () => { try { return localStorage.getItem(CHAVE_QUEM); } catch (e) { return null; } };
  const gravarQuem = v => { try { v ? localStorage.setItem(CHAVE_QUEM, v) : localStorage.removeItem(CHAVE_QUEM); } catch (e) {} };
  const primeiroNome = s => String(s).split(" ")[0];

  function acharOperadora(texto, ops) {
    const n = N(texto);
    return ops.find(o => n.includes(N(o.nome))) || ops.find(o => new RegExp("\\b" + N(primeiroNome(o.nome)) + "\\b").test(n));
  }

  function numerosDe(D, op, multEscolhido) {
    const base = Number(D.metas[op.codigo] || 0), mult = multEscolhido || D.mult;
    const meta = base * mult, total = op.totalMes, falta = Math.max(0, meta - total);
    const dias = Math.max(1, D.duRestantes);
    const passados = Math.max(1, D.duPassados);
    return { base, mult, meta, total, falta, porDia: falta / dias, pct: meta ? total / meta * 100 : 0,
             media: total / passados, desejado: D.pctDesejado };
  }

  function respostaTv(q) {
    const D = window.FE_TV, n = N(q);
    const ops = D ? D.operadores : [{ nome: "Graziele Garcia" }, { nome: "Kessya Marques" }, { nome: "Sabrina Rocha" }, { nome: "Ana Clara" }];
    const nomesChips = ops.map(o => "Sou a " + primeiroNome(o.nome));

    // Quem é você?
    if (/\b(nao sou|trocar (de )?pessoa|esquec[ae]|sair)\b/.test(n)) { gravarQuem(null); bot("Tudo bem! Esqueci por aqui. Quem está falando comigo agora?"); chips(nomesChips); return true; }
    const idf = n.match(/\b(?:sou (?:a |o )?|eu sou (?:a |o )?|meu nome e |aqui e (?:a |o )?|quem fala e (?:a |o )?)([a-z]+(?: [a-z]+)?)/);
    const opNome = idf ? acharOperadora(idf[1], ops) : (ops.find(o => n === N(primeiroNome(o.nome)) || n === N(o.nome)));
    if (opNome) {
      gravarQuem(opNome.nome);
      bot(sorteia(["Oi, ", "Que bom te ver, ", "Olá, "]) + primeiroNome(opNome.nome) + "! 😊 A partir de agora, neste computador, eu te respondo sobre os seus números.");
      if (D) resumoPessoa(D, D.operadores.find(o => o.nome === opNome.nome));
      chips(["O que preciso fazer para bater a meta?", "Quanto preciso vender hoje?", "Como estou na meta?", "Quanto falta para a meta 2?"]);
      return true;
    }
    if (/quem (sou eu|e (que )?esta falando)|^quem sou/.test(n)) {
      const q2 = lerQuem();
      bot(q2 ? `Por aqui você é a ${primeiroNome(q2)}. 😉 Se não for, diga “não sou eu”.` : "Ainda não sei! Me diga quem é você:");
      if (!q2) chips(nomesChips);
      return true;
    }

    const sobreNumeros = /vend|meta|precis|falt|ritmo|como estou|resultado|faturamento|faturei|desempenho|media|melhor dia|quanto|plano|dica|previs|chance|bater|chego|chegar|estrateg|objetivo|melhorar/.test(n);
    if (!sobreNumeros) return false;

    // Perguntou de outra pessoa?
    const quem = lerQuem();
    const outra = ops.find(o => new RegExp("\\b" + N(primeiroNome(o.nome)) + "\\b").test(n) && o.nome !== quem);
    if (outra && quem) { bot(`Cada pessoa vê só o próprio resultado, tá? 😊 Posso te contar os seus, ${primeiroNome(quem)}!`); return true; }
    if (!quem) { bot("Para te responder, preciso saber quem é você. 😊 Assim eu mostro só os seus números:"); chips(nomesChips); return true; }
    if (!D) { bot("Ainda estou carregando o painel. Se você estiver vendo um dia específico, clique em “Hoje” para voltar ao mês e me pergunte de novo. 🙏"); return true; }
    const op = D.operadores.find(o => o.nome === quem);
    if (!op) { gravarQuem(null); bot("Não te achei no painel deste mês. Me diga de novo quem é você:"); chips(nomesChips); return true; }

    const mMeta = n.match(/meta\s*(1|2|3|um|dois|tres)/);
    const idxMeta = mMeta ? ({ "1": 0, um: 0, "2": 1, dois: 1, "3": 2, tres: 2 })[mMeta[1]] : null;
    const num = numerosDe(D, op, idxMeta != null ? D.metaMult[idxMeta] : null);
    const nomeMeta = idxMeta != null ? `Meta ${idxMeta + 1}` : (D.mult === 1 ? "Meta 1" : `Meta ${D.metaMult.indexOf(D.mult) + 1}`);
    const nome = primeiroNome(quem);
    const iso = d => `${D.ano}-${String(D.mes).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const nomeMes = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"][D.mes - 1];

    // "quanto vendi dia 10"
    let m = n.match(/\bdia\s*(\d{1,2})\b/);
    if (m && /vend|fatur/.test(n)) {
      const dia = +m[1], v = op.porDia[iso(dia)];
      bot(v ? `No dia ${dia} de ${nomeMes} você vendeu ${brl(v)}, ${nome}. ${v >= num.porDia ? "Mandou bem! 💪" : ""}`
            : `Não encontrei venda sua no dia ${dia} de ${nomeMes}. Pode ter sido domingo, feriado ou o dia ainda não ter sido atualizado pelo Movere.`);
      return true;
    }
    if (/ontem/.test(n) && /vend|fatur/.test(n)) {
      const dias = Object.keys(op.porDia).filter(k => k < iso(D.diaHoje)).sort();
      const ult = dias[dias.length - 1];
      bot(ult ? `No último dia com vendas (${ult.slice(8)}/${ult.slice(5, 7)}) você vendeu ${brl(op.porDia[ult])}. 😊` : "Ainda não tenho vendas suas anteriores a hoje neste mês.");
      return true;
    }
    if (/hoje/.test(n) && /vendi|faturei/.test(n)) {
      const v = op.porDia[iso(D.diaHoje)];
      bot(v ? `Hoje, até a última atualização, você vendeu ${brl(v)}.` : "As vendas de hoje ainda não chegaram do Movere (o painel atualiza de hora em hora). Pergunte de novo mais tarde! ⏳");
      return true;
    }
    if (/melhor dia/.test(n)) {
      const dias = Object.entries(op.porDia).sort((a, b) => b[1] - a[1]);
      bot(dias.length ? `Seu melhor dia em ${nomeMes} foi ${dias[0][0].slice(8)}/${dias[0][0].slice(5, 7)}, com ${brl(dias[0][1])}. 🏆` : "Ainda não há vendas suas neste mês.");
      return true;
    }
    if (/o que (eu )?(preciso|tenho que|devo|posso) fazer|como (eu )?(chego|chegar|bato|bater|alcanc|atinj)|vou bater|consigo bater|da pra bater|previs|projec|chance|dica|plano|estrateg|vender mais|melhorar|objetivo/.test(n)) {
      planoMeta(D, op, idxMeta != null ? D.metaMult[idxMeta] : null, nomeMeta);
      return true;
    }
    if (/media/.test(n)) { bot(`Sua média é de ${brl(num.media)} por dia útil trabalhado (${D.duPassados} dias úteis até agora).`); return true; }
    if (/precis|por dia|hoje/.test(n)) {
      bot(num.falta <= 0
        ? `Você já bateu a ${nomeMeta}, ${nome}! 🎉 Vendeu ${brl(num.total)} de ${brl(num.meta)}. Agora é buscar a próxima!`
        : `Para bater a ${nomeMeta} (${brl(num.meta)}), você precisa vender ${brl(num.porDia)} por dia nos ${D.duRestantes} dia(s) útil(eis) que faltam, contando hoje. 💪\nAté agora: ${brl(num.total)} (${num.pct.toFixed(1).replace(".", ",")}%).`);
      return true;
    }
    if (/falt/.test(n)) {
      bot(num.falta <= 0 ? `Nada! Você já passou da ${nomeMeta}. 🎉` : `Faltam ${brl(num.falta)} para a ${nomeMeta}, ${nome}. Isso dá ${brl(num.porDia)} por dia útil restante.`);
      return true;
    }
    if (/mes|total|vendi|fatur/.test(n) && !/como estou|ritmo|meta/.test(n)) {
      bot(`Em ${nomeMes} você vendeu ${brl(num.total)} até agora, ${nome}. 😊`);
      return true;
    }
    resumoPessoa(D, op, idxMeta != null ? D.metaMult[idxMeta] : null, nomeMeta);
    return true;
  }

  function resumoPessoa(D, op, mult, nomeMeta) {
    if (!op) return;
    const num = numerosDe(D, op, mult), nome = primeiroNome(op.nome);
    const noRitmo = num.pct >= num.desejado;
    nomeMeta = nomeMeta || (num.mult === 1 ? "Meta 1" : `Meta ${D.metaMult.indexOf(num.mult) + 1}`);
    bot(`📊 Seu resultado, ${nome}:\n• Vendido no mês: ${brl(num.total)}\n• ${nomeMeta}: ${brl(num.meta)} → ${num.pct.toFixed(1).replace(".", ",")}%\n` +
        `• Esperado para hoje: ${num.desejado}% (${D.duPassados} de ${D.duTotal} dias úteis)\n` +
        (num.falta > 0 ? `• Falta: ${brl(num.falta)} → ${brl(num.porDia)} por dia útil (${D.duRestantes} restantes)\n` : "• Meta batida! 🎉\n") +
        (noRitmo ? "\nVocê está no ritmo! Continue assim. 🚀" : "\nEstá um pouco abaixo do ritmo, mas dá para recuperar. Bora! 💪"));
  }

  // ══════════════════════ PLANO PARA A META (estatística simples) ══════════════════════
  // Usa só as vendas por dia da própria pessoa (já estão no painel). Nada sai do navegador.
  const SEMANA = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
  function estatDias(D, op) {
    const hoje = `${D.ano}-${String(D.mes).padStart(2, "0")}-${String(D.diaHoje).padStart(2, "0")}`;
    const dias = Object.entries(op.porDia).filter(([d, v]) => v > 0 && d < hoje).sort();
    const vals = dias.map(x => x[1]);
    const media = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
    const dp = vals.length > 1 ? Math.sqrt(vals.reduce((a, v) => a + (v - media) ** 2, 0) / (vals.length - 1)) : 0;
    const ult = vals.slice(-5), mediaUlt = ult.length ? ult.reduce((a, b) => a + b, 0) / ult.length : 0;
    const porSem = {};
    dias.forEach(([d, v]) => { const [a, m, dd] = d.split("-").map(Number); const w = new Date(a, m - 1, dd).getDay(); (porSem[w] = porSem[w] || []).push(v); });
    const semanas = Object.entries(porSem).filter(([, l]) => l.length >= 2)
      .map(([w, l]) => ({ dia: SEMANA[w], media: l.reduce((a, b) => a + b, 0) / l.length })).sort((a, b) => b.media - a.media);
    return { dias, vals, media, dp, mediaUlt, nUlt: ult.length, semanas };
  }
  // Chance de a média dos próximos n dias ficar acima do necessário (aproximação normal)
  function chance(media, dp, precisa, n) {
    if (precisa <= 0) return 1;
    if (!dp || !n) return media >= precisa ? 0.9 : 0.1;
    const z = (media - precisa) / (dp / Math.sqrt(n));
    const t = 1 / (1 + 0.2316419 * Math.abs(z)), d = 0.3989423 * Math.exp(-z * z / 2);
    const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
    return Math.min(0.97, Math.max(0.03, z > 0 ? 1 - p : p));
  }
  function planoMeta(D, op, mult, nomeMeta) {
    const num = numerosDe(D, op, mult), nome = primeiroNome(op.nome), E = estatDias(D, op);
    nomeMeta = nomeMeta || (num.mult === 1 ? "Meta 1" : `Meta ${D.metaMult.indexOf(num.mult) + 1}`);
    const pct = v => v.toFixed(0) + "%";
    if (num.falta <= 0) {
      const prox = D.metaMult.find(x => x > num.mult);
      bot(`Você já bateu a ${nomeMeta}, ${nome}! 🎉` + (prox ? ` Quer o plano para a Meta ${D.metaMult.indexOf(prox) + 1}? É só perguntar “o que preciso fazer para a meta ${D.metaMult.indexOf(prox) + 1}”.` : ""));
      return;
    }
    if (E.vals.length < 3) {
      bot(`Ainda tenho poucos dias de venda seus neste mês para fazer as contas com segurança, ${nome}. 🙏\nPor enquanto: faltam ${brl(num.falta)}, ou seja ${brl(num.porDia)} por dia útil nos ${D.duRestantes} dia(s) que faltam.`);
      return;
    }
    const previsao = num.total + E.media * D.duRestantes;
    const pPrev = previsao / num.meta * 100;
    const esforco = (num.porDia / E.media - 1) * 100;
    const p = chance(E.media, E.dp, num.porDia, D.duRestantes);
    const acertos = E.vals.filter(v => v >= num.porDia).length;
    const tend = E.mediaUlt / E.media - 1;
    const ticket = op.clientesMes > 0 ? num.total / op.clientesMes : 0;

    let t = `🎯 Plano para a ${nomeMeta}, ${nome}:\n\n`;
    t += `📍 Onde você está: ${brl(num.total)} de ${brl(num.meta)} (${pct(num.pct)}).\n`;
    t += `📈 No seu ritmo (média de ${brl(E.media)} por dia), você fecha o mês em uns ${brl(previsao)}, ${pct(pPrev)} da meta.\n`;
    t += `✅ Para bater: ${brl(num.porDia)} por dia nos ${D.duRestantes} dia(s) útil(eis) que faltam` +
         (esforco > 3 ? `, ${pct(esforco)} acima da sua média.` : esforco < -3 ? `, abaixo da sua média: é só manter o ritmo!` : `, praticamente a sua média.`) + "\n";
    if (ticket > 0) {
      const vendas = Math.ceil(num.falta / ticket), porDia = Math.max(1, Math.round(vendas / D.duRestantes));
      t += `🧾 Seu ticket médio é ${brl(ticket)}: são umas ${vendas} vendas, cerca de ${porDia} por dia.\n`;
    }
    const pc = Math.round(p * 20) * 5;   // de 5 em 5%
    t += `🎲 Chance de bater no ritmo de hoje: ${p >= 0.7 ? "boa" : p >= 0.4 ? "média" : p >= 0.1 ? "difícil, mas dá para virar com o plano abaixo" : "muito difícil este mês"} (uns ${pc}%).\n`;
    t += `📅 Você vendeu ${brl(num.porDia)} ou mais em ${acertos} de ${E.vals.length} dias.`;
    if (E.nUlt >= 3 && Math.abs(tend) >= 0.1) t += ` Nos últimos ${E.nUlt} dias sua média ${tend > 0 ? "subiu" : "caiu"} ${pct(Math.abs(tend) * 100)}${tend > 0 ? " 🔥" : ""}.`;
    if (E.semanas.length >= 2) t += `\n⭐ Seu melhor dia da semana é ${E.semanas[0].dia} (média de ${brl(E.semanas[0].media)}).`;

    const dicas = [];
    if (esforco > 15) dicas.push("Retome hoje as cotações em aberto de maior valor: é o caminho mais rápido para o que falta.");
    if (ticket > 0 && esforco > 0) {
      const cobre = Math.min(100, 0.1 * E.media / (num.porDia - E.media) * 100);
      dicas.push(`Aumente o ticket: se cada venda tiver ${brl(ticket * 0.1)} a mais (kit completo, serviços junto), isso sozinho cobre ${pct(cobre)} da diferença, sem precisar de mais clientes.`);
    }
    const idxAtual = D.metaMult.indexOf(num.mult);
    if (p < 0.1 && idxAtual > 0) dicas.unshift(`Foque primeiro na Meta ${idxAtual}: ela está bem mais perto. Pergunte “o que preciso fazer para a meta ${idxAtual}”.`);
    if (acertos / E.vals.length < 0.5) dicas.push("Seus dias variam bastante: comece o dia pelos clientes mais quentes para garantir um piso de vendas logo cedo.");
    if (tend < -0.1) dicas.push("O ritmo caiu nos últimos dias: vale voltar nos clientes que pediram para pensar e fazer a 2ª tentativa pelo WhatsApp.");
    if (E.semanas.length >= 2) dicas.push(`Concentre os retornos importantes na ${E.semanas[0].dia}, seu dia mais forte.`);
    if (!dicas.length) dicas.push("Você está no caminho: mantenha a rotina de retornos e não deixe cotação esfriar.");
    t += "\n\n💡 O que fazer:\n" + dicas.slice(0, 3).map(d => "• " + d).join("\n");
    t += "\n\nAs contas usam só as suas vendas deste mês. Bora! 💪";
    bot(t);
  }

  // ══════════════════════ CONTAS ══════════════════════
  function respostaConta(q) {
    const n = N(q).replace(/r\$/g, "");
    let m = n.match(/(\d[\d.,]*)\s*%\s*de\s*(\d[\d.,]*)/);
    if (m) { const p = numBR(m[1]), v = numBR(m[2]); bot(`${m[1]}% de ${brl(v)} = ${brl(v * p / 100)}. ${p < 100 ? `Sobra ${brl(v - v * p / 100)}.` : ""}`); return true; }
    m = n.match(/desconto de (\d[\d.,]*)\s*%\s*(?:em|sobre|no valor de)?\s*(\d[\d.,]*)/);
    if (m) { const p = numBR(m[1]), v = numBR(m[2]); bot(`Com ${m[1]}% de desconto, ${brl(v)} fica ${brl(v * (1 - p / 100))} (desconto de ${brl(v * p / 100)}).`); return true; }
    m = n.match(/(\d[\d.,]*)\s*(?:em|parcelad[oa] em)\s*(\d{1,2})\s*x/);
    if (m && /parcel|vezes|\dx/.test(n)) { const v = numBR(m[1]), x = +m[2]; bot(`${brl(v)} em ${x}x fica ${brl(v / x)} por parcela (sem juros).`); return true; }
    const expr = n.replace(/quanto e|quanto da|calcule|calcula|=|\?/g, "").replace(/x/g, "*").replace(/,/g, ".").trim();
    if (/^[\d\s.+\-*/()]+$/.test(expr) && /\d\s*[+\-*/]\s*\d/.test(expr)) {
      try { const r = Function('"use strict";return (' + expr + ")")(); if (isFinite(r)) { bot(`${expr.replace(/\*/g, "×")} = ${Number(r).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}`); return true; } } catch (e) {}
    }
    return false;
  }

  // ══════════════════════ PONTO DE ENTRADA ══════════════════════
  window.feAjuda = function (q) {
    const n = N(q);
    if (/quem (e|eh) (voce|vc)|qual (e )?(o )?seu nome|voce e (uma )?(ia|robo)/.test(n)) {
      bot("Eu sou a Fernanda, a assistente do FOXNET! 🦊\nAjudo a encontrar as coisas no site, explico tudo sobre pneus (medida, segmentos, quando trocar…), treino vendas (simulação com nota, objeções, auditoria de conversa), preencho o cadastro de desconto (até lendo o orçamento em PDF ou imagem), mostro os seus números no painel do televendas e faço contas.\nTudo aqui no seu navegador: nada do que você me manda sai do computador. 🔒");
      return true;
    }
    // Treinadora de vendas (fernanda-vendas.js): simulação, auditoria, objeções. Vem antes: no meio de um
    // treino, a resposta do vendedor fala de pneu e não pode cair na parte de pneus.
    if (window.feVendas && window.feVendas.resposta(q)) return true;
    // Conhecimento de pneus (fernanda-pneus.js): medida, segmentos, troca, DOT, etiqueta, run-flat…
    if (window.fePneus && window.fePneus.resposta(q)) return true;
    if (respostaConta(q)) return true;
    // Tela das Ligações: a Fernanda conhece os clientes da pessoa (fernanda-ligacoes.js)
    if (/\/ligacoes/.test(location.pathname) && window.feLig && window.feLig.resposta(q)) return true;
    const tela = telaCadastro();
    if (tela) {
      const r = ajudaCadastro(q, tela);
      // ajudaCadastro é assíncrona: decide pelo tipo de mensagem
      if (r && typeof r.then === "function") {
        if (/cadastr|preench|desconto|orcamento|o\.?s\.?|cotacao|cba|valor|pagamento|validade|medida|segmento|loja|vendedor|telefone|concorr|salva|falta|confirm|anexo|obs|motivo|^\d/.test(n) || arquivoPendente) {
          r.then(ok => { if (!ok) window.feAnswerBase(q); });
          return true;
        }
        return false;
      }
    }
    if (/televendas/.test(location.pathname) && respostaTv(q)) return true;
    // Perguntou dos números do televendas fora do painel → leva até lá
    if (!/televendas/.test(location.pathname) &&
        (/\b(sou a|eu sou)\s+(graziele|kessya|sabrina|ana)\b/.test(n) || /(quanto (eu )?(preciso )?vend|minha meta|como estou na meta|bater a meta|chegar na meta|vender mais)/.test(n))) {
      bot("Os seus números de vendas ficam no Painel do televendas. Abra por aqui e me pergunte lá, eu te mostro só os seus! 😊");
      if (typeof window.feHtml === "function" && typeof window.feAct === "function")
        window.feHtml(window.feAct({ t: "Painel do televendas", d: "Faturamento e metas de cada vendedora", go: "#/televendas" }));
      return true;
    }
    return false;
  };

  // ══════════════════════ BOTÃO 📎 E SUGESTÕES ══════════════════════
  function montar() {
    const form = document.querySelector("#fePanel .fe-in");
    if (!form || document.getElementById("fe-clip")) return;
    const st = document.createElement("style");
    st.textContent = ".fe-clip{background:#1B3247;border:none;color:#fff;border-radius:10px;width:42px;flex-shrink:0;font-size:18px;cursor:pointer}.fe-clip:hover{background:#2A4A66}.fe-in{gap:6px}";
    document.head.appendChild(st);
    const bt = document.createElement("button");
    bt.type = "button"; bt.id = "fe-clip"; bt.className = "fe-clip"; bt.title = "Enviar PDF ou imagem do orçamento (também dá para colar um print com Ctrl+V)"; bt.textContent = "📎";
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = "application/pdf,image/*"; inp.style.display = "none";
    bt.onclick = () => inp.click();
    inp.onchange = () => { const f = inp.files[0]; inp.value = ""; if (f) receberArquivo(f); };
    form.insertBefore(bt, form.firstChild); form.appendChild(inp);

    // Colar um print (Ctrl+V) ou arrastar o arquivo para a conversa
    const painel = document.getElementById("fePanel");
    const campo = document.getElementById("feIn");
    if (campo) campo.placeholder = "Escreva, ou cole um print (Ctrl+V)…";
    painel.addEventListener("paste", e => {
      const itens = [...((e.clipboardData && e.clipboardData.items) || [])];
      const img = itens.find(i => i.kind === "file" && /^image\//.test(i.type));
      if (!img) return;                       // texto colado continua normal
      e.preventDefault();
      const f = img.getAsFile();
      if (f) receberArquivo(new File([f], "print-colado." + ((f.type.split("/")[1] || "png").replace("jpeg", "jpg")), { type: f.type }));
    });
    painel.addEventListener("dragover", e => { e.preventDefault(); painel.style.outline = "2px dashed #E6F77A"; });
    painel.addEventListener("dragleave", () => { painel.style.outline = ""; });
    painel.addEventListener("drop", e => {
      e.preventDefault(); painel.style.outline = "";
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) receberArquivo(f);
    });

    // Sugestões da tela ao abrir a conversa
    const abrir = window.feOpen;
    window.feOpen = function () {
      const primeira = !window.feStartedAjuda; window.feStartedAjuda = true;
      abrir.apply(this, arguments);
      if (!primeira) return;
      setTimeout(() => {
        if (/\/ligacoes/.test(location.pathname) && window.feLig) {
          window.feLig.boasVindas();
        } else if (telaCadastro()) {
          bot("Estou vendo que você está no Cadastrar desconto. 📝 Posso preencher para você: mande o PDF pelo 📎, cole um print aqui (Ctrl+V) ou escreva os dados.");
          chips(["Como você preenche?", "O que falta?"]);
        } else if (/televendas/.test(location.pathname)) {
          const q = lerQuem();
          bot(q ? `Oi, ${primeiroNome(q)}! 😊 Quer saber como está a sua meta?` : "Quer saber os seus números do mês? Me diga quem é você. 😊");
          chips(q ? ["Como estou na meta?", "Quanto preciso vender hoje?", "Quanto vendi ontem?", "Não sou eu"] :
                    ["Sou a Graziele", "Sou a Kessya", "Sou a Sabrina", "Sou a Ana"]);
        }
      }, 120);
    };
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", montar); else montar();
  // Ligações das lojas: carrega a parte da Fernanda que conhece os clientes da pessoa
  if (/\/ligacoes/.test(location.pathname)) { const s = document.createElement("script"); s.src = "/fernanda-ligacoes.js"; s.defer = true; document.head.appendChild(s); }
  // Conhecimento de pneus (estudo da Fox): em todas as telas
  { const s = document.createElement("script"); s.src = "/fernanda-pneus.js"; s.defer = true; document.head.appendChild(s); }
  // Treinadora de vendas (Base de Conhecimento Mestre da Fox): em todas as telas
  { const s = document.createElement("script"); s.src = "/fernanda-vendas.js"; s.defer = true; document.head.appendChild(s); }

  // Para testes
  window.FE_AJUDA_TESTE = { lerOrcamento, prepararImagem, textoDoPdf, montarLinhas, lerMensagem, numBR, dataDoTexto, medidaDoTexto, segmentoDoTexto, pgtoDoTexto, lojaDoTexto };
})();
