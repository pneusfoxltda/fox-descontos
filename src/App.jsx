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
        return { data: await r.json(), error: r.ok ? null : "erro" };
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
const CONCORRENTES_PADRAO=["Atacado Pneus","GBIM Pneus","Bono Pneus","Camargo Pneus","Espantalho","GP Pneus","Iccap Randon","JK Pneus","Japurá","Morena Pneus","Muniz","Pemaza","Pneu Fácil","Pneu Paulista","Queiroz Pneus","Rei dos Pneus","Rondobras","Shopping dos Pneus","Toyota","Vip Pneus"];
const RED="#CC1F1F",CARD="#1C1C1C",TEXT="#F0F0F0",MUTED="#888",BORDER="#2E2E2E",AMBER="#E0A820",BLUE="#6090E0",GREEN="#4CAF50";
const CC=["#CC1F1F","#E02020","#A01515","#FF4444","#880E0E","#FF7070","#CC5555","#991111"];

function isExp(v){if(!v)return false;return new Date(v+"T23:59:59")<new Date();}
function fmtVal(v){const n=parseFloat(v);return isNaN(n)?v:"R$ "+n.toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2});}
function fmtDate(d){if(!d)return"-";const[y,m,dd]=d.split("-");return dd+"/"+m+"/"+y;}
function roleName(r){return{admin:"Gerente",televendas:"Descontos",comercial:"Comercial"}[r]||r;}
function roleColor(r){return{admin:RED,televendas:BLUE,comercial:AMBER}[r]||MUTED;}

