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
  };
  window.addEventListener("storage", e => { if (e.key === CHAVE) avisar(); });
})();
