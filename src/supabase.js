// Login seguro do FOXNET (Supabase Auth).
// A sessão fica guardada com a chave "foxnet-auth" e vale para todas as páginas
// do site (App de descontos, Cadastrar, Painel do televendas).
import { createClient } from "@supabase/supabase-js";

export const SUPA_URL = "https://dxwkiaxpygibzmwzvcuz.supabase.co";
// Chave pública (anon): pode ficar no site. Quem protege os dados são as regras do banco.
export const SUPA_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR4d2tpYXhweWdpYnptd3p2Y3V6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzczMTE3NzcsImV4cCI6MjA5Mjg4Nzc3N30.mVbUlLaRCI5OMf539Ehjt-XpfAY-wjr7_WCzPsgVvp0";

export const sb = createClient(SUPA_URL, SUPA_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, storageKey: "foxnet-auth" },
});

// Token de quem está logado, para as chamadas diretas ao banco (fetch).
// Sem login, usa a chave pública.
let token = null;
sb.auth.getSession().then(({ data }) => { token = data.session?.access_token || null; });
sb.auth.onAuthStateChange((_evento, sessao) => { token = sessao?.access_token || null; });
export const tokenAtual = () => token || SUPA_KEY;

// Cliente avulso, sem guardar sessão: usado pelo admin para cadastrar uma pessoa
// sem sair da própria conta.
export const clienteAvulso = () =>
  createClient(SUPA_URL, SUPA_KEY, {
    auth: { persistSession: false, autoRefreshToken: false, storageKey: "foxnet-avulso" },
  });

// Níveis de acesso (tabela perfis) → permissões que as telas do App já usam.
//   admin      → tudo
//   comercial  → cadastrar, consultar e liberar (antigo "cadastrar2")
//   gerente    → relatórios (Dashboard)
//   televendas → cadastrar
export const NIVEIS = [
  ["admin", "🛡️", "Admin", "Tudo: usuários, excluir, desfazer liberação e logs"],
  ["comercial", "🤝", "Comercial", "Cadastrar, consultar e liberar descontos"],
  ["gerente", "📊", "Gerente", "Relatórios (Dashboard)"],
  ["televendas", "📞", "Televendas", "Cadastrar pedidos de desconto"],
];
const MAPA = { comercial: "cadastrar2", gerente: "gerente", televendas: "televendas" };
export function papelLegado(funcoes = []) {
  if (funcoes.includes("admin")) return "admin";
  return funcoes.map((f) => MAPA[f]).filter(Boolean).join(",");
}

export async function carregarPerfil(userId) {
  const { data } = await sb
    .from("perfis")
    .select("id,nome,email,funcoes,ativo,foto")
    .eq("id", userId)
    .maybeSingle();
  return data;
}
