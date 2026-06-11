/* Job Lead Tool — frontend wired to the FastAPI backend (/api/*).
   Replaces the prototype's localStorage + sample data with real API calls.
   The passcode gate, profile, leads, pipeline, add-a-job, data sources and
   dashboard all read/write through the server. */

/* ---------- tiny API client ---------- */
const TOKEN_KEY = "jlt_token";
function getToken(){ return sessionStorage.getItem(TOKEN_KEY) || ""; }
function setToken(t){ if(t) sessionStorage.setItem(TOKEN_KEY, t); }
function clearToken(){ sessionStorage.removeItem(TOKEN_KEY); }

async function api(path, opts){
  opts = opts || {};
  const headers = {};
  const tok = getToken(); if(tok) headers["Authorization"] = "Bearer " + tok;
  let body;
  if(opts.json !== undefined){ headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  else if(opts.form !== undefined){ body = opts.form; }
  const r = await fetch(path, { method: opts.method || "GET", headers, body });
  if(r.status === 401){ clearToken(); showGate(); throw new Error("Your session expired — please sign in again."); }
  let data = null; try { data = await r.json(); } catch(e){}
  if(!r.ok){ const err = new Error((data && data.detail) || ("Request failed ("+r.status+")")); err.status = r.status; err.data = data; throw err; }
  return data;
}
function esc(s){ return (s==null?"":String(s)).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

/* ---------- data-source display metadata (UI copy lives here; on/off + connection come from the server) ---------- */
const SOURCES = [
  {key:"adzuna", name:"Adzuna", tier:"Free", cost:0, desc:"Aggregated listings from many job boards.", keyless:false, help:"https://developer.adzuna.com/", helpName:"developer.adzuna.com", fields:[{id:"app_id",label:"App ID",ph:"e.g. a1b2c3d4"},{id:"app_key",label:"App Key",ph:"your Adzuna app key"}]},
  {key:"greenhouse", name:"Greenhouse boards", tier:"Free", cost:0, desc:"Direct from employers' public Greenhouse career pages.", keyless:true, fields:[]},
  {key:"lever", name:"Lever boards", tier:"Free", cost:0, desc:"Direct from employers' public Lever career pages.", keyless:true, fields:[]},
  {key:"usajobs", name:"USAJOBS", tier:"Free", cost:0, desc:"Official US government & public-sector roles.", keyless:false, help:"https://developer.usajobs.gov/", helpName:"developer.usajobs.gov", fields:[{id:"email",label:"Contact email",ph:"used as User-Agent header"},{id:"api_key",label:"API Key",ph:"your USAJOBS key"}]},
  {key:"googlejobs", name:"Google Jobs (SerpApi)", tier:"Paid", cost:75, desc:"LinkedIn, ZipRecruiter, Glassdoor & company sites via Google. Does not include Indeed.", keyless:false, help:"https://serpapi.com/manage-api-key", helpName:"serpapi.com", fields:[{id:"api_key",label:"SerpApi API Key",ph:"your SerpApi private key"}]},
  {key:"indeed", name:"Indeed (data vendor)", tier:"Paid", cost:45, desc:"Indeed-exclusive postings via a licensed data feed.", keyless:false, help:"https://brightdata.com/", helpName:"vendor portal", fields:[{id:"api_token",label:"Vendor API Token",ph:"e.g. Bright Data API token"},{id:"dataset",label:"Dataset / Collector ID",ph:"optional",optional:true}]}
];
function srcMeta(key){ return SOURCES.find(S => S.key === key); }

/* ---------- in-memory cache, hydrated from the server ---------- */
let state = { candidate:{ profile:{}, intro:"" }, leads:[], sources:{}, currentBatch:0 };

async function loadProfile(){ const d = await api("/api/profile"); state.candidate.profile = d.profile || {}; state.candidate.intro = d.intro || ""; }
async function loadSources(){
  const d = await api("/api/sources"); const m = {};
  (d.sources || []).forEach(s => { m[s.key] = { on:s.on, connected:s.connected, cred_hint:s.cred_hint, keyless:s.keyless }; });
  state.sources = m;
}
async function loadLeads(){ const d = await api("/api/leads"); state.leads = (d.leads || []).map(normLead); state.currentBatch = d.current_batch || 0; }
function normLead(l){ l.reason = (l.reasons && l.reasons.length) ? l.reasons.join(", ") : null; return l; }
async function loadAll(){ await Promise.all([loadProfile(), loadSources(), loadLeads()]); renderAll(); }

/* ---------- profile getters ---------- */
function P(id){ return (state.candidate.profile && state.candidate.profile[id]) || {narrative:"",derived:"",priority:3}; }
function derivedOf(id){ return P(id).derived || ""; }
function splitList(s){ return (s||"").split(/[;,]/).map(x=>x.trim()).filter(Boolean); }
function clampQ(n){ return Math.max(1, Math.min(50, n||20)); }
function quota(){ const el=document.getElementById("quota"); return clampQ(el ? parseInt(el.value) : 20); }
function primaryRole(){ return (derivedOf("role").split(/[·,;|]/)[0]||"—").trim(); }
function candName(){ return (derivedOf("name").split(/[·,;|]/)[0]||"—").trim(); }

/* ---------- source helpers ---------- */
function sourceKeyOf(l){ return l.source_key || "internal"; }
function sourceEnabled(l){
  const k = sourceKeyOf(l);
  if(k === "internal" || k === "manual") return true;
  const s = state.sources[k];
  return !!(s && s.on);
}
function activeNewLeads(){ return state.leads.filter(l => l.status==="new" && sourceEnabled(l)); }
function monthlyCost(){ return SOURCES.filter(S => S.cost && state.sources[S.key] && state.sources[S.key].on).reduce((a,S)=>a+S.cost,0); }

const REASONS=["Wrong location","Pay too low","Wrong seniority","Not interested in org","Wrong role","Not remote-friendly","Org too small","Already applied"];
const PIPELINE_STATUSES=["in_progress","app_complete","round1","round2","round3","archived"];
const STATUS_LABEL={new:"New",in_progress:"In Progress",app_complete:"App Complete",round1:"Round 1",round2:"Round 2",round3:"Round 3",archived:"Archived"};
const PIPELINE_COLS=[["in_progress","In Progress"],["app_complete","App Complete"],["round1","Round 1"],["round2","Round 2"],["round3","Round 3"],["archived","Archived"]];

document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  document.querySelectorAll("nav button").forEach(x => x.classList.remove("active"));
  document.querySelectorAll(".view").forEach(x => x.classList.remove("active"));
  b.classList.add("active"); document.getElementById(b.dataset.v).classList.add("active");
});

