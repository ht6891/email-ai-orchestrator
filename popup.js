// popup.js
const API = "http://localhost:5000";

let emails = [];
let selected = null;       // {id, subject, snippet, text}
let currentLang = localStorage.getItem("lang") || "auto";

const $ = (s)=>document.querySelector(s);
const listEl = $("#list");
const emailBox = $("#emailBox");
const summaryBox = $("#summaryBox");
const sentPills = $("#sentPills");
const replyBox = $("#replyBox");
const manual = $("#manual");
const langSel = $("#langSel");

const replyWrap = $("#replyProgress");
const replyBar = $("#replyBar");
const replyPct = $("#replyPct");

// init
langSel.value = currentLang;
langSel.addEventListener("change", ()=>{
  currentLang = langSel.value;
  localStorage.setItem("lang", currentLang);
});

// Load emails
async function loadEmails(){
  listEl.innerHTML = `<div class="item"><div class="subject">Loading…</div></div>`;
  try{
    const r = await fetch(`${API}/api/emails`);
    const data = await r.json();
    emails = data;
    renderList();
  }catch(e){
    listEl.innerHTML = `<div class="item"><div class="subject">Failed to load: ${e}</div></div>`;
  }
}

function renderList(){
  listEl.innerHTML = "";
  emails.forEach((m, idx)=>{
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML = `
      <div class="subject">${escapeHtml(m.subject || "(no subject)")}</div>
      <div class="snippet">${escapeHtml(m.snippet || "")}</div>
    `;
    div.addEventListener("click", ()=>{
      selected = m;
      emailBox.textContent = m.text || "";
      summaryBox.textContent = "";
      replyBox.textContent = "";
      sentPills.innerHTML = "";
    });
    listEl.appendChild(div);
  });
}

// Helpers
function escapeHtml(s=""){
  return s.replace(/[&<>"']/g, m=>({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[m]));
}
async function postJSON(url, body){
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  return r.json();
}

// Actions
$("#btnRefresh").addEventListener("click", loadEmails);

$("#btnRunAll").addEventListener("click", async ()=>{
  if(!selected){ alert("Select an email first."); return; }
  await runSumm(selected.text);
  await runSent(selected.text);
  await runReply(selected.text);
});

$("#btnSumm").addEventListener("click", async ()=>{
  if(!selected){ alert("Select an email first."); return; }
  await runSumm(selected.text);
});

$("#btnReply").addEventListener("click", async ()=>{
  if(!selected){ alert("Select an email first."); return; }
  await runReply(selected.text);
});

async function runSumm(text){
  summaryBox.textContent = "Summarizing…";
  const data = await postJSON(`${API}/summarize`, { text, lang: currentLang });
  summaryBox.textContent = data.summary || "";
}

async function runSent(text){
  sentPills.innerHTML = "";
  const data = await postJSON(`${API}/sentiment`, { text });
  const pill = document.createElement("span");
  pill.className = "pill";
  pill.textContent = `${data.mapped_category} (${data.label} • ${data.score})`;
  sentPills.appendChild(pill);
}

async function runReply(text){
  replyBox.textContent = "";
  startFakeProgress();

  try{
    const data = await postJSON(`${API}/reply`, { text, lang: (currentLang==="ko"?"ko":"en") });
    stopFakeProgress();
    replyBox.textContent = data.reply || "";
  }catch(e){
    stopFakeProgress();
    replyBox.textContent = "Error: " + e;
  }
}

// Fake progress bar (client-side timer)
let progTimer = null, pct = 0;
function startFakeProgress(){
  replyWrap.style.display = "flex";
  pct = 0; updateBar();
  progTimer = setInterval(()=>{
    // 95%까지만 올렸다가 결과 들어오면 100%
    if(pct < 95){ pct += Math.random()*7; updateBar(); }
  }, 350);
}
function stopFakeProgress(){
  if(progTimer){ clearInterval(progTimer); progTimer = null; }
  pct = 100; updateBar();
  setTimeout(()=>{ replyWrap.style.display = "none"; }, 700);
}
function updateBar(){
  const clamped = Math.min(100, Math.floor(pct));
  replyBar.style.inset = `0 ${100-clamped}% 0 0`;
  replyPct.textContent = `Generating… ${clamped}%`;
}

// Translation buttons (email box)
$("#btnToEN").addEventListener("click", async ()=>{
  const src = (selected?.text || emailBox.textContent || "").trim();
  if(!src){ return; }
  const data = await postJSON(`${API}/translate`, { text: src, target_lang: "en" });
  emailBox.textContent = data.translated || "";
});
$("#btnToKO").addEventListener("click", async ()=>{
  const src = (selected?.text || emailBox.textContent || "").trim();
  if(!src){ return; }
  const data = await postJSON(`${API}/translate`, { text: src, target_lang: "ko" });
  emailBox.textContent = data.translated || "";
});

// Manual area
$("#btnManualSumm").addEventListener("click", async ()=>{
  const text = manual.value.trim();
  if(!text){return;}
  const data = await postJSON(`${API}/summarize`, { text, lang: currentLang });
  summaryBox.textContent = data.summary || "";
});
$("#btnManualSent").addEventListener("click", async ()=>{
  const text = manual.value.trim();
  if(!text){return;}
  const data = await postJSON(`${API}/sentiment`, { text });
  sentPills.innerHTML = "";
  const pill = document.createElement("span");
  pill.className = "pill";
  pill.textContent = `${data.mapped_category} (${data.label} • ${data.score})`;
  sentPills.appendChild(pill);
});
$("#btnManualReply").addEventListener("click", async ()=>{
  const text = manual.value.trim();
  if(!text){return;}
  startFakeProgress();
  try{
    const data = await postJSON(`${API}/reply`, { text, lang: (currentLang==="ko"?"ko":"en") });
    stopFakeProgress();
    replyBox.textContent = data.reply || "";
  }catch(e){
    stopFakeProgress();
    replyBox.textContent = "Error: " + e;
  }
});
$("#btnManToEN").addEventListener("click", async ()=>{
  const text = manual.value.trim();
  if(!text){return;}
  const data = await postJSON(`${API}/translate`, { text, target_lang: "en" });
  manual.value = data.translated || manual.value;
});
$("#btnManToKO").addEventListener("click", async ()=>{
  const text = manual.value.trim();
  if(!text){return;}
  const data = await postJSON(`${API}/translate`, { text, target_lang: "ko" });
  manual.value = data.translated || manual.value;
});

// start
loadEmails();
