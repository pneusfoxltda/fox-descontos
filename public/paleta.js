/* ═════════════════════════════════════════════════════════════════════════
   Paleta de cores comum (🎨): App de descontos, Cadastrar, Consulta, Televendas, /admin e Monitor.
   (O FOXNET e as Ligações têm a própria paleta, ligada à MESMA escolha.)

   · A escolha é a mesma em todos os sistemas (tema-comum.js / window.FoxTema).
   · Quem nunca escolheu vê cada página com a cor de sempre: as cores da página estão escritas como
     var(--fx-..., cor de sempre). Sem escolha, nenhuma --fx-* é definida e vale a cor de sempre.
   · Com escolha, este arquivo define as --fx-* a partir do modo (claro/escuro/dispositivo) e da cor.

   Uso na página (depois de /tema-comum.js):
     <script src="/paleta.js" data-padrao="escuro,#CC1F1F" data-antes=".logout"></script>
       data-padrao: a cor de sempre da página (o que "Voltar ao padrão" mostra na janela)
       data-antes / data-dentro: onde pôr o botão 🎨 (antes de / dentro de um elemento); sem isso, fica flutuando.
   ═════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  const eu = document.currentScript;
  const [modoPadrao, corPadrao] = String((eu && eu.dataset.padrao) || "escuro,#CC1F1F").split(",");
  const PADRAO = {modo: modoPadrao, cor: corPadrao.toUpperCase()};
  const FOX = "#CC1F1F";
  const CORES = [
    ["Vermelho Fox", FOX], ["Roxo FOXNET", "#7D2AE8"], ["Azul", "#0B57D0"], ["Cinza", "#5F6368"],
    ["Azul-marinho", "#3B5BA5"], ["Ardósia", "#4A5A78"], ["Petróleo", "#4F6B6E"], ["Turquesa", "#00796B"],
    ["Verde", "#3C7A2E"], ["Sálvia", "#5B6E55"], ["Mostarda", "#7A6400"], ["Laranja", "#A0501A"],
    ["Marrom", "#7A5B4C"], ["Vinho", "#8E3A4E"], ["Ameixa", "#8A3F7F"],
  ];
  const NOMES = ["bg", "s1", "s2", "bd", "tx", "tx0", "tx2", "tx3", "tx4", "ac", "ac2", "ac3", "acbg", "hd", "hd2", "hdtx", "cs",
    "okbg", "oktx", "avbg", "avtx", "inbg", "intx", "erbg", "ertx"];

  function hexHsl(hex) {
    const n = parseInt(String(hex).replace("#", ""), 16), r = (n >> 16 & 255) / 255, g = (n >> 8 & 255) / 255, b = (n & 255) / 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn;
    if (!d) return [0, 0, l * 100];
    const s = d / (1 - Math.abs(2 * l - 1));
    const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return [(h * 60 + 360) % 360, s * 100, l * 100];
  }
  const cl = v => Math.max(0, Math.min(100, v));
  const hsl = (h, s, l) => `hsl(${Math.round((h + 360) % 360)} ${cl(s).toFixed(1)}% ${cl(l).toFixed(1)}%)`;

  // Cores de uma escolha (modo + cor) para todas as páginas
  function cores(cor, escuro) {
    const [h, s0, l0] = hexHsl(cor), s = Math.min(s0, 85), neutro = cor.toUpperCase() === FOX, t = neutro ? 0 : Math.min(s, 70) * 0.3;
    if (escuro) return {
      bg: hsl(h, t, 5), s1: hsl(h, t, 9.5), s2: hsl(h, t, 15), bd: hsl(h, t, 22), tx: hsl(h, t * .4, 94), tx0: hsl(h, t * .3, 98),
      tx2: hsl(h, t * .4, 78), tx3: hsl(h, t * .4, 58), tx4: hsl(h, t * .3, 44),
      ac: hsl(h, s, Math.max(45, Math.min(l0 + 8, 58))), ac2: hsl(h, s, Math.max(52, Math.min(l0 + 15, 65))), ac3: hsl(h, s * .9, 30),
      acbg: hsl(h, s * .6, 13), hd: hsl(h, s * .5, 15), hd2: hsl(h, s * .5, 24), hdtx: "#FFFFFF", cs: "dark",
      // cores de situação (ok / atenção / informação / erro): fundo e texto
      okbg: "#0E2A1F", oktx: "#4ADE80", avbg: "#2A2108", avtx: "#FBBF24", inbg: "#12304A", intx: "#93C5FD", erbg: "#2A1212", ertx: "#F87171"};
    return {
      bg: hsl(h, t + 6, 96), s1: hsl(h, t, 99.5), s2: hsl(h, t + 6, 93), bd: hsl(h, t + 6, 85), tx: hsl(h, t * .5, 13), tx0: hsl(h, t * .5, 10),
      tx2: hsl(h, t * .4, 28), tx3: hsl(h, t * .4, 44), tx4: hsl(h, t * .3, 58),
      ac: hsl(h, s, Math.min(l0, 44)), ac2: hsl(h, s, Math.min(l0, 44) + 7), ac3: hsl(h, s, Math.min(l0, 44) - 8),
      acbg: hsl(h, Math.max(s * .7, 10), 93), hd: hsl(h, s * .65, 24), hd2: hsl(h, s * .6, 32), hdtx: "#FFFFFF", cs: "light",
      okbg: "#DCFCE7", oktx: "#15803D", avbg: "#FEF3C7", avtx: "#92400E", inbg: "#DBEAFE", intx: "#1D4ED8", erbg: "#FEE2E2", ertx: "#B91C1C"};
  }

  const midia = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const escolha = () => (window.FoxTema && FoxTema.get()) || null;
  const atual = () => escolha() || PADRAO;
  const ehEscuro = t => t.modo === "escuro" || (t.modo === "dispositivo" && !!midia && midia.matches);

  function aplicar() {
    const e = escolha(), raiz = document.documentElement;
    if (!e) NOMES.forEach(n => raiz.style.removeProperty("--fx-" + n));   // cor de sempre da página
    else Object.entries(cores(e.cor, ehEscuro(e))).forEach(([k, v]) => raiz.style.setProperty("--fx-" + k, v));
    const esc = ehEscuro(atual());
    raiz.classList.toggle("fx-escuro", esc);
    raiz.classList.toggle("fx-claro", !esc);
    raiz.classList.toggle("fx-tema", !!e);
    raiz.style.colorScheme = e ? (esc ? "dark" : "light") : "";
    desenhar();
  }

  // ── Janela (igual à das Ligações) ──
  const st = document.createElement("style");
  st.textContent = `
.fxp-bt{display:inline-flex;align-items:center;gap:4px;background:transparent;border:1px solid var(--fx-bd,#3A3A3A);color:var(--fx-tx2,#ccc);border-radius:8px;padding:6px 10px;font-size:13px;cursor:pointer;font-family:inherit;line-height:1.2}
.fxp-bt:hover{border-color:var(--fx-ac,#CC1F1F)}
.fxp-bt.flutua{position:fixed;left:14px;bottom:14px;z-index:390;background:var(--fx-s1,#1C1C1C);box-shadow:0 4px 14px rgba(0,0,0,.25)}
.fxp-bt.claro{border-color:#D1D5DB;color:#374151;background:#fff}
.fxp-pop{position:fixed;top:58px;right:14px;z-index:400;width:330px;max-width:calc(100vw - 20px);background:var(--fx-s1,#1C1C1C);color:var(--fx-tx,#F0F0F0);border:1px solid var(--fx-bd,#3A3A3A);border-radius:22px;padding:16px;box-shadow:0 14px 40px rgba(0,0,0,.35);display:none;font-family:inherit}
.fxp-pop.on{display:block}
.fxp-pop.baixo{top:auto;bottom:60px;left:14px;right:auto}
html.fx-claro .fxp-pop{box-shadow:0 14px 40px rgba(0,0,0,.15)}
.fxp-modos{display:flex;border:1px solid var(--fx-bd,#3A3A3A);border-radius:30px;padding:3px;margin-bottom:14px}
.fxp-modos button{flex:1;background:transparent;border:none;color:inherit;border-radius:26px;padding:9px 4px;font-size:12.5px;font-weight:600;cursor:pointer;white-space:nowrap;font-family:inherit}
.fxp-modos button.on{background:var(--fx-acbg,#2A0E0E);box-shadow:inset 0 0 0 1px var(--fx-ac,#CC1F1F)}
.fxp-cores{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}
.fxp-pop .tcor{position:relative;aspect-ratio:1;border-radius:16px;background:var(--fx-s2,#2A2A2A);border:2px solid transparent;display:flex;align-items:center;justify-content:center;padding:0;cursor:pointer}
.fxp-pop .tcor.on{border-color:var(--fx-ac,#CC1F1F)}
.fxp-pop .bola{width:70%;aspect-ratio:1;border-radius:50%;overflow:hidden;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr}
.fxp-pop .bola i:first-child{grid-column:1/3}
.fxp-pop .ok{position:absolute;top:4px;right:4px;width:20px;height:20px;border-radius:50%;background:var(--fx-ac,#CC1F1F);color:#fff;font-size:12px;font-weight:800;display:none;align-items:center;justify-content:center}
.fxp-pop .tcor.on .ok{display:flex}
.fxp-pop .gotas .bola{background:#A8C7FA;display:flex;align-items:center;justify-content:center;font-size:20px}
.fxp-pop .tcor input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.fxp-nota{font-size:11px;color:var(--fx-tx3,#888);margin-top:12px;line-height:1.5}
.fxp-pad{background:none;border:none;color:var(--fx-tx3,#888);text-decoration:underline;font-size:12px;margin-top:6px;padding:0;cursor:pointer;font-family:inherit}`;
  document.head.appendChild(st);

  let pop, bt;
  function bola(cor, esc) {
    const [h, s] = hexHsl(cor);
    return `<span class="bola"><i style="background:${esc ? hsl(h, s * .7, 30) : hsl(h, s, 88)}"></i><i style="background:${esc ? hsl(h, s, 78) : hsl(h, s, 40)}"></i><i style="background:${hsl(h, 12, esc ? 50 : 75)}"></i></span>`;
  }
  function desenhar() {
    if (!pop) return;
    const t = atual(), esc = ehEscuro(t), cor = t.cor.toUpperCase(), propria = !CORES.some(c => c[1] === cor);
    pop.querySelector(".fxp-cores").innerHTML = CORES.map(([n, c]) => `<button type="button" class="tcor ${c === cor ? "on" : ""}" data-cor="${c}" title="${n}">${bola(c, esc)}<span class="ok">✓</span></button>`).join("") +
      `<label class="tcor gotas ${propria ? "on" : ""}" title="Escolher outra cor"><span class="bola" ${propria ? `style="background:${cor}"` : ""}>🖊️</span><span class="ok">✓</span><input type="color" value="${propria ? cor : "#0B57D0"}"></label>`;
    pop.querySelectorAll("button.tcor").forEach(b => b.onclick = () => escolher({cor: b.dataset.cor}));
    pop.querySelector(".gotas input").oninput = e => escolher({cor: e.target.value});
    pop.querySelectorAll(".fxp-modos button").forEach(b => b.classList.toggle("on", b.dataset.modo === t.modo));
  }
  function escolher(m) {
    const t = Object.assign({}, atual(), m);
    if (window.FoxTema) FoxTema.set(t.modo, t.cor);
    aplicar();
  }
  function montar() {
    pop = document.createElement("div");
    pop.className = "fxp-pop"; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", "Cores da tela");
    pop.innerHTML = `<div class="fxp-modos"><button type="button" data-modo="claro">☀️ Claro</button><button type="button" data-modo="escuro">🌙 Escuro</button><button type="button" data-modo="dispositivo">💻 Dispositivo</button></div>
      <div class="fxp-cores"></div>
      <div class="fxp-nota">A cor escolhida vale para todos os sistemas da Fox neste navegador. "Dispositivo" segue o claro/escuro do computador ou celular.</div>
      <button type="button" class="fxp-pad">Voltar ao padrão (cada tela com a sua cor de sempre)</button>`;
    document.body.appendChild(pop);
    pop.querySelectorAll(".fxp-modos button").forEach(b => b.onclick = () => escolher({modo: b.dataset.modo}));
    pop.querySelector(".fxp-pad").onclick = () => { if (window.FoxTema) FoxTema.padrao(); aplicar(); };
    bt = document.createElement("button");
    bt.type = "button"; bt.className = "fxp-bt"; bt.title = "Cores da tela"; bt.innerHTML = `🎨 <span style="font-size:10px">▾</span>`;
    bt.onclick = e => { e.stopPropagation(); pop.classList.toggle("on"); };
    document.addEventListener("click", e => { if (!pop.contains(e.target) && e.target !== bt && !bt.contains(e.target)) pop.classList.remove("on"); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") pop.classList.remove("on"); });
    colocarBotao();
    desenhar();
  }
  // Coloca o 🎨 no topo da página (espera a tela aparecer, como no App); sem lugar, fica flutuando
  function colocarBotao() {
    const antes = eu && eu.dataset.antes, dentro = eu && eu.dataset.dentro;
    const achar = () => {
      const alvo = (antes && document.querySelector(antes)) || (dentro && document.querySelector(dentro));
      if (alvo && alvo.offsetParent !== null) {
        bt.classList.remove("flutua"); pop.classList.remove("baixo");
        if (antes) alvo.parentNode.insertBefore(bt, alvo); else alvo.insertBefore(bt, alvo.firstChild);
        if (eu.dataset.claro !== undefined && !document.documentElement.classList.contains("fx-tema")) bt.classList.add("claro");
        return true;
      }
      return false;
    };
    if (!(antes || dentro) || !achar()) {
      bt.classList.add("flutua"); pop.classList.add("baixo"); document.body.appendChild(bt);
    }
    if (antes || dentro) {      // a tela aparece depois (login, React) ou é redesenhada: põe o 🎨 de volta no lugar
      let agendado = false;
      new MutationObserver(() => {
        if (agendado) return; agendado = true;
        setTimeout(() => {
          agendado = false;
          const alvo = (antes && document.querySelector(antes)) || (dentro && document.querySelector(dentro));
          const certo = alvo && (antes ? bt.nextSibling === alvo : bt.parentNode === alvo);
          if (!certo) achar();
        }, 150);
      }).observe(document.body, {childList: true, subtree: true});
    }
  }

  if (window.FoxTema) FoxTema.onChange(aplicar);
  if (midia && midia.addEventListener) midia.addEventListener("change", aplicar);
  aplicar();   // já no carregamento (antes de desenhar a tela, sem piscar)
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", montar); else montar();
  window.FoxPaleta = {aplicar, cores};
})();