function norm(s){ return (s||"").toLowerCase().replace(/[^a-z0-9]/g,""); }
function isDuplicate(lead){
  return state.leads.some(x => x.id!==lead.id && norm(x.company)===norm(lead.company) && norm(x.title)===norm(lead.title) && x.status!=="new");
}
function engagedCompanies(){
  const active=["in_progress","app_complete","round1","round2","round3"];
  return [...new Set(state.leads.filter(l=>active.includes(l.status)).map(l=>l.company))];
}
function coverageOf(l){
  if(l.portal==="unknown") return {cls:"unknown", label:"⚠ needs your check"};
  return {cls:"auto", label:"✓ data auto-verified"};
}
function scoreText(l){ return l.addedManually ? "—" : l.score; }

/* ---------- dashboard ---------- */
function importanceWord(p){ return p>=5?"a firm requirement":p>=4?"important":p>=3?"a moderate factor":p>=2?"flexible":"very flexible"; }
function renderSummary(){
  const first=(candName().split(" ")[0]||"This candidate");
  const exp=derivedOf("experience"), role=derivedOf("role"), loc=derivedOf("location"),
        sal=derivedOf("salary"), skills=derivedOf("skills"), ind=derivedOf("industries"),
        excl=derivedOf("exclude"), motiv=derivedOf("motivation");
  const salP=P("salary").priority;
  const rparts=role.split("·"), titles=(rparts[0]||"").trim(), sen=(rparts[1]||"").trim();
  const L=state.leads;
  const approved=L.filter(x=>["in_progress","app_complete","round1","round2","round3"].includes(x.status)).length;
  const rejected=L.filter(x=>x.status==="archived" && ((x.reasons&&x.reasons.length)||x.reason));
  const reviewed=approved+rejected.length;
  const tally={}; rejected.forEach(x=>{ const rs=(x.reasons&&x.reasons.length)?x.reasons:(x.reason?[x.reason]:[]); rs.forEach(r=>tally[r]=(tally[r]||0)+1); });
  const topReasons=Object.entries(tally).sort((a,b)=>b[1]-a[1]).slice(0,3).map(x=>x[0].toLowerCase());

  if(!titles && !exp && !skills){
    document.getElementById("searchSummary").innerHTML="Fill in the <b>Candidate Profile</b> tab (or upload a resume) and this becomes a prose summary of the search — blending stated preferences with what approvals and rejections reveal.";
    return;
  }
  let t=`<b>${esc(candName())}</b> comes to this search with ${esc(exp)||"a professional background to draw on"}. `;
  t+=`${esc(first)} is looking for ${esc(titles)||"a new role"}${sen?` at the ${esc(sen)} level`:""}`;
  t+= loc?`, ideally ${esc(loc)}`:"";
  t+= sal?`, and treats ${esc(sal)} as ${importanceWord(salP)}`:"";
  t+=". ";
  if(skills) t+=`Their strengths lie in ${esc(skills)}`;
  if(skills && ind) t+=`, and they're drawn to work in ${esc(ind)}`;
  else if(ind) t+=`They're drawn to work in ${esc(ind)}`;
  if(skills||ind) t+=". ";
  if(excl) t+=`They've ruled out anything ${esc(excl)}. `;
  if(motiv) t+=`Above all, what's driving the move is ${esc(motiv.charAt(0).toLowerCase()+motiv.slice(1))}. `;
  if(reviewed===0){
    t+=`No leads have been reviewed yet, so this reflects ${esc(first)}'s own words — it will grow more specific as they start approving and passing on real openings.`;
  } else {
    const rate=Math.round(approved/reviewed*100);
    t+=`So far ${esc(first)} has reviewed ${reviewed} lead${reviewed!==1?"s":""} and kept ${approved} of them (${rate}% approval)`;
    t+= topReasons.length ? `; the roles they pass on keep sharing ${esc(topReasons.join(", "))}, so the search is quietly learning to steer around those.` : `, though the passes haven't been given reasons yet.`;
  }
  document.getElementById("searchSummary").innerHTML=t;
}
function renderDash(){
  const L=state.leads, c=s=>L.filter(x=>x.status===s).length;
  const active=c("in_progress")+c("app_complete")+c("round1")+c("round2")+c("round3");
  const interviewing=c("round1")+c("round2")+c("round3");
  const cards=[
    ["blue", activeNewLeads().length, "New leads to review"],
    ["green", active, "Active pipeline"],
    ["green", c("app_complete")+interviewing, "Applications submitted"],
    ["amber", interviewing, "In interviews"],
    ["red", c("archived"), "Archived"]
  ];
  document.getElementById("statCards").innerHTML=cards.map(c=>
    `<div class="stat ${c[0]}"><div class="n">${c[1]}</div><div class="l">${c[2]}</div></div>`).join("");
  renderSummary();

  const eng=engagedCompanies();
  const recos=L.filter(l=>l.status==="new" && eng.includes(l.company));
  const rEl=document.getElementById("recos");
  if(recos.length===0){
    rEl.innerHTML=`No additional openings detected yet. Once you apply to (or add) a job, other openings at that same organization surface here — e.g. a remote role you didn't apply for.`;
  }else{
    rEl.innerHTML=recos.map(l=>
      `<div class="rec"><div><div class="t"><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.company)} — ${esc(l.title)} ↗</a></div>
        <div class="s">${esc(l.location)} · ${esc(l.salary)} · you're already engaged with ${esc(l.company)}</div></div>
        <button class="btn" onclick="approve(${l.id});switchTo('pipeline')">Add to pipeline</button></div>`).join("");
  }

  const rejected=L.filter(x=>x.status==="archived" && ((x.reasons&&x.reasons.length)||x.reason));
  const approved=L.filter(x=>["in_progress","app_complete","round1","round2","round3"].includes(x.status)).length;
  const reviewed=approved+rejected.length;
  const fb=document.getElementById("feedbackSummary");
  if(reviewed===0){ fb.innerHTML="No leads reviewed yet. Approve or reject leads in <b>Leads</b> and the patterns you dislike will surface here to retrain ranking."; }
  else{
    const tally={}; rejected.forEach(x=>{ const rs=(x.reasons&&x.reasons.length)?x.reasons:(x.reason?[x.reason]:[]); rs.forEach(r=>tally[r]=(tally[r]||0)+1); });
    const rate=Math.round(approved/reviewed*100);
    const tags=Object.entries(tally).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<span class="chip">${esc(k)} · ${v}</span>`).join(" ")||'<span class="muted">none yet</span>';
    fb.innerHTML=`Approval rate <b style="color:var(--green)">${rate}%</b> (${approved} kept / ${reviewed} reviewed).<br><br>
      Top rejection reasons — these down-weight similar future leads:<div class="meta">${tags}</div>`;
  }
}

/* ---------- competitor portal check (Phase 3) ---------- */
function renderCompetitors(){
  const el=document.getElementById("competitors");
  if(!state.competitors){
    el.innerHTML=`We can suggest organizations similar to your seed orgs and check whether each runs a
      readable hiring portal (Greenhouse/Lever) with roles matching your profile.
      <div class="save-row" style="margin-top:10px"><button class="btn" onclick="scanCompetitors()">Find similar organizations</button>
      <span class="saved" id="compMsg"></span></div>`;
    return;
  }
  const rows=state.competitors.map(r=>{
    const chip = r.portal==="yes"
      ? `<span class="chip auto">portal: yes · ${esc(r.ats)}</span>`
      : `<span class="chip unknown">portal: unknown</span>`;
    const counts = r.portal==="yes"
      ? `${r.matching} matching of ${r.openings} open role${r.openings!==1?"s":""}`
      : "no public Greenhouse/Lever board found — they may hire elsewhere";
    const pull = (r.portal==="yes" && r.matching>0)
      ? `<button class="btn" onclick="pullCompetitor('${esc(r.company).replace(/'/g,"&#39;")}')">Pull openings</button>` : "";
    return `<div class="rec"><div><div class="t">${esc(r.company)}</div>
      <div class="s">${chip} · ${counts}</div></div>${pull}</div>`;
  }).join("");
  el.innerHTML=(rows||"No new suggestions this time.")+
    `<div class="save-row" style="margin-top:10px"><button class="btn ghost" onclick="scanCompetitors()">Scan again</button>
     <span class="saved" id="compMsg"></span></div>`;
}
async function scanCompetitors(){
  const el=document.getElementById("competitors");
  el.innerHTML="Asking the LLM for similar organizations, then checking each one's public hiring boards… (can take ~30 seconds)";
  try{
    const r=await api("/api/competitors/scan",{method:"POST"});
    if(!r.ok){
      state.competitors=null;
      el.innerHTML=`<span style="color:var(--amber)">${esc(r.detail)}</span>
        <div class="save-row" style="margin-top:10px"><button class="btn ghost" onclick="scanCompetitors()">Try again</button></div>`;
      return;
    }
    state.competitors=r.competitors;
    renderCompetitors();
  }catch(e){
    el.innerHTML='<span style="color:var(--red)">Scan failed: '+esc(e.message)+'</span>'+
      '<div class="save-row" style="margin-top:10px"><button class="btn ghost" onclick="scanCompetitors()">Try again</button></div>';
  }
}
async function pullCompetitor(co){
  const m=document.getElementById("compMsg");
  flash(m,"Pulling openings…","var(--muted)");
  try{
    const r=await api("/api/expand",{method:"POST",json:{company:co}});
    await loadLeads(); renderQueue(); renderDash();
    flash(m, r.added?`Added ${r.added} lead${r.added!==1?"s":""} from ${co} ✓ — see the Leads tab`:"No new matching openings (they may already be in your leads).", r.added?"var(--green)":"var(--amber)");
  }catch(e){ flash(m,"Could not pull: "+e.message,"var(--red)"); }
}

