/* ═════════════════════════════════════════════════════════════════════════
   Paleta de cores ÚNICA para todos os sistemas (FOXNET, Ligações e os próximos).
   · Quem nunca escolheu: cada página fica com a cara de sempre (o seu padrão).
   · Escolheu em qualquer página: vale em todas (decisão do TI).
   Guardado no navegador (localStorage "fox_tema"): {modo, cor, em} ou {padrao: true, em}.
   O FOXNET (foxnet-intranet.vercel.app) e os sistemas (fox-descontos.vercel.app) são endereços
   diferentes e o navegador não deixa um ler a memória do outro: por isso, ao passar de um para o
   outro, a escolha vai junto no endereço (?tema=...) e a mais nova vale.
   Abas abertas ao mesmo tempo se atualizam sozinhas.
   ═════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  const CHAVE = "fox_tema";
  const MODOS = /^(claro|escuro|dispositivo)$/;
  const valido = t => !!t && (t.padrao === true || (MODOS.test(t.modo) && /^#[0-9A-F]{6}$/i.test(t.cor || "")));
  const guardar = t => { try { localStorage.setItem(CHAVE, JSON.stringify(t)); } catch (e) {} };

  function lerBruto() {
    try { const t = JSON.parse(localStorage.getItem(CHAVE) || "null"); if (valido(t)) return t; } catch (e) {}
    // Escolha feita antes de a paleta ser única (só nas Ligações ou só no FOXNET): aproveita
    for (const k of ["lig_tema", "foxnet_tema"]) {
      try { const t = JSON.parse(localStorage.getItem(k) || "null"); if (valido(t)) { const n = {modo: t.modo, cor: t.cor.toUpperCase(), em: 1}; guardar(n); return n; } } catch (e) {}
    }
    return null;
  }

  // Veio do outro endereço com ?tema=escuro.CC1F1F.1732400000000 (ou ?tema=padrao.1732400000000)
  try {
    const u = new URL(location.href), p = u.searchParams.get("tema");
    if (p !== null) {
      const [a, b, c] = p.split(".");
      const recebido = a === "padrao" ? {padrao: true, em: Number(b) || 0} : {modo: a, cor: "#" + String(b || "").toUpperCase(), em: Number(c) || 0};
      const atual = lerBruto();
      if (valido(recebido) && (!atual || (recebido.em || 0) > (atual.em || 0))) guardar(recebido);
      u.searchParams.delete("tema");
      history.replaceState(history.state, "", u.pathname + (u.searchParams.toString() ? "?" + u.searchParams : "") + u.hash);
    }
  } catch (e) {}

  const ouvintes = [];
  const avisar = () => { const t = FoxTema.get(); ouvintes.forEach(f => { try { f(t); } catch (e) {} }); };
  window.FoxTema = {
    // Escolha da pessoa ({modo, cor}) ou null = "use o padrão desta página"
    get() { const t = lerBruto(); return t && !t.padrao ? {modo: t.modo, cor: t.cor} : null; },
    set(modo, cor) { guardar({modo, cor: String(cor).toUpperCase(), em: Date.now()}); avisar(); },
    padrao() { guardar({padrao: true, em: Date.now()}); avisar(); },
    onChange(f) { ouvintes.push(f); },
    // Endereço para o outro domínio levando a escolha junto
    link(url) {
      const t = lerBruto(); if (!t) return url;
      const v = t.padrao ? "padrao." + (t.em || 0) : t.modo + "." + t.cor.replace("#", "") + "." + (t.em || 0);
      return url + (url.includes("?") ? "&" : "?") + "tema=" + v;
    },
    // O FOXNET roda no endereço da intranet: os sistemas abrem no outro endereço
    noDominioIntranet: () => /^foxnet[.-]/i.test(location.hostname),
    // Quem entrou como admin em qualquer sistema: o FOXNET deste navegador mostra o botão 🩺 Monitor.
    // A intranet é outro endereço: a marca vai junto no link da raposa (?monitor=1).
    admin() { try { localStorage.setItem("fox_monitor", "1"); } catch (e) {} },
    ehAdminAqui() { try { return localStorage.getItem("fox_monitor") === "1"; } catch (e) { return false; } },
  };
  window.addEventListener("storage", e => { if (e.key === CHAVE) avisar(); });

  // ── Limite de tentativas de login (todas as telas de login) — decisão do TI ──
  // 5 senhas erradas seguidas no mesmo e-mail → espera de 5 min; se errar de novo: 15 min, depois 30 min.
  // Guardado neste navegador. No servidor, o Supabase também limita as tentativas por internet
  // (todos de uma loja saem pela mesma internet, por isso lá o limite não é baixo).
  const TENT = "fox_login_tentativas", MAX = 5, ESPERA = [5, 15, 30];
  const lerT = () => { try { return JSON.parse(localStorage.getItem(TENT) || "{}"); } catch (e) { return {}; } };
  const gravarT = t => { try { localStorage.setItem(TENT, JSON.stringify(t)); } catch (e) {} };
  window.FoxLogin = {
    // Igual a cli.auth.signInWithPassword({email, password}); o erro traz "mensagem" pronta para a tela
    async entrar(cli, cred) {
      const email = String((cred && cred.email) || "").trim().toLowerCase(), t = lerT(), e = t[email] || {n: 0, b: 0, ate: 0};
      if (e.ate > Date.now()) {
        const min = Math.ceil((e.ate - Date.now()) / 60000);
        return {data: {}, error: {message: "travado", travado: true,
          mensagem: `Muitas tentativas erradas. Por segurança, espere ${min} minuto${min > 1 ? "s" : ""} e tente de novo. Esqueceu a senha? Fale com o TI.`}};
      }
      const r = await cli.auth.signInWithPassword(cred);
      if (!r.error) { delete t[email]; gravarT(t); return r; }
      const st = r.error.status, msg = String(r.error.message || "");
      if (st === 429 || /rate limit|too many/i.test(msg)) {
        r.error.mensagem = "Muitas tentativas nesta internet. Espere alguns minutos e tente de novo.";
        return r;
      }
      if (st === 400 || /invalid login|credentials/i.test(msg)) {
        e.n++;
        if (e.n >= MAX) { e.ate = Date.now() + ESPERA[Math.min(e.b, ESPERA.length - 1)] * 60000; e.b++; e.n = 0;
          r.error.mensagem = `Senha errada ${MAX} vezes. Por segurança, este e-mail ficou travado por ${ESPERA[Math.min(e.b - 1, ESPERA.length - 1)]} minutos. Esqueceu a senha? Fale com o TI.`; }
        else r.error.mensagem = "E-mail ou senha incorretos." + (MAX - e.n <= 2 ? ` Atenção: mais ${MAX - e.n} tentativa${MAX - e.n > 1 ? "s" : ""} errada${MAX - e.n > 1 ? "s" : ""} e o acesso fica travado por alguns minutos.` : "");
        t[email] = e; gravarT(t);
      }
      return r;
    },
  };

  // ── A raposa (logo) de qualquer sistema volta para a intranet (FOXNET) — decisão do TI ──
  // Vale em todas as telas que carregam este arquivo, inclusive nas telas de login. No próprio FOXNET a
  // raposa já leva ao início, então ali não muda nada. Leva a cor escolhida junto (endereços diferentes).
  const noFoxnet = /^foxnet[.-]/i.test(location.hostname) || /^\/foxnet(\/|$)/.test(location.pathname);
  if (!noFoxnet) {
    const RAPOSA = 'img[src$="/logo-fox.png"], .header .logo';
    const destino = () => location.hostname === "fox-descontos.vercel.app"
      ? FoxTema.link("https://foxnet-intranet.vercel.app/" + (FoxTema.ehAdminAqui() ? "?monitor=1" : ""))
      : "/foxnet/";                                      // links de teste e computador local: o FOXNET do mesmo endereço
    const st = document.createElement("style");
    st.textContent = `${RAPOSA}{cursor:pointer}`;
    (document.head || document.documentElement).appendChild(st);
    document.addEventListener("click", e => {
      const r = e.target && e.target.closest && e.target.closest(RAPOSA);
      if (!r) return;
      e.preventDefault(); e.stopPropagation();
      if (e.ctrlKey || e.metaKey) window.open(destino(), "_blank"); else location.href = destino();
    }, true);
    const titulo = () => document.querySelectorAll(RAPOSA).forEach(el => { if (!el.title) el.title = "Voltar para a intranet (FOXNET)"; });
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", titulo); else titulo();
    setTimeout(titulo, 2500);                              // telas que aparecem depois (App, login)
  }
})();
