/* funil-televendas.js · Painel "Funil do televendas" no fim do /televendas.html (pedido do TI, 27/11/2026)
   Lê funil_resumo e funil_abertos (SQL 33), gravados pelo robô funil_televendas.py (Kommo + Movere).
   Só aparece com login (televendas, gerente ou admin). Nada de nome ou telefone de cliente: o lead abre no Kommo.
   Nível 1: funil e gargalo, tempo de compra (mediana, IQR, P90, outliers, histograma, boxplot), velocidade do pipeline,
   oportunidades paradas (acima do P75 da etapa), coortes. Nível 2: ranking justo (z-score + Wilson, "inconclusivo"),
   diagnóstico por etapa, curva de sobrevivência, controle semanal (média ± 2 desvios). Nível 3: lead scoring, previsão
   do mês, alertas. No fim, a leitura estruturada. */
(function () {
  const KOMMO = "https://foxpneusltda.kommo.com/leads/detail/";
  const E = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const pct = (v, d = 0) => v == null ? "" : (v * 100).toFixed(d).replace(".", ",") + "%";
  const num = v => v == null ? "" : Number(v).toLocaleString("pt-BR", {maximumFractionDigits: 0});
  const dia = v => v == null ? "" : Number(v).toLocaleString("pt-BR", {maximumFractionDigits: 1}) + " d";
  const brl = v => v == null ? "" : Number(v).toLocaleString("pt-BR", {style: "currency", currency: "BRL", maximumFractionDigits: 0});
  const fmtD = iso => iso ? iso.slice(8, 10) + "/" + iso.slice(5, 7) : "";
  const NOME_ETAPA = {entrou: "Entrou", cotou: "Cotou", negociou: "Negociou", agendou: "Agendou", comprou: "Comprou"};
  const CLASSE = {"destaque": ["⭐ Destaque", "#16a34a"], "dentro do esperado": ["✓ Dentro do esperado", "#475569"],
                  "precisa de apoio": ["⚠ Precisa de apoio", "#CC1F1F"], "inconclusivo": ["… Inconclusivo", "#9aabb8"]};
  let R = {}, ABERTOS = [], periodo = "mes", operadora = "", soAtrasados = true;

  const css = `
  #funil-tv{margin-top:28px}#funil-tv[hidden]{display:none}
  .ft-botao{border:1px solid var(--fx-hd,#0F1F3D);background:var(--fx-hd,#0F1F3D);color:#fff;border-radius:8px;padding:7px 14px;font-weight:700;font-size:13px;cursor:pointer;white-space:nowrap}
  .ft-botao.on{background:var(--fx-s1,#fff);color:var(--fx-hd,#0F1F3D)}
  #funil-tv h2{font-size:20px;font-weight:800;color:var(--fx-tx0,#0f1f3d);margin:0 0 4px}
  #funil-tv .sub{font-size:12px;color:var(--fx-tx3,#7a8ba0);margin-bottom:14px}
  #funil-tv .ft-bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
  #funil-tv .ft-bar button,#funil-tv .ft-bar select{border:1px solid var(--fx-bd,#e2e8f0);background:var(--fx-s1,#fff);color:var(--fx-tx,#1a2332);border-radius:8px;padding:7px 12px;font-weight:700;font-size:12px;cursor:pointer}
  #funil-tv .ft-bar button.on{background:var(--fx-hd,#0F1F3D);color:#fff;border-color:var(--fx-hd,#0F1F3D)}
  #funil-tv .ft-sec{background:var(--fx-s1,#fff);border:1px solid var(--fx-bd,#e2e8f0);border-radius:12px;padding:16px 18px;margin-bottom:14px;box-shadow:0 1px 3px #0001}
  #funil-tv .ft-sec h3{font-size:14px;font-weight:800;margin:0 0 4px;color:var(--fx-tx0,#0f1f3d)}
  #funil-tv .ft-sec .ex{font-size:11px;color:var(--fx-tx3,#7a8ba0);margin-bottom:10px}
  #funil-tv .ft-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}
  #funil-tv .ft-k{background:var(--fx-s1,#fff);border:1px solid var(--fx-bd,#e2e8f0);border-radius:10px;padding:12px 14px}
  #funil-tv .ft-k b{display:block;font-size:20px;font-weight:800;color:var(--fx-tx0,#0f1f3d)}
  #funil-tv .ft-k span{font-size:10px;text-transform:uppercase;letter-spacing:.5px;font-weight:700;color:var(--fx-tx3,#7a8ba0)}
  #funil-tv .ft-k small{display:block;font-size:11px;color:var(--fx-tx3,#7a8ba0);margin-top:2px}
  #funil-tv table{font-size:12px}#funil-tv th{font-size:11px;padding:8px 6px;background:var(--fx-hd,#0F1F3D);color:#fff}
  #funil-tv td{padding:7px 6px;border-top:1px solid var(--fx-bd,#eef2f7)}
  #funil-tv .ft-tw{overflow-x:auto}
  #funil-tv .ft-bad{background:var(--fx-erbg,#fde8e8)}#funil-tv .ft-bad td{color:var(--fx-ertx,#b91c1c)}
  #funil-tv .ft-tag{display:inline-block;border-radius:99px;padding:2px 9px;font-size:11px;font-weight:700;color:#fff}
  #funil-tv .ft-alerta{background:var(--fx-avbg,#fff8e7);border:1px solid #fde68a;color:var(--fx-avtx,#92400e);border-radius:10px;padding:10px 14px;margin-bottom:14px;font-size:13px}
  #funil-tv .ft-leitura p{font-size:13px;line-height:1.6;margin:0 0 10px;color:var(--fx-tx,#1a2332)}
  #funil-tv .ft-leitura h4{font-size:13px;margin:14px 0 4px;color:var(--fx-tx0,#0f1f3d)}
  #funil-tv .ft-2{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:900px){#funil-tv .ft-2{grid-template-columns:1fr}}
  #funil-tv svg text{font-family:inherit}`;

  function sec(titulo, ex, corpo) { return `<div class="ft-sec"><h3>${titulo}</h3>${ex ? `<div class="ex">${ex}</div>` : ""}${corpo}</div>`; }

  // ── Gráficos (SVG feito à mão, sem biblioteca) ──
  function barrasFunil(f) {
    const et = ["entrou", "cotou", "agendou", "comprou"], max = f.etapas.entrou || 1, W = 560;
    const gar = f.gargalo;
    return `<svg viewBox="0 0 ${W} ${et.length * 46}" style="width:100%;max-width:${W}px">` + et.map((e, i) => {
      const v = f.etapas[e], w = Math.max(4, v / max * (W - 210)), y = i * 46;
      const p = i ? f.passos[i - 1] : null, ruim = p && gar === p.de + "→" + p.para;
      return `<rect x="0" y="${y + 6}" width="${w}" height="30" rx="5" fill="${ruim ? "#CC1F1F" : "#0F1F3D"}" opacity="${1 - i * .15}"/>
        <text x="${w + 8}" y="${y + 26}" font-size="13" font-weight="700" fill="currentColor">${NOME_ETAPA[e]}: ${num(v)}</text>
        ${p ? `<text x="${W - 4}" y="${y + 26}" font-size="12" text-anchor="end" fill="${ruim ? "#CC1F1F" : "#64748b"}">${pct(p.taxa)} da etapa anterior${ruim ? " · gargalo" : ""}</text>` : ""}`;
    }).join("") + `</svg>`;
  }
  function histograma(h) {
    const max = Math.max(1, ...h.map(x => x.n)), W = 520, H = 150, bw = W / h.length;
    return `<svg viewBox="0 0 ${W} ${H + 30}" style="width:100%;max-width:${W}px">` + h.map((x, i) => {
      const hh = x.n / max * H;
      return `<rect x="${i * bw + 3}" y="${H - hh}" width="${bw - 6}" height="${hh}" fill="#3b82f6" rx="3"/>
        <text x="${i * bw + bw / 2}" y="${H - hh - 4}" font-size="11" text-anchor="middle" fill="currentColor">${x.n || ""}</text>
        <text x="${i * bw + bw / 2}" y="${H + 16}" font-size="10" text-anchor="middle" fill="#64748b">${x.ate == null ? x.de + "+" : x.de + "–" + (x.ate - 1)}</text>`;
    }).join("") + `<text x="${W / 2}" y="${H + 29}" font-size="10" text-anchor="middle" fill="#64748b">dias entre a entrada e a compra</text></svg>`;
  }
  function boxplot(ops) {
    const L = Object.entries(ops).filter(([, x]) => x.q1 != null);
    if (!L.length) return "<p>Ainda sem compras suficientes.</p>";
    const max = Math.max(...L.map(([, x]) => x.max || 0), 1), W = 560, x0 = 120, esc = v => x0 + v / max * (W - x0 - 20);
    return `<svg viewBox="0 0 ${W} ${L.length * 34 + 20}" style="width:100%;max-width:${W}px">` + L.map(([n, x], i) => {
      const y = i * 34 + 16;
      return `<text x="0" y="${y + 4}" font-size="12" fill="currentColor">${E(n)}</text>
        <line x1="${esc(x.min)}" x2="${esc(x.max)}" y1="${y}" y2="${y}" stroke="#94a3b8"/>
        <rect x="${esc(x.q1)}" y="${y - 9}" width="${Math.max(2, esc(x.q3) - esc(x.q1))}" height="18" fill="#bfdbfe" stroke="#3b82f6"/>
        <line x1="${esc(x.tempo_mediano)}" x2="${esc(x.tempo_mediano)}" y1="${y - 9}" y2="${y + 9}" stroke="#0F1F3D" stroke-width="2.5"/>`;
    }).join("") + `<text x="${W - 20}" y="${L.length * 34 + 16}" font-size="10" text-anchor="end" fill="#64748b">0 a ${num(max)} dias · caixa = Q1 a Q3 · traço = mediana</text></svg>`;
  }
  function linha(pontos, {ymax = 1, faixa = null, W = 560, H = 160, rotX = v => v, rotY = v => pct(v)} = {}) {
    if (!pontos.length) return "";
    const xs = pontos.map(p => p[0]), xmin = Math.min(...xs), xmax = Math.max(...xs, xmin + 1);
    const X = v => 40 + (v - xmin) / (xmax - xmin) * (W - 60), Y = v => 10 + (1 - v / ymax) * H;
    let s = `<svg viewBox="0 0 ${W} ${H + 40}" style="width:100%;max-width:${W}px">`;
    if (faixa) s += `<rect x="40" y="${Y(faixa[1])}" width="${W - 60}" height="${Math.max(1, Y(faixa[0]) - Y(faixa[1]))}" fill="#dcfce7"/>
      <line x1="40" x2="${W - 20}" y1="${Y(faixa[2])}" y2="${Y(faixa[2])}" stroke="#16a34a" stroke-dasharray="4"/>`;
    s += `<polyline fill="none" stroke="#0F1F3D" stroke-width="2.2" points="${pontos.map(p => X(p[0]) + "," + Y(p[1])).join(" ")}"/>`;
    s += pontos.map(p => `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="3.2" fill="${p[2] ? "#CC1F1F" : "#0F1F3D"}"/>`).join("");
    s += `<text x="4" y="${Y(ymax) + 4}" font-size="10" fill="#64748b">${rotY(ymax)}</text><text x="4" y="${Y(0)}" font-size="10" fill="#64748b">${rotY(0)}</text>`;
    s += `<text x="40" y="${H + 30}" font-size="10" fill="#64748b">${rotX(xmin)}</text><text x="${W - 20}" y="${H + 30}" font-size="10" text-anchor="end" fill="#64748b">${rotX(xmax)}</text></svg>`;
    return s;
  }

  // ── Leitura estruturada (texto automático, no fim do painel) ──
  function leitura(r, ops) {
    const f = r.funil, et = f.etapas, t = r.tempos.entrada_compra || {}, v = r.velocidade, prev = r.previsao || {};
    const apoio = Object.entries(ops).filter(([, x]) => x.classe === "precisa de apoio");
    const dest = Object.entries(ops).filter(([, x]) => x.classe === "destaque");
    const inc = Object.entries(ops).filter(([, x]) => x.classe === "inconclusivo");
    const paradas = ABERTOS.filter(a => a.atrasado).length;
    const coo = (r.coortes || []).filter(c => c.conv_30d != null), ult = coo[coo.length - 1], pen = coo[coo.length - 2];
    const p = [];
    p.push(`<h4>1. Resumo do período</h4><p>De ${fmtD(r.desde)} a ${fmtD(r.ate)} entraram <b>${num(et.entrou)}</b> clientes no Funil Principal (sem disparos e sem ${num(Object.values(r.fora_da_conta || {}).reduce((a, b) => a + b, 0))} contatos que não eram oportunidade). <b>${num(et.cotou)}</b> cotaram, <b>${num(et.agendou)}</b> agendaram e <b>${num(et.comprou)}</b> compraram: conversão geral de <b>${pct(f.geral, 1)}</b>.</p>`);
    if (f.gargalo) { const g = f.passos.find(x => x.de + "→" + x.para === f.gargalo);
      p.push(`<h4>2. Onde mais se perde (gargalo)</h4><p>A passagem <b>${NOME_ETAPA[g.de]} → ${NOME_ETAPA[g.para]}</b> tem a menor conversão (${pct(g.taxa)}): ${num(g.perdidos)} clientes ficam nessa etapa. É aqui que um ponto de melhoria rende mais.</p>`); }
    p.push(`<h4>3. Equipe</h4><p>${dest.length ? `Destaque: ${dest.map(([n]) => "<b>" + E(n) + "</b>").join(", ")}. ` : ""}${apoio.length ? `Precisa de apoio: ${apoio.map(([n, x]) => "<b>" + E(n) + "</b>" + (x.pior_etapa ? ` (perde mais em ${x.pior_etapa.replace("→", " → ")})` : "")).join(", ")}. ` : "Ninguém está claramente abaixo da equipe. "}${inc.length ? `Inconclusivo (poucos clientes ou intervalo que cruza a média, a diferença pode ser sorte): ${inc.map(([n]) => E(n)).join(", ")}.` : ""}</p>`);
    if (t.n) p.push(`<h4>4. Tempo até a compra</h4><p>Metade dos clientes compra em até <b>${dia(t.mediana)}</b> depois de entrar (mediana); a média é ${dia(t.media)} porque poucos clientes lentos puxam para cima. 50% ficam entre ${dia(t.q1)} e ${dia(t.q3)}; 90% compram em até ${dia(t.p90)}. ${t.outliers ? `${t.outliers} compra(s) muito fora do normal foram separadas.` : ""} Chance de comprar em até 30 dias: <b>${pct((r.sobrevivencia.chance || {})["30"], 1)}</b>.</p>`);
    if (v.por_dia != null) p.push(`<h4>5. Velocidade do pipeline</h4><p>Passam pelo funil cerca de <b>${brl(v.por_dia)} por dia</b> (${num(v.oportunidades)} oportunidades abertas × ${pct(v.conversao, 1)} de conversão × ${brl(v.ticket)} de ticket ÷ ${dia(v.ciclo_dias)} de ciclo). Para aumentar: mais oportunidades, mais conversão, ticket maior ou ciclo menor.</p>`);
    p.push(`<h4>6. Follow-up de hoje</h4><p>${paradas ? `<b>${num(paradas)}</b> oportunidade(s) estão paradas há mais tempo que o normal da etapa (acima do percentil 75). Comece pelas de maior chance de compra na lista de oportunidades paradas.` : "Nenhuma oportunidade parada além do normal."}</p>`);
    if (ult) p.push(`<h4>7. Tendência</h4><p>Dos clientes que entraram em ${ult.mes.slice(5, 7)}/${ult.mes.slice(0, 4)} (já com 30 dias), ${pct(ult.conv_30d, 1)} compraram em até 30 dias${pen ? `, contra ${pct(pen.conv_30d, 1)} de quem entrou em ${pen.mes.slice(5, 7)}/${pen.mes.slice(0, 4)}` : ""}. ${(r.semanal || {}).fora && r.semanal.fora.length ? "<b>Atenção:</b> houve semana fora dos limites normais no controle semanal." : "A conversão semanal está dentro da variação normal."}</p>`);
    if (prev.previsao != null) p.push(`<h4>8. Previsão do mês</h4><p>Já vendido pelo funil: ${brl(prev.vendido)}. Com a chance de compra de cada oportunidade aberta, a previsão para o fim do mês é <b>${brl(prev.previsao)}</b> (faixa provável de ${brl(prev.minimo)} a ${brl(prev.maximo)}). ${r.modelo && r.modelo.auc ? `O modelo acertou a ordem de quem compra em ${pct(r.modelo.auc)} dos pares testados (AUC).` : ""}</p>`);
    p.push(`<h4>9. Qualidade dos dados</h4><p>A previsão só é tão boa quanto as datas: manter marcadas no cartão do Kommo as etapas (cotação, negociação, agendamento) e mover para VENDA GANHA quem foi à loja deixa os números mais certos.</p>`);
    return p.join("");
  }

  function desenhar() {
    const box = document.getElementById("funil-tv"); if (!box) return;
    // Períodos: os que o robô gravou (o ano passado só aparece quando a carga do histórico chegar lá)
    const NOMES_P = {mes: "Este mês", "30d": "Últimos 30 dias", "90d": "Últimos 90 dias", ano: "Este ano", tudo: "Desde o início"};
    const ps = ["mes", "30d", "90d", "ano", ...Object.keys(R).filter(k => /^\d{4}$/.test(k)).sort(), "tudo"].filter(k => R[k]);
    box.querySelector("#ft-periodos").innerHTML = ps.map(k => `<button data-p="${k}" class="${k === periodo ? "on" : ""}" style="margin-right:6px">${NOMES_P[k] || k}</button>`).join("");
    box.querySelectorAll("[data-p]").forEach(b => b.onclick = () => { periodo = b.dataset.p; desenhar(); });
    const r = R[periodo];
    if (!r) { box.querySelector(".ft-corpo").innerHTML = `<div class="ft-sec">Ainda não há dados do funil. O robô roda às 6h30, 12h30 e 18h30.</div>`; return; }
    const ops = r.operadoras || {}, opList = Object.keys(ops).filter(n => n !== "(sem operadora)" && n !== "Fox Pneus");
    const sel = operadora && ops[operadora] ? ops[operadora] : null;
    const f = sel ? {etapas: {entrou: sel.clientes, cotou: sel.cotou, agendou: sel.agendou, comprou: sel.comprou}, passos: sel.passos, geral: sel.conversao,
      gargalo: (() => { const v = sel.passos.filter(p => p.taxa != null); return v.length ? (m => m.de + "→" + m.para)(v.reduce((a, b) => a.taxa <= b.taxa ? a : b)) : null; })()} : r.funil;
    const t = r.tempos, v = r.velocidade, prev = r.previsao || {};
    let h = "";
    if (r.carga_desde && r.carga_desde > "2025-01-01") h += `<div class="ft-alerta" style="background:#eef6ff;border-color:#bfdbfe;color:#1e3a8a">📚 Histórico carregado desde ${fmtD(r.carga_desde)}/${r.carga_desde.slice(0, 4)}. O robô volta 2 meses por rodada até janeiro de 2025 (alguns dias).</div>`;
    if ((r.alertas || []).length) h += `<div class="ft-alerta">🔔 <b>Alertas</b><br>· ${r.alertas.map(E).join("<br>· ")}</div>`;
    h += `<div class="ft-grid">
      <div class="ft-k"><span>Entraram</span><b>${num(f.etapas.entrou)}</b><small>Funil Principal, sem disparos</small></div>
      <div class="ft-k"><span>Cotaram</span><b>${num(f.etapas.cotou)}</b><small>${pct(f.etapas.entrou ? f.etapas.cotou / f.etapas.entrou : null)}</small></div>
      <div class="ft-k"><span>Agendaram</span><b>${num(f.etapas.agendou)}</b><small>${pct(f.etapas.entrou ? f.etapas.agendou / f.etapas.entrou : null)}</small></div>
      <div class="ft-k"><span>Compraram</span><b>${num(f.etapas.comprou)}</b><small>conversão ${pct(f.geral, 1)}</small></div>
      <div class="ft-k"><span>Velocidade</span><b>${v.por_dia != null ? brl(v.por_dia) : ""}</b><small>por dia no funil</small></div>
      <div class="ft-k"><span>Previsão do mês</span><b>${brl(prev.previsao)}</b><small>${brl(prev.minimo)} a ${brl(prev.maximo)}</small></div></div>`;
    // Pelo Kommo (Trackeamento): os mesmos números dos filtros do Kommo (campos = Sim agora), pedido do TI 28/11/2026
    const K = r.kommo;
    if (K && !sel) {
      const pc = (a, b) => b ? ` <i style="color:#64748b;font-style:normal">(${pct(a / b)})</i>` : "";
      const lin = (n, v, sub) => `<tr><td style="text-align:left">${n}</td><td><b>${num(v)}</b></td><td style="text-align:left;color:#64748b">${sub || ""}</td></tr>`;
      h += sec("📋 Pelo Kommo (Trackeamento)", "Como os filtros do Kommo: campos do cartão marcados como Sim agora, nos cartões criados no período (Funil Principal, sem disparos). Bate com o que a equipe vê no Kommo.",
        `<div class="ft-tw"><table><tr><th style="text-align:left">No Kommo</th><th>Cartões</th><th style="text-align:left">Detalhe</th></tr>` +
        lin("Entrou no Kommo de alguma forma", K.alguma_forma, "todos os cartões criados") +
        lin("1 · Entrou (Contato Inicial)", K.contato, `${num(K.sem_contato)} adicionados sem Contato Inicial`) +
        lin("2 · Fez cotação", K.cotou, `${pc(K.cotou, K.contato).trim()} dos que entraram · cotou sem Contato Inicial: ${num(K.cotou_sem_contato)}`) +
        lin("&nbsp;&nbsp;3 · Cotação criada pela IA", K.cotou_ia, `orçamento que a IA fez${pc(K.cotou_ia, K.cotou)}${K.so_cotacao_ia ? ` · ${num(K.so_cotacao_ia)} sem o "Fez cotação"` : ""}`) +
        lin("&nbsp;&nbsp;Cotou sem passar pela IA", K.cotou_sem_ia, "a equipe fez o orçamento (Fez cotação sem o campo da IA)") +
        lin("4 · Negociou", K.negociou, "") +
        lin("6/7 · Agendou (IA ou equipe)", K.agendou, `só IA ${num(K.ag_so_ia)} · IA confirmado pela equipe ${num(K.ag_ia_e_equipe)} · só equipe ${num(K.ag_so_equipe)}`) +
        lin("&nbsp;&nbsp;Agendamento IA (campo 6)", K.ag_ia, "") +
        lin("&nbsp;&nbsp;Agendamento (campo 7)", K.ag_equipe, "") +
        lin("&nbsp;&nbsp;IA + Agendamento (os dois)", K.ag_ia_e_equipe, `VENDA GANHA ${num(K.ag_conf_ganha)} · venda perdida ${num(K.ag_conf_perdida)} · comprou no Movere ${num(K.ag_conf_comprou_real)}`) +
        lin("Contato Inicial + Fez cotação + Agendamento IA", K.caminho_cot_agia, `VENDA GANHA ${num(K.caminho_cot_agia_ganha)} · venda perdida ${num(K.caminho_cot_agia_perdida)}`) +
                lin("🟢 VENDA GANHA (etapa)", K.venda_ganha, `com o Movere (nota ou O.S.): ${num(K.comprou_real)} compraram`) +
        lin("🔴 venda perdida (etapa)", K.venda_perdida, "") +
        lin("5 · Recuperação Inicial (disparo noturno)", K.recuperacao, `passou pela etapa Disparo Noturno e recebeu a mensagem das 19h30 · ${num(K.recuperacao_comprou)} compraram depois`) +
        `</table></div>`, true);
    }
    h += `<div class="ft-2">` + sec("1. Funil de vendas" + (sel ? " · " + E(operadora) : ""), "Quem comprou conta como tendo passado pelas etapas anteriores. Em vermelho, o gargalo (a passagem com a menor conversão).", barrasFunil(f))
      + sec("Por que perdemos", "Motivo da venda perdida (Kommo). Fora da conta (não eram oportunidade): " + Object.entries(r.fora_da_conta || {}).map(([k, n]) => E(k) + " " + num(n)).join(" · "),
        `<div class="ft-tw"><table><tr><th>Motivo</th><th>Clientes</th></tr>${Object.entries(r.motivos_perda || {}).slice(0, 12).map(([k, n]) => `<tr><td style="text-align:left">${E(k)}</td><td>${num(n)}</td></tr>`).join("")}</table></div>`) + `</div>`;
    // Ranking justo + diagnóstico
    h += sec("2. Desempenho das operadoras (ranking justo)", "z-score da conversão em relação à equipe e intervalo de confiança de 95% (Wilson). Com menos de 30 clientes ou quando o intervalo cruza a média da equipe (" + pct(r.media_equipe, 1) + "), a diferença pode ser sorte: fica \"inconclusivo\".",
      `<div class="ft-tw"><table><tr><th>Operadora</th><th>Clientes</th><th>Cotou</th><th>Agendou</th><th>Comprou</th><th>Conversão (IC 95%)</th><th>Entrou→Cotou</th><th>Cotou→Agendou</th><th>Agendou→Comprou</th><th>Receita</th><th>Ticket</th><th>Tempo mediano</th><th>z</th><th>Situação</th><th>Onde mais perde</th></tr>` +
      opList.sort((a, b) => (ops[b].conversao || 0) - (ops[a].conversao || 0)).map(n => { const x = ops[n], c = CLASSE[x.classe] || ["", "#999"];
        return `<tr><td style="text-align:left;font-weight:700">${E(n)}</td><td>${num(x.clientes)}</td><td>${num(x.cotou)}</td><td>${num(x.agendou)}</td><td>${num(x.comprou)}</td>
        <td><b>${pct(x.conversao, 1)}</b> <small style="color:#64748b">(${pct(x.ic_inf, 1)} a ${pct(x.ic_sup, 1)})</small></td>
        ${x.passos.map(p => `<td>${pct(p.taxa)}</td>`).join("")}<td>${brl(x.receita)}</td><td>${brl(x.ticket)}</td><td>${dia(x.tempo_mediano)}</td><td>${x.z.toFixed(2).replace(".", ",")}</td>
        <td><span class="ft-tag" style="background:${c[1]}">${c[0]}</span></td><td>${x.pior_etapa ? x.pior_etapa.replace("→", " → ") + ` (${pct(x.pior_dif)})` : ""}</td></tr>`; }).join("") + `</table></div>`);
    // Tempo
    const linT = (n, k) => { const x = t[k] || {}; return `<tr><td style="text-align:left">${n}</td><td><b>${dia(x.mediana)}</b></td><td>${dia(x.media)}</td><td>${x.n ? dia(x.q1) + " a " + dia(x.q3) : ""}</td><td>${dia(x.p25)}</td><td>${dia(x.p50)}</td><td>${dia(x.p75)}</td><td>${dia(x.p90)}</td><td>${num(x.outliers)}</td><td>${num(x.n)}</td></tr>`; };
    h += sec("3. Tempo de compra", "A mediana é a medida principal: o tempo tem assimetria positiva (poucos clientes lentos puxam a média). Outliers: fora de Q1 − 1,5×IQR e Q3 + 1,5×IQR.",
      `<div class="ft-tw"><table><tr><th>Etapa</th><th>Mediana</th><th>Média</th><th>Q1 a Q3</th><th>P25</th><th>P50</th><th>P75</th><th>P90</th><th>Outliers</th><th>Clientes</th></tr>${linT("Entrada → cotação", "entrada_cotacao")}${linT("Cotação → agendamento", "cotacao_agendamento")}${linT("Agendamento → compra", "agendamento_compra")}${linT("<b>Entrada → compra</b>", "entrada_compra")}</table></div>
      <div class="ft-2" style="margin-top:12px"><div>${histograma(t.histograma || [])}</div><div>${boxplot(ops)}</div></div>`
      + ((t.outliers || []).length ? `<div class="ex" style="margin-top:6px">Compras fora do normal (abrir no Kommo): ${t.outliers.slice(0, 20).map(id => `<a href="${KOMMO}${id}" target="_blank" rel="noopener">#${id}</a>`).join(" ")}</div>` : ""));
    // Velocidade
    h += sec("4. Velocidade do pipeline", "velocidade = oportunidades abertas × conversão × ticket médio ÷ ciclo (dias). Em vermelho, a alavanca que está abaixo da equipe.",
      `<div class="ft-tw"><table><tr><th>Quem</th><th>Oportunidades</th><th>Conversão</th><th>Ticket</th><th>Ciclo</th><th>R$ por dia</th></tr>
      <tr style="font-weight:700"><td style="text-align:left">Equipe</td><td>${num(v.oportunidades)}</td><td>${pct(v.conversao, 1)}</td><td>${brl(v.ticket)}</td><td>${dia(v.ciclo_dias)}</td><td>${brl(v.por_dia)}</td></tr>` +
      opList.map(n => { const x = ops[n], m = (a, b, inv) => (a != null && b != null && (inv ? a > b : a < b)) ? ' style="color:#CC1F1F;font-weight:700"' : "";
        return `<tr><td style="text-align:left">${E(n)}</td><td${m(x.abertos, v.oportunidades / Math.max(1, opList.length))}>${num(x.abertos)}</td><td${m(x.conversao, v.conversao)}>${pct(x.conversao, 1)}</td><td${m(x.ticket, v.ticket)}>${brl(x.ticket)}</td><td${m(x.tempo_mediano, v.ciclo_dias, true)}>${dia(x.tempo_mediano)}</td><td>${brl(x.velocidade)}</td></tr>`; }).join("") + `</table></div>`);
    // Aging + lead scoring
    const ab = ABERTOS.filter(a => (!operadora || a.operadora === operadora) && (!soAtrasados || a.atrasado)).sort((a, b) => (b.chance || 0) - (a.chance || 0));
    h += sec("5. Oportunidades paradas (follow-up do dia)", `Em vermelho, paradas há mais tempo que o percentil 75 da etapa (${Object.entries(r.p75_etapa || {}).map(([e, d]) => NOME_ETAPA[e] + " " + dia(d)).join(" · ")}). Ordenadas pela chance de compra (lead scoring): comece pelas mais quentes. O nº abre o cartão no Kommo.`,
      `<div class="ft-bar"><button id="ft-atr" class="${soAtrasados ? "on" : ""}">Só as paradas (${num(ABERTOS.filter(a => a.atrasado && (!operadora || a.operadora === operadora)).length)})</button><button id="ft-tod" class="${!soAtrasados ? "on" : ""}">Todas em aberto</button></div>
      <div class="ft-tw" style="max-height:420px;overflow:auto"><table><tr><th>Lead</th><th>Operadora</th><th>Etapa</th><th>Desde</th><th>Dias parado</th><th>Valor da cotação</th><th>Chance de compra</th><th>Origem</th></tr>` +
      ab.slice(0, 300).map(a => `<tr class="${a.atrasado ? "ft-bad" : ""}"><td><a href="${KOMMO}${a.lead_id}" target="_blank" rel="noopener">#${a.lead_id}</a></td><td>${E(a.operadora)}</td><td>${NOME_ETAPA[a.etapa] || E(a.etapa)}</td><td>${fmtD(a.desde)}</td><td><b>${num(a.dias_parado)}</b></td><td>${brl(a.valor_cotacao)}</td><td>${a.chance != null ? (a.chance >= .3 ? "🔥 " : "") + pct(a.chance) : ""}</td><td>${E(a.origem)}</td></tr>`).join("") + `</table></div>`);
    // Coortes + sobrevivência
    h += `<div class="ft-2">` + sec("6. Coortes por mês de entrada", "Compara os clientes pelo mês em que ENTRARAM. \"Em 30 dias\" só conta quem já teve 30 dias (comparação justa).",
      `<div class="ft-tw"><table><tr><th>Mês</th><th>Entraram</th><th>Cotaram</th><th>Agendaram</th><th>Compraram</th><th>Conversão até hoje</th><th>Compraram em 30 dias</th></tr>` +
      (r.coortes || []).map(c => `<tr><td>${c.mes.slice(5, 7)}/${c.mes.slice(0, 4)}</td><td>${num(c.entrou)}</td><td>${num(c.cotou)}</td><td>${num(c.agendou)}</td><td>${num(c.comprou)}</td><td>${pct(c.conversao, 1)}</td><td>${c.conv_30d != null ? pct(c.conv_30d, 1) : "ainda sem 30 dias"}</td></tr>`).join("") + `</table></div>`)
      + sec("7. Curva de tempo até a compra (sobrevivência)", "Conta também quem ainda não comprou (Kaplan-Meier). Chance de comprar em até: " + Object.entries(r.sobrevivencia.chance || {}).map(([d, c]) => `<b>${d} dias: ${pct(c, 1)}</b>`).join(" · "),
        linha((r.sobrevivencia.curva || []).map(([d, s]) => [d, 1 - s]), {ymax: Math.max(.05, ...(r.sobrevivencia.curva || []).map(([, s]) => 1 - s)), rotX: v => v + " dias"})) + `</div>`;
    // Controle semanal + modelo
    const s = r.semanal || {};
    h += `<div class="ft-2">` + sec("8. Controle semanal da conversão", s.media != null ? `Conversão em até 14 dias por semana de entrada. Faixa verde = média (${pct(s.media, 1)}) ± 2 desvios (${pct(s.lim_inf, 1)} a ${pct(s.lim_sup, 1)}). Ponto vermelho = semana fora do normal (problema real, não variação).` : "Ainda são poucas semanas para o controle.",
      linha((s.semanas || []).map((w, i) => [i, w.taxa, (s.fora || []).includes(w.semana)]), {ymax: Math.max(.05, s.lim_sup || 0, ...(s.semanas || []).map(w => w.taxa)) * 1.1, faixa: s.media != null ? [s.lim_inf, s.lim_sup, s.media] : null, rotX: i => (s.semanas[i] ? "sem. " + fmtD(s.semanas[i].semana) : "")}))
      + sec("9. Lead scoring (chance de compra)", r.modelo ? `Modelo treinado com ${num(r.modelo.n_treino)} clientes que já tiveram 30 dias (${pct(r.modelo.base, 1)} compraram). Validação nos 20% mais recentes: AUC ${r.modelo.auc != null ? r.modelo.auc.toFixed(2).replace(".", ",") : ""} (0,5 = chute · 1 = perfeito).` : "Ainda sem dados suficientes para o modelo.",
        r.modelo ? `<div class="ft-tw"><table><tr><th>O que mais pesa</th><th>Efeito</th></tr>${r.modelo.fatores.map(([n, w]) => `<tr><td style="text-align:left">${E(n)}</td><td style="color:${w >= 0 ? "#16a34a" : "#CC1F1F"};font-weight:700">${w >= 0 ? "aumenta" : "diminui"} a chance</td></tr>`).join("")}</table></div>` : "") + `</div>`;
    // Origem
    h += sec("10. Origem dos clientes", "Conversão por origem (utm do Kommo).", `<div class="ft-tw"><table><tr><th>Origem</th><th>Entraram</th><th>Compraram</th><th>Conversão</th></tr>` +
      Object.entries(r.origens || {}).sort((a, b) => b[1].entrou - a[1].entrou).slice(0, 10).map(([o, x]) => `<tr><td style="text-align:left">${E(o)}</td><td>${num(x.entrou)}</td><td>${num(x.comprou)}</td><td>${pct(x.entrou ? x.comprou / x.entrou : null, 1)}</td></tr>`).join("") + `</table></div>`);
    // De onde veio cada compra (qualidade dos dados)
    const FONTES = {os: "🧾 Cotação virou O.S. (Movere)", movere: "📄 Nota no Movere pelo telefone", venda_ganha: "✅ Coluna VENDA GANHA do Kommo", "1a_venda": "📝 Campo 1ª Venda do Kommo", sem_fonte: "Sem a informação (antes desta melhoria)"};
    const fc = Object.entries(r.fontes_compra || {}), tf = fc.reduce((a, [, n]) => a + n, 0);
    if (tf) h += sec("11. De onde veio cada compra", "Como o sistema soube que o cliente comprou. Quanto mais vier do Movere (O.S. ou nota), mais confiável o número.",
      `<div class="ft-tw"><table><tr><th>Fonte</th><th>Compras</th><th>%</th></tr>` + fc.sort((a, b) => b[1] - a[1]).map(([k, n]) => `<tr><td style="text-align:left">${E(FONTES[k] || k)}</td><td>${num(n)}</td><td>${pct(n / tf, 1)}</td></tr>`).join("") + `</table></div>`);
    h += sec("📋 Leitura estruturada", "Texto automático com os números do período.", `<div class="ft-leitura">${leitura(r, ops)}</div>`);
    box.querySelector(".ft-corpo").innerHTML = h;
    const a1 = document.getElementById("ft-atr"), a2 = document.getElementById("ft-tod");
    if (a1) a1.onclick = () => { soAtrasados = true; desenhar(); };
    if (a2) a2.onclick = () => { soAtrasados = false; desenhar(); };
    box.querySelector(".ft-hora").textContent = r && R._em ? "Atualizado " + R._em : "";
    const so = box.querySelector("#ft-op");
    so.innerHTML = `<option value="">Equipe toda</option>` + opList.map(n => `<option ${n === operadora ? "selected" : ""}>${E(n)}</option>`).join("");
    window.FE_FUNIL = {r, ops, abertos: ABERTOS, periodo};      // para a Fernanda responder perguntas sobre o funil
  }

  async function carregar() {
    const box = document.getElementById("funil-tv");
    box.querySelector(".ft-corpo").innerHTML = `<div class="ft-sec">Carregando o funil…</div>`;
    try {
      const [a, b] = await Promise.all([lerTV(`${SB_URL}/rest/v1/funil_resumo?select=periodo,dados,atualizado_em`),
                                       lerTV(`${SB_URL}/rest/v1/funil_abertos?select=*&limit=5000`)]);
      if (!a.ok) throw new Error(a.status === 404 ? "falta rodar o passo 33 no Supabase" : "erro " + a.status);
      const rows = await a.json();
      R = {}; rows.forEach(x => { R[x.periodo] = x.dados; R._em = new Date(x.atualizado_em).toLocaleString("pt-BR", {timeZone: "America/Porto_Velho", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"}); });
      ABERTOS = b.ok ? await b.json() : [];
      if (!rows.length) { box.querySelector(".ft-corpo").innerHTML = `<div class="ft-sec">Ainda não há dados do funil (ou o seu login não tem acesso). O robô roda às 6h30, 12h30 e 18h30.</div>`; return; }
      desenhar();
    } catch (e) { box.querySelector(".ft-corpo").innerHTML = `<div class="ft-sec">Não consegui carregar o funil: ${E(e.message)}</div>`; }
  }

  function montar() {
    if (document.getElementById("funil-tv")) return;
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    const box = document.createElement("div"); box.id = "funil-tv"; box.hidden = true;   // abre pelo botão "📈 Estatísticas"
    box.innerHTML = `<h2>📈 Funil do televendas</h2><div class="sub">Kommo (entrada, cotação, agendamento, venda ganha/perdida) + Movere (cotação e nota fiscal pelo telefone) · <span class="ft-hora"></span></div>
      <div class="ft-bar"><span id="ft-periodos"></span><select id="ft-op"><option value="">Equipe toda</option></select></div><div class="ft-corpo"></div>`;
    (document.getElementById("tabela-wrap") || document.body).insertAdjacentElement("afterend", box);
    box.querySelector("#ft-op").onchange = e => { operadora = e.target.value; desenhar(); };
    // Botão "📈 Estatísticas" no topo, ao lado do filtro de data (pedido do TI, 27/11/2026): abre e fecha o painel
    const bot = document.createElement("button");
    bot.className = "ft-botao"; bot.id = "ft-abrir"; bot.type = "button"; bot.textContent = "📈 Estatísticas";
    bot.title = "Funil do televendas: entrou → cotou → agendou → comprou, tempos, ranking, previsão";
    // Fica EMBAIXO do filtro de data (que continua no mesmo lugar) e só aparece para o admin (TI, 27/11/2026)
    const lugar = document.querySelector(".filtro-data-wrap");
    if (lugar) {
      const col = document.createElement("div");
      col.style.cssText = "display:flex;flex-direction:column;align-items:flex-end;gap:8px";
      lugar.parentNode.insertBefore(col, lugar);
      col.appendChild(lugar); col.appendChild(bot);
    } else box.insertAdjacentElement("beforebegin", bot);
    bot.hidden = true;
    const conferirAdmin = () => { const adm = typeof isAdmin === "function" && isAdmin(); bot.hidden = !adm; if (!adm) box.hidden = true; return adm; };
    // o login do FOXNET é conferido alguns segundos depois de abrir a página: confere de novo por 20 s
    let tentativas = 0;
    const t = setInterval(() => { if (conferirAdmin() || ++tentativas > 20) clearInterval(t); }, 1000);
    conferirAdmin();
    let carregado = false;
    bot.onclick = () => {
      const abrir = box.hidden;
      if (!conferirAdmin()) return;
      if (abrir && !isAutenticado()) { exigirAcesso(() => { box.hidden = false; bot.classList.add("on"); bot.textContent = "✕ Fechar estatísticas"; carregado = true; carregar(); box.scrollIntoView({behavior: "smooth"}); }); return; }
      box.hidden = !abrir;
      bot.classList.toggle("on", abrir);
      bot.textContent = abrir ? "✕ Fechar estatísticas" : "📈 Estatísticas";
      if (abrir) { if (!carregado) { carregado = true; carregar(); } box.scrollIntoView({behavior: "smooth"}); }
    };
  }
  // espera o login do FOXNET ser conferido (entrarTV) antes de decidir
  function iniciar() { montar(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar); else iniciar();
  window.FunilTV = {carregar, desenhar};
})();