/* ---------- leads / batch ---------- */
async function buildBatch(){
  const info=document.getElementById("batchInfo");
  info.textContent="Searching your enabled sources…";
  try{
    const r=await api("/api/leads/refresh",{method:"POST"});
    const b=await api("/api/leads/batch",{method:"POST",json:{n:quota()}});
    await loadLeads();
    renderQueue(); renderDash(); renderSources();
    let msg;
    if(!b.leads.length){
      msg="No unreviewed leads available — connect/enable more sources, or add seed organizations in your profile.";
    }else{
      const repeats=b.leads.length-b.fresh;
      msg=`Batch #${b.batch}: ${b.leads.length} leads by match score`;
      msg+= repeats===0 ? ` — all new to you.` : ` — ${b.fresh} new to you, ${repeats} shown before (fresh ones are running low).`;
      if(r.added) msg+=` (${r.added} just found.)`;
    }
    if(r.errors && r.errors.length) msg+=" Some sources reported an error.";
    info.textContent=msg;
  }catch(e){ info.textContent="Couldn't build a batch: "+e.message; }
}
function renderQueue(){
  const qEl=document.getElementById("quota"); if(qEl) qEl.value=quota();
  // After the first batch is built, the queue shows the CURRENT batch only —
  // rebuilding brings the next set instead of repeating what you ignored.
  const pool = state.currentBatch>0
    ? activeNewLeads().filter(l=>l.batchId===state.currentBatch).sort((a,b)=>b.score-a.score)
    : activeNewLeads().sort((a,b)=>b.score-a.score).slice(0,quota());
  const el=document.getElementById("queue");
  if(pool.length===0){
    el.innerHTML = (state.currentBatch>0 && activeNewLeads().length>0)
      ? '<div class="empty">You\'ve worked through this batch ✓<br>Press <b>Build batch</b> for your next set of unreviewed leads.</div>'
      : '<div class="empty">No new leads from your enabled sources yet.<br>Press <b>Build batch</b> to search, enable more in <b>Data Sources</b>, or check the Pipeline tab.</div>';
    return;
  }
  el.innerHTML=pool.map(leadCard).join("");
}
function leadCard(l){
  const dup=isDuplicate(l);
  const cov=coverageOf(l);
  const preview = l.description ? esc(l.description).slice(0,260) : "Open the full ad to read the role's responsibilities and requirements before deciding.";
  return `<div class="lead" id="lead-${l.id}">
    <div class="top">
      <div>
        <h3><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)} ↗</a></h3>
        <div class="co">${esc(l.company)} · ${esc(l.location)}</div>
      </div>
      <div class="score-badge" title="Match score 0–100">${scoreText(l)}</div>
    </div>
    <div class="meta">
      <span class="chip score">match ${scoreText(l)}</span>
      <span class="chip">${esc(l.salary)||"salary n/a"}</span>
      <span class="chip">source: ${esc(l.source)}</span>
      <span class="chip ${cov.cls}">${cov.label}</span>
      ${dup?'<span class="chip dup">possible duplicate</span>':''}
    </div>
    <div class="preview"><b>Quick preview</b> — open the full ad before approving: ${preview}</div>
    <div class="actions">
      <a class="viewad" href="${esc(l.url)}" target="_blank" rel="noopener">View full job ad ↗</a>
      <button class="approve" onclick="approve(${l.id})">✓ Approve → pipeline</button>
      <button class="reject" onclick="toggleReasons(${l.id})">✕ Reject</button>
    </div>
    <div class="reasons" id="reasons-${l.id}">
      <div class="rhint">Pick all that apply (or add your own), then confirm:</div>
      <div class="rwrap">${REASONS.map(r=>`<span class="reason" onclick="this.classList.toggle('sel')">${r}</span>`).join("")}</div>
      <input class="rcustom" id="rcustom-${l.id}" placeholder="Add a custom reason (optional)">
      <button class="btn rconfirm" onclick="confirmReject(${l.id})">Confirm reject</button>
    </div>
  </div>`;
}
function toggleReasons(id){ document.getElementById("reasons-"+id).classList.toggle("show"); }
function byId(id){ return state.leads.find(x=>x.id===id); }

