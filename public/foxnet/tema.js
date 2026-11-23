/* ═════════════════════════════════════════════════════════════════════════
   FOXNET · Paleta de cores (🎨 ▾ no topo). Igual à das Ligações das lojas:
   Claro / Escuro / Dispositivo + 15 cores + conta-gotas (cor própria).
   Guardada só neste navegador (localStorage "foxnet_tema"), sem login.
   Padrão: claro com o roxo do FOXNET (igual a antes: não mexe em nada).
   ═════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  const ROXO = "#7D2AE8";
  const CORES = [
    ["Roxo FOXNET", ROXO], ["Vermelho Fox", "#CC1F1F"], ["Azul", "#0B57D0"], ["Cinza", "#5F6368"],
    ["Azul-marinho", "#3B5BA5"], ["Ardósia", "#4A5A78"], ["Petróleo", "#4F6B6E"], ["Turquesa", "#00796B"],
    ["Verde", "#3C7A2E"], ["Sálvia", "#5B6E55"], ["Mostarda", "#7A6400"], ["Laranja", "#A0501A"],
    ["Marrom", "#7A5B4C"], ["Vinho", "#8E3A4E"], ["Ameixa", "#8A3F7F"],
  ];
  const VARS = ["--bg", "--card", "--line", "--txt", "--mut", "--brand", "--side", "--side-bd", "--sb-tx", "--hover", "--on", "--mut2",
    "--dash", "--dash2", "--hero", "--dia", "--frase", "--tab-bg", "--tab-bd", "--tab-tx", "--brand-bg", "--brand-bd", "--brand-tx",
    "--s2", "--s3", "--sub", "--kv", "--btn-tx", "--cs"];
  const $ = id => document.getElementById(id);

  function hexHsl(hex) {
    const n = parseInt(String(hex).replace("#", ""), 16), r = (n >> 16 & 255) / 255, g = (n >> 8 & 255) / 255, b = (n & 255) / 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn;
    if (!d) return [0, 0, l * 100];
    const s = d / (1 - Math.abs(2 * l - 1));
    const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return [(h * 60 + 360) % 360, s * 100, l * 100];
  }
  const cl = v => Math.max(0, Math.min(100, v));
  const hsl = (h, s, l, a) => `hsl(${Math.round((h + 360) % 360)} ${cl(s).toFixed(1)}% ${cl(l).toFixed(1)}%${a != null ? " / " + a : ""})`;

  let tema = (() => { try { return Object.assign({modo: "claro", cor: ROXO}, JSON.parse(localStorage.getItem("foxnet_tema") || "{}")); } catch (e) { return {modo: "claro", cor: ROXO}; } })();
  const midia = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const escuro = () => tema.modo === "escuro" || (tema.modo === "dispositivo" && !!midia && midia.matches);

  function cores(cor, esc) {
    const [h, s0, l0] = hexHsl(cor), s = Math.min(s0, 85), t = Math.min(s, 70) * 0.35;
    if (esc) return {
      "--bg": hsl(h, t, 7), "--card": hsl(h, t, 11), "--line": hsl(h, t, 21), "--txt": hsl(h, t * .4, 93), "--mut": hsl(h, t * .4, 66),
      "--brand": hsl(h, s, Math.max(55, Math.min(l0 + 15, 66))), "--side": hsl(h, t, 10), "--side-bd": hsl(h, t, 17), "--sb-tx": hsl(h, t * .5, 78),
      "--hover": hsl(h, s * .4, 18), "--on": hsl(h, s * .5, 24), "--mut2": hsl(h, t * .5, 55), "--dash": hsl(h, t, 30), "--dash2": hsl(h, t, 26),
      "--hero": `linear-gradient(115deg,${hsl(h - 70, s * .45, 16)} 0%,${hsl(h - 30, s * .45, 17)} 45%,${hsl(h, s * .5, 19)} 100%)`,
      "--dia": hsl(h, s * .6, 75), "--frase": `linear-gradient(90deg,${hsl(h - 50, 80, 72)},${hsl(h - 20, 80, 74)} 45%,${hsl(h, 85, 76)})`,
      "--tab-bg": hsl(h, t, 14, .75), "--tab-bd": hsl(h, t, 24), "--tab-tx": hsl(h, t * .5, 85),
      "--brand-bg": hsl(h, s * .5, 20), "--brand-bd": hsl(h, s * .6, 45), "--brand-tx": hsl(h, s, 82),
      "--s2": hsl(h, t, 13), "--s3": hsl(h, t, 12), "--sub": hsl(h, t * .4, 70), "--kv": hsl(h, t, 18), "--btn-tx": hsl(h, t * .4, 93), "--cs": "dark"};
    return {
      "--bg": hsl(h, t + 8, 97.5), "--card": "#FFFFFF", "--line": hsl(h, t + 5, 91), "--txt": hsl(h, t * .6, 14), "--mut": hsl(h, t * .4, 44),
      "--brand": hsl(h, s, Math.min(l0, 48)), "--side": hsl(h, t + 15, 96), "--side-bd": hsl(h, t + 15, 93), "--sb-tx": hsl(h, t * .6, 32),
      "--hover": hsl(h, s * .55, 92), "--on": hsl(h, s * .7, 89), "--mut2": hsl(h, t * .5, 62), "--dash": hsl(h, t + 10, 83), "--dash2": hsl(h, t + 10, 87),
      "--hero": `linear-gradient(115deg,${hsl(h - 70, s * .7, 89)} 0%,${hsl(h - 30, s * .75, 92)} 45%,${hsl(h, s * .8, 91)} 100%)`,
      "--dia": hsl(h, s * .4, 42), "--frase": `linear-gradient(90deg,${hsl(h - 50, 75, 45)},${hsl(h - 20, 70, 48)} 45%,${hsl(h, s, Math.min(l0, 48))})`,
      "--tab-bg": "#ffffffb3", "--tab-bd": "#ffffff", "--tab-tx": hsl(h, t * .6, 28),
      "--brand-bg": hsl(h, s * .8, 94), "--brand-bd": hsl(h, s * .7, 75), "--brand-tx": hsl(h, s, 34),
      "--s2": hsl(h, t + 15, 98.5), "--s3": hsl(h, t + 15, 99), "--sub": hsl(h, t * .4, 36), "--kv": hsl(h, t + 10, 94), "--btn-tx": hsl(h, t * .6, 14), "--cs": "light"};
  }

  function aplicar() {
    const esc = escuro(), raiz = document.documentElement.style;
    if (!esc && tema.cor.toUpperCase() === ROXO) VARS.forEach(v => raiz.removeProperty(v));   // padrão de sempre
    else Object.entries(cores(tema.cor, esc)).forEach(([k, v]) => raiz.setProperty(k, v));
    document.documentElement.classList.toggle("fx-escuro", esc);
    desenhar();
  }
  function bola(cor, esc) {
    const [h, s] = hexHsl(cor);
    return `<span class="bola"><i style="background:${esc ? hsl(h, s * .7, 30) : hsl(h, s, 88)}"></i><i style="background:${esc ? hsl(h, s, 78) : hsl(h, s, 40)}"></i><i style="background:${hsl(h, 12, esc ? 50 : 75)}"></i></span>`;
  }
  function desenhar() {
    const caixa = $("fx-cores"); if (!caixa) return;
    const esc = escuro(), atual = tema.cor.toUpperCase(), propria = !CORES.some(c => c[1].toUpperCase() === atual);
    caixa.innerHTML = CORES.map(([nome, cor]) => `<button type="button" class="tcor ${cor.toUpperCase() === atual ? "on" : ""}" data-cor="${cor}" title="${nome}">${bola(cor, esc)}<span class="ok">✓</span></button>`).join("") +
      `<label class="tcor gotas ${propria ? "on" : ""}" title="Escolher outra cor"><span class="bola" ${propria ? `style="background:${tema.cor}"` : ""}>🖊️</span><span class="ok">✓</span>` +
      `<input type="color" id="fx-propria" value="${propria ? tema.cor : "#0B57D0"}"></label>`;
    caixa.querySelectorAll("button.tcor").forEach(b => b.onclick = () => mudar({cor: b.dataset.cor}));
    $("fx-propria").oninput = e => mudar({cor: e.target.value.toUpperCase()});
    document.querySelectorAll("#fx-modos button").forEach(b => b.classList.toggle("on", b.dataset.modo === tema.modo));
  }
  function mudar(m) {
    Object.assign(tema, m);
    try { localStorage.setItem("foxnet_tema", JSON.stringify(tema)); } catch (e) {}
    aplicar();
  }

  // Janela da paleta
  const st = document.createElement("style");
  st.textContent = `
.fx-pop{position:fixed;top:70px;right:20px;z-index:350;width:330px;max-width:calc(100vw - 20px);background:var(--card);border:1px solid var(--line);border-radius:22px;padding:16px;box-shadow:0 14px 40px rgba(0,0,0,.18);display:none;color:var(--txt)}
.fx-pop.on{display:block}
.fx-modos{display:flex;border:1px solid var(--line);border-radius:30px;padding:3px;margin-bottom:14px}
.fx-modos button{flex:1;background:transparent;border:none;color:var(--txt);border-radius:26px;padding:9px 4px;font-size:12.5px;font-weight:600;white-space:nowrap}
.fx-modos button.on{background:var(--brand-bg);color:var(--brand-tx);box-shadow:inset 0 0 0 1px var(--brand-bd)}
.fx-cores{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}
.fx-pop .tcor{position:relative;aspect-ratio:1;border-radius:16px;background:var(--side);border:2px solid transparent;display:flex;align-items:center;justify-content:center;padding:0;cursor:pointer}
.fx-pop .tcor:hover{border-color:var(--line)} .fx-pop .tcor.on{border-color:var(--brand)}
.fx-pop .bola{width:70%;aspect-ratio:1;border-radius:50%;overflow:hidden;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr}
.fx-pop .bola i:first-child{grid-column:1/3}
.fx-pop .ok{position:absolute;top:4px;right:4px;width:20px;height:20px;border-radius:50%;background:var(--brand);color:#fff;font-size:12px;font-weight:800;display:none;align-items:center;justify-content:center}
.fx-pop .tcor.on .ok{display:flex}
.fx-pop .gotas .bola{background:#A8C7FA;display:flex;align-items:center;justify-content:center;font-size:20px}
.fx-pop .tcor input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.fx-nota{font-size:11px;color:var(--mut);margin-top:12px;line-height:1.5}
.fx-pad{background:none;border:none;color:var(--mut);text-decoration:underline;font-size:12px;margin-top:6px;padding:0}
.tema-bt{padding:5px 12px;font-size:13px;line-height:1.2}
html.fx-escuro .tile{box-shadow:0 0 0 1px #ffffff12}`;
  document.head.appendChild(st);
  const pop = document.createElement("div");
  pop.className = "fx-pop"; pop.id = "fx-pop"; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", "Cores da tela");
  pop.innerHTML = `<div class="fx-modos" id="fx-modos"><button type="button" data-modo="claro">☀️ Claro</button><button type="button" data-modo="escuro">🌙 Escuro</button><button type="button" data-modo="dispositivo">💻 Dispositivo</button></div>
    <div class="fx-cores" id="fx-cores"></div>
    <div class="fx-nota">A cor fica guardada só neste navegador. "Dispositivo" segue o claro/escuro do computador ou celular.</div>
    <button type="button" class="fx-pad" id="fx-pad">Voltar ao padrão (claro, roxo FOXNET)</button>`;
  document.body.appendChild(pop);
  document.querySelectorAll("#fx-modos button").forEach(b => b.onclick = () => mudar({modo: b.dataset.modo}));
  $("fx-pad").onclick = () => mudar({modo: "claro", cor: ROXO});
  const bt = $("tema-bt");
  if (bt) bt.onclick = e => { e.stopPropagation(); pop.classList.toggle("on"); };
  document.addEventListener("click", e => { if (!e.target.closest("#fx-pop") && !e.target.closest("#tema-bt")) pop.classList.remove("on"); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") pop.classList.remove("on"); });
  if (midia && midia.addEventListener) midia.addEventListener("change", () => { if (tema.modo === "dispositivo") aplicar(); });
  aplicar();
})();
