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
 *   foxnet.vercel.app/   (ou qualquer domínio que comece com "foxnet")
 *                        → abre direto o FOXNET (a página de /foxnet/)
 *   /descontos           → App de descontos, em qualquer domínio
 *   fox-descontos.vercel.app/ continua abrindo o App de descontos, como antes.
 */
import { ipAddress, next, rewrite } from '@vercel/functions';

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
<body><div class="c"><div style="font-size:40px">🦊</div><h1>${esc(titulo)}</h1><p>${texto}</p>
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

function encaminhar(url, request) {
  const caminho = url.pathname.replace(/\/+$/, '') || '/';
  // App de descontos com endereço próprio, em qualquer domínio
  if (caminho === '/descontos') return rewrite(new URL('/index.html', request.url));
  // Domínio do FOXNET: a raiz abre direto a intranet
  if (ehDominioFoxnet(url.hostname) && caminho === '/') return rewrite(new URL('/foxnet/', request.url));
  return next();
}