const css=`
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:#0D0D0D;font-family:'Inter',sans-serif;color:#F0F0F0;}
.wrap{min-height:100vh;background:#0D0D0D;}
.topbar{background:#161616;border-bottom:2px solid #CC1F1F;padding:0 24px;display:flex;align-items:center;justify-content:space-between;height:64px;}
.brand{display:flex;align-items:center;gap:12px;}
.brand-icon{width:40px;height:40px;background:#CC1F1F;border-radius:8px;display:flex;align-items:center;justify-content:center;}
.brand-name{font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:2px;color:#fff;}
.brand-sub{font-size:10px;color:#888;letter-spacing:1px;text-transform:uppercase;}
.chip{display:flex;align-items:center;gap:8px;background:#1C1C1C;border:1px solid #2E2E2E;border-radius:6px;padding:6px 14px;font-size:13px;}
.logout{background:transparent;border:1px solid #333;color:#888;border-radius:6px;padding:6px 14px;font-family:'Inter',sans-serif;font-size:12px;cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:6px;}
.logout:hover{border-color:#CC1F1F;color:#CC1F1F;}
.tabs{display:flex;background:#161616;border-bottom:1px solid #2E2E2E;padding:0 24px;overflow-x:auto;}
.tab{padding:14px 18px;font-size:13px;font-weight:600;cursor:pointer;color:#888;border-bottom:3px solid transparent;transition:all .15s;position:relative;top:1px;display:flex;align-items:center;gap:7px;white-space:nowrap;}
.tab:hover{color:#F0F0F0;}.tab.active{color:#fff;border-bottom-color:#CC1F1F;}
.tab-dot{width:7px;height:7px;border-radius:50%;background:#444;flex-shrink:0;}.tab.active .tab-dot{background:#CC1F1F;}
.main{padding:24px;max-width:1100px;margin:0 auto;}
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
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px;}
.stat-card{background:#1C1C1C;border:1px solid #2E2E2E;border-radius:10px;padding:16px;}
.stat-lbl{font-size:11px;font-weight:700;color:#888;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;display:flex;align-items:center;gap:6px;}
.stat-val{font-family:'Bebas Neue',sans-serif;font-size:30px;letter-spacing:1px;color:#fff;line-height:1;}.stat-sub{font-size:11px;color:#888;margin-top:4px;}
.chart-card{background:#1C1C1C;border:1px solid #2E2E2E;border-radius:10px;padding:20px;margin-bottom:16px;}
.chart-t{display:flex;align-items:center;gap:8px;margin-bottom:16px;font-family:'Bebas Neue',sans-serif;font-size:16px;letter-spacing:1.5px;color:#fff;}
.filter-row{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;}
.empty{text-align:center;padding:40px 20px;color:#888;}
.divider{border:none;border-top:1px solid #2E2E2E;margin:16px 0;}
.info-box{background:#1A1A1A;border-left:3px solid #CC1F1F;border-radius:0 6px 6px 0;padding:10px 14px;margin-bottom:16px;font-size:12px;color:#888;line-height:1.6;}
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
  const[quotes,setQuotes]=useState([]);
  const[form,setForm]=useState({tipo:"orcamento",numero:"",cba:"",medida:"",segmento:"",loja:"",vendedor:"",valor:"",pgto:"",validade:"",obs:""});
  const[search,setSearch]=useState("");
  const[result,setResult]=useState(null);
  const[notFound,setNotFound]=useState(false);
  const[toast,setToast]=useState(null);
  const[newUser,setNewUser]=useState({nome:"",email:"",pass:"",role:"televendas"});
  const[dash,setDash]=useState({dataIni:"",dataFim:"",loja:"",segmento:"",medida:""});
  const[filtroStatus,setFiltroStatus]=useState("todos");
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
  const[editForm,setEditForm]=useState({cba:"",medida:"",segmento:"",loja:"",valor:"",pgto:"",validade:"",obs:""});
  const[exportRows,setExportRows]=useState([]);
  const[galeriaModal,setGaleriaModal]=useState(null);

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
    if(qu) setQuotes(qu.map(q=>({
      tipo:q.tipo,numero:q.numero,cba:q.cba,medida:q.medida,segmento:q.segmento,
      loja:q.loja,valor:q.valor,pgto:q.pgto,validade:q.validade,obs:q.obs,
      liberado:q.liberado,negociadorNome:q.negociador_nome,negociadorEmail:q.negociador_email,
      liberadorNome:q.liberador_nome,liberadorEmail:q.liberador_email,
      liberadoEm:q.liberado_em,criadoEm:q.criado_em,_id:q.id, vendedor:q.vendedor,
      anexoBase64:q.anexo_base64,anexoTipo:q.anexo_tipo,anexoNome:q.anexo_nome
    })));
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
    setEditForm({cba:q.cba||"",medida:q.medida||"",segmento:q.segmento||"",loja:q.loja||"",valor:q.valor||"",pgto:q.pgto||"",validade:q.validade||"",obs:q.obs||""});
    setEditModal(q);
  };

  const doSaveEdit=async()=>{
    if(!editForm.validade||!editForm.medida||!editForm.valor){toast_("Preencha os campos obrigatórios.",false);return;}
    try{
      const db = await supa.from("descontos");
      await db.update({
        cba:editForm.cba, medida:editForm.medida, segmento:editForm.segmento,
        loja:editForm.loja, valor:editForm.valor, pgto:editForm.pgto,
        validade:editForm.validade, obs:editForm.obs
      },{numero:editModal.numero,tipo:editModal.tipo});
      const updated={...editForm};
      setQuotes(prev=>prev.map(x=>(x.numero===editModal.numero&&x.tipo===editModal.tipo)?{...x,...updated}:x));
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

  const doAdd=async()=>{
    if(!form.numero||!form.cba||!form.medida||!form.segmento||!form.loja||!form.vendedor||!form.valor||!form.pgto||!form.validade){toast_("Preencha todos os campos.",false);return;}
    if(quotes.find(q=>q.numero===form.numero.trim()&&q.tipo===form.tipo)){toast_("Número já cadastrado.",false);return;}
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
      setForm({tipo:"orcamento",numero:"",cba:"",medida:"",segmento:"",loja:"",vendedor:"",valor:"",pgto:"",validade:"",obs:""});
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
      const {error} = await db.insert({nome:newUser.nome.trim(),email:em,senha:newUser.pass,role:newUser.role});
      if(error){toast_("Erro ao criar usuário.",false);return;}
      setUsers(prev=>[...prev,{nome:newUser.nome.trim(),email:em,pass:newUser.pass,role:newUser.role}]);
      setNewUser({nome:"",email:"",pass:"",role:"televendas"});toast_("Usuário criado!");
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
    <div className="topbar">
      <div className="brand">
        <div className="brand-icon"><span style={{fontSize:22}}>🦊</span></div>
        <div><div className="brand-name">Fox Pneus</div><div className="brand-sub">Sistema de Descontos</div></div>
      </div>
      <div style={{display:"flex",alignItems:"center",gap:10}}>
        <div className="chip">
          <span style={{fontSize:18}}>{session.role==="admin"?"🛡️":session.role==="televendas"?"📞":"🤝"}</span>
          <span style={{fontSize:13,fontWeight:600}}>{session.username}</span>
          <span style={{fontSize:11,color:roleColor(session.role)}}>{roleName(session.role)}</span>
        </div>
        <button className="logout" onClick={doLogout}>Sair</button>
      </div>
    </div>

    <div className="tabs">
      {session.role==="admin"&&<div className={`tab ${tab==="dashboard"?"active":""}`} onClick={()=>setTab("dashboard")}><span className="tab-dot"/>Dashboard</div>}
      {(session.role==="televendas"||session.role==="admin")&&<div className={`tab ${tab==="cadastrar"?"active":""}`} onClick={()=>setTab("cadastrar")}><span className="tab-dot"/>Descontos — Cadastrar</div>}
      {(session.role==="comercial"||session.role==="admin")&&<div className={`tab ${tab==="consultar"?"active":""}`} onClick={()=>{setTab("consultar");setResult(null);setNotFound(false);}}><span className="tab-dot"/>Comercial — Consultar</div>}
      {session.role==="admin"&&<div className={`tab ${tab==="users"?"active":""}`} onClick={()=>setTab("users")}><span className="tab-dot"/>Usuários</div>}
    </div>

    <div className="main">

    {/* DASHBOARD */}
    {tab==="dashboard"&&session.role==="admin"&&(<>
        <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:20,flexWrap:"wrap",gap:12}}>
          <div><p className="sec-t">Dashboard — Inteligência Comercial</p><p className="sec-s">Análise completa por medida, segmento, loja e vendedor.</p></div>
          <button className="btn-out" onClick={()=>exportXLS(filtered.length>0?filtered:quotes)}>⬇ Exportar Dados ({(filtered.length>0?filtered:quotes).length})</button>
        </div>

        {/* Filtros */}
        <div className="card" style={{marginBottom:16}}>
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
            <div className="stat-val" style={{color:RED}}>{filtered.length}</div>
            <div className="stat-sub">todas as negociações</div>
          </div>
          <div className="stat-card" style={{borderTop:"3px solid "+GREEN}}>
            <div className="stat-lbl">Fechadas (Liberadas)</div>
            <div className="stat-val" style={{color:GREEN}}>{filtered.filter(q=>q.liberado).length}</div>
            <div className="stat-sub">{filtered.length>0?((filtered.filter(q=>q.liberado).length/filtered.length)*100).toFixed(0):0}% de conversão</div>
          </div>
          <div className="stat-card" style={{borderTop:"3px solid "+AMBER}}>
            <div className="stat-lbl">Pendentes</div>
            <div className="stat-val" style={{color:AMBER}}>{filtered.filter(q=>!q.liberado&&!isExp(q.validade)).length}</div>
            <div className="stat-sub">aguardando aprovação</div>
          </div>
          <div className="stat-card" style={{borderTop:"3px solid #888"}}>
            <div className="stat-lbl">Vencidas</div>
            <div className="stat-val" style={{color:MUTED}}>{filtered.filter(q=>isExp(q.validade)&&!q.liberado).length}</div>
            <div className="stat-sub">não fechadas no prazo</div>
          </div>
        </div>

        {filtered.length===0?(<div className="card"><div className="empty"><div style={{fontSize:36,opacity:.2,marginBottom:12}}>📊</div><p>Nenhum dado para os filtros.</p></div></div>):(<>

        {/* Grid: Medidas + Segmentos */}
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16,marginBottom:16}}>

          {/* Ranking Medidas */}
          <div className="chart-card" style={{marginBottom:0}}>
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
                  <td style={{padding:"8px 8px"}}>{(()=>{const imgs=filtered.filter(q=>q.medida===m.name&&q.anexoBase64&&q.anexoTipo&&q.anexoTipo.startsWith("image"));return imgs.length>0?(<button onClick={()=>setGaleriaModal({medida:m.name,imagens:imgs})} style={{background:"#1A1E2E",border:"1px solid "+BLUE,color:BLUE,borderRadius:6,padding:"4px 10px",fontSize:11,fontWeight:700,cursor:"pointer",whiteSpace:"nowrap"}}>🖼️ {imgs.length} foto{imgs.length!==1?"s":""}</button>):(<span style={{color:MUTED,fontSize:11}}>—</span>);})()}</td>
                </tr>);})}
              </tbody>
            </table>
          </div>

          {/* Ranking Segmentos */}
          <div className="chart-card" style={{marginBottom:0}}>
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

        {/* Ranking Lojas */}
        <div className="chart-card">
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
          if(!vList.length)return(<div className="chart-card"><div className="chart-t">👤 Ranking de Vendedores</div><div className="empty" style={{padding:"20px"}}><p style={{color:MUTED}}>Nenhum vendedor registrado ainda. Cadastre descontos com o campo Vendedor preenchido.</p></div></div>);
          return(<div className="chart-card">
            <div className="chart-t">👤 Ranking de Vendedores — Negociações e Fechamentos</div>
            <table style={{width:"100%",borderCollapse:"collapse"}}>
              <thead><tr style={{borderBottom:"1px solid #2E2E2E"}}>
                {["#","Vendedor","Negociações","Fechou","Pendentes","Vencidas","Valor","Conversão"].map(h=><th key={h} style={{padding:"6px 10px",textAlign:"left",fontSize:10,fontWeight:700,color:MUTED,letterSpacing:1,textTransform:"uppercase"}}>{h}</th>)}
              </tr></thead>
              <tbody>{vList.map((v,i)=>{
                const conv=v.total>0?((v.lib/v.total)*100).toFixed(0):0;
                const barW=Math.max(4,parseInt(conv));
                return(<tr key={v.nome} style={{borderBottom:"1px solid #1C1C1C",background:i===0?"#1A2E1A":"transparent"}}>
                  <td style={{padding:"10px 10px"}}><span style={{display:"inline-flex",alignItems:"center",justifyContent:"center",width:24,height:24,borderRadius:"50%",background:i<3?[GREEN,"#888","#663300"][i]:"#2E2E2E",color:"#fff",fontSize:10,fontWeight:700}}>{i+1}</span></td>
                  <td style={{padding:"10px 10px",fontWeight:700,color:i===0?GREEN:TEXT,fontSize:14}}>{v.nome}</td>
                  <td style={{padding:"10px 10px"}}><span style={{background:RED+"22",color:RED,borderRadius:4,padding:"2px 10px",fontWeight:700,fontSize:13}}>{v.total}</span></td>
                  <td style={{padding:"10px 10px"}}><span style={{background:GREEN+"22",color:GREEN,borderRadius:4,padding:"2px 10px",fontWeight:700,fontSize:13}}>{v.lib}</span></td>
                  <td style={{padding:"10px 10px"}}><span style={{background:AMBER+"22",color:AMBER,borderRadius:4,padding:"2px 10px",fontWeight:700,fontSize:13}}>{v.pend}</span></td>
                  <td style={{padding:"10px 10px"}}><span style={{color:MUTED,fontWeight:700,fontSize:13}}>{v.venc}</span></td>
                  <td style={{padding:"10px 10px",fontWeight:600,color:TEXT,fontSize:12}}>{fmtVal(v.val)}</td>
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

        </>)}
      </>)}

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
{session.role==="admin"&&<button className="btn-out" onClick={()=>exportXLS(quotes)}>Gerar Planilha ({quotes.length})</button>}
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
            <span className="list-num">#{q.numero}</span>
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
        <div className="edit-modal" onClick={e=>e.stopPropagation()}>
          <div className="edit-title">✏ Editar — #{editModal.numero}</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:14}}>
            <div className="field">
              <label>CBA</label>
              <input placeholder="CBA" value={editForm.cba} onChange={e=>setEditForm(f=>({...f,cba:e.target.value}))}/>
            </div>
            <div className="field">
              <label>Medida *</label>
              <input placeholder="Ex: 175/65R17" value={editForm.medida} onChange={e=>setEditForm(f=>({...f,medida:e.target.value}))}/>
            </div>
            <div className="field">
              <label>Segmento</label>
              <select value={editForm.segmento} onChange={e=>setEditForm(f=>({...f,segmento:e.target.value}))}>
                <option value="">Selecione...</option>
                {SEGS.map(s=><option key={s}>{s}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Loja</label>
              <select value={editForm.loja} onChange={e=>setEditForm(f=>({...f,loja:e.target.value}))}>
                <option value="">Selecione...</option>
                {LOJAS.map(l=><option key={l}>{l}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Valor com Desconto *</label>
              <input type="number" step="0.01" placeholder="0,00" value={editForm.valor} onChange={e=>setEditForm(f=>({...f,valor:e.target.value}))}/>
            </div>
            <div className="field">
              <label>Forma de Pagamento</label>
              <select value={editForm.pgto} onChange={e=>setEditForm(f=>({...f,pgto:e.target.value}))}>
                <option value="">Selecione...</option>
                {PGTO.map(o=><option key={o}>{o}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Validade *</label>
              <input type="date" value={editForm.validade} onChange={e=>setEditForm(f=>({...f,validade:e.target.value}))}/>
            </div>
            <div className="field">
              <label>Observações</label>
              <input placeholder="Motivo / obs" value={editForm.obs} onChange={e=>setEditForm(f=>({...f,obs:e.target.value}))}/>
            </div>
          </div>
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
              <div style={{fontSize:12,color:MUTED,marginTop:2}}>{galeriaModal.imagens.length} imagem{galeriaModal.imagens.length!==1?"ns":""} encontrada{galeriaModal.imagens.length!==1?"s":""}</div>
            </div>
            <button onClick={()=>setGaleriaModal(null)} style={{background:"#2E2E2E",border:"none",color:"#fff",borderRadius:8,padding:"8px 20px",fontSize:13,fontWeight:700,cursor:"pointer"}}>✕ Fechar</button>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(260px,1fr))",gap:16}}>
            {galeriaModal.imagens.map((q,i)=>(
              <div key={q.numero+i} style={{background:"#1C1C1C",borderRadius:10,overflow:"hidden",border:"1px solid #2E2E2E"}}>
                <img
                  src={q.anexoBase64}
                  alt={q.anexoNome}
                  onClick={()=>setImgModal({src:q.anexoBase64,nome:q.anexoNome})}
                  style={{width:"100%",height:200,objectFit:"cover",display:"block",cursor:"zoom-in"}}
                  title="Clique para ampliar"
                />
                <div style={{padding:"10px 12px"}}>
                  <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:16,color:RED,letterSpacing:1,marginBottom:4}}>#{q.numero}</div>
                  <div style={{fontSize:11,color:MUTED}}>{q.loja}</div>
                  <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginTop:6}}>
                    <span style={{background:GREEN+"22",color:GREEN,borderRadius:4,padding:"2px 8px",fontSize:12,fontWeight:700}}>{fmtVal(q.valor)}</span>
                    <span style={{fontSize:10,color:MUTED}}>{q.criadoEm?new Date(q.criadoEm).toLocaleDateString("pt-BR"):"—"}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )}
    {toast&&<div className={`toast ${toast.ok?"t-ok":"t-err"}`}>{toast.msg}</div>}
  </div></>);
}
