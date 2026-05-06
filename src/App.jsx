import { useState, useEffect, useMemo } from "react";


// ── Supabase Client ──────────────────────────────────────────────
const SUPA_URL = "https://dxwkiaxpygibzmwzvcuz.supabase.co";
const SUPA_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR4d2tpYXhweWdpYnptd3p2Y3V6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzczMTE3NzcsImV4cCI6MjA5Mjg4Nzc3N30.mVbUlLaRCI5OMf539Ehjt-XpfAY-wjr7_WCzPsgVvp0";

const supa = {
  async from(table) {
    const base = SUPA_URL + "/rest/v1/" + table;
    const headers = {
      "apikey": SUPA_KEY,
      "Authorization": "Bearer " + SUPA_KEY,
      "Content-Type": "application/json",
      "Prefer": "return=representation"
    };
    return {
      async select(cols="*") {
        const r = await fetch(base + "?select=" + cols, { headers });
        return { data: await r.json(), error: r.ok ? null : "erro" };
      },
      async insert(obj) {
        const h = {...headers, "Prefer":"return=minimal"};
        const r = await fetch(base, { method:"POST", headers:h, body: JSON.stringify(obj) });
        if(!r.ok){ const e=await r.text(); return {data:null,error:e}; }
        return { data:null, error:null };
      },
      async update(obj, match) {
        const q = Object.entries(match).map(([k,v])=>k+"=eq."+encodeURIComponent(v)).join("&");
        const r = await fetch(base+"?"+q, { method:"PATCH", headers, body: JSON.stringify(obj) });
        if(!r.ok){ const e=await r.text(); return {data:null,error:e}; }
        const txt=await r.text();
        return { data:txt?JSON.parse(txt):null, error:null };
      },
      async delete(match) {
        const q = Object.entries(match).map(([k,v])=>k+"=eq."+encodeURIComponent(v)).join("&");
        const r = await fetch(base+"?"+q, { method:"DELETE", headers });
        return { error: r.ok ? null : "erro" };
      }
    };
  }
};

const ADMIN_USER="ti@redefox.com.br", ADMIN_PASS="FoxAdmin@2025";
const LOJAS=["CAUTO/MATRIZ PVH","CAUTO ARIQUEMES","CAUTO JIPARANA","CAUTO CACOAL","CAUTO VILHENA","PARINTINS - MANAUS","XAPURI - RIO BRANCO"];
const SEGS=["Liso","A/T","A/T+","T/A","CARGA","LISO MISTO"];
const VENDEDORES=["Clebe Higa","Kessya Marques","Ana Clara","Sabrina Duarte"];
const PGTO=["À vista","2x no cartão","3x no cartão","4x no cartão","5x no cartão","6x no cartão","7x no cartão","8x no cartão","9x no cartão","10x no cartão","11x no cartão","12x no cartão","13x no cartão","14x no cartão"];
const FOTOS_VENDEDORES={
  "Ana Clara":"data:image/jpeg;base64,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",
  "Kessya Marques":"data:image/jpeg;base64,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",
  "Clebe Higa":"data:image/jpeg;base64,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",
  "Sabrina Duarte":"data:image/jpeg;base64,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",
};
const CONCORRENTES_PADRAO=["Atacado Pneus","GBIM Pneus","Bono Pneus","Camargo Pneus","Espantalho","GP Pneus","Iccap Randon","JK Pneus","Japurá","Morena Pneus","Muniz","Pemaza","Pneu Fácil","Pneu Paulista","Queiroz Pneus","Rei dos Pneus","Rondobras","Shopping dos Pneus","Toyota","Vip Pneus"];
const RED="#CC1F1F",CARD="#1C1C1C",TEXT="#F0F0F0",MUTED="#888",BORDER="#2E2E2E",AMBER="#E0A820",BLUE="#6090E0",GREEN="#4CAF50";
const CC=["#CC1F1F","#E02020","#A01515","#FF4444","#880E0E","#FF7070","#CC5555","#991111"];

function isExp(v){if(!v)return false;return new Date(v+"T23:59:59")<new Date();}
function fmtVal(v){const n=parseFloat(v);return isNaN(n)?v:"R$ "+n.toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2});}
function parseConcObs(obs){
  if(!obs||!obs.includes("\u{1F4CA} CONCORRENTES:"))return[];
  const block=(obs.split("\u{1F4CA} CONCORRENTES:")[1]||"").trim();
  return block.split("\n").filter(l=>l.trim().startsWith("\u2022")).map(l=>{
    const sem=l.trim().slice(1).trim();
    const ci=sem.indexOf(":");if(ci===-1)return null;
    const empresa=sem.slice(0,ci).trim();
    const resto=sem.slice(ci+1).trim();
    const mVal=resto.match(/R\$\s*([\d.,]+)/);
    const mPgto=resto.match(/\(([^)]+)\)/);
    const valor=mVal?parseFloat(mVal[1].replace(/\./g,"").replace(",",".")):0;
    const pgto=mPgto?mPgto[1]:"";
    return empresa?{empresa,valor,pgto}:null;
  }).filter(Boolean);
}
function fmtDate(d){if(!d)return"-";const[y,m,dd]=d.split("-");return dd+"/"+m+"/"+y;}
function roleName(r){return{admin:"Gerente",televendas:"Descontos",comercial:"Comercial"}[r]||r;}
function roleColor(r){return{admin:RED,televendas:BLUE,comercial:AMBER}[r]||MUTED;}

const css=`
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&display=swap');


*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:#0A0A0A;font-family:'Inter',sans-serif;color:#F0F0F0;}
.wrap{height:100vh;width:100vw;background:#0A0A0A;display:flex;overflow:hidden;position:fixed;top:0;left:0;}
.sidebar{width:180px;min-height:100vh;background:#111;border-right:1px solid #1E1E1E;display:flex;flex-direction:column;flex-shrink:0;position:sticky;top:0;height:100vh;}
.sb-brand{padding:14px 14px 12px;border-bottom:1px solid #1E1E1E;}
.brand-icon{width:40px;height:40px;background:#CC1F1F;border-radius:8px;display:flex;align-items:center;justify-content:center;}
.brand-name{font-family:'Bebas Neue',sans-serif;font-size:16px;letter-spacing:2px;color:#fff;margin-top:8px;}
.brand-sub{font-size:9px;color:#555;letter-spacing:1.5px;text-transform:uppercase;}
.sb-nav{flex:1;padding:12px 0;}
.tab{display:flex;align-items:center;gap:8px;padding:9px 14px;font-size:12px;font-weight:600;cursor:pointer;color:#666;transition:all .15s;border-left:3px solid transparent;white-space:nowrap;}
.tab:hover{color:#F0F0F0;background:#1A1A1A;}
.tab.active{color:#fff;border-left-color:#CC1F1F;background:#1A1A1A;}
.tab-dot{width:7px;height:7px;border-radius:50%;background:#333;flex-shrink:0;}.tab.active .tab-dot{background:#CC1F1F;}
.sb-footer{padding:10px 14px;border-top:1px solid #1E1E1E;}
.chip{display:flex;align-items:center;gap:8px;background:#161616;border:1px solid #222;border-radius:8px;padding:8px 10px;font-size:12px;margin-bottom:8px;}
.logout{background:transparent;border:1px solid #333;color:#888;border-radius:6px;padding:7px 14px;font-family:'Inter',sans-serif;font-size:12px;cursor:pointer;transition:all .15s;width:100%;justify-content:center;display:flex;align-items:center;gap:6px;}
.logout:hover{border-color:#CC1F1F;color:#CC1F1F;}
.content-wrap{flex:1;min-width:0;display:flex;flex-direction:column;overflow-y:auto;overflow-x:hidden;height:100vh;}
.main{padding:14px 18px;width:100%;box-sizing:border-box;}
.ph{display:flex;align-items:center;gap:16px;margin-bottom:24px;}
.ph-icon{width:56px;height:56px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.ph-t{font-family:'Bebas Neue',sans-serif;font-size:24px;letter-spacing:2px;color:#fff;}
.ph-s{font-size:13px;color:#888;margin-top:3px;line-height:1.5;}
.sec-t{font-family:'Bebas Neue',sans-serif;font-size:18px;letter-spacing:2px;color:#fff;margin-bottom:4px;}
.sec-s{font-size:12px;color:#888;margin-bottom:16px;}
.card{background:#1C1C1C;border:1px solid #2E2E2E;border-radius:10px;padding:22px;margin-bottom:18px;}
.card-np{background:#1C1C1C;border:1px solid #2E2E2E;border-radius:10px;overflow:hidden;margin-bottom:18px;}
.fg2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;}
.fg3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:14px;}
.field{display:flex;flex-direction:column;gap:5px;}
.field.mb{margin-bottom:14px;}
label{font-size:11px;font-weight:700;color:#888;letter-spacing:1px;text-transform:uppercase;}
input,select{background:#161616;border:1px solid #3A3A3A;border-radius:7px;color:#F0F0F0;font-family:'Inter',sans-serif;font-size:14px;padding:10px 13px;outline:none;transition:border-color .15s;width:100%;}
input:focus,select:focus{border-color:#CC1F1F;}input::placeholder{color:#444;}select option{background:#1C1C1C;}
.tipo-row{display:flex;gap:10px;margin-bottom:14px;}
.tipo-btn{flex:1;background:#161616;border:1px solid #3A3A3A;border-radius:8px;color:#888;font-family:'Inter',sans-serif;font-size:13px;font-weight:600;padding:11px;cursor:pointer;transition:all .15s;text-align:center;}
.tipo-btn.sel{background:#2E1A1A;border-color:#CC1F1F;color:#fff;}
.btn-red{background:#CC1F1F;color:#fff;border:none;border-radius:8px;font-family:'Inter',sans-serif;font-size:14px;font-weight:700;padding:12px 24px;cursor:pointer;transition:background .15s;width:100%;}
.btn-red:hover{background:#E02020;}
.btn-out{background:transparent;border:1px solid #3A3A3A;color:#888;border-radius:7px;font-family:'Inter',sans-serif;font-size:13px;font-weight:600;padding:9px 16px;cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:6px;}
.btn-out:hover{border-color:#CC1F1F;color:#CC1F1F;}
.btn-sm{background:transparent;color:#888;border:1px solid #333;border-radius:5px;font-family:'Inter',sans-serif;font-size:12px;padding:5px 11px;cursor:pointer;transition:all .15s;}
.btn-sm:hover{border-color:#CC1F1F;color:#CC1F1F;}
.s-wrap{position:relative;}
.s-in{font-size:17px;padding:14px 130px 14px 18px;letter-spacing:2px;font-weight:700;}
.s-btn{position:absolute;right:8px;top:50%;transform:translateY(-50%);background:#CC1F1F;color:#fff;border:none;border-radius:6px;padding:9px 20px;font-weight:700;font-size:14px;cursor:pointer;font-family:'Inter',sans-serif;}
.s-btn:hover{background:#E02020;}
.list-row{display:flex;align-items:center;padding:12px 18px;border-bottom:1px solid #2E2E2E;transition:background .12s;gap:10px;}
.list-row:last-child{border-bottom:none;}.list-row:hover{background:#222;}.list-row.cl{cursor:pointer;}
.list-num{font-family:'Bebas Neue',sans-serif;font-size:15px;color:#CC1F1F;min-width:88px;letter-spacing:1px;}
.list-d{font-size:13px;color:#F0F0F0;flex:1;}.list-m{font-size:11px;color:#888;}
.list-val{font-size:13px;font-weight:700;color:#fff;min-width:88px;text-align:right;}
.badge{font-size:10px;font-weight:700;padding:3px 9px;border-radius:3px;letter-spacing:1px;}
.b-valid{background:#1A2E1A;color:#4CAF50;border:1px solid #2E4A2E;}.b-exp{background:#2E1A1A;color:#CC1F1F;border:1px solid #4A2E2E;}
.b-tv{background:#1A1E2E;color:#6090E0;border:1px solid #2A3A60;}.b-com{background:#2E2A1A;color:#E0A820;border:1px solid #504020;}
.b-os{background:#1E2A1E;color:#60C060;border:1px solid #2A4A2A;}.b-orc{background:#1E1E2E;color:#8080E0;border:1px solid #2A2A50;}
.b-lib{background:#1A2E1A;color:#4CAF50;border:1px solid #2E4A2E;}.b-pend{background:#2A2000;color:#E0A820;border:1px solid #504020;}
.rc{background:#1C1C1C;border:1px solid #2E2E2E;border-radius:10px;overflow:hidden;margin-bottom:18px;}
.rh{background:#CC1F1F;padding:18px 22px;display:flex;align-items:center;justify-content:space-between;}
.rn{font-family:'Bebas Neue',sans-serif;font-size:28px;letter-spacing:3px;color:#fff;}
.rt{background:rgba(0,0,0,.3);color:#fff;font-size:11px;font-weight:700;padding:5px 12px;border-radius:4px;letter-spacing:1px;}
.rgrid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#2E2E2E;}
.rcell{background:#1C1C1C;padding:16px 20px;}.rcell.full{grid-column:1/-1;}
.rl{font-size:10px;font-weight:700;color:#888;letter-spacing:1px;text-transform:uppercase;margin-bottom:5px;}
.rv{font-size:14px;font-weight:500;color:#F0F0F0;}.rv-big{font-size:20px;font-weight:700;color:#CC1F1F;}
.rv-ok{color:#4CAF50;font-weight:700;font-size:14px;}.rv-exp{color:#CC1F1F;font-weight:700;font-size:14px;}
.warn-bar{background:#2E1A1A;border-top:1px solid #4A2E2E;padding:12px 20px;color:#E57373;font-size:13px;font-weight:500;display:flex;align-items:center;gap:8px;}
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px;}
.stat-card{background:#161616;border:1px solid #252525;border-radius:10px;padding:14px 16px;position:relative;overflow:hidden;}
.stat-lbl{font-size:11px;font-weight:700;color:#888;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;display:flex;align-items:center;gap:6px;}
.stat-val{font-family:'Bebas Neue',sans-serif;font-size:34px;letter-spacing:1px;color:#fff;line-height:1;margin:6px 0 4px;}.stat-sub{font-size:10px;color:#666;margin-top:2px;letter-spacing:.5px;}
.chart-card{background:#161616;border:1px solid #222;border-radius:10px;padding:14px;margin-bottom:10px;}
.chart-t{display:flex;align-items:center;gap:6px;margin-bottom:10px;font-family:'Bebas Neue',sans-serif;font-size:14px;letter-spacing:1.5px;color:#fff;}
.filter-row{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;}
.empty{text-align:center;padding:40px 20px;color:#888;}
.divider{border:none;border-top:1px solid #2E2E2E;margin:16px 0;}
.info-box{background:#1A1A1A;border-left:3px solid #CC1F1F;border-radius:0 6px 6px 0;padding:10px 14px;margin-bottom:16px;font-size:12px;color:#888;line-height:1.6;}
@keyframes foxUp{0%{opacity:0;transform:translateY(30px)}100%{opacity:1;transform:translateY(0)}}
@keyframes foxIn{0%{opacity:0;transform:translateY(16px)}100%{opacity:1;transform:translateY(0)}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes foxLeft{0%{opacity:0;transform:translateX(-20px)}100%{opacity:1;transform:translateX(0)}}
@keyframes foxPop{0%{opacity:0;transform:scale(.4)}60%{transform:scale(1.12)}100%{opacity:1;transform:scale(1)}}
@keyframes foxPulse{0%,100%{box-shadow:0 0 0 0 rgba(204,31,31,.4)}50%{box-shadow:0 0 0 10px rgba(204,31,31,0)}}
.scroll-anim{opacity:0;transform:translateY(28px);transition:opacity .7s cubic-bezier(.25,.46,.45,.94),transform .7s cubic-bezier(.25,.46,.45,.94);}
.scroll-anim.in-view{opacity:1;transform:translateY(0);}
@keyframes foxUp{0%{opacity:0;transform:translateY(40px)}100%{opacity:1;transform:translateY(0)}}
@keyframes foxLeft{0%{opacity:0;transform:translateX(-20px)}100%{opacity:1;transform:translateX(0)}}
@keyframes foxPop{0%{opacity:0;transform:scale(.5)}70%{transform:scale(1.08)}100%{opacity:1;transform:scale(1)}}
.toast{position:fixed;bottom:22px;right:22px;color:#fff;padding:12px 20px;border-radius:8px;font-weight:700;font-size:14px;z-index:999;animation:pop .25s ease;}
.t-ok{background:#2E7D32;}.t-err{background:#CC1F1F;}
@keyframes pop{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.edit-overlay{position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:1001;display:flex;align-items:center;justify-content:center;padding:16px;}
  .edit-modal{background:#1C1C1C;border:1px solid #CC1F1F;border-radius:12px;padding:24px;width:100%;max-width:440px;}
  .edit-title{font-family:'Bebas Neue',sans-serif;font-size:18px;letter-spacing:1.5px;color:#fff;margin-bottom:18px;}
  .overlay{position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:1000;display:flex;align-items:center;justify-content:center;padding:16px;}
.modal{background:#1C1C1C;border:1px solid #CC1F1F;border-radius:12px;padding:22px;width:100%;max-width:1000px;max-height:88vh;display:flex;flex-direction:column;gap:14px;}
.modal-t{font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:1.5px;color:#fff;}
.exp-table{overflow-x:auto;overflow-y:auto;max-height:58vh;border-radius:8px;border:1px solid #2E2E2E;}
.exp-table table{width:100%;border-collapse:collapse;font-size:12px;}
.exp-table th{background:#CC1F1F;padding:8px 10px;text-align:left;color:#fff;font-weight:700;font-size:11px;letter-spacing:.5px;white-space:nowrap;position:sticky;top:0;}
.exp-table td{padding:6px 10px;white-space:nowrap;border-bottom:1px solid #333;}
.exp-table tr:nth-child(even) td{background:#222;}
.exp-table tr:nth-child(odd) td{background:#1C1C1C;}
.login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0D0D0D;padding:20px;}
.login-card{background:#161616;border:1px solid #2E2E2E;border-radius:14px;padding:38px 34px;width:100%;max-width:380px;}
.login-logo{display:flex;justify-content:center;margin-bottom:22px;}
.login-t{font-family:'Bebas Neue',sans-serif;font-size:22px;letter-spacing:2px;color:#fff;text-align:center;margin-bottom:4px;}
.login-s{font-size:12px;color:#888;text-align:center;margin-bottom:24px;}
.login-err{background:#2E1A1A;border:1px solid #4A2E2E;color:#E57373;border-radius:7px;padding:10px 14px;font-size:13px;margin-bottom:14px;}
.login-f{margin-bottom:12px;}
.login-f label{display:block;font-size:11px;font-weight:700;color:#888;letter-spacing:1px;text-transform:uppercase;margin-bottom:5px;}
.login-f input{background:#0D0D0D;border:1px solid #3A3A3A;border-radius:7px;color:#F0F0F0;font-family:'Inter',sans-serif;font-size:14px;padding:11px 13px;outline:none;transition:border-color .15s;width:100%;}
.login-f input:focus{border-color:#CC1F1F;}
.login-f input::placeholder{color:#444;}
.btn-login{background:#CC1F1F;color:#fff;border:none;border-radius:8px;font-family:'Inter',sans-serif;font-size:14px;font-weight:700;padding:13px;cursor:pointer;transition:background .15s;width:100%;margin-top:4px;}
.btn-login:hover{background:#E02020;}
.login-hint{font-size:11px;color:#555;text-align:center;margin-top:12px;}
`;