async function setStatus(id, status, reasons){
  await api("/api/leads/"+id+"/status",{method:"POST",json:{status, reasons: reasons||[]}});
  await loadLeads();
}
async function approve(id){
  try{ await setStatus(id,"in_progress"); renderQueue(); renderDash(); renderBoard(); }
  catch(e){ alert("Could not approve: "+e.message); }
}
async function confirmReject(id){
  const wrap=document.getElementById("reasons-"+id);
  const sel=Array.prototype.slice.call(wrap.querySelectorAll(".reason.sel")).map(x=>x.textContent.trim());
  const customEl=document.getElementById("rcustom-"+id); const custom=customEl?customEl.value.trim():"";
  if(custom) sel.push(custom);
  try{ await setStatus(id,"archived",sel); renderQueue(); renderDash(); renderBoard(); }
  catch(e){ alert("Could not reject: "+e.message); }
}
async function moveLead(id,s){
  try{ await setStatus(id,s); renderBoard(); renderDash(); renderQueue(); }
  catch(e){ alert("Could not move: "+e.message); }
}

/* ---------- pipeline ---------- */
function renderBoard(){
  const board=document.getElementById("board");
  board.innerHTML=PIPELINE_COLS.map(([key,label])=>{
    const items=state.leads.filter(l=>l.status===key);
    const cards=items.map(pipeCard).join("")||'<div class="muted" style="padding:8px;font-size:12px">—</div>';
    const cls=key==="archived"?"col archived":"col";
    return `<div class="${cls}"><h4>${label}<span class="cnt">${items.length}</span></h4>${cards}</div>`;
  }).join("");
}
function pipeCard(l){
  const opts=PIPELINE_STATUSES.map(s=>`<option value="${s}" ${l.status===s?"selected":""}>${STATUS_LABEL[s]}</option>`).join("");
  return `<div class="card">
    <h5>${esc(l.title)}</h5>
    <div class="co">${esc(l.company)} · ${esc(l.location)}</div>
    <div class="co">${l.addedManually?"":"match "+l.score+" · "}${esc(l.salary)}</div>
    <select onchange="moveLead(${l.id},this.value)">${opts}</select>
    <div class="src">${l.addedManually?"added manually":"via "+esc(l.source)}${l.reason?" · "+esc(l.reason):""}</div>
    <div style="margin-top:5px"><a href="${esc(l.url)}" target="_blank" rel="noopener">View full job ad ↗</a></div>
  </div>`;
}

