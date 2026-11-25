/* resultados-abas.js · Barra de abas ÚNICA de "Resultados Fox Pneus" (pedido do TI, 25/11/2026)
   Aparece igual em todas as telas de resultado (Início, Televendas, Varejo, Atacado, Truck) e fica presa no topo.
   Uso: <div id="abas-resultados"></div> + <script src="/resultados-abas.js"></script>.
   No Televendas (que também é aberto fora de Resultados) só aparece quando a pessoa veio de Resultados
   (?resultados=1 no link, guardado na aba do navegador). Para mexer nas abas: só aqui, na lista ABAS. */
(function () {
  const ABAS = [
    {id: "inicio", t: "🏠 Início", href: "/resultados"},
    {id: "televendas", t: "💰 Resultado Televendas", href: "/televendas.html?resultados=1"},
    {id: "varejo", t: "🏪 Resultado Varejo · Geral", href: "/resultados#varejo"},
    {id: "atacado", t: "📦 Resultado Atacado", href: "/atacado"},
    {id: "truck", t: "🚚 Resultado Truck", breve: true},
  ];
  const css = `
  #abas-resultados{position:sticky;top:0;z-index:30;display:flex;gap:8px;flex-wrap:wrap;padding:10px 0;margin-bottom:6px;
    background:var(--fx-bg,transparent)}
  #abas-resultados a,#abas-resultados span{font-family:'Inter',system-ui,sans-serif;background:var(--fx-s1,#fff);border:1px solid var(--fx-bd,#dde3ec);
    color:var(--fx-tx2,#374151);border-radius:999px;padding:8px 16px;font-size:13px;font-weight:700;text-decoration:none;white-space:nowrap}
  #abas-resultados a:hover{border-color:var(--fx-ac,#CC1F1F)}
  #abas-resultados a.on{background:var(--fx-ac,#CC1F1F);border-color:var(--fx-ac,#CC1F1F);color:#fff}
  #abas-resultados span{opacity:.5;cursor:default}
  #abas-resultados small{font-weight:500;font-size:11px;opacity:.8;margin-left:4px}
  @media(max-width:700px){#abas-resultados{flex-wrap:nowrap;overflow-x:auto}#abas-resultados a,#abas-resultados span{padding:7px 12px;font-size:12px}}`;

  function atual() {
    const p = location.pathname.replace(/\.html$/, "");
    if (p === "/atacado") return "atacado";
    if (p === "/televendas") return "televendas";
    if (p === "/resultados") return location.hash === "#varejo" ? "varejo" : "inicio";
    return "";
  }
  function desenhar() {
    const el = document.getElementById("abas-resultados");
    if (!el) return;
    const sob = el.dataset.sob && document.querySelector(el.dataset.sob);   // fica logo abaixo de um cabeçalho que já é fixo
    if (sob) el.style.top = sob.offsetHeight + "px";
    const ag = atual(), naPagina = location.pathname.replace(/\.html$/, "") === "/resultados";
    el.innerHTML = ABAS.map(a => a.breve
      ? `<span title="Será feito no futuro">${a.t}<small>em breve</small></span>`
      : `<a class="${a.id === ag ? "on" : ""}" href="${naPagina && a.href.startsWith("/resultados") ? (a.href.split("#")[1] ? "#" + a.href.split("#")[1] : "#") : a.href}">${a.t}</a>`).join("");
  }
  function iniciar() {
    const el = document.getElementById("abas-resultados");
    if (!el) return;
    // Televendas: só com a barra quando veio de Resultados
    if (atual() === "televendas") {
      try {
        if (new URLSearchParams(location.search).get("resultados") === "1") sessionStorage.setItem("fox_resultados", "1");
        if (sessionStorage.getItem("fox_resultados") !== "1") { el.remove(); return; }
      } catch (e) {}
    } else {
      try { sessionStorage.setItem("fox_resultados", "1"); } catch (e) {}
    }
    if (!document.getElementById("abas-resultados-css")) {
      const st = document.createElement("style"); st.id = "abas-resultados-css"; st.textContent = css; document.head.appendChild(st);
    }
    window.addEventListener("resize", desenhar);
    desenhar();
  }
  window.FoxAbas = {desenhar};
  window.addEventListener("hashchange", desenhar);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar); else iniciar();
})();
