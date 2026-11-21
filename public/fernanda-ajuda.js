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
      ? /(?:tel(?:efone)?|cel(?:ular)?|fone|whats(?:app)?|contato)\s*(?:do cliente)?\s*[:=]?\s*(\+?[\d()\s.-]{8,20})/i
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
  const ROTULOS = /^(cliente|telefone|vendedor|celular|canal|campanha|cota[cç][aã]o|condi[cç][aã]o|parcelas|total|c[oó]d|descri[cç][aã]o|marca|qtd|pre[cç]o|data)\b/i;
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
  function lerOrcamento(texto, itens) {
    const t = String(texto || "").replace(/\r/g, "");
    const d = {};
    if (itens && itens.length) {
      const L = montarLinhas(itens);
      const so = (re, v) => { const m = String(v || "").match(re); return m ? m[1] : null; };
      const cot = abaixoDe(L, /^cota[cç][aã]o\b/i);
      if (so(/(\d{3,})/, cot)) { d.numero = so(/(\d{3,})/, cot); d.tipo = "orcamento"; }
      const os = abaixoDe(L, /^(ordem de servi[cç]o|o\.?s\.?)\b/i);
      if (!d.numero && so(/(\d{3,})/, os)) { d.numero = so(/(\d{3,})/, os); d.tipo = "os"; }
      const cli = abaixoDe(L, /^cliente\s*:?/i);
      if (cli) d.cliente = cli.replace(/^\d+\s*-\s*/, "").trim();
      const tel = abaixoDe(L, /^telefone\s*:?/i) || abaixoDe(L, /^celular\s*:?/i);
      if (tel && tel.replace(/\D/g, "").length >= 8) d.telefone = so(/(\+?[\d()\s.-]{8,20})/, tel).trim();
      const ven = abaixoDe(L, /^vendedor\s*:?/i);
      if (ven) d.vendedor = ven.replace(/^\d+\s*-\s*/, "").trim().split(/\s+/)[0];
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
    if (!d.telefone) { m = t.match(/(?:Telefone|Celular)\s*:\s*(\+?[\d()\s.-]{8,20})/i); if (m && m[1].replace(/\D/g, "").length >= 8) d.telefone = m[1].trim(); }
    if (!d.vendedor) { m = t.match(/Vendedor\s*:\s*(?:\d+\s*-\s*)?([A-Za-zÀ-ú]+)/i); if (m) d.vendedor = m[1].trim(); }
    d.medida = medidaDoTexto(t);
    if (d.medida) {
      const i = t.toUpperCase().search(/\d{3}\s*\/\s*\d{2}\s*Z?R|\d{1,2}[.,]\d{2}\s*[-–]\s*\d{2}/);
      d.segmento = segmentoDoTexto(t.slice(i, i + 60));
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
    m = semConc.match(/valor(?:\s*(?:com desconto|negociado|final|do desconto|de venda))?\s*(?:e|de|:|=)?\s*(?:r\$\s*)?(\d[\d.]*(?:,\d{1,2})?)/) ||
        semConc.match(/\bpor\s*r\$\s*(\d[\d.]*(?:,\d{1,2})?)/);
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
        if (c === "vendedor" && N(v) === "fernanda") { avisos.push("No orçamento o vendedor aparece como “Fernanda” — escolha o vendedor responsável na lista (ou me diga, ex.: “vendedor Kessya”)."); continue; }
        const op = escolherOpcao(el, v, c);
        if (!op) { avisos.push(`Não achei “${v}” na lista de ${CAMPOS[c]} — escolha na tela.`); continue; }
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
    bot("Para salvar, ainda falta:\n" + f.map(c => `• ${CAMPOS[c]} — ex.: “${ex[c]}”`).join("\n") +
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
  async function textoDaImagem(arquivo) {
    await carregarScript("https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js");
    const r = await window.Tesseract.recognize(arquivo, "por");
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
    const d = lerOrcamento(lido.texto, lido.itens);
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
        bot("A tela perguntou sobre a concorrência — é só responder lá. 😉");
      else bot(msg ? "Pronto! A tela respondeu: “" + msg + "”" : "Mandei salvar! Confira a mensagem na tela. ✅");
      return true;
    }
    const d = lerMensagem(q);
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
          if (obs) setValor(obs, (obs.value ? obs.value + "\n\n" : "") + `📊 CONCORRENTES:\n• ${d.conc.nome}: ${brl(d.conc.valor)} (${d.conc.pgto || "—"})`);
        }
      }
      if (txt) bot(txt);
      pedirOQueFalta(tela);
      return true;
    }
    if (/cadastr|preench|desconto|orcamento|negociacao/.test(n)) {
      bot("Posso preencher o desconto para você! 🦊\n\n• Mande o PDF ou um print do orçamento pelo 📎 aqui embaixo, ou\n• Escreva os dados, por exemplo:\n“orçamento 951290, loja Ariquemes, vendedor Kessya, telefone 69 98152-5711, medida 255/50R20 liso, CBA 1234, valor 7.200, pagamento à vista, validade 7 dias, motivo: cobrir a concorrência”");
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
      chips(["Quanto preciso vender hoje?", "Quanto vendi ontem?", "Como estou na meta?", "Quanto falta para a meta 2?"]);
      return true;
    }
    if (/quem (sou eu|e (que )?esta falando)|^quem sou/.test(n)) {
      const q2 = lerQuem();
      bot(q2 ? `Por aqui você é a ${primeiroNome(q2)}. 😉 Se não for, diga “não sou eu”.` : "Ainda não sei! Me diga quem é você:");
      if (!q2) chips(nomesChips);
      return true;
    }

    const sobreNumeros = /vend|meta|precis|falt|ritmo|como estou|resultado|faturamento|faturei|desempenho|media|melhor dia|quanto/.test(n);
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
      bot("Eu sou a Fernanda, a assistente do FOXNET! 🦊\nAjudo a encontrar as coisas no site, preencho o cadastro de desconto (até lendo o orçamento em PDF ou imagem), mostro os seus números no painel do televendas e faço contas.\nTudo aqui no seu navegador — nada do que você me manda sai do computador. 🔒");
      return true;
    }
    if (respostaConta(q)) return true;
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
        (/\b(sou a|eu sou)\s+(graziele|kessya|sabrina|ana)\b/.test(n) || /(quanto (eu )?(preciso )?vend|minha meta|como estou na meta)/.test(n))) {
      bot("Os seus números de vendas ficam no Painel do televendas. Abra por aqui e me pergunte lá — eu te mostro só os seus! 😊");
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
    bt.type = "button"; bt.id = "fe-clip"; bt.className = "fe-clip"; bt.title = "Enviar PDF ou imagem do orçamento"; bt.textContent = "📎";
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = "application/pdf,image/*"; inp.style.display = "none";
    bt.onclick = () => inp.click();
    inp.onchange = () => { const f = inp.files[0]; inp.value = ""; if (f) receberArquivo(f); };
    form.insertBefore(bt, form.firstChild); form.appendChild(inp);

    // Sugestões da tela ao abrir a conversa
    const abrir = window.feOpen;
    window.feOpen = function () {
      const primeira = !window.feStartedAjuda; window.feStartedAjuda = true;
      abrir.apply(this, arguments);
      if (!primeira) return;
      setTimeout(() => {
        if (telaCadastro()) {
          bot("Estou vendo que você está no Cadastrar desconto. 📝 Posso preencher para você: mande o PDF ou o print do orçamento pelo 📎, ou escreva os dados aqui.");
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

  // Para testes
  window.FE_AJUDA_TESTE = { lerOrcamento, textoDoPdf, montarLinhas, lerMensagem, numBR, dataDoTexto, medidaDoTexto, segmentoDoTexto, pgtoDoTexto, lojaDoTexto };
})();