/* ---------- data sources tab ---------- */
function isConnected(key){ const S=srcMeta(key); if(S.keyless) return true; const c=state.sources[key]; return !!(c && c.connected); }
function maskKey(hint){ return hint ? "••••"+hint : "••••"; }
function openConnect(key){ const el=document.getElementById("conn_"+key); if(el) el.style.display=(el.style.display==="none"?"block":"none"); }
function renderSources(){
  document.getElementById("sourceList").innerHTML=SOURCES.map(S=>{
    const st=state.sources[S.key]||{on:S.keyless,connected:S.keyless,cred_hint:""};
    const on=st.on;
    const cost=S.cost?("$"+S.cost+"/mo"):"Free";
    const n=state.leads.filter(l=>l.status==="new" && sourceKeyOf(l)===S.key).length;
    let conn;
    if(S.keyless){ conn=`<span style="color:var(--green);font-size:11.5px">● No key needed (public board)</span>`; }
    else if(isConnected(S.key)){ conn=`<span style="color:var(--green);font-size:11.5px">● Connected · key ${maskKey(st.cred_hint)}</span> <a href="#" onclick="openConnect('${S.key}');return false" style="font-size:11.5px">edit</a>`; }
    else { conn=`<span style="color:var(--amber);font-size:11.5px">● Not connected</span> <a href="#" onclick="openConnect('${S.key}');return false" style="font-size:11.5px">connect</a>`; }
    const form=S.keyless?"":`<div class="connform" id="conn_${S.key}" style="display:none">
      ${S.fields.map(f=>`<label>${f.label}${f.optional?' <span class="muted">(optional)</span>':''}</label><input id="cred_${S.key}_${f.id}" placeholder="${f.ph}" value="">`).join("")}
      <div class="save-row" style="margin-top:10px"><button class="btn" onclick="saveSourceKey('${S.key}')">Save key</button>
      ${S.help?`<a href="${S.help}" target="_blank" rel="noopener" style="font-size:12px;margin-left:8px">Where do I get this? (${S.helpName}) ↗</a>`:""}
      <span class="saved" id="connmsg_${S.key}"></span></div></div>`;
    return `<div class="srow">
      <label class="switch"><input type="checkbox" ${on?"checked":""} onchange="toggleSource('${S.key}')"><span class="slider"></span></label>
      <div class="info"><div class="nm">${S.name}<span class="tier ${S.tier==='Free'?'free':'paid'}">${S.tier}</span></div>
        <div class="ds">${S.desc}${n?` · ${n} new lead${n>1?'s':''}`:''}</div>
        <div style="margin-top:5px">${conn}</div>${form}</div>
      <div class="cost">${cost}</div>
    </div>`;
  }).join("");
  const total=monthlyCost();
  document.getElementById("sourceSummary").innerHTML=`<span>Estimated subscription cost</span><b style="color:${total?'var(--amber)':'var(--green)'};font-size:15px">${total?'$'+total+'/mo':'$0 — free sources only'}</b>`;
}
async function saveSourceKey(key){
  const S=srcMeta(key); const creds={}; let ok=true;
  S.fields.forEach(f=>{ const el=document.getElementById("cred_"+key+"_"+f.id); const v=el?el.value.trim():""; if(!v && !f.optional) ok=false; creds[f.id]=v; });
  const msg=document.getElementById("connmsg_"+key);
  if(!ok){ flash(msg,"Enter the required field(s).","var(--red)"); return; }
  try{
    await api("/api/sources/"+key+"/connect",{method:"POST",json:creds});
    await loadSources(); renderSources(); renderDash();
    flash(document.getElementById("connmsg_"+key),"Connected & enabled ✓","var(--green)");
  }catch(e){ flash(msg,"Could not connect: "+e.message,"var(--red)"); }
}
async function toggleSource(key){
  const st=state.sources[key]||{};
  const connected = srcMeta(key).keyless || st.connected;
  if(!st.on && !connected){ renderSources(); openConnect(key); flash(document.getElementById("connmsg_"+key),"Connect this source first — add the key, then it enables.","var(--amber)"); return; }
  try{
    const r=await api("/api/sources/"+key+"/toggle",{method:"POST"});
    if(state.sources[key]) state.sources[key].on=r.on;
    renderSources(); renderDash(); renderQueue();
  }catch(e){
    const m=document.getElementById("connmsg_"+key); if(m) flash(m, e.message, "var(--amber)");
    renderSources();
  }
}