function AnimatedNumber({value, duration=1200}){
  const [display, setDisplay] = useState(0);
  const end = parseFloat(value)||0;
  useEffect(()=>{
    let current=0;
    if(end===0){setDisplay(0);return;}
    const totalFrames=Math.max(1,Math.round(duration/16));
    let frame=0;
    const timer=setInterval(()=>{
      frame++;
      const progress=frame/totalFrames;
      const eased=1-Math.pow(1-progress,3);
      current=Math.round(eased*end);
      setDisplay(current);
      if(frame>=totalFrames){setDisplay(end);clearInterval(timer);}
    },16);
    return()=>clearInterval(timer);
  },[end]);
  return <span>{display}</span>;
}

export default function App(){
  useEffect(()=>{
    document.title="Descontos Fox Pneus";
    let lk=document.querySelector("link[rel~='icon']");
    if(!lk){lk=document.createElement("link");lk.rel="icon";document.head.appendChild(lk);}
    lk.href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🦊</text></svg>";
  },[]);

  const[session,setSession]=useState(null);
  const[loginForm,setLoginForm]=useState({email:"",pass:""});
  const[loginErr,setLoginErr]=useState("");
  const[users,setUsers]=useState([]);
  const[tab,setTab]=useState("main");
  const[dashKey,setDashKey]=useState(0);
    const[quotes,setQuotes]=useState([]);
  const[form,setForm]=useState({tipo:"orcamento",numero:"",cba:"",medida:"",segmento:"",loja:"",vendedor:"",valor:"",pgto:"",validade:"",obs:"",erroInterno:false});
  const[search,setSearch]=useState("");
  const[result,setResult]=useState(null);
  const[notFound,setNotFound]=useState(false);
  const[toast,setToast]=useState(null);
  const[newUser,setNewUser]=useState({nome:"",email:"",pass:"",role:"televendas",foto:null});
  const[dash,setDash]=useState({dataIni:"",dataFim:"",loja:"",segmento:"",medida:""});
  const[filtroStatus,setFiltroStatus]=useState("todos");
  const quotesPorStatus=useMemo(()=>quotes.filter(q=>{
    if(filtroStatus==="todos")return true;
    if(filtroStatus==="liberado")return !!q.liberado;
    if(filtroStatus==="pendente")return !q.liberado;
    if(filtroStatus==="validos")return !isExp(q.validade)&&!q.liberado;
    if(filtroStatus==="vencido")return isExp(q.validade)&&!q.liberado;
    return true;
  }),[quotes,filtroStatus]);
  const[showExport,setShowExport]=useState(false);
  const[anexo,setAnexo]=useState(null);
  const[concAdicionados,setConcAdicionados]=useState([]);
  const[concQuery,setConcQuery]=useState("");
  const[concValor,setConcValor]=useState("");
  const[concPgto,setConcPgto]=useState("");
  const[concShowDrop,setConcShowDrop]=useState(false);
  const[concExtras,setConcExtras]=useState(()=>{try{return JSON.parse(localStorage.getItem("fox_concorrentes")||"[]");}catch{return[];}});
  const[imgModal,setImgModal]=useState(null); // {src, nome}
  const[editModal,setEditModal]=useState(null);
  const[editForm,setEditForm]=useState({cba:"",medida:"",segmento:"",loja:"",valor:"",pgto:"",validade:"",obs:"",erroInterno:false});
  const[editConcAdicionados,setEditConcAdicionados]=useState([]);
  const[editConcQuery,setEditConcQuery]=useState("");
  const[editConcValor,setEditConcValor]=useState("");
  const[editConcPgto,setEditConcPgto]=useState("");
  const[editConcDrop,setEditConcDrop]=useState(false);
  const[exportRows,setExportRows]=useState([]);
  const[volPeriodo,setVolPeriodo]=useState("semana");
  const[concIntelSel,setConcIntelSel]=useState(null);
  const[copiedNum,setCopiedNum]=useState(null);
  const[showConcAviso,setShowConcAviso]=useState(false);
  const[galeriaModal,setGaleriaModal]=useState(null);



  useEffect(()=>{
    if(tab!=="dashboard")return;
    window.scrollTo({top:0,behavior:"instant"});
    const timer=setTimeout(()=>{
      const els=document.querySelectorAll('.scroll-anim');
      els.forEach(el=>el.classList.remove('in-view'));
      const obs=new IntersectionObserver((entries)=>{
        entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in-view');}});
      },{threshold:0.05,rootMargin:"0px 0px -40px 0px"});
      els.forEach(el=>obs.observe(el));
    },100);
    return()=>clearTimeout(timer);
  },[tab,dashKey]);

  useEffect(()=>{
    try{
      const saved=localStorage.getItem("fox_session");
      if(saved){
        const s=JSON.parse(saved);
        setSession(s);
        setTab(s.role==="admin"?"dashboard":s.role==="televendas"?"cadastrar":"consultar");
      }
    }catch(e){}
  },[]);

  useEffect(()=>{(async()=>{try{
    const db = await supa.from("descontos");
    const {data:qu} = await db.select();
    if(qu){setDashKey(k=>k+1);setQuotes(qu.map(q=>({
      tipo:q.tipo,numero:q.numero,cba:q.cba,medida:q.medida,segmento:q.segmento,
      loja:q.loja,valor:q.valor,pgto:q.pgto,validade:q.validade,obs:q.obs,
      liberado:q.liberado,negociadorNome:q.negociador_nome,negociadorEmail:q.negociador_email,erroInterno:q.erro_interno||false,
      liberadorNome:q.liberador_nome,liberadorEmail:q.liberador_email,
      liberadoEm:q.liberado_em,criadoEm:q.criado_em,_id:q.id, vendedor:q.vendedor,
      anexoBase64:q.anexo_base64,anexoTipo:q.anexo_tipo,anexoNome:q.anexo_nome
    })));}
    const ub = await supa.from("usuarios");
    const {data:us} = await ub.select();
    if(us) setUsers(us.map(u=>({nome:u.nome,email:u.email,pass:u.senha,role:u.role})));
  }catch(e){console.log("Erro ao carregar:",e);}})();}, []);

  const saveQ=async q=>{setQuotes(q);}; // dados salvos direto no Supabase
  const saveU=async u=>{setUsers(u);}; // dados salvos direto no Supabase
  const toast_=(msg,ok=true)=>{setToast({msg,ok});setTimeout(()=>setToast(null),3200);};

  const handleAnexo=(e)=>{
    const file = e.target.files[0];
    if(!file)return;
    const maxMB = file.type.startsWith("audio") ? 5 : 3;
    if(file.size > maxMB*1024*1024){toast_("Arquivo muito grande. Máx "+maxMB+"MB.",false);return;}
    const reader = new FileReader();
    reader.onload=(ev)=>setAnexo({base64:ev.target.result,tipo:file.type,nome:file.name});
    reader.readAsDataURL(file);
  };

  const doEdit=(q)=>{
    const obsLimpa=(q.obs||"").split("\n\n📊 CONCORRENTES:")[0];
    const concExist=parseConcObs(q.obs||"");
    setEditForm({cba:q.cba||"",medida:q.medida||"",segmento:q.segmento||"",loja:q.loja||"",valor:q.valor||"",pgto:q.pgto||"",validade:q.validade||"",obs:obsLimpa,erroInterno:q.erroInterno||false});
    setEditConcAdicionados(concExist);
    setEditConcQuery("");setEditConcValor("");setEditConcPgto("");
    setEditModal(q);
  };

  const doSaveEdit=async()=>{
    if(!editForm.validade||!editForm.medida||!editForm.valor){toast_("Preencha os campos obrigatórios.",false);return;}
    try{
      const db = await supa.from("descontos");
      const {error:eUpd} = await db.update({
        cba:editForm.cba, medida:editForm.medida, segmento:editForm.segmento,
        loja:editForm.loja, valor:editForm.valor, pgto:editForm.pgto,
        validade:editForm.validade,
        erro_interno:editForm.erroInterno,
        obs:editForm.obs+(editConcAdicionados.length>0?"\n\n📊 CONCORRENTES:\n"+editConcAdicionados.map(x=>`• ${x.empresa}: ${parseFloat(x.valor).toLocaleString("pt-BR",{style:"currency",currency:"BRL"})} (${x.pgto})`).join("\n"):"")
      },{numero:editModal.numero,tipo:editModal.tipo});
      if(eUpd){toast_("Erro ao atualizar: "+eUpd,false);return;}
      const updated={...editForm};
      const obsFinal=editForm.obs+(editConcAdicionados.length>0?"\n\n📊 CONCORRENTES:\n"+editConcAdicionados.map(x=>`• ${x.empresa}: ${parseFloat(x.valor).toLocaleString("pt-BR",{style:"currency",currency:"BRL"})} (${x.pgto})`).join("\n"):"");
      setQuotes(prev=>prev.map(x=>(x.numero===editModal.numero&&x.tipo===editModal.tipo)?{...x,...updated,obs:obsFinal,erroInterno:editForm.erroInterno}:x));
      if(result&&result.numero===editModal.numero&&result.tipo===editModal.tipo)setResult(prev=>({...prev,...updated}));
      setEditModal(null);
      toast_("Desconto atualizado!");
    }catch(e){toast_("Erro ao atualizar.",false);}
  };

  const doExport=(data)=>{
    // Build CSV with BOM - opens perfectly in Excel
    const headers=["Cadastro (Responsável)","Loja","Medida","Segmento","Preço negociado","Forma Pagamento","Liberação","Data Liberação","Número","Tipo","CBA","Validade","Obs"];
    const rows2=data.map(q=>[
      q.negociadorNome||"",
      q.loja||"",
      q.medida||"",
      q.segmento||"",
      (parseFloat(q.valor)||0).toFixed(2),
      q.pgto||"",
      q.liberado?"Liberado":"Pendente",
      q.liberadoEm?new Date(q.liberadoEm).toLocaleString("pt-BR",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"}):"",
      q.numero||"",
      q.tipo==="os"?"O.S.":"Orçamento",
      q.cba||"",
      q.validade?q.validade.split("-").reverse().join("/"):"",
      (q.obs||"").replace(/"/g,"'")
    ]);
    const csvLines = [headers, ...rows2]
      .map(row => row.map(v => '"'+String(v||"").replace(/"/g,"''")+'"').join(";"))
      .join("\r\n");
    const BOM = "\uFEFF";
    const blob = new Blob([BOM + csvLines], {type:"text/csv;charset=utf-8;"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href=url;
    a.download="Fox_Negociacoes_"+new Date().toLocaleDateString("pt-BR").split("/").join("-")+".csv";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast_("Planilha gerada! Abra o arquivo .csv no Excel.");
    return;
    const rows=data.map(q=>({
      "Cadastro (Responsável negociação)": q.negociadorNome||"",
      "Loja":        q.loja||"",
      "Medida":      q.medida||"",
      "Segmento":    q.segmento||"",
      "Preço negociado": (parseFloat(q.valor)||0).toFixed(2).replace(".",","),
      "Forma Pagamento": q.pgto||"",
      "Liberação":   q.liberado?"Liberado":"Pendente",
      "Data da liberação": q.liberado&&q.liberadoEm
        ? new Date(q.liberadoEm).toLocaleString("pt-BR",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"})
        : q.obs||""
    }));
    setExportRows(rows);
    setShowExport(true);
  };
  const exportCSV=(data)=>doExport(data);
  const exportXLS=(data)=>doExport(data);

  const doLogin=()=>{
    const u=loginForm.email.trim().toLowerCase(),p=loginForm.pass;
    if(u===ADMIN_USER&&p===ADMIN_PASS){const s={username:"admin",email:"admin",role:"admin"};setSession(s);localStorage.setItem("fox_session",JSON.stringify(s));setTab("dashboard");setLoginErr("");return;}
    const f=users.find(x=>x.email.toLowerCase()===u&&x.pass===p);
    if(f){const s={username:f.nome||f.email,email:f.email,role:f.role};setSession(s);localStorage.setItem("fox_session",JSON.stringify(s));setTab(f.role==="televendas"?"cadastrar":"consultar");setLoginErr("");return;}
    setLoginErr("Usuário ou senha incorretos.");
  };
  const doLogout=()=>{setSession(null);localStorage.removeItem("fox_session");setLoginForm({email:"",pass:""});setLoginErr("");setResult(null);setNotFound(false);};

  const doAdd=async(forcar=false)=>{
    if(!form.numero||!form.cba||!form.medida||!form.segmento||!form.loja||!form.vendedor||!form.valor||!form.pgto||!form.validade){toast_("Preencha todos os campos.",false);return;}
    if(quotes.find(q=>q.numero===form.numero.trim()&&q.tipo===form.tipo)){toast_("Número já cadastrado.",false);return;}
    if(!forcar&&concAdicionados.length===0&&!form.erroInterno){setShowConcAviso(true);return;}
    try{
      const db = await supa.from("descontos");
      const {error} = await db.insert({
        tipo:form.tipo, numero:form.numero.trim(), cba:form.cba, medida:form.medida,
        segmento:form.segmento, loja:form.loja, valor:form.valor, pgto:form.pgto,
        validade:form.validade, obs:form.obs, liberado:false,
        negociador_nome:session.username, negociador_email:session.email, vendedor:form.vendedor||null,
        anexo_base64:anexo?anexo.base64:null,
        anexo_tipo:anexo?anexo.tipo:null,
        anexo_nome:anexo?anexo.nome:null
      });
      if(error){console.error("Supabase error:",error);toast_("Erro ao salvar: "+String(error).substring(0,80),false);return;}
      const novo={...form,numero:form.numero.trim(),criadoEm:new Date().toISOString(),negociadorNome:session.username,negociadorEmail:session.email,liberado:false};
      setQuotes(prev=>[novo,...prev]);
      setForm({tipo:"orcamento",numero:"",cba:"",medida:"",segmento:"",loja:"",vendedor:"",valor:"",pgto:"",validade:"",obs:"",erroInterno:false});
      setAnexo(null);
      setConcAdicionados([]);setConcQuery("");setConcValor("");setConcPgto("");
      toast_("Desconto cadastrado!");
    }catch(e){toast_("Erro ao salvar.",false);}
  };
  const doDel=async id=>{
    try{
      const db = await supa.from("descontos");
      await db.delete({numero:id.numero, tipo:id.tipo});
      setQuotes(prev=>prev.filter(q=>!(q.numero===id.numero&&q.tipo===id.tipo)));
      toast_("Removido.");
    }catch(e){toast_("Erro ao remover.",false);}
  };

  const doSearch=()=>{
    const q=quotes.find(q=>q.numero.toLowerCase()===search.trim().toLowerCase());
    if(q){setResult(q);setNotFound(false);}else{setResult(null);setNotFound(true);}
  };
  const clickRow=q=>{setSearch(q.numero);setResult(q);setNotFound(false);window.scrollTo({top:0,behavior:"smooth"});};

  const doLiberar=async(q,e)=>{
    if(e)e.stopPropagation();
    const nowLib=!q.liberado;
    const ldata=nowLib?{liberadorNome:session.username,liberadorEmail:session.email,liberadoEm:new Date().toISOString()}:{liberadorNome:null,liberadorEmail:null,liberadoEm:null};
    try{
      const db = await supa.from("descontos");
      await db.update({
        liberado:nowLib,
        liberador_nome:ldata.liberadorNome,
        liberador_email:ldata.liberadorEmail,
        liberado_em:ldata.liberadoEm
      },{numero:q.numero,tipo:q.tipo});
      setQuotes(prev=>prev.map(x=>(x.numero===q.numero&&x.tipo===q.tipo)?{...x,liberado:nowLib,...ldata}:x));
      if(result&&result.numero===q.numero&&result.tipo===q.tipo)setResult(prev=>({...prev,liberado:nowLib,...ldata}));
      toast_(nowLib?"Desconto liberado!":"Liberação removida.");
    }catch(e){toast_("Erro.",false);}
  };

  const doAddUser=async()=>{
    const em=newUser.email.trim().toLowerCase();
    if(!newUser.nome.trim()||!em||!newUser.pass){toast_("Preencha todos os campos.",false);return;}
    if(em===ADMIN_USER){toast_("E-mail reservado.",false);return;}
    if(users.find(x=>x.email.toLowerCase()===em)){toast_("E-mail já cadastrado.",false);return;}
    try{
      const db = await supa.from("usuarios");
      const {error} = await db.insert({nome:newUser.nome.trim(),email:em,senha:newUser.pass,role:newUser.role,foto:newUser.foto||null});
      if(error){toast_("Erro ao criar usuário.",false);return;}
      setUsers(prev=>[...prev,{nome:newUser.nome.trim(),email:em,pass:newUser.pass,role:newUser.role,foto:newUser.foto||null}]);
      setNewUser({nome:"",email:"",pass:"",role:"televendas",foto:null});toast_("Usuário criado!");
    }catch(e){toast_("Erro.",false);}
  };
  const doDelUser=async em=>{
    try{
      const db = await supa.from("usuarios");
      await db.delete({email:em});
      setUsers(prev=>prev.filter(x=>x.email!==em));
      toast_("Usuário removido.");
    }catch(e){toast_("Erro.",false);}
  };

  const filtered=useMemo(()=>quotes.filter(q=>{
    if(q.erroInterno)return false;
    if(dash.loja&&q.loja!==dash.loja)return false;
    if(dash.segmento&&q.segmento!==dash.segmento)return false;
    if(dash.medida&&!q.medida.toLowerCase().includes(dash.medida.toLowerCase().trim()))return false;
    if(dash.dataIni&&q.criadoEm<dash.dataIni)return false;
    if(dash.dataFim&&q.criadoEm>dash.dataFim+"T23:59:59")return false;
    return true;
  }),[quotes,dash]);

  const mChart=useMemo(()=>{const c={};filtered.forEach(q=>{c[q.medida]=(c[q.medida]||0)+1;});return Object.entries(c).sort((a,b)=>b[1]-a[1]).slice(0,10).map(([name,value])=>({name,value}));},[filtered]);
  const sChart=useMemo(()=>{const c={};filtered.forEach(q=>{c[q.segmento]=(c[q.segmento]||0)+1;});return Object.entries(c).sort((a,b)=>b[1]-a[1]).map(([name,value])=>({name,value}));},[filtered]);
  const lChart=useMemo(()=>{const c={};filtered.forEach(q=>{c[q.loja]=(c[q.loja]||0)+1;});return Object.entries(c).sort((a,b)=>b[1]-a[1]).map(([name,value])=>({name,value}));},[filtered]);
  const totVal=useMemo(()=>filtered.reduce((s,q)=>s+(parseFloat(q.valor)||0),0),[filtered]);
  const chartColors=["#CC1F1F","#E02020","#A01515","#FF4444","#880E0E","#FF7070","#CC5555","#991111"];

  if(!session)return(<><style>{css}</style><div className="login-wrap"><div className="login-card">
    <div className="login-logo"><div style={{width:64,height:64,background:RED,borderRadius:14,display:"flex",alignItems:"center",justifyContent:"center",fontSize:36}}>🦊</div></div>
    <div className="login-t">Sistema de Descontos</div>
    <div className="login-s">Acesso restrito — Fox Pneus</div>
    {loginErr&&<div className="login-err">{loginErr}</div>}
    <div className="login-f"><label>E-mail</label><input type="email" placeholder="seu@email.com" value={loginForm.email} onChange={e=>setLoginForm(f=>({...f,email:e.target.value}))} onKeyDown={e=>e.key==="Enter"&&doLogin()}/></div>
    <div className="login-f"><label>Senha</label><input type="password" placeholder="Senha" value={loginForm.pass} onChange={e=>setLoginForm(f=>({...f,pass:e.target.value}))} onKeyDown={e=>e.key==="Enter"&&doLogin()}/></div>
    <button className="btn-login" onClick={doLogin}>Entrar</button>
    <div className="login-hint">Somente usuários cadastrados pelo administrador.</div>
  </div></div></>);

  return(<><style>{css}</style><div className="wrap">
    {/* ── SIDEBAR ── */}
    <div className="sidebar">
      <div className="sb-brand">
        <div className="brand-icon"><span style={{fontSize:22}}>🦊</span></div>
        <div className="brand-name">Fox Pneus</div>
        <div className="brand-sub">Sistema de Descontos</div>
      </div>
      <nav className="sb-nav">
        {session.role==="admin"&&<div className={`tab ${tab==="dashboard"?"active":""}`} onClick={()=>{setTab("dashboard");setDashKey(k=>k+1);}}><span className="tab-dot"/>Dashboard</div>}
        {(session.role==="televendas"||session.role==="admin")&&<div className={`tab ${tab==="cadastrar"?"active":""}`} onClick={()=>setTab("cadastrar")}><span className="tab-dot"/>Cadastrar</div>}
        {(session.role==="comercial"||session.role==="admin")&&<div className={`tab ${tab==="consultar"?"active":""}`} onClick={()=>{setTab("consultar");setResult(null);setNotFound(false);}}><span className="tab-dot"/>Consultar</div>}
        {session.role==="admin"&&<div className={`tab ${tab==="users"?"active":""}`} onClick={()=>setTab("users")}><span className="tab-dot"/>Usuários</div>}
      </nav>
      <div className="sb-footer">
        <div className="chip">
          <span style={{fontSize:16}}>{session.role==="admin"?"🛡️":session.role==="televendas"?"📞":"🤝"}</span>
          <div><div style={{fontSize:12,fontWeight:700,color:"#F0F0F0"}}>{session.username}</div><div style={{fontSize:10,color:roleColor(session.role)}}>{roleName(session.role)}</div></div>
        </div>
        <button className="logout" onClick={doLogout}>Sair</button>
      </div>
    </div>
    {/* ── CONTEÚDO ── */}
    <div className="content-wrap">
    <div className="main">

    {/* DASHBOARD */}
    {tab==="dashboard"&&session.role==="admin"&&(<div key={dashKey}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16,flexWrap:"wrap",gap:12,borderBottom:"1px solid #1E1E1E",paddingBottom:14}}>
          <div style={{display:"flex",alignItems:"center",gap:12}}>
            <div style={{width:4,height:28,background:RED,borderRadius:2}}/>
            <div>
              <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:22,letterSpacing:2,color:"#fff"}}>INTELIGÊNCIA COMERCIAL</div>
              <div style={{fontSize:11,color:"#555",letterSpacing:1}}>FOX PNEUS — SISTEMA DE DESCONTOS</div>
            </div>
          </div>
          <button className="btn-out" onClick={()=>exportXLS(filtered.length>0?filtered:quotes)}>⬇ Exportar ({(filtered.length>0?filtered:quotes).length})</button>
        </div>

        {/* Filtros */}
        <div className="card" style={{marginBottom:10,padding:"12px 16px"}}>
          <div style={{fontSize:11,fontWeight:700,color:MUTED,letterSpacing:1,textTransform:"uppercase",marginBottom:10}}>Filtros</div>
          <div className="filter-row">
            <div className="field" style={{flex:1}}><label>Data inicial</label><input type="date" value={dash.dataIni} onChange={e=>setDash(d=>({...d,dataIni:e.target.value}))}/></div>
            <div className="field" style={{flex:1}}><label>Data final</label><input type="date" value={dash.dataFim} onChange={e=>setDash(d=>({...d,dataFim:e.target.value}))}/></div>
            <div className="field" style={{flex:1}}><label>Loja</label><select value={dash.loja} onChange={e=>setDash(d=>({...d,loja:e.target.value}))}><option value="">Todas</option>{LOJAS.map(l=><option key={l}>{l}</option>)}</select></div>
            <div className="field" style={{flex:1}}><label>Segmento</label><select value={dash.segmento} onChange={e=>setDash(d=>({...d,segmento:e.target.value}))}><option value="">Todos</option>{SEGS.map(s=><option key={s}>{s}</option>)}</select></div>
            <div className="field" style={{flex:1,minWidth:140}}><label>Medida</label><input type="text" placeholder="Ex: 175/75R13" value={dash.medida} onChange={e=>setDash(d=>({...d,medida:e.target.value}))}/></div>
            <div style={{display:"flex",alignItems:"flex-end"}}><button className="btn-sm" onClick={()=>setDash({dataIni:"",dataFim:"",loja:"",segmento:"",medida:""})} style={{height:40,padding:"0 14px",borderRadius:7}}>Limpar</button></div>
          </div>
        </div>

        {/* KPIs */}
        <div className="stat-grid">
          <div className="stat-card" style={{borderTop:"3px solid "+RED}}>
            <div className="stat-lbl">Total negociações</div>
            <div className="stat-val" style={{color:RED}}><AnimatedNumber value={filtered.length}/></div>
            <div className="stat-sub">todas as negociações</div>
          </div>
          <div className="stat-card" style={{borderTop:"3px solid "+GREEN}}>
            <div className="stat-lbl">Fechadas (Liberadas)</div>
            <div className="stat-val" style={{color:GREEN}}><AnimatedNumber value={filtered.filter(q=>q.liberado).length}/></div>
            <div className="stat-sub">{filtered.length>0?((filtered.filter(q=>q.liberado).length/filtered.length)*100).toFixed(0):0}% de conversão</div>
          </div>
          <div className="stat-card" style={{borderTop:"3px solid "+AMBER}}>
            <div className="stat-lbl">Pendentes</div>
            <div className="stat-val" style={{color:AMBER}}><AnimatedNumber value={filtered.filter(q=>!q.liberado&&!isExp(q.validade)).length}/></div>
            <div className="stat-sub">aguardando aprovação</div>
          </div>
          <div className="stat-card" style={{borderTop:"3px solid #888"}}>
            <div className="stat-lbl">Vencidas</div>
            <div className="stat-val" style={{color:MUTED}}><AnimatedNumber value={filtered.filter(q=>isExp(q.validade)&&!q.liberado).length}/></div>
            <div className="stat-sub">não fechadas no prazo</div>
          </div>
        </div>

        {filtered.length===0?(<div className="card"><div className="empty"><div style={{fontSize:36,opacity:.2,marginBottom:12}}>📊</div><p>Nenhum dado para os filtros.</p></div></div>):(<>

        {/* Grid: Medidas + Segmentos */}
        <div className="scroll-anim" style={{display:"grid",gridTemplateColumns:"1.4fr 1fr",gap:10,marginBottom:10}}>

          {/* Ranking Medidas */}
          <div className="scroll-anim" style={{background:"#1C1C1C",border:"1px solid #2E2E2E",borderRadius:10,padding:20,marginBottom:0}}>
            <div className="chart-t">🏆 Medidas Mais Negociadas</div>
            <table style={{width:"100%",borderCollapse:"collapse"}}>
              <thead><tr style={{borderBottom:"1px solid #2E2E2E"}}>
                {["#","Medida","Qtd","Fechou","%",""].map(h=><th key={h} style={{padding:"5px 8px",textAlign:"left",fontSize:10,fontWeight:700,color:MUTED,letterSpacing:1,textTransform:"uppercase"}}>{h}</th>)}
              </tr></thead>
              <tbody>{mChart.map((m,i)=>{
                const pct=filtered.length>0?((m.value/filtered.length)*100).toFixed(1):0;
                const lib=filtered.filter(q=>q.medida===m.name&&q.liberado).length;
                return(<tr key={m.name} style={{borderBottom:"1px solid #1C1C1C",background:i===0?"#2E1A1A":"transparent"}}>
                  <td style={{padding:"8px 8px"}}><span style={{display:"inline-flex",alignItems:"center",justifyContent:"center",width:20,height:20,borderRadius:"50%",background:i<3?[RED,"#888","#663300"][i]:"#2E2E2E",color:"#fff",fontSize:9,fontWeight:700}}>{i+1}</span></td>
                  <td style={{padding:"8px 8px",fontWeight:i===0?700:500,color:i===0?RED:TEXT,fontSize:13}}>{m.name}</td>
                  <td style={{padding:"8px 8px",textAlign:"center"}}><span style={{background:RED+"22",color:RED,borderRadius:4,padding:"1px 8px",fontWeight:700,fontSize:12}}>{m.value}</span></td>
                  <td style={{padding:"8px 8px",textAlign:"center"}}><span style={{background:GREEN+"22",color:GREEN,borderRadius:4,padding:"1px 8px",fontWeight:700,fontSize:12}}>{lib}</span></td>
                  <td style={{padding:"8px 8px",fontSize:11,color:MUTED}}>{pct}%</td>
                  <td style={{padding:"8px 8px"}}>{(()=>{
  const imgs=filtered.filter(q=>q.medida===m.name&&q.anexoBase64&&q.anexoTipo&&q.anexoTipo.startsWith("image"));
  const semFoto=filtered.filter(q=>q.medida===m.name&&!q.anexoBase64&&parseConcObs(q.obs).length>0);
  if(imgs.length>0)return(<button onClick={()=>setGaleriaModal({medida:m.name,imagens:imgs,semFoto})} style={{background:"#1A1E2E",border:"1px solid "+BLUE,color:BLUE,borderRadius:6,padding:"4px 10px",fontSize:11,fontWeight:700,cursor:"pointer",whiteSpace:"nowrap"}}>🖼️ {imgs.length} foto{imgs.length!==1?"s":""}</button>);
  if(semFoto.length>0)return(<button onClick={()=>setGaleriaModal({medida:m.name,imagens:[],semFoto})} style={{background:"#1A1E0E",border:"1px solid #4CAF50",color:"#4CAF50",borderRadius:6,padding:"4px 10px",fontSize:11,fontWeight:700,cursor:"pointer",whiteSpace:"nowrap"}}>🏢 {semFoto.length} conc.</button>);
  return(<span style={{color:MUTED,fontSize:11}}>—</span>);
})()}</td>
                </tr>);})}
              </tbody>
            </table>
          </div>

          {/* Ranking Segmentos */}
          <div className="scroll-anim" style={{background:"#1C1C1C",border:"1px solid #2E2E2E",borderRadius:10,padding:20,marginBottom:0}}>
            <div className="chart-t">🔖 Por Segmento</div>
            <table style={{width:"100%",borderCollapse:"collapse"}}>
              <thead><tr style={{borderBottom:"1px solid #2E2E2E"}}>
                {["#","Segmento","Total","Fechou","Pend."].map(h=><th key={h} style={{padding:"5px 8px",textAlign:"left",fontSize:10,fontWeight:700,color:MUTED,letterSpacing:1,textTransform:"uppercase"}}>{h}</th>)}
              </tr></thead>
              <tbody>{sChart.map((s,i)=>{
                const lib=filtered.filter(q=>q.segmento===s.name&&q.liberado).length;
                const pend=filtered.filter(q=>q.segmento===s.name&&!q.liberado&&!isExp(q.validade)).length;
                return(<tr key={s.name} style={{borderBottom:"1px solid #1C1C1C"}}>
                  <td style={{padding:"8px 8px"}}><span style={{display:"inline-flex",alignItems:"center",justifyContent:"center",width:20,height:20,borderRadius:"50%",background:CC[i%8]+"44",color:CC[i%8],fontSize:9,fontWeight:700}}>{i+1}</span></td>
                  <td style={{padding:"8px 8px",color:TEXT,fontSize:13}}>{s.name}</td>
                  <td style={{padding:"8px 8px",fontWeight:700,color:TEXT}}>{s.value}</td>
                  <td style={{padding:"8px 8px"}}><span style={{color:GREEN,fontWeight:700,fontSize:12}}>{lib}</span></td>
                  <td style={{padding:"8px 8px"}}><span style={{color:AMBER,fontWeight:700,fontSize:12}}>{pend}</span></td>
                </tr>);})}
              </tbody>
            </table>
          </div>
        </div>

        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10,alignItems:"start"}}>
        <div>
        {/* Ranking Lojas */}
        <div style={{background:"#161616",border:"1px solid #2E2E2E",borderRadius:10,padding:20,marginBottom:16}}>
          <div className="chart-t">📍 Ranking por Loja</div>
          <table style={{width:"100%",borderCollapse:"collapse"}}>
            <thead><tr style={{borderBottom:"1px solid #2E2E2E"}}>
              {["#","Loja","Total","Fechou","Pendentes","Vencidas","Conv."].map(h=><th key={h} style={{padding:"6px 10px",textAlign:"left",fontSize:10,fontWeight:700,color:MUTED,letterSpacing:1,textTransform:"uppercase"}}>{h}</th>)}
            </tr></thead>
            <tbody>{lChart.map((l,i)=>{
              const items=filtered.filter(q=>q.loja===l.name);
              const lib=items.filter(q=>q.liberado).length;
              const pend=items.filter(q=>!q.liberado&&!isExp(q.validade)).length;
              const venc=items.filter(q=>isExp(q.validade)&&!q.liberado).length;
              const val=items.reduce((s,q)=>s+(parseFloat(q.valor)||0),0);
              const conv=l.value>0?((lib/l.value)*100).toFixed(0):0;
              return(<tr key={l.name} style={{borderBottom:"1px solid #1C1C1C",background:i===0?"#2E1A1A":"transparent"}}>
                <td style={{padding:"9px 10px"}}><span style={{display:"inline-flex",alignItems:"center",justifyContent:"center",width:20,height:20,borderRadius:"50%",background:i===0?RED:"#2E2E2E",color:"#fff",fontSize:9,fontWeight:700}}>{i+1}</span></td>
                <td style={{padding:"9px 10px",color:i===0?RED:TEXT,fontWeight:i===0?700:500,fontSize:13}}>{l.name}</td>
                <td style={{padding:"9px 10px",fontWeight:700,color:TEXT}}>{l.value}</td>
                <td style={{padding:"9px 10px"}}><span style={{color:GREEN,fontWeight:700}}>{lib}</span></td>
                <td style={{padding:"9px 10px"}}><span style={{color:AMBER,fontWeight:700}}>{pend}</span></td>
                <td style={{padding:"9px 10px"}}><span style={{color:MUTED,fontWeight:700}}>{venc}</span></td>
                <td style={{padding:"9px 10px"}}><span style={{background:parseInt(conv)>=50?GREEN+"22":RED+"22",color:parseInt(conv)>=50?GREEN:RED,borderRadius:4,padding:"2px 8px",fontWeight:700,fontSize:12}}>{conv}%</span></td>
              </tr>);})}
            </tbody>
          </table>
        </div>

        </div>
        <div>
        {/* Ranking Vendedores */}
        {(()=>{
          const byV={};
          filtered.filter(q=>q.vendedor).forEach(q=>{
            if(!byV[q.vendedor])byV[q.vendedor]={nome:q.vendedor,total:0,lib:0,pend:0,venc:0,val:0};
            byV[q.vendedor].total++;
            if(q.liberado)byV[q.vendedor].lib++;
            else if(isExp(q.validade))byV[q.vendedor].venc++;
            else byV[q.vendedor].pend++;
            byV[q.vendedor].val+=(parseFloat(q.valor)||0);
          });
          const vList=Object.values(byV).sort((a,b)=>b.lib-a.lib||b.total-a.total);
          const fotoMap={...FOTOS_VENDEDORES}; users.forEach(u=>{if(u.foto)fotoMap[u.nome]=u.foto;});
          if(!vList.length)return(<div style={{background:"#1C1C1C",border:"1px solid #2E2E2E",borderRadius:10,padding:20,marginBottom:16}}><div className="chart-t">👤 Ranking de Vendedores</div><div className="empty" style={{padding:"20px"}}><p style={{color:MUTED}}>Nenhum vendedor registrado ainda. Cadastre descontos com o campo Vendedor preenchido.</p></div></div>);
          return(<div className="scroll-anim" style={{background:"#1C1C1C",border:"1px solid #2E2E2E",borderRadius:10,padding:20,marginBottom:16}}>
            <div className="chart-t">👤 Ranking de Vendedores — Negociações e Fechamentos</div>
            <table style={{width:"100%",borderCollapse:"collapse"}}>
              <thead><tr style={{borderBottom:"1px solid #2E2E2E"}}>
                {["#","Vendedor","Neg.","Fechou","Pend.","Venc.","Conv."].map(h=><th key={h} style={{padding:"5px 8px",textAlign:"left",fontSize:9,fontWeight:700,color:MUTED,letterSpacing:1,textTransform:"uppercase"}}>{h}</th>)}
              </tr></thead>
              <tbody>{vList.map((v,i)=>{
                const conv=v.total>0?((v.lib/v.total)*100).toFixed(0):0;
                const barW=Math.max(4,parseInt(conv));
                return(<tr key={v.nome} style={{borderBottom:"1px solid #1C1C1C",background:i===0?"#1A2E1A":"transparent",animation:"foxLeft .4s ease "+(0.4+i*0.07)+"s both"}}>
                  <td style={{padding:"8px 10px"}}>
                    {fotoMap[v.nome]
                      ?<img src={fotoMap[v.nome]} alt={v.nome} style={{width:32,height:32,borderRadius:"50%",objectFit:"cover",border:"2px solid "+(i===0?GREEN:i===1?"#888":i===2?"#8B4513":"#2E2E2E"),display:"block",animation:"foxPop .6s ease "+(0.4+i*0.1)+"s both"}}/>
                      :<div style={{width:40,height:40,borderRadius:"50%",background:i===0?GREEN+"33":i===1?"#88888833":"#66330033",border:"2px solid "+(i===0?GREEN:i===1?"#888":"#8B4513"),display:"flex",alignItems:"center",justifyContent:"center",fontSize:15,fontWeight:900,color:i===0?GREEN:i===1?"#888":"#CD853F"}}>
                        {v.nome.charAt(0).toUpperCase()}
                      </div>
                    }
                  </td>
                  <td style={{padding:"10px 10px"}}> 
                    <div style={{fontWeight:700,color:i===0?GREEN:TEXT,fontSize:14}}>{v.nome}</div>
                    <div style={{fontSize:10,color:MUTED,marginTop:2}}>{i===0?"🏆 Líder":i===1?"🥈 2º lugar":i===2?"🥉 3º lugar":"#"+(i+1)}</div>
                  </td>
                  <td style={{padding:"10px 10px"}}><span style={{background:RED+"22",color:RED,borderRadius:4,padding:"2px 10px",fontWeight:700,fontSize:13}}>{v.total}</span></td>
                  <td style={{padding:"10px 10px"}}><span style={{background:GREEN+"22",color:GREEN,borderRadius:4,padding:"2px 10px",fontWeight:700,fontSize:13}}>{v.lib}</span></td>
                  <td style={{padding:"10px 10px"}}><span style={{background:AMBER+"22",color:AMBER,borderRadius:4,padding:"2px 10px",fontWeight:700,fontSize:13}}>{v.pend}</span></td>
                  <td style={{padding:"10px 10px"}}><span style={{color:MUTED,fontWeight:700,fontSize:13}}>{v.venc}</span></td>
                  <td style={{padding:"10px 10px",minWidth:120}}>
                    <div style={{display:"flex",alignItems:"center",gap:8}}>
                      <div style={{flex:1,height:8,background:"#2E2E2E",borderRadius:4,overflow:"hidden"}}>
                        <div style={{width:barW+"%",height:"100%",background:parseInt(conv)>=50?GREEN:parseInt(conv)>=30?AMBER:RED,borderRadius:4,transition:"width .3s"}}/>
                      </div>
                      <span style={{fontSize:12,fontWeight:700,color:parseInt(conv)>=50?GREEN:parseInt(conv)>=30?AMBER:RED,minWidth:35}}>{conv}%</span>
                    </div>
                  </td>
                </tr>);})}
              </tbody>
            </table>
          </div>);
        })()}



        {/* ── INTELIGÊNCIA DE CONCORRÊNCIA ── */}
        {(()=>{
          // collect all concorrentes from filtered quotes
          const allConc=[];
          filtered.forEach(q=>{
            const items=parseConcObs(q.obs);
            items.forEach(item=>{
              allConc.push({...item, medida:q.medida, numero:q.numero, criadoEm:q.criadoEm, loja:q.loja, valorFox:q.valor});
            });
          });
          if(!allConc.length)return null;

          // rank by frequency
          const empMap={};
          allConc.forEach(item=>{
            if(!empMap[item.empresa])empMap[item.empresa]={empresa:item.empresa,count:0,medidas:[]};
            empMap[item.empresa].count++;
            empMap[item.empresa].medidas.push({medida:item.medida,valor:item.valor,pgto:item.pgto,criadoEm:item.criadoEm,loja:item.loja,valorFox:item.valorFox});
          });
          const ranked=Object.values(empMap).sort((a,b)=>b.count-a.count);
          const selEmp=concIntelSel||ranked[0]?.empresa;
          const selData=empMap[selEmp];

          // group medidas for selected competitor — best (lowest) price per medida
          const medMap={};
          (selData?.medidas||[]).forEach(m=>{
            if(!medMap[m.medida])medMap[m.medida]={medida:m.medida,count:0,melhor:null,pgto:"",criadoEm:"",loja:"",valorFox:m.valorFox};
            medMap[m.medida].count++;
            if(m.valor>0&&(medMap[m.medida].melhor===null||m.valor<medMap[m.medida].melhor)){
              medMap[m.medida].melhor=m.valor;
              medMap[m.medida].pgto=m.pgto;
              medMap[m.medida].criadoEm=m.criadoEm;
              medMap[m.medida].loja=m.loja;
              medMap[m.medida].valorFox=m.valorFox;
            }
          });
          const medList=Object.values(medMap).sort((a,b)=>b.count-a.count);

          return(
            <div className="scroll-anim" style={{background:"#1C1C1C",border:"1px solid #2E2E2E",borderRadius:10,padding:20,marginBottom:16,marginTop:0}}>
              <div className="chart-t">🏢 Inteligência de Concorrência</div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1.6fr",gap:16,alignItems:"start"}}>

                {/* LEFT — ranking */}
                <div>
                  <div style={{fontSize:10,color:MUTED,fontWeight:700,letterSpacing:1,textTransform:"uppercase",marginBottom:10}}>Empresas que mais negociamos</div>
                  <div style={{display:"flex",flexDirection:"column",gap:6}}>
                    {ranked.map((emp,i)=>{
                      const isSel=emp.empresa===selEmp;
                      const pct=Math.round((emp.count/ranked[0].count)*100);
                      return(
                        <div key={emp.empresa} onClick={()=>setConcIntelSel(emp.empresa)} style={{background:isSel?"#1A1E2E":"#161616",border:"1px solid "+(isSel?BLUE:"#2E2E2E"),borderRadius:8,padding:"10px 12px",cursor:"pointer",transition:"all .15s"}}>
                          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:isSel?6:0}}>
                            <div style={{display:"flex",alignItems:"center",gap:8}}>
                              <span style={{fontSize:11,fontWeight:800,color:i===0?RED:MUTED,minWidth:18}}>#{i+1}</span>
                              <span style={{fontSize:13,fontWeight:700,color:isSel?"#fff":"#C0C0C0"}}>{emp.empresa}</span>
                            </div>
                            <span style={{background:isSel?BLUE+"33":RED+"22",color:isSel?BLUE:RED,borderRadius:20,padding:"2px 10px",fontSize:11,fontWeight:800}}>{emp.count}x</span>
                          </div>
                          <div style={{height:4,background:"#2E2E2E",borderRadius:2,overflow:"hidden",marginTop:6}}>
                            <div style={{width:pct+"%",height:"100%",background:i===0?RED:isSel?BLUE:"#3E3E3E",borderRadius:2,transition:"width .4s"}}/>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* RIGHT — medidas do selecionado */}
                <div>
                  <div style={{fontSize:10,color:MUTED,fontWeight:700,letterSpacing:1,textTransform:"uppercase",marginBottom:10}}>
                    Melhores preços de <span style={{color:BLUE}}>{selEmp}</span> por medida
                  </div>
                  {medList.length===0?<div style={{color:MUTED,fontSize:13}}>Nenhum dado disponível.</div>:(
                    <div style={{display:"flex",flexDirection:"column",gap:8}}>
                      {medList.map(m=>{
                        const diff=m.valorFox&&m.melhor?m.valorFox-m.melhor:null;
                        return(
                          <div key={m.medida} style={{background:"#161616",border:"1px solid #2E2E2E",borderRadius:8,padding:"10px 14px"}}>
                            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:6}}>
                              <div>
                                <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:17,color:AMBER,letterSpacing:1}}>{m.medida}</div>
                                <div style={{fontSize:10,color:MUTED,marginTop:1}}>{m.loja} · {m.criadoEm?new Date(m.criadoEm).toLocaleDateString("pt-BR"):""}</div>
                              </div>
                              <div style={{textAlign:"right"}}>
                                <div style={{fontSize:15,fontWeight:800,color:RED}}>{m.melhor?fmtVal(m.melhor):"—"}</div>
                                {m.pgto&&<div style={{fontSize:10,color:MUTED}}>{m.pgto}</div>}
                              </div>
                            </div>
                            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginTop:8,flexWrap:"wrap",gap:6}}>
                              <div style={{display:"flex",gap:10,alignItems:"center"}}>
                                <span style={{fontSize:10,color:MUTED}}>Nosso preço:</span>
                                <span style={{fontSize:12,fontWeight:700,color:GREEN}}>{m.valorFox?fmtVal(m.valorFox):"—"}</span>
                                {diff!==null&&<span style={{fontSize:11,fontWeight:700,color:diff<0?GREEN:diff>0?RED:MUTED,background:(diff<0?GREEN:diff>0?RED:MUTED)+"22",borderRadius:4,padding:"1px 7px"}}>{diff<0?"▼ "+fmtVal(Math.abs(diff))+" mais barato":diff>0?"▲ "+fmtVal(diff)+" mais caro":"= Mesmo preço"}</span>}
                              </div>
                              <span style={{background:RED+"22",color:RED,borderRadius:4,padding:"2px 8px",fontSize:10,fontWeight:700}}>Negociado {m.count}x</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })()}

        </div></div>

        {/* ── VOLUME DE NEGOCIAÇÕES POR DIA ── */}
        {(()=>{
          const hoje = new Date();
          const dias = volPeriodo==="semana"?7:30;
          const rows=[];
          for(let i=dias-1;i>=0;i--){
            const d=new Date(hoje);d.setDate(hoje.getDate()-i);
            const key=d.toISOString().slice(0,10);
            const label=d.toLocaleDateString("pt-BR",{day:"2-digit",month:"2-digit"});
            const diaSem=d.toLocaleDateString("pt-BR",{weekday:"short"}).replace(".","").toUpperCase();
            const count=filtered.filter(q=>q.criadoEm&&q.criadoEm.slice(0,10)===key).length;
            rows.push({key,label,diaSem,count});
          }
          const max=Math.max(...rows.map(r=>r.count),1);
          const total=rows.reduce((a,r)=>a+r.count,0);
          const media=total>0?(total/rows.filter(r=>r.count>0).length||1).toFixed(1):0;
          const topDia=rows.reduce((a,r)=>r.count>a.count?r:a,rows[0]);
          const hojeKey=hoje.toISOString().slice(0,10);
          const hojeCount=rows.find(r=>r.key===hojeKey)?.count||0;
          return(
            <div className="scroll-anim" style={{background:"#141414",border:"1px solid #222",borderRadius:10,padding:20,marginBottom:16,marginTop:0}}>
              {/* Header */}
              <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:20,flexWrap:"wrap",gap:10}}>
                <div style={{display:"flex",alignItems:"center",gap:10}}>
                  <div style={{width:4,height:22,background:RED,borderRadius:2}}/>
                  <span style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:18,letterSpacing:2,color:"#fff"}}>VOLUME DE NEGOCIAÇÕES</span>
                </div>
                <div style={{display:"flex",gap:6,background:"#0D0D0D",padding:4,borderRadius:8,border:"1px solid #222"}}>
                  {["semana","mes"].map(p=>(
                    <button key={p} onClick={()=>setVolPeriodo(p)} style={{background:volPeriodo===p?RED:"transparent",color:volPeriodo===p?"#fff":MUTED,border:"none",borderRadius:6,padding:"6px 18px",fontSize:11,fontWeight:800,cursor:"pointer",letterSpacing:1,textTransform:"uppercase",transition:"all .2s"}}>
                      {p==="semana"?"7 DIAS":"30 DIAS"}
                    </button>
                  ))}
                </div>
              </div>
              {/* KPI strip */}
              <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(120px,1fr))",gap:10,marginBottom:24}}>
                {[
                  {label:"Total",val:total,cor:RED,icon:"📊"},
                  {label:"Hoje",val:hojeCount,cor:AMBER,icon:"📅",pulse:true},
                  {label:"Recorde",val:topDia?.count||0,cor:GREEN,icon:"🏆"},
                  {label:"Média/dia",val:media,cor:BLUE,icon:"📈"},
                ].map((k,i)=>(
                  <div key={k.label} style={{background:"#0D0D0D",borderRadius:10,padding:"12px 16px",border:"1px solid #1E1E1E",borderTop:"3px solid "+k.cor}}>
                    <div style={{fontSize:10,color:MUTED,fontWeight:700,letterSpacing:1,textTransform:"uppercase",marginBottom:4}}>{k.icon} {k.label}</div>
                    <div style={{fontSize:28,fontWeight:900,color:"#fff",lineHeight:1+(.1+i*.12)+"s both"}}>{k.val}</div>
                    {k.label==="Recorde"&&topDia?.count>0&&<div style={{fontSize:10,color:MUTED,marginTop:3}}>{topDia.label} · {topDia.diaSem}</div>}
                  </div>
                ))}
              </div>
              {/* Chart area */}
              <div style={{background:"#0D0D0D",borderRadius:12,border:"1px solid #1E1E1E",overflowX:"auto"}}>
                <div style={{minWidth:volPeriodo==="mes"?rows.length*34+20:0,padding:"16px 16px 0"}}>
                  {/* Bars + grid rows stacked */}
                  {(()=>{
                    const BAR_H=180;
                    const GRID=[100,75,50,25];
                    return(
                      <div style={{position:"relative"}}>
                        {/* Grid rows behind bars */}
                        <div style={{position:"absolute",top:0,left:0,right:0,height:BAR_H,pointerEvents:"none"}}>
                          {GRID.map(pct=>(
                            <div key={pct} style={{position:"absolute",left:0,right:0,top:BAR_H-(BAR_H*(pct/100)),borderTop:"1px dashed #1E1E1E"}}>
                              <span style={{position:"absolute",right:"100%",paddingRight:4,top:-8,fontSize:9,color:"#333",fontWeight:600,whiteSpace:"nowrap"}}>{Math.round(max*(pct/100))}</span>
                            </div>
                          ))}
                        </div>
                        {/* Bars row */}
                        <div style={{display:"flex",alignItems:"flex-end",gap:volPeriodo==="semana"?10:4,height:BAR_H,position:"relative",zIndex:1}}>
                          {rows.map((r)=>{
                            const pct=max>0?(r.count/max):0;
                            const isTop=r.count===max&&r.count>0;
                            const isHoje=r.key===hojeKey;
                            const barH=pct>0?Math.max(Math.round(pct*BAR_H),8):3;
                            const col=isTop?"#22c55e":isHoje?AMBER:r.count===0?"#1C1C1C":"#CC1F1F";
                            const glow=isTop?"rgba(34,197,94,.35)":isHoje?"rgba(245,158,11,.35)":"rgba(204,31,31,.25)";
                            return(
                              <div key={r.key} style={{flex:volPeriodo==="semana"?1:"0 0 28px",minWidth:volPeriodo==="semana"?32:28,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"flex-end",height:"100%",position:"relative"}}>
                                {r.count>0&&<div style={{fontSize:volPeriodo==="semana"?13:10,fontWeight:900,color:col,marginBottom:5,textShadow:"0 0 8px "+col,whiteSpace:"nowrap"}}>{r.count}</div>}
                                <div style={{width:"100%",height:barH,background:r.count===0?"#181818":`linear-gradient(180deg,${col} 0%,${col}BB 100%)`,borderRadius:"4px 4px 0 0",boxShadow:r.count>0?"0 0 14px "+glow+",inset 0 1px 0 rgba(255,255,255,0.12)":"none",position:"relative",overflow:"hidden",transition:"height .4s ease"}}>
                                  {r.count>0&&<div style={{position:"absolute",inset:"0 0 60% 0",background:"rgba(255,255,255,0.07)",borderRadius:"4px 4px 0 0"}}/>}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        {/* Separator line */}
                        <div style={{height:1,background:"#1E1E1E",margin:"0 0 8px"}}/>
                        {/* Date labels row */}
                        <div style={{display:"flex",gap:volPeriodo==="semana"?10:4,paddingBottom:volPeriodo==="semana"?6:10}}>
                          {rows.map((r)=>{
                            const isHoje=r.key===hojeKey;
                            return(
                              <div key={r.key} style={{flex:volPeriodo==="semana"?1:"0 0 28px",minWidth:volPeriodo==="semana"?32:28,display:"flex",flexDirection:"column",alignItems:"center",gap:2}}>
                                <div style={{fontSize:volPeriodo==="semana"?10:8,color:isHoje?AMBER:"#4A4A4A",fontWeight:isHoje?800:500,whiteSpace:"nowrap"}}>{r.label}</div>
                                {volPeriodo==="semana"&&<div style={{fontSize:9,color:isHoje?AMBER:"#333",fontWeight:isHoje?700:400}}>{r.diaSem}</div>}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
              {/* Legend */}
              <div style={{display:"flex",gap:20,marginTop:14,flexWrap:"wrap"}}>
                <span style={{display:"flex",alignItems:"center",gap:6,fontSize:11,color:"#555"}}><span style={{width:12,height:12,borderRadius:3,background:"#22c55e",boxShadow:"0 0 6px rgba(34,197,94,.4)",display:"inline-block"}}/>Recorde do período</span>
                <span style={{display:"flex",alignItems:"center",gap:6,fontSize:11,color:"#555"}}><span style={{width:12,height:12,borderRadius:3,background:AMBER,boxShadow:"0 0 6px rgba(245,158,11,.4)",display:"inline-block"}}/>Hoje</span>
                <span style={{display:"flex",alignItems:"center",gap:6,fontSize:11,color:"#555"}}><span style={{width:12,height:12,borderRadius:3,background:RED,boxShadow:"0 0 6px rgba(204,31,31,.3)",display:"inline-block"}}/>Outros dias</span>
              </div>
            </div>
          );
        })()}

        </>)}
        </div>)}
      {tab==="cadastrar"&&(<>
      <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:22,flexWrap:"wrap",gap:12}}>
        <div className="ph">
          <div className="ph-icon" style={{background:"#1A1E2E",border:"2px solid "+BLUE}}><span style={{fontSize:24}}>📞</span></div>
          <div><div className="ph-t">Descontos — Cadastrar</div><div className="ph-s">Cadastre o produto aqui — informe o orçamento ou ordem de serviço.<br/>O Comercial consultará pelo número no balcão.</div></div>
        </div>

      </div>
      <div className="card">
        <label style={{marginBottom:6,display:"block"}}>Tipo de documento *</label>
        <div className="tipo-row">
          <button className={`tipo-btn ${form.tipo==="orcamento"?"sel":""}`} onClick={()=>setForm(f=>({...f,tipo:"orcamento"}))}>Orçamento</button>
          <button className={`tipo-btn ${form.tipo==="os"?"sel":""}`} onClick={()=>setForm(f=>({...f,tipo:"os"}))}>Ordem de Serviço (O.S.)</button>
        </div>
        <div className="fg2">
          <div className="field"><label>Nº {form.tipo==="os"?"da O.S.":"do Orçamento"} *</label><input placeholder={form.tipo==="os"?"Ex: OS-00123":"Ex: 000123"} value={form.numero} onChange={e=>setForm(f=>({...f,numero:e.target.value}))}/></div>
          <div className="field"><label>Loja *</label><select value={form.loja} onChange={e=>setForm(f=>({...f,loja:e.target.value}))}><option value="">Selecione...</option>{LOJAS.map(l=><option key={l}>{l}</option>)}</select></div>
          <div className="field"><label>Vendedor responsável *</label><select value={form.vendedor} onChange={e=>setForm(f=>({...f,vendedor:e.target.value}))}><option value="">Selecione o vendedor...</option>{VENDEDORES.map(v=><option key={v}>{v}</option>)}</select></div>
        </div>
        <div className="fg3">
          <div className="field"><label>CBA *</label><input placeholder="Ex: 0000" value={form.cba} onChange={e=>setForm(f=>({...f,cba:e.target.value}))}/></div>
          <div className="field"><label>Medida do Pneu *</label><input placeholder="Ex: 175/65R17" value={form.medida} onChange={e=>setForm(f=>({...f,medida:e.target.value}))}/></div>
          <div className="field"><label>Segmento *</label><select value={form.segmento} onChange={e=>setForm(f=>({...f,segmento:e.target.value}))}><option value="">Selecione...</option>{SEGS.map(s=><option key={s}>{s}</option>)}</select></div>
        </div>
        <div className="fg3">
          <div className="field"><label>Valor com Desconto *</label><input type="number" step="0.01" placeholder="0,00" value={form.valor} onChange={e=>setForm(f=>({...f,valor:e.target.value}))}/></div>
          <div className="field"><label>Forma de Pagamento *</label><select value={form.pgto} onChange={e=>setForm(f=>({...f,pgto:e.target.value}))}><option value="">Selecione...</option>{PGTO.map(o=><option key={o}>{o}</option>)}</select></div>
          <div className="field"><label>Validade *</label><input type="date" value={form.validade} onChange={e=>setForm(f=>({...f,validade:e.target.value}))}/></div>
        </div>
        <div className="field mb"><label>Observações</label><input placeholder="Opcional" value={form.obs} onChange={e=>setForm(f=>({...f,obs:e.target.value}))}/></div>
        {/* Concorrentes */}
        <div className="field mb" style={{marginTop:6}}>
          <label>🏢 Concorrentes (opcional)</label>
          <div style={{display:"flex",gap:8,marginTop:6,flexWrap:"wrap",alignItems:"flex-end"}}>
            <div style={{flex:2,minWidth:180,position:"relative"}}>
              <input
                placeholder="Digite para buscar concorrente..."
                value={concQuery}
                onChange={e=>{setConcQuery(e.target.value);setConcShowDrop(true);}}
                onFocus={()=>setConcShowDrop(true)}
                onBlur={()=>setTimeout(()=>setConcShowDrop(false),180)}
                style={{width:"100%",boxSizing:"border-box"}}
                autoComplete="off"
              />
              {concShowDrop&&concQuery.length>0&&(()=>{
                const todas=[...CONCORRENTES_PADRAO,...concExtras].filter((v,i,a)=>a.indexOf(v)===i).sort();
                const sug=todas.filter(x=>x.toLowerCase().includes(concQuery.toLowerCase()));
                const novaOpc=concQuery.trim()&&!todas.map(x=>x.toLowerCase()).includes(concQuery.trim().toLowerCase());
                if(!sug.length&&!novaOpc)return null;
                return(<div style={{position:"absolute",top:"100%",left:0,right:0,background:"#1C1C1C",border:"1px solid #3A3A3A",borderRadius:7,zIndex:99,maxHeight:200,overflowY:"auto",boxShadow:"0 8px 24px rgba(0,0,0,.6)"}}>
                  {sug.map(s=>(
                    <div key={s} onMouseDown={()=>{setConcQuery(s);setConcShowDrop(false);}} style={{padding:"8px 12px",cursor:"pointer",fontSize:13,color:"#F0F0F0"}} onMouseEnter={e=>e.currentTarget.style.background="#2E2E2E"} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>{s}</div>
                  ))}
                  {novaOpc&&(<div onMouseDown={()=>{const n=concQuery.trim();const upd=[...concExtras,n];setConcExtras(upd);localStorage.setItem("fox_concorrentes",JSON.stringify(upd));setConcQuery(n);setConcShowDrop(false);}} style={{padding:"8px 12px",cursor:"pointer",fontSize:13,color:"#6090E0",borderTop:"1px solid #2E2E2E"}} onMouseEnter={e=>e.currentTarget.style.background="#2E2E2E"} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>➕ Adicionar "{concQuery.trim()}"</div>)}
                </div>);
              })()}
            </div>
            <div style={{flex:1,minWidth:110}}>
              <input type="number" step="0.01" placeholder="Valor deles" value={concValor} onChange={e=>setConcValor(e.target.value)} style={{width:"100%",boxSizing:"border-box"}}/>
            </div>
            <div style={{flex:1,minWidth:130}}>
              <select value={concPgto} onChange={e=>setConcPgto(e.target.value)} style={{width:"100%"}}>
                <option value="">Pagamento</option>
                {PGTO.map(o=><option key={o}>{o}</option>)}
              </select>
            </div>
            <button type="button" onClick={()=>{if(!concQuery.trim())return;setConcAdicionados(a=>[...a,{empresa:concQuery.trim(),valor:concValor,pgto:concPgto}]);setConcQuery("");setConcValor("");setConcPgto("");}} style={{background:BLUE,color:"#fff",border:"none",borderRadius:7,padding:"0 16px",height:40,fontWeight:700,cursor:"pointer",whiteSpace:"nowrap",fontSize:13}}>+ Adicionar</button>
          </div>
          {concAdicionados.length>0&&(
            <div style={{marginTop:10,display:"flex",flexDirection:"column",gap:6}}>
              {concAdicionados.map((item,i)=>(
                <div key={i} style={{display:"flex",alignItems:"center",gap:10,background:"#161616",border:"1px solid #2E2E2E",borderRadius:7,padding:"7px 12px"}}>
                  <span style={{fontWeight:700,color:"#F0F0F0",fontSize:13,flex:2}}>{item.empresa}</span>
                  {item.valor&&<span style={{color:"#CC1F1F",fontWeight:700,fontSize:13}}>{parseFloat(item.valor).toLocaleString("pt-BR",{style:"currency",currency:"BRL"})}</span>}
                  {item.pgto&&<span style={{color:"#888",fontSize:12}}>{item.pgto}</span>}
                  <button onClick={()=>setConcAdicionados(a=>a.filter((_,j)=>j!==i))} style={{background:"transparent",border:"none",color:"#888",cursor:"pointer",fontSize:18,lineHeight:1,marginLeft:"auto"}}>×</button>
                </div>
              ))}
            </div>
          )}
        </div>
        {/* Anexo opcional */}
        <div className="field mb" style={{marginTop:6}}>
          <label>Anexo — imagem ou áudio (opcional)</label>
          <div style={{display:"flex",alignItems:"center",gap:12,marginTop:4}}>
            <label style={{background:"#161616",border:"1px dashed #3A3A3A",borderRadius:8,padding:"10px 18px",cursor:"pointer",color:MUTED,fontSize:13,fontWeight:500,transition:"all .15s",textTransform:"none",letterSpacing:0}} onMouseEnter={e=>{e.currentTarget.style.borderColor=RED;e.currentTarget.style.color="#F0F0F0";}} onMouseLeave={e=>{e.currentTarget.style.borderColor="#3A3A3A";e.currentTarget.style.color=MUTED;}}>
              📎 Selecionar arquivo
              <input type="file" accept="image/png,image/jpeg,image/jpg,image/webp,audio/mp3,audio/mpeg,audio/ogg,audio/wav,audio/m4a" style={{display:"none"}} onChange={handleAnexo}/>
            </label>
            {anexo&&(
              <div style={{display:"flex",alignItems:"center",gap:8,background:"#1A2E1A",border:"1px solid #2E4A2E",borderRadius:7,padding:"6px 14px"}}>
                <span style={{fontSize:16}}>{anexo.tipo.startsWith("audio")?"🎵":"🖼️"}</span>
                <span style={{fontSize:12,color:"#4CAF50",fontWeight:600}}>{anexo.nome}</span>
                <button onClick={()=>setAnexo(null)} style={{background:"transparent",border:"none",color:MUTED,cursor:"pointer",fontSize:16,lineHeight:1}}>×</button>
              </div>
            )}
          </div>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:10,marginTop:4}}>
          <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",userSelect:"none",padding:"8px 14px",background:form.erroInterno?"#2A1A1A":"#161616",border:"1px solid "+(form.erroInterno?"#CC1F1F":"#2E2E2E"),borderRadius:8,transition:"all .2s"}}>
            <input type="checkbox" checked={form.erroInterno} onChange={e=>setForm(f=>({...f,erroInterno:e.target.checked}))} style={{width:15,height:15,accentColor:"#CC1F1F",cursor:"pointer"}}/>
            <span style={{fontSize:12,fontWeight:700,color:form.erroInterno?"#CC1F1F":"#888"}}>⚠️ Erro interno — não contabilizar no Dashboard</span>
          </label>
          {form.erroInterno&&<span style={{fontSize:11,color:"#888",fontStyle:"italic"}}>Esta negociação não aparecerá nas análises.</span>}
        </div>
        <button className="btn-red" onClick={doAdd} style={{marginTop:6}}>Salvar Desconto Autorizado</button>
      </div>
    </>)}

    {/* CONSULTAR */}
    {tab==="consultar"&&(<>
      <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:22,flexWrap:"wrap",gap:12}}>
        <div className="ph">
          <div className="ph-icon" style={{background:"#2E2A1A",border:"2px solid "+AMBER}}><span style={{fontSize:24}}>🤝</span></div>
          <div><div className="ph-t">Comercial — Consultar</div><div className="ph-s">Busque pelo Orçamento ou O.S. — ou clique em uma linha da lista.</div></div>
        </div>
{session.role==="admin"&&<button className="btn-out" onClick={()=>exportXLS(quotesPorStatus)}>Gerar Planilha — {filtroStatus==="todos"?"Todos":filtroStatus==="validos"?"Válidos":filtroStatus==="pendente"?"Pendentes":filtroStatus==="liberado"?"Liberados":"Vencidas"} ({quotesPorStatus.length})</button>}
      </div>
      <div className="card">
        <div className="s-wrap">
          <input className="s-in" placeholder="ORÇAMENTO ou Nº O.S. ..." value={search} onChange={e=>{setSearch(e.target.value);setResult(null);setNotFound(false);}} onKeyDown={e=>e.key==="Enter"&&doSearch()}/>
          <button className="s-btn" onClick={doSearch}>BUSCAR</button>
        </div>
      </div>
      {result&&(<div className="rc">
        <div className="rh">
          <div>
            {result.negociadorNome&&<div style={{display:"flex",alignItems:"center",gap:7,background:"rgba(0,0,0,.25)",borderRadius:6,padding:"4px 10px",marginBottom:8,width:"fit-content"}}>🦊
              <span style={{fontSize:11,fontWeight:700,color:"rgba(255,255,255,.9)",letterSpacing:".5px"}}>{result.negociadorNome}</span>
              {result.negociadorEmail&&<span style={{fontSize:10,color:"rgba(255,255,255,.55)"}}>· {result.negociadorEmail}</span>}
            </div>}
            <div style={{fontSize:11,fontWeight:700,color:"rgba(255,255,255,.6)",letterSpacing:"1.5px",marginBottom:3}}>{result.tipo==="os"?"ORDEM DE SERVIÇO":"ORÇAMENTO"} — {result.loja}</div>
            <div className="rn">#{result.numero}</div>
          </div>
          <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:8}}>
            <span className="rt">{isExp(result.validade)?"⚠ EXPIRADO":"✓ VÁLIDO"}</span>
            <span className={`badge ${result.tipo==="os"?"b-os":"b-orc"}`}>{result.tipo==="os"?"Ordem de Serviço":"Orçamento"}</span>
              {!result.liberado&&<button onClick={()=>doEdit(result)} style={{background:"rgba(0,0,0,0.4)",color:"#fff",border:"1px solid rgba(255,255,255,0.4)",borderRadius:6,padding:"5px 14px",fontFamily:"'Inter',sans-serif",fontWeight:600,fontSize:12,cursor:"pointer",marginTop:4}}>✏ Editar</button>}
              {session.role==="admin"&&<button onClick={()=>{if(window.confirm("Excluir esta negociação? Esta ação não pode ser desfeita.")){doDel({numero:result.numero,tipo:result.tipo});setResult(null);setSearch("");}}} style={{background:"rgba(0,0,0,0.5)",color:"#E57373",border:"1px solid rgba(229,115,115,0.5)",borderRadius:6,padding:"5px 14px",fontFamily:"'Inter',sans-serif",fontWeight:600,fontSize:12,cursor:"pointer",marginTop:4}}>🗑 Excluir</button>}
              {result.anexoBase64&&session.role==="admin"&&<span style={{background:"rgba(0,0,0,0.35)",color:"#fff",borderRadius:5,padding:"3px 10px",fontSize:11,fontWeight:600,display:"flex",alignItems:"center",gap:4}}>{result.anexoTipo&&result.anexoTipo.startsWith("audio")?"🎵":"🖼️"} {result.anexoTipo&&result.anexoTipo.startsWith("audio")?"Áudio anexado":"Imagem anexada"}</span>}
            <button onClick={()=>doLiberar(result,null)} style={{background:result.liberado?"rgba(0,0,0,.5)":"rgba(0,0,0,.5)",color:result.liberado?GREEN:"#fff",border:"2px solid "+(result.liberado?GREEN:"rgba(255,255,255,.5)"),borderRadius:7,padding:"7px 16px",fontFamily:"'Inter',sans-serif",fontWeight:700,fontSize:12,cursor:"pointer",marginTop:4}}>
              {result.liberado?"✓ LIBERADO — Remover":"Liberar Desconto"}
            </button>
            {result.liberado&&result.liberadorNome&&<div style={{background:"rgba(0,0,0,.3)",borderRadius:5,padding:"4px 10px",display:"flex",alignItems:"center",gap:5}}>
              ✓<span style={{fontSize:10,color:"rgba(255,255,255,.7)",fontWeight:600}}>{result.liberadorNome}</span>
            </div>}
          </div>
        </div>
        <div className="rgrid">
          <div className="rcell"><div className="rl">CBA</div><div className="rv">{result.cba}</div></div>
          <div className="rcell"><div className="rl">Medida</div><div className="rv" style={{fontWeight:700,color:AMBER}}>{result.medida}</div></div>
          <div className="rcell"><div className="rl">Valor com Desconto</div><div className="rv-big">{fmtVal(result.valor)}</div></div>
          <div className="rcell"><div className="rl">Segmento</div><div className="rv">{result.segmento}</div></div>
          <div className="rcell"><div className="rl">Pagamento</div><div className="rv">{result.pgto}</div></div>
          <div className="rcell"><div className="rl">Loja</div><div className="rv">{result.loja}</div></div>
                    {result.vendedor&&<div className="rcell"><div className="rl">Vendedor</div><div className="rv" style={{color:AMBER,fontWeight:600}}>{result.vendedor}</div></div>}
          <div className="rcell"><div className="rl">Validade</div><div className={result.liberado?"rv-ok":isExp(result.validade)?"rv-exp":"rv-ok"}>{fmtDate(result.validade)}</div></div>
          <div className="rcell"><div className="rl">Status</div><div className={result.liberado?"rv-ok":isExp(result.validade)?"rv-exp":"rv-ok"}>{result.liberado?"Venda liberada":isExp(result.validade)?"Fora da validade":"Pendente de liberação"}</div></div>
          
          {result.obs&&<div className="rcell full"><div className="rl">Obs</div><div className="rv">{result.obs}</div></div>}
        </div>
        {/* ANEXO — somente admin */}
        {result.anexoBase64&&session.role==="admin"&&(
          <div style={{background:"#0D1117",borderTop:"2px solid #1A1E3A",padding:"18px 22px"}}>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:12}}>
              <span style={{fontSize:14}}>{result.anexoTipo&&result.anexoTipo.startsWith("audio")?"🎵":"🖼️"}</span>
              <span style={{fontSize:11,fontWeight:700,color:BLUE,letterSpacing:1,textTransform:"uppercase"}}>Anexo — somente você (admin) vê isso</span>
            </div>
            {result.anexoTipo&&result.anexoTipo.startsWith("image")
              ?<div>
                <img
                  src={result.anexoBase64}
                  alt={result.anexoNome}
                  onClick={()=>setImgModal({src:result.anexoBase64,nome:result.anexoNome})}
                  style={{maxWidth:"100%",maxHeight:260,borderRadius:8,border:"1px solid #2E2E3E",cursor:"zoom-in",display:"block"}}
                  title="Clique para ver em tela cheia"
                />
                <div style={{display:"flex",gap:10,marginTop:10}}>
                  <button onClick={()=>setImgModal({src:result.anexoBase64,nome:result.anexoNome})} style={{background:"#1A1E2E",border:"1px solid "+BLUE,color:BLUE,borderRadius:7,padding:"7px 16px",fontFamily:"'Inter',sans-serif",fontWeight:700,fontSize:12,cursor:"pointer"}}>🔍 Tela cheia</button>
                  <a href={result.anexoBase64} download={result.anexoNome} style={{background:RED,color:"#fff",borderRadius:7,padding:"7px 16px",fontFamily:"'Inter',sans-serif",fontWeight:700,fontSize:12,textDecoration:"none",display:"inline-flex",alignItems:"center",gap:5}}>⬇ Baixar</a>
                </div>
              </div>
              :<div>
                <audio controls src={result.anexoBase64} style={{width:"100%",outline:"none",marginBottom:10}}><track kind="captions"/></audio>
                <a href={result.anexoBase64} download={result.anexoNome} style={{background:RED,color:"#fff",borderRadius:7,padding:"7px 16px",fontFamily:"'Inter',sans-serif",fontWeight:700,fontSize:12,textDecoration:"none",display:"inline-flex",alignItems:"center",gap:5}}>⬇ Baixar áudio</a>
              </div>
            }
            <div style={{fontSize:11,color:MUTED,marginTop:8}}>{result.anexoNome}</div>
          </div>
        )}
        {isExp(result.validade)&&!result.liberado&&<div className="warn-bar"><span>⚠</span>Desconto fora do prazo. Contate o setor de Descontos antes de aplicar.</div>}
          {result.liberado&&<div style={{background:"#1A2E1A",borderTop:"1px solid #2E4A2E",padding:"13px 22px",color:"#4CAF50",fontSize:13,fontWeight:600,display:"flex",alignItems:"center",gap:8}}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            Venda liberada por <strong style={{marginLeft:4}}>{result.liberadorNome}</strong>{result.liberadoEm&&<span style={{color:"#888",fontWeight:400,marginLeft:6}}>· {new Date(result.liberadoEm).toLocaleString("pt-BR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})}</span>}
          </div>}
      </div>)}
      {notFound&&<div className="card" style={{marginBottom:16}}><div className="empty"><span style={{fontSize:32,opacity:.2}}>🔍</span><p style={{color:RED,fontWeight:700,marginBottom:6}}>Não encontrado</p><p>Verifique o número com o cliente.</p></div></div>}

      {/* Lista */}
      <div style={{marginTop:8,marginBottom:12}}>
        <p className="sec-t">Todos os Descontos</p>
        <div style={{display:"flex",gap:8,marginBottom:14,marginTop:8,flexWrap:"wrap"}}>
          {[
            ["todos","Todos","#555"],
            ["validos","Válidos",GREEN],
            ["pendente","Pendentes",AMBER],
            ["liberado","Liberados",GREEN],
            ["vencido","Vencidas","#CC1F1F"]
          ].map(([v,l,c])=>{
            const cnt = v==="todos"?quotes.length
              :v==="validos"?quotes.filter(q=>!isExp(q.validade)&&!q.liberado).length
              :v==="pendente"?quotes.filter(q=>!q.liberado).length
              :v==="liberado"?quotes.filter(q=>q.liberado).length
              :quotes.filter(q=>isExp(q.validade)&&!q.liberado).length;
            return(<button key={v} onClick={()=>setFiltroStatus(v)} style={{background:filtroStatus===v?c+"22":"transparent",border:"1px solid "+(filtroStatus===v?c:"#333"),color:filtroStatus===v?c:"#888",borderRadius:6,padding:"6px 14px",fontFamily:"'Inter',sans-serif",fontWeight:700,fontSize:12,cursor:"pointer",transition:"all .15s"}}>
              {l} ({cnt})
            </button>);
          })}
        </div>
      </div>
      {quotes.length===0?(<div className="card"><div className="empty"><span style={{fontSize:32,opacity:.2}}>📋</span><p>Nenhum desconto cadastrado.</p></div></div>):(
        <div className="card-np">{quotes.filter(q=>{
            if(filtroStatus==="todos")return true;
            if(filtroStatus==="liberado")return !!q.liberado;
            if(filtroStatus==="pendente")return !q.liberado;
            if(filtroStatus==="validos")return !isExp(q.validade)&&!q.liberado;
            if(filtroStatus==="vencido")return isExp(q.validade)&&!q.liberado;
            return true;
          }).map((q,i)=>(
          <div className="list-row cl" key={i} onClick={()=>clickRow(q)}>
            <span className="list-num" style={{background:"#CC1F1F",color:"#fff",padding:"6px 10px",borderRadius:6,textAlign:"center",minWidth:88,display:"inline-flex",alignItems:"center",justifyContent:"center",flexShrink:0,fontSize:14,letterSpacing:"1.5px"}}>#{q.numero}</span>
            <div style={{flex:1}}>
              <div className="list-d">{q.medida} — {q.segmento}</div>
              <div className="list-m">{q.loja} · {q.pgto} · val. {fmtDate(q.validade)}</div>
            </div>
            <span className={`badge ${q.tipo==="os"?"b-os":"b-orc"}`} style={{marginLeft:6}}>{q.tipo==="os"?"O.S.":"ORC."}</span>
            <span className="list-val">{fmtVal(q.valor)}</span>
            <span className={`badge ${q.liberado?"b-lib":isExp(q.validade)?"b-exp":"b-valid"}`} style={{marginLeft:8}}>{q.liberado?"Liberado":isExp(q.validade)?"Expirado":"Válido"}</span>
            <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:2,marginLeft:8,flexShrink:0}}>
              <span className={`badge ${q.liberado?"b-lib":"b-pend"}`}>{q.liberado?"✓ LIB.":"PEND."}</span>
              {q.liberado&&q.liberadorNome&&<span style={{fontSize:9,color:MUTED}}>{q.liberadorNome}</span>}
            </div>
            <button onClick={e=>doLiberar(q,e)} style={{marginLeft:8,background:q.liberado?"#1A2E1A":RED,color:"#fff",border:"none",borderRadius:6,padding:"5px 12px",fontFamily:"'Inter',sans-serif",fontWeight:700,fontSize:12,cursor:"pointer",flexShrink:0,whiteSpace:"nowrap"}}>
              {q.liberado?"✓":"Liberar"}
            </button>
            {session.role==="admin"&&<button onClick={e=>{e.stopPropagation();if(window.confirm("Excluir esta negociação?"))doDel({numero:q.numero,tipo:q.tipo});}} style={{marginLeft:4,background:"transparent",color:"#E57373",border:"1px solid rgba(229,115,115,0.3)",borderRadius:6,padding:"5px 10px",fontFamily:"'Inter',sans-serif",fontSize:12,cursor:"pointer",flexShrink:0}}>🗑</button>}
          </div>
        ))}</div>
      )}
    </>)}

    {/* USERS */}
    {tab==="users"&&session.role==="admin"&&(<>
      <div style={{marginBottom:20}}><p className="sec-t">Gerenciar Usuários</p><p className="sec-s">Somente o administrador pode criar ou remover acessos.</p></div>
      <div className="card">
        <p style={{fontSize:13,fontWeight:700,color:TEXT,marginBottom:14}}>Criar novo acesso</p>
        <div className="fg2">
          <div className="field"><label>Nome completo</label><input placeholder="Nome do colaborador" value={newUser.nome} onChange={e=>setNewUser(f=>({...f,nome:e.target.value}))}/></div>
          <div className="field"><label>E-mail</label><input type="email" placeholder="email@foxpneus.com.br" value={newUser.email} onChange={e=>setNewUser(f=>({...f,email:e.target.value}))}/></div>
        </div>
        <div className="fg2">
          <div className="field"><label>Senha</label><input type="password" placeholder="Senha de acesso" value={newUser.pass} onChange={e=>setNewUser(f=>({...f,pass:e.target.value}))}/></div>
          <div className="field"><label>Setor</label><select value={newUser.role} onChange={e=>setNewUser(f=>({...f,role:e.target.value}))}><option value="televendas">Descontos — cadastra</option><option value="comercial">Comercial — consulta</option></select></div>
        </div>
        <button className="btn-red" onClick={doAddUser}>Criar Usuário</button>
      </div>
      <hr className="divider"/>
      <p className="sec-t" style={{marginBottom:4}}>Usuários ({users.length})</p>
      {users.length===0?(<div className="card"><div className="empty"><span style={{fontSize:32,opacity:.2}}>👥</span><p>Nenhum usuário.</p></div></div>):(
        <div className="card-np">{users.map(u=>(
          <div className="list-row" key={u.email}>
            <div style={{width:36,height:36,borderRadius:"50%",background:CARD,border:"2px solid "+roleColor(u.role),display:"flex",alignItems:"center",justifyContent:"center",fontSize:14,fontWeight:700,color:roleColor(u.role),flexShrink:0}}>{(u.nome||u.email)[0].toUpperCase()}</div>
            <div style={{flex:1}}><div className="list-d" style={{fontWeight:600}}>{u.nome}</div><div className="list-m">{u.email} — {roleName(u.role)}</div></div>
            <span className={`badge ${u.role==="televendas"?"b-tv":"b-com"}`}>{roleName(u.role)}</span>
            <button className="btn-sm" style={{marginLeft:12}} onClick={()=>doDelUser(u.email)}>Remover</button>
          </div>
        ))}</div>
      )}
      <div className="info-box" style={{marginTop:16}}><strong style={{color:TEXT}}>Conta admin:</strong> Usuário <strong style={{color:RED}}>admin@foxpneus.com.br</strong> é fixo e só você conhece a senha.</div>
    </>)}

    </div>

    {/* EXPORT MODAL */}
    {imgModal&&(
      <div onClick={()=>setImgModal(null)} style={{position:"fixed",inset:0,background:"rgba(0,0,0,.92)",zIndex:2000,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:16,cursor:"zoom-out"}}>
        <div style={{position:"absolute",top:16,right:20,display:"flex",gap:12}}>
          <a href={imgModal.src} download={imgModal.nome} onClick={e=>e.stopPropagation()} style={{background:RED,color:"#fff",borderRadius:8,padding:"9px 22px",fontFamily:"'Inter',sans-serif",fontWeight:700,fontSize:13,cursor:"pointer",textDecoration:"none",display:"inline-flex",alignItems:"center",gap:7}}>⬇ Baixar</a>
          <button onClick={()=>setImgModal(null)} style={{background:"#2E2E2E",color:"#fff",border:"none",borderRadius:8,padding:"9px 18px",fontFamily:"'Inter',sans-serif",fontWeight:700,fontSize:13,cursor:"pointer"}}>✕ Fechar</button>
        </div>
        <img src={imgModal.src} alt={imgModal.nome} onClick={e=>e.stopPropagation()} style={{maxWidth:"94vw",maxHeight:"88vh",borderRadius:10,border:"1px solid #3A3A3A",objectFit:"contain"}}/>
        <div style={{color:"#888",fontSize:12,marginTop:10}}>{imgModal.nome}</div>
      </div>
    )}
    {editModal&&(
      <div className="edit-overlay" onClick={()=>setEditModal(null)}>
        <div className="edit-modal" onClick={e=>e.stopPropagation()} style={{maxWidth:560,width:"100%"}}>
          <div className="edit-title">✏ Editar — #{editModal.numero}</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:14}}>
            <div className="field"><label>CBA</label><input placeholder="CBA" value={editForm.cba} onChange={e=>setEditForm(f=>({...f,cba:e.target.value}))}/></div>
            <div className="field"><label>Medida *</label><input placeholder="Ex: 175/65R17" value={editForm.medida} onChange={e=>setEditForm(f=>({...f,medida:e.target.value}))}/></div>
            <div className="field"><label>Segmento</label><select value={editForm.segmento} onChange={e=>setEditForm(f=>({...f,segmento:e.target.value}))}><option value="">Selecione...</option>{SEGS.map(s=><option key={s}>{s}</option>)}</select></div>
            <div className="field"><label>Loja</label><select value={editForm.loja} onChange={e=>setEditForm(f=>({...f,loja:e.target.value}))}><option value="">Selecione...</option>{LOJAS.map(l=><option key={l}>{l}</option>)}</select></div>
            <div className="field"><label>Valor com Desconto *</label><input type="number" step="0.01" placeholder="0,00" value={editForm.valor} onChange={e=>setEditForm(f=>({...f,valor:e.target.value}))}/></div>
            <div className="field"><label>Forma de Pagamento</label><select value={editForm.pgto} onChange={e=>setEditForm(f=>({...f,pgto:e.target.value}))}><option value="">Selecione...</option>{PGTO.map(o=><option key={o}>{o}</option>)}</select></div>
            <div className="field"><label>Validade *</label><input type="date" value={editForm.validade} onChange={e=>setEditForm(f=>({...f,validade:e.target.value}))}/></div>
            <div className="field"><label>Observações</label><input placeholder="Motivo / obs" value={editForm.obs} onChange={e=>setEditForm(f=>({...f,obs:e.target.value}))}/></div>
          </div>
          {/* Concorrentes no edit */}
          <div style={{borderTop:"1px solid #2E2E2E",paddingTop:14,marginBottom:14}}>
            <div style={{fontSize:11,color:MUTED,fontWeight:700,textTransform:"uppercase",letterSpacing:1,marginBottom:10}}>🏢 Concorrentes</div>
            <div style={{display:"flex",gap:8,flexWrap:"wrap",alignItems:"flex-end",marginBottom:8}}>
              <div style={{flex:2,minWidth:150,position:"relative"}}>
                <input placeholder="Buscar concorrente..." value={editConcQuery} onChange={e=>{setEditConcQuery(e.target.value);setEditConcDrop(true);}} onFocus={()=>setEditConcDrop(true)} onBlur={()=>setTimeout(()=>setEditConcDrop(false),180)} style={{width:"100%",boxSizing:"border-box"}} autoComplete="off"/>
                {editConcDrop&&editConcQuery.length>0&&(()=>{
                  const todas=[...CONCORRENTES_PADRAO,...concExtras].filter((v,i,a)=>a.indexOf(v)===i).sort();
                  const sug=todas.filter(x=>x.toLowerCase().includes(editConcQuery.toLowerCase()));
                  if(!sug.length)return null;
                  return(<div style={{position:"absolute",top:"100%",left:0,right:0,background:"#1C1C1C",border:"1px solid #3A3A3A",borderRadius:7,zIndex:99,maxHeight:160,overflowY:"auto",boxShadow:"0 8px 24px rgba(0,0,0,.6)"}}>
                    {sug.map(s=>(<div key={s} onMouseDown={()=>{setEditConcQuery(s);setEditConcDrop(false);}} style={{padding:"7px 12px",cursor:"pointer",fontSize:13,color:"#F0F0F0"}} onMouseEnter={e=>e.currentTarget.style.background="#2E2E2E"} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>{s}</div>))}
                  </div>);
                })()}
              </div>
              <div style={{flex:1,minWidth:90}}><input type="number" step="0.01" placeholder="Valor deles" value={editConcValor} onChange={e=>setEditConcValor(e.target.value)} style={{width:"100%",boxSizing:"border-box"}}/></div>
              <div style={{flex:1,minWidth:110}}><select value={editConcPgto} onChange={e=>setEditConcPgto(e.target.value)} style={{width:"100%"}}><option value="">Pagamento</option>{PGTO.map(o=><option key={o}>{o}</option>)}</select></div>
              <button type="button" onClick={()=>{if(!editConcQuery.trim())return;setEditConcAdicionados(a=>[...a,{empresa:editConcQuery.trim(),valor:editConcValor,pgto:editConcPgto}]);setEditConcQuery("");setEditConcValor("");setEditConcPgto("");}} style={{background:BLUE,color:"#fff",border:"none",borderRadius:7,padding:"0 14px",height:40,fontWeight:700,cursor:"pointer",fontSize:13}}>+ Add</button>
            </div>
            {editConcAdicionados.length>0&&(
              <div style={{display:"flex",flexDirection:"column",gap:5}}>
                {editConcAdicionados.map((item,i)=>(
                  <div key={i} style={{display:"flex",alignItems:"center",gap:10,background:"#161616",border:"1px solid #2E2E2E",borderRadius:7,padding:"6px 10px"}}>
                    <span style={{fontWeight:700,color:"#F0F0F0",fontSize:12,flex:2}}>{item.empresa}</span>
                    {item.valor&&<span style={{color:RED,fontWeight:700,fontSize:12}}>{parseFloat(item.valor).toLocaleString("pt-BR",{style:"currency",currency:"BRL"})}</span>}
                    {item.pgto&&<span style={{color:MUTED,fontSize:11}}>{item.pgto}</span>}
                    <button onClick={()=>setEditConcAdicionados(a=>a.filter((_,j)=>j!==i))} style={{background:"transparent",border:"none",color:MUTED,cursor:"pointer",fontSize:16,marginLeft:"auto"}}>×</button>
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* Erro interno */}
          <label style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",padding:"8px 12px",background:editForm.erroInterno?"#2A1A1A":"#161616",border:"1px solid "+(editForm.erroInterno?RED:"#2E2E2E"),borderRadius:8,marginBottom:12,transition:"all .2s"}}>
            <input type="checkbox" checked={editForm.erroInterno} onChange={e=>setEditForm(f=>({...f,erroInterno:e.target.checked}))} style={{width:15,height:15,accentColor:RED,cursor:"pointer"}}/>
            <span style={{fontSize:12,fontWeight:700,color:editForm.erroInterno?RED:"#888"}}>⚠️ Erro interno — não contabilizar no Dashboard</span>
          </label>
          <div style={{display:"flex",gap:10}}>
            <button className="btn-sm" style={{flex:1,padding:"10px"}} onClick={()=>setEditModal(null)}>Cancelar</button>
            <button className="btn-red" style={{flex:2}} onClick={doSaveEdit}>Salvar Atualização</button>
          </div>
        </div>
      </div>
    )}
    {showExport&&exportRows.length>0&&(
      <div className="overlay" onClick={()=>setShowExport(false)}>
        <div className="modal" onClick={e=>e.stopPropagation()}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between"}}>
            <div className="modal-t">Dados Exportados — {exportRows.length} registro(s)</div>
            <button className="btn-red" style={{width:"auto",padding:"7px 18px"}} onClick={()=>setShowExport(false)}>Fechar</button>
          </div>
          <div style={{fontSize:11,color:MUTED,background:"#161616",borderRadius:6,padding:"8px 12px",display:"flex",alignItems:"center",gap:8}}>
            Selecione toda a tabela, copie (Ctrl+C) e cole direto no Excel ou Google Planilhas.
          </div>
          <div className="exp-table">
            <table>
              <thead><tr>{Object.keys(exportRows[0]).map(h=><th key={h}>{h}</th>)}</tr></thead>
              <tbody>{exportRows.map((row,i)=>(
                <tr key={i}>{Object.entries(row).map(([k,v],j)=>(
                  <td key={j} style={{color:k==="Status"?(v==="Liberado"?GREEN:AMBER):TEXT,fontWeight:k==="Status"||k==="Medida"?700:400}}>{v||"—"}</td>
                ))}</tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      </div>
    )}


    {galeriaModal&&(
      <div onClick={()=>setGaleriaModal(null)} style={{position:"fixed",inset:0,background:"rgba(0,0,0,.92)",zIndex:1000,display:"flex",flexDirection:"column",alignItems:"center",padding:"24px 16px",overflowY:"auto"}}>
        <div onClick={e=>e.stopPropagation()} style={{width:"100%",maxWidth:1100}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:20}}>
            <div>
              <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:26,color:"#fff",letterSpacing:2}}>🖼️ Comprovantes — {galeriaModal.medida}</div>
              <div style={{fontSize:12,color:MUTED,marginTop:2}}>{galeriaModal.imagens.length} imagem{galeriaModal.imagens.length!==1?"ns":""} · {(galeriaModal.semFoto||[]).length} sem foto com concorrentes</div>
            </div>
            <button onClick={()=>setGaleriaModal(null)} style={{background:"#2E2E2E",border:"none",color:"#fff",borderRadius:8,padding:"8px 20px",fontSize:13,fontWeight:700,cursor:"pointer"}}>✕ Fechar</button>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(260px,1fr))",gap:16}}>
            {galeriaModal.imagens.map((q,i)=>{
              const conc=parseConcObs(q.obs);
              const isCopied=copiedNum===q.numero;
              const copyNum=()=>{navigator.clipboard.writeText(q.numero).then(()=>{setCopiedNum(q.numero);setTimeout(()=>setCopiedNum(null),2000);});};
              return(
              <div key={q.numero+i} style={{background:"#1C1C1C",borderRadius:10,overflow:"hidden",border:"1px solid #2E2E2E",display:"flex",flexDirection:"column"}}>
                {/* Número + copy em destaque ANTES da imagem */}
                <div style={{background:"#141414",borderBottom:"1px solid #2E2E2E",padding:"10px 12px",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                  <div>
                    <div style={{fontSize:9,color:MUTED,fontWeight:700,letterSpacing:1,textTransform:"uppercase"}}>{q.tipo==="os"?"Ordem de Serviço":"Orçamento"}</div>
                    <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:22,color:"#fff",letterSpacing:2,lineHeight:1.1}}>#{q.numero}</div>
                  </div>
                  <button onClick={copyNum} title="Copiar número" style={{background:isCopied?GREEN+"22":"#1A1E2E",border:"1px solid "+(isCopied?GREEN:BLUE),color:isCopied?GREEN:BLUE,borderRadius:7,padding:"6px 14px",fontSize:12,fontWeight:700,cursor:"pointer",transition:"all .2s",whiteSpace:"nowrap"}}>
                    {isCopied?"✓ Copiado!":"📋 Copiar"}
                  </button>
                </div>
                {/* Imagem */}
                <img
                  src={q.anexoBase64}
                  alt={q.anexoNome}
                  onClick={()=>setImgModal({src:q.anexoBase64,nome:q.anexoNome})}
                  style={{width:"100%",height:180,objectFit:"cover",display:"block",cursor:"zoom-in"}}
                  title="Clique para ampliar"
                />
                {/* Corpo do card */}
                <div style={{padding:"10px 12px",flex:1}}>
                  <div style={{fontSize:11,color:MUTED,marginBottom:8}}>{q.loja} · {q.criadoEm?new Date(q.criadoEm).toLocaleDateString("pt-BR"):"—"}</div>
                  {/* Concorrentes em destaque */}
                  {conc.length>0&&(
                    <div style={{background:"#0D0D0D",border:"1px solid "+RED+"44",borderRadius:8,padding:"8px 10px",marginBottom:8}}>
                      <div style={{fontSize:9,color:RED,fontWeight:700,textTransform:"uppercase",letterSpacing:1,marginBottom:6}}>🏢 Concorrentes</div>
                      {conc.map((item,ci)=>(
                        <div key={ci} style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:ci<conc.length-1?6:0}}>
                          <span style={{fontSize:12,color:"#E0E0E0",fontWeight:700}}>{item.empresa}</span>
                          <div style={{textAlign:"right"}}>
                            <div style={{fontSize:14,fontWeight:800,color:RED}}>{item.valor?fmtVal(item.valor):"—"}</div>
                            {item.pgto&&<div style={{fontSize:9,color:MUTED}}>{item.pgto}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Nosso preço */}
                  <div style={{display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                    <span style={{fontSize:10,color:MUTED,fontWeight:600}}>Nosso preço negociado:</span>
                    <span style={{background:GREEN+"22",color:GREEN,borderRadius:4,padding:"2px 10px",fontSize:13,fontWeight:800}}>{fmtVal(q.valor)}</span>
                  </div>
                </div>
              </div>
              );
            })}
          </div>
          {/* Cards sem foto mas com concorrentes */}
          {(galeriaModal.semFoto||[]).length>0&&(
            <div style={{marginTop:20}}>
              <div style={{fontSize:11,color:MUTED,fontWeight:700,textTransform:"uppercase",letterSpacing:1,marginBottom:10}}>🏢 Negociações sem foto — dados de concorrência</div>
              <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(260px,1fr))",gap:12}}>
                {(galeriaModal.semFoto||[]).map((q,i)=>{
                  const conc=parseConcObs(q.obs);
                  const isCopied=copiedNum===q.numero;
                  return(
                    <div key={q.numero+i} style={{background:"#1C1C1C",borderRadius:10,overflow:"hidden",border:"1px solid #2E3E2E"}}>
                      <div style={{background:"#141414",borderBottom:"1px solid #2E2E2E",padding:"10px 12px",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                        <div>
                          <div style={{fontSize:9,color:MUTED,fontWeight:700,letterSpacing:1,textTransform:"uppercase"}}>{q.tipo==="os"?"Ordem de Serviço":"Orçamento"}</div>
                          <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:22,color:"#fff",letterSpacing:2,lineHeight:1.1}}>#{q.numero}</div>
                        </div>
                        <button onClick={()=>{navigator.clipboard.writeText(q.numero).then(()=>{setCopiedNum(q.numero);setTimeout(()=>setCopiedNum(null),2000);});}} style={{background:isCopied?GREEN+"22":"#1A1E2E",border:"1px solid "+(isCopied?GREEN:BLUE),color:isCopied?GREEN:BLUE,borderRadius:7,padding:"6px 14px",fontSize:12,fontWeight:700,cursor:"pointer",transition:"all .2s"}}>
                          {isCopied?"✓ Copiado!":"📋 Copiar"}
                        </button>
                      </div>
                      <div style={{padding:"10px 12px"}}>
                        <div style={{fontSize:11,color:MUTED,marginBottom:8}}>{q.loja} · {q.criadoEm?new Date(q.criadoEm).toLocaleDateString("pt-BR"):"—"}</div>
                        {conc.length>0&&(
                          <div style={{background:"#0D0D0D",border:"1px solid "+RED+"44",borderRadius:8,padding:"8px 10px",marginBottom:8}}>
                            <div style={{fontSize:9,color:RED,fontWeight:700,textTransform:"uppercase",letterSpacing:1,marginBottom:6}}>🏢 Concorrentes</div>
                            {conc.map((item,ci)=>(
                              <div key={ci} style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:ci<conc.length-1?6:0}}>
                                <span style={{fontSize:12,color:"#E0E0E0",fontWeight:700}}>{item.empresa}</span>
                                <div style={{textAlign:"right"}}>
                                  <div style={{fontSize:14,fontWeight:800,color:RED}}>{item.valor?fmtVal(item.valor):"—"}</div>
                                  {item.pgto&&<div style={{fontSize:9,color:MUTED}}>{item.pgto}</div>}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                          <span style={{fontSize:10,color:MUTED,fontWeight:600}}>Nosso preço negociado:</span>
                          <span style={{background:GREEN+"22",color:GREEN,borderRadius:4,padding:"2px 10px",fontSize:13,fontWeight:800}}>{fmtVal(q.valor)}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    )}

    {showConcAviso&&(
      <div onClick={()=>setShowConcAviso(false)} style={{position:"fixed",inset:0,background:"rgba(0,0,0,.85)",zIndex:3000,display:"flex",alignItems:"center",justifyContent:"center",padding:16}}>
        <div onClick={e=>e.stopPropagation()} style={{background:"#1C1C1C",border:"1px solid #3A3A3A",borderRadius:12,padding:"28px 28px",maxWidth:420,width:"100%",textAlign:"center"}}>
          <div style={{fontSize:32,marginBottom:12}}>⚠️</div>
          <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:20,color:"#fff",letterSpacing:1,marginBottom:8}}>Nenhum concorrente adicionado</div>
          <p style={{fontSize:13,color:"#888",marginBottom:24,lineHeight:1.6}}>Você não informou nenhum concorrente nessa negociação. Tem certeza que deseja salvar assim? Se foi um <strong style={{color:"#fff"}}>erro interno</strong>, marque a opção correspondente antes de salvar.</p>
          <div style={{display:"flex",gap:10,justifyContent:"center"}}>
            <button onClick={()=>setShowConcAviso(false)} style={{background:"#2E2E2E",color:"#fff",border:"none",borderRadius:8,padding:"10px 24px",fontSize:13,fontWeight:700,cursor:"pointer"}}>← Voltar e adicionar</button>
            <button onClick={()=>{setShowConcAviso(false);doAdd(true);}} style={{background:"#CC1F1F",color:"#fff",border:"none",borderRadius:8,padding:"10px 24px",fontSize:13,fontWeight:700,cursor:"pointer"}}>Salvar mesmo assim</button>
          </div>
        </div>
      </div>
    )}
    {toast&&<div className={`toast ${toast.ok?"t-ok":"t-err"}`}>{toast.msg}</div>}
  </div></div></>);
}
