/*
 * FOXNET · Restrição por internet (IP público)
 *
 * O site só abre nas internets liberadas (lojas e casa do TI).
 * A lista fica no Vercel, não no código:
 *   Vercel → projeto fox-descontos → Settings → Environment Variables
 *   Nome:  FOXNET_IPS_LIBERADOS
 *   Valor: os IPs públicos separados por vírgula, ex.:
 *          177.10.20.30, 189.45.67.89, 2804:14c:65:*
 *          (um * no final libera uma faixa inteira, útil para IPv6)
 *   Depois de salvar: Deployments → ⋯ no último → Redeploy.
 *
 * Segurança contra se trancar para fora: se a variável estiver vazia
 * ou não existir, NADA é bloqueado.
 *
 * /meu-ip sempre responde (mesmo bloqueado) e mostra o IP público de quem
 * abriu, para descobrir o IP de cada loja.
 *
 * Endereços:
 *   Domínio da intranet (qualquer um que comece com "foxnet", ex.: foxnet.foxpneu.com.br)
 *     → mostra SÓ o FOXNET. A raiz abre a intranet; qualquer outro endereço
 *       (Consulta, Descontos, Cadastrar, Televendas…) é enviado para o
 *       domínio dos sistemas: SISTEMAS_URL (fox-descontos.vercel.app).
 *   fox-descontos.vercel.app → continua com todos os sistemas, como antes.
 *   /descontos → App de descontos (no domínio dos sistemas).
 */
import { ipAddress, next, rewrite } from '@vercel/functions';

export const SISTEMAS_URL = 'https://fox-descontos.vercel.app';

export const config = {
  // Vale para todas as páginas e arquivos do site.
  matcher: '/:path*',
};

export function lerLista(valor) {
  return String(valor || '')
    .split(/[\s,;]+/)
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean);
}

export function ipLiberado(ip, lista) {
  const alvo = String(ip || '').trim().toLowerCase();
  if (!alvo) return false;
  return lista.some((item) =>
    item.endsWith('*') ? alvo.startsWith(item.slice(0, -1)) : alvo === item,
  );
}

const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

function pagina(titulo, texto, ip, status) {
  const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(titulo)} · FOXNET</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:linear-gradient(115deg,#BDF3EE,#D7E4FA 45%,#E7D9FB);font-family:Inter,system-ui,sans-serif;color:#1F1D2B}
.c{background:#fff;border-radius:20px;padding:34px 30px;max-width:440px;margin:20px;text-align:center;box-shadow:0 10px 40px #4F46E522}
h1{font-size:22px;margin:0 0 10px}p{color:#5b5870;line-height:1.55;margin:0 0 18px}
.ip{font:700 22px ui-monospace,monospace;background:#F4F1FB;border:1px dashed #B794F4;border-radius:12px;padding:14px;word-break:break-all;color:#5B21B6}
small{display:block;margin-top:16px;color:#8a879c}</style></head>
<body><div class="c"><img src="data:image/png;base64,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" alt="Fox Pneus" width="64" height="64"><h1>${esc(titulo)}</h1><p>${texto}</p>
<div class="ip">${esc(ip || 'não identificado')}</div><small>FOXNET · Sistema Integrado Rede Fox Pneus</small></div></body></html>`;
  return new Response(html, {
    status,
    headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' },
  });
}

export default function middleware(request) {
  const ip = ipAddress(request) || '';
  const url = new URL(request.url);

  if (url.pathname === '/meu-ip' || url.pathname === '/meu-ip/') {
    return pagina('IP público desta internet',
      'Envie este número para o TI para liberar o acesso ao FOXNET nesta internet.', ip, 200);
  }

  const lista = lerLista(process.env.FOXNET_IPS_LIBERADOS);
  if (lista.length && !ipLiberado(ip, lista)) {
    return pagina('Acesso não liberado nesta internet',
      'O FOXNET só abre nas internets das lojas Fox Pneus. Se você precisa acessar daqui, envie o número abaixo para o TI.',
      ip, 403);
  }
  return encaminhar(url, request);
}

export function ehDominioFoxnet(hostname) {
  return /^foxnet[.-]/i.test(String(hostname || ''));
}

// No domínio da intranet só existem estes endereços; o resto vai para o domínio dos sistemas.
export function ehDaIntranet(caminho) {
  return caminho === '/' || caminho === '/foxnet' || caminho.startsWith('/foxnet/') ||
    caminho === '/fernanda.js' || caminho === '/favicon.svg' ||
    caminho === '/favicon.png' || caminho === '/logo-fox.png';
}

function encaminhar(url, request) {
  const caminho = url.pathname.replace(/\/+$/, '') || '/';
  if (ehDominioFoxnet(url.hostname)) {
    if (!ehDaIntranet(caminho)) {
      return Response.redirect(SISTEMAS_URL + url.pathname + url.search, 307);
    }
    if (caminho === '/') return rewrite(new URL('/foxnet/', request.url));
    return next();
  }
  // App de descontos com endereço próprio
  if (caminho === '/descontos') return rewrite(new URL('/index.html', request.url));
  return next();
}