/* ---------- add a job ---------- */
async function readJob(){
  const url=val("j_url"); const s=document.getElementById("readStatus");
  if(!url){ s.innerHTML='<span style="color:var(--red)">Paste a job link first.</span>'; return; }
  resetAddPanels(); s.innerHTML="Reading…";
  let host=""; try{ host=new URL(url).hostname.replace(/^www\./,""); }catch(e){ host=url; }
  try{
    const r=await api("/api/jobs/read",{method:"POST",json:{url}});
    if(r.ok && r.details){
      const d=r.details;
      fill("f_company",d.company); fill("f_title",d.title); fill("f_location",d.location); fill("f_salary",d.salary||"");
      s.innerHTML=`<span style="color:var(--green)">✓ Read this posting from <b>${esc(host)}</b>. Confirm the details below.</span>`;
      show("detailsPanel");
    } else {
      s.innerHTML=`<span style="color:var(--amber)">⚠ We can't read <b>${esc(host)}</b> automatically (sites like Indeed/LinkedIn block it). Paste the description below instead.</span>`;
      show("pastePanel");
    }
  }catch(e){ s.innerHTML='<span style="color:var(--amber)">Could not read it automatically — paste the description below.</span>'; show("pastePanel"); }
}
async function extractFromDesc(){
  const t=val("j_desc"); if(!t) return;
  const status=document.getElementById("readStatus");
  try{
    const r=await api("/api/jobs/extract",{method:"POST",json:{text:t}});
    const d=r.details||{};
    fill("f_title",d.title); fill("f_company",d.company); fill("f_location",d.location); fill("f_salary",d.salary||"");
    status.innerHTML=`<span style="color:var(--green)">✓ Pulled details from the pasted description. Edit anything that's off, then add.</span>`;
    show("detailsPanel");
  }catch(e){ status.innerHTML='<span style="color:var(--red)">Extract failed: '+esc(e.message)+'</span>'; }
}
async function addJobFull(){
  const co=val("f_company"), title=val("f_title");
  const msg=document.getElementById("addMsg");
  if(!co||!title){ flash(msg,"Organization and job title are required.","var(--red)"); return; }
  try{
    await api("/api/leads/add",{method:"POST",json:{
      company:co, title, location:val("f_location"), salary:val("f_salary"),
      url:val("j_url")||"#", status:val("f_status")||"in_progress"
    }});
    await loadLeads(); renderBoard(); renderDash();
    flash(msg,"Added ✓","var(--green)");
    showExpand(co);
  }catch(e){ flash(msg,"Could not add: "+e.message,"var(--red)"); }
}
function showExpand(co){
  document.getElementById("expandBody").innerHTML=
    `<b>${esc(co)}</b> is now in your pipeline. We can scan <b>${esc(co)}</b>'s public Greenhouse/Lever career board for other matching openings and add them to your Leads:
     <div class="save-row" style="margin-top:10px"><button class="btn" onclick="scanCompany('${esc(co).replace(/'/g,"&#39;")}')">Scan for openings</button>
     <span class="saved" id="scanMsg"></span></div>`;
  show("expandPanel");
}
async function scanCompany(co){
  const m=document.getElementById("scanMsg");
  flash(m,"Scanning…","var(--muted)");
  try{
    const r=await api("/api/expand",{method:"POST",json:{company:co}});
    await loadLeads(); renderQueue(); renderDash(); renderSources();
    flash(m, r.added?`Added ${r.added} new leads to your Leads batch ✓`:"No new matching openings found on public boards.", r.added?"var(--green)":"var(--amber)");
  }catch(e){ flash(m,"Scan failed: "+e.message,"var(--red)"); }
}
function resetAddPanels(){ ["pastePanel","detailsPanel","expandPanel"].forEach(i=>document.getElementById(i).style.display="none"); }

