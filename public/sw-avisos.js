/* Avisos da Fernanda (Ligações das lojas): recebe o aviso do robô e mostra na tela.
   O aviso chega criptografado e só traz números (nada de nome ou telefone de cliente). */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));

self.addEventListener("push", e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { corpo: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.titulo || "🦊 Fernanda", {
    body: d.corpo || "Você tem clientes para ligar hoje.",
    icon: "/icone-192.png",
    badge: "/favicon.png",
    tag: d.tag || "fe-lig",
    renotify: true,
    data: { url: d.url || "/ligacoes.html" },
  }));
});

// Tocou no aviso: abre (ou traz para frente) a página das Ligações
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/ligacoes.html";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(janelas => {
    for (const j of janelas) if (j.url.includes("/ligacoes")) return j.focus();
    return self.clients.openWindow(url);
  }));
});