/* ---------- profile tab ---------- */
function prioLabel(v){ return {1:"1 · Flexible",2:"2 · Minor",3:"3 · Moderate",4:"4 · Important",5:"5 · Critical"}[v]||("· "+v); }
function setPrio(id,v){ document.getElementById("pval_"+id).textContent=prioLabel(v); }
function captureProfileInputs(){
  PROFILE_Q.forEach(function(Q){
    const n=document.getElementById("narr_"+Q.id), d=document.getElementById("der_"+Q.id), p=document.getElementById("pri_"+Q.id);
    if(!n && !d && !p) return;
    const cur=P(Q.id);
    state.candidate.profile[Q.id]={ narrative:n?n.value:cur.narrative, derived:d?d.value:cur.derived, priority:p?parseInt(p.value):(cur.priority||3) };
  });
}
function fillEmptyFromDraft(draft){
  PROFILE_Q.forEach(function(Q){
    if(Q.id==="resume"||Q.id==="name") return;
    const cur=P(Q.id), dr=(draft&&draft[Q.id])||{};
    if((!cur.narrative||!cur.narrative.trim()) && dr.narrative) cur.narrative=dr.narrative;
    if((!cur.derived||!cur.derived.trim()) && dr.derived) cur.derived=dr.derived;
    state.candidate.profile[Q.id]=cur;
  });
}
async function persistProfile(){
  await api("/api/profile",{method:"PUT",json:{profile:state.candidate.profile, intro:state.candidate.intro||""}});
}
async function handleResume(){
  captureProfileInputs();
  const f=document.getElementById("resumeFile");
  const file=f&&f.files&&f.files[0];
  const name=file?file.name:"resume";
  const r=P("resume"); r.narrative="Uploaded: "+name; state.candidate.profile.resume=r;
  const rs=document.getElementById("resumeStatus");
  if(!file) return;
  rs.innerHTML="Reading "+esc(name)+"…";
  try{
    const fd=new FormData(); fd.append("resume",file);
    const d=await api("/api/profile/parse",{method:"POST",form:fd});
    const got=Object.keys(d.draft||{}).length;
    fillEmptyFromDraft(d.draft||{});
    await persistProfile();
    renderProfile(); renderDash(); renderQueue();
    rs.innerHTML= got
      ? `<span style="color:var(--green)">✓ Read ${esc(name)} — drafted suggestions for blank questions (your own answers are kept).</span>`
      : `<span style="color:var(--amber)">Read ${esc(name)}. Auto-drafting needs an ANTHROPIC_API_KEY in your .env — add it to have the resume fill answers, or fill them in yourself below.</span>`;
  }catch(e){ rs.innerHTML='<span style="color:var(--red)">Could not read the resume: '+esc(e.message)+'</span>'; }
}
async function applyIntroNarrative(){
  captureProfileInputs();
  const el=document.getElementById("introNarrative"); const txt=el?el.value.trim():"";
  state.candidate.intro=txt;
  const m=document.getElementById("introMsg");
  try{
    if(txt){
      const d=await api("/api/profile/parse",{method:"POST",form:formOf({narrative:txt})});
      const got=Object.keys(d.draft||{}).length;
      fillEmptyFromDraft(d.draft||{});
      await persistProfile(); renderProfile(); renderDash(); renderQueue();
      flash(m, got?"Suggestions added to blank fields — your entries kept ✓":"Saved. (Add ANTHROPIC_API_KEY in .env for auto-drafting.)","var(--green)");
    } else {
      await persistProfile(); flash(m,"Saved ✓","var(--green)");
    }
  }catch(e){ flash(m,"Could not draft: "+e.message,"var(--red)"); }
}
function formOf(obj){ const fd=new FormData(); Object.keys(obj).forEach(k=>fd.append(k,obj[k])); return fd; }

const PROFILE_Q=[
  {id:"resume", q:"Upload the candidate's resume — we'll draft answers to every question below for you to review and correct.", derive:"Resume highlights", weightable:false, type:"file"},
  {id:"name", q:"Who is the candidate? (name and email)", derive:"Name & email", weightable:false},
  {id:"role", q:"Describe the role you're targeting — the titles, the kind of work, and the level you're after.", derive:"Target titles & seniority", weightable:true},
  {id:"location", q:"Where do you want to work? Cities, remote, hybrid — and how tied are you to a place?", derive:"Locations & arrangement", weightable:true},
  {id:"salary", q:"What does pay look like for you? Give a target and tell us how firm it is.", derive:"Target salary", weightable:true},
  {id:"skills", q:"What are your core skills and strengths — the things you want this role to use?", derive:"Must-have keywords", weightable:true},
  {id:"exclude", q:"What are your dealbreakers — things you will not consider?", derive:"Exclusions", weightable:true},
  {id:"industries", q:"What industries or kinds of organizations appeal to you?", derive:"Industries", weightable:true},
  {id:"size", q:"Any preference on organization size or stage?", derive:"Org size", weightable:true},
  {id:"motivation", q:"What's driving this search, and what matters most in your next role?", derive:"Priorities & motivations", weightable:true},
  {id:"dream", q:"Are there organizations you'd love to work for? (These seed the free Greenhouse/Lever board search.)", derive:"Seed organizations", weightable:true},
  {id:"auth", q:"Any work-authorization needs or hard constraints we must respect?", derive:"Authorization / constraints", weightable:true},
  {id:"experience", q:"Briefly, what's your background and years of experience?", derive:"Experience", weightable:false},
  {id:"quota", q:"How many job leads do you want per batch?", derive:"Daily quota", weightable:false}
];
function renderProfile(){
  document.getElementById("whoLine").textContent=`Candidate: ${candName()} · ${primaryRole()}`;
  document.getElementById("profileForm").innerHTML=PROFILE_Q.map((Q,idx)=>{
    const p=P(Q.id);
    const der=(p.derived||"").replace(/"/g,"&quot;");
    const num=`<span class="qnum">${idx+1}.</span>`;
    if(Q.type==="file"){
      return `<div class="qcard">
        <div class="qhead">${num}${Q.q}</div>
        <input type="file" id="resumeFile" accept=".pdf,.doc,.docx,.txt" onchange="handleResume()">
        <div id="resumeStatus" class="muted" style="margin-top:8px;font-size:12.5px">${esc(p.narrative)||"No resume uploaded yet — upload one to auto-draft the answers below."}</div>
        <details class="derived">
          <summary>▸ What we understood — ${Q.derive} (click to view / edit)</summary>
          <div class="dlabel">What we learned from the resume (edit if needed):</div>
          <input id="der_resume" value="${der}">
        </details>
        <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--line)">
          <div style="font-weight:600;font-size:13px;margin-bottom:4px">Or describe yourself in your own words <span class="muted" style="font-weight:400">(optional)</span></div>
          <div class="muted" style="font-size:12px;margin-bottom:7px">Tell us about your experience and the roles you want. We'll suggest answers for any question you haven't filled in yet — your own entries are never overwritten.</div>
          <textarea id="introNarrative" placeholder="e.g. I've led nonprofit communications for 15 years and I'm after a VP or director role at a mission-driven org...">${esc(state.candidate.intro||"")}</textarea>
          <div class="save-row" style="margin-top:10px"><button class="btn" onclick="applyIntroNarrative()">Draft suggestions from this</button><span class="saved" id="introMsg"></span></div>
        </div>
      </div>`;
    }
    const narr=(p.narrative||"").replace(/</g,"&lt;");
    const prio=p.priority||3;
    const weightUI=Q.weightable?`
      <div class="prio">
        <span class="plabel">How important?</span>
        <input type="range" min="1" max="5" value="${prio}" id="pri_${Q.id}" oninput="setPrio('${Q.id}',this.value)">
        <span class="pval" id="pval_${Q.id}">${prioLabel(prio)}</span>
      </div>`:"";
    return `<div class="qcard">
      <div class="qhead">${num}${Q.q}</div>
      <textarea id="narr_${Q.id}" placeholder="Answer in your own words...">${narr}</textarea>
      <details class="derived">
        <summary>▸ What we understood — ${Q.derive} (click to view / edit)</summary>
        <div class="dlabel">Structured criteria we'll search on (edit if we got it wrong):</div>
        <input id="der_${Q.id}" value="${der}">
      </details>
      ${weightUI}
    </div>`;
  }).join("");
}
async function saveProfile(){
  captureProfileInputs();
  try{
    await persistProfile();
    flash(document.getElementById("profileMsg"),"Saved ✓","var(--green)");
    renderProfile(); renderDash(); renderQueue();
  }catch(e){ flash(document.getElementById("profileMsg"),"Could not save: "+e.message,"var(--red)"); }
}
async function resetData(){
  if(!confirm("Reset everything for a new candidate? This wipes the profile, resume, leads, pipeline and connected keys, and cannot be undone.")) return;
  try{ await api("/api/reset",{method:"POST"}); clearToken(); location.reload(); }
  catch(e){ alert("Could not reset: "+e.message); }
}

/* ---------- misc DOM helpers ---------- */
function fill(id,v){ const e=document.getElementById(id); if(e) e.value=v||""; }
function show(id){ document.getElementById(id).style.display="block"; }
function val(id){ const e=document.getElementById(id); return e?e.value.trim():""; }
function flash(el,t,color){ if(!el) return; el.textContent=t; el.style.color=color; el.classList.add("show"); setTimeout(()=>el.classList.remove("show"),2800); }
function switchTo(view){
  document.querySelectorAll("nav button").forEach(x=>x.classList.toggle("active",x.dataset.v===view));
  document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id===view));
}
function renderAll(){ renderProfile(); renderSources(); renderDash(); renderQueue(); renderBoard(); renderCompetitors(); }

/* ---------- passcode gate (server-enforced) ---------- */
let gateMode="enter";
function showGate(){
  const g=document.getElementById("gate"); g.style.display="flex";
  document.getElementById("gateInput").value="";
  document.getElementById("gateErr").textContent="";
  setTimeout(()=>document.getElementById("gateInput").focus(),50);
}
function hideGate(){ document.getElementById("gate").style.display="none"; }
async function bootGate(){
  let status;
  try{ status=await api("/api/auth/status"); }catch(e){ status={passcode_set:false}; }
  if(!status.passcode_set){
    gateMode="set";
    document.getElementById("gateTitle").textContent="Set a passcode";
    document.getElementById("gateHint").textContent="Protect this candidate's data with a passcode (4+ characters). You'll enter it on each visit.";
  } else {
    gateMode="enter";
    document.getElementById("gateTitle").textContent="Enter passcode";
    document.getElementById("gateHint").textContent="This dashboard is passcode-protected.";
  }
  showGate();
}
async function submitGate(){
  const v=document.getElementById("gateInput").value.trim();
  const err=document.getElementById("gateErr");
  err.textContent="";
  try{
    if(gateMode==="set"){
      if(v.length<4){ err.textContent="Use at least 4 characters."; return; }
      const r=await api("/api/auth/set",{method:"POST",json:{passcode:v}});
      setToken(r.token); hideGate(); await loadAll();
    } else {
      const r=await api("/api/auth/login",{method:"POST",json:{passcode:v}});
      if(r.ok){ setToken(r.token); hideGate(); await loadAll(); }
      else { err.textContent="Incorrect passcode."; }
    }
  }catch(e){ err.textContent=e.message || "Something went wrong."; }
}

/* ---------- boot ---------- */
async function boot(){
  if(getToken()){
    try{ await loadAll(); hideGate(); return; }
    catch(e){ /* token invalid/expired -> fall through to gate */ }
  }
  await bootGate();
}
boot();
