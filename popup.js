const BASE = "http://localhost:5000";

const els = {
  emailList: document.getElementById("emailList"),
  listEmpty: document.getElementById("listEmpty"),
  original: document.getElementById("original"),
  summary: document.getElementById("summary"),
  reply: document.getElementById("reply"),
  sentLabel: document.getElementById("sentLabel"),
  sentScore: document.getElementById("sentScore"),
  sentCat: document.getElementById("sentCat"),
  loadingSummary: document.getElementById("loadingSummary"),
  loadingSentiment: document.getElementById("loadingSentiment"),
  loadingReply: document.getElementById("loadingReply"),
  btnRefresh: document.getElementById("btnRefresh"),
  btnRunAll: document.getElementById("btnRunAll"),
  btnSummary: document.getElementById("btnSummary"),
  btnSentiment: document.getElementById("btnSentiment"),
  btnReply: document.getElementById("btnReply"),
  manualText: document.getElementById("manualText"),
  btnUseManual: document.getElementById("btnUseManual"),
};

let state = {
  emails: [],         // array of strings (bodies) or objects
  selectedIndex: -1,  // index in emails
};

function trim(str){ return (str || "").replace(/\s+/g," ").trim(); }

// Simple client-side footer/signature trimming (best effort)
function removeSignatureLocal(text){
  if(!text) return "";
  const killers = [
    "CONFIDENTIALITY", "Sekyee Business ICT Solutions", "173 Junction Road",
    "Facebook icon", "LinkedIn icon", "Twitter icon", "Logo",
    "*From:*","*Sent:*","*To:*","*Subject:*","www.sekyee.co.uk",
    "이 전자우편","기밀한 정보","KB국민은행","https://www.kbstar.com"
  ];
  const lines = (text + "").split(/\r?\n/);
  const out = [];
  for(const line of lines){
    const s = line.trim().toLowerCase();
    if(killers.some(k => s.includes(k.toLowerCase()))){ break; }
    out.push(line);
  }
  return trim(out.join("\n"));
}

function previewFromBody(body){
  const first = trim(body).split(/\n/).find(Boolean) || "(no subject)";
  return first.length > 60 ? first.slice(0,57) + "…" : first;
}

function renderList(){
  els.emailList.innerHTML = "";
  if(!state.emails.length){
    els.listEmpty.style.display = "block";
    return;
  }
  els.listEmpty.style.display = "none";
  state.emails.forEach((item, i) => {
    const body = typeof item === "string" ? item : (item.body || "");
    const sender = typeof item === "object" ? (item.from || "") : "";
    const time = typeof item === "object" ? (item.date || "") : "";

    const div = document.createElement("div");
    div.className = "email-item";
    div.innerHTML = `
      <div class="subj">${escapeHtml(previewFromBody(body))}</div>
      <div class="meta">${escapeHtml(sender)} ${time ? " · " + escapeHtml(time) : ""}</div>
    `;
    div.addEventListener("click", () => selectEmail(i));
    els.emailList.appendChild(div);
  });
}

function selectEmail(index){
  state.selectedIndex = index;
  const item = state.emails[index];
  const body = typeof item === "string" ? item : (item.body || "");
  const cleaned = removeSignatureLocal(body);

  els.original.textContent = cleaned || "(empty)";
  clearOutputs();
}

function clearOutputs(){
  els.summary.textContent = "";
  els.reply.textContent = "";
  els.sentLabel.textContent = "-";
  els.sentScore.textContent = "-";
  els.sentCat.textContent = "-";
  setSentimentClass(null);
}

function setLoading(which, on){
  const map = {
    summary: els.loadingSummary,
    sentiment: els.loadingSentiment,
    reply: els.loadingReply,
  };
  const el = map[which];
  if(!el) return;
  el.classList.toggle("hidden", !on);
}

function setSentimentClass(cat){
  const block = document.querySelector(".analysis.card.sentiment");
  block.classList.remove("positive","neutral","negative");
  if(cat) block.classList.add(cat);
}

async function fetchJSON(url, options){
  const res = await fetch(url, options);
  if(!res.ok){
    const t = await res.text();
    throw new Error(`HTTP ${res.status}: ${t}`);
  }
  return res.json();
}

async function loadEmails(){
  try{
    const data = await fetchJSON(`${BASE}/api/emails`);
    // Expecting array; keep flexible
    state.emails = Array.isArray(data) ? data : (data.emails || []);
  }catch(e){
    // Fallback to single dummy endpoint if /api/emails not available
    try{
      const one = await fetchJSON(`${BASE}/fetch_latest_email`);
      state.emails = [one.email_body || ""];
    }catch(err){
      console.error(err);
      state.emails = [];
    }
  }
  renderList();
  if(state.emails.length) selectEmail(0);
}

async function runSummary(text){
  setLoading("summary", true);
  try{
    const data = await fetchJSON(`${BASE}/summarize`, {
      method: "POST",
      headers: { "Content-Type":"application/json" },
      body: JSON.stringify({ text })
    });
    els.summary.textContent = data.summary || "(no summary)";
  }catch(e){
    els.summary.textContent = `Error: ${e.message}`;
  }finally{
    setLoading("summary", false);
  }
}

async function runSentiment(text){
  setLoading("sentiment", true);
  try{
    const data = await fetchJSON(`${BASE}/sentiment`, {
      method: "POST",
      headers: { "Content-Type":"application/json" },
      body: JSON.stringify({ text })
    });
    els.sentLabel.textContent = data.label ?? "-";
    els.sentScore.textContent = (typeof data.score === "number") ? data.score.toFixed(2) : "-";
    const cat = data.mapped_category || guessCategory(data.label);
    els.sentCat.textContent = cat || "-";
    setSentimentClass(cat);
  }catch(e){
    els.sentLabel.textContent = "error";
    els.sentScore.textContent = "-";
    els.sentCat.textContent = "-";
    setSentimentClass(null);
  }finally{
    setLoading("sentiment", false);
  }
}

async function runReply(text){
  setLoading("reply", true);
  try{
    const data = await fetchJSON(`${BASE}/reply`, {
      method: "POST",
      headers: { "Content-Type":"application/json" },
      body: JSON.stringify({ text })
    });
    els.reply.textContent = (data.reply || "").trim() || "(empty)";
  }catch(e){
    els.reply.textContent = `Error: ${e.message}`;
  }finally{
    setLoading("reply", false);
  }
}

function currentText(){
  if(state.selectedIndex < 0) return "";
  const item = state.emails[state.selectedIndex];
  const body = typeof item === "string" ? item : (item.body || "");
  return removeSignatureLocal(body);
}

function guessCategory(label=""){
  const l = label.toLowerCase();
  if(l.includes("1") || l.includes("2") || l.includes("neg")) return "negative";
  if(l.includes("3") || l.includes("neu")) return "neutral";
  if(l.includes("4") || l.includes("5") || l.includes("pos")) return "positive";
  return null;
}

function escapeHtml(s){
  return (s || "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

/* Events */
els.btnRefresh.addEventListener("click", () => loadEmails());
els.btnRunAll.addEventListener("click", async () => {
  const text = currentText();
  if(!text) return;
  await Promise.all([ runSummary(text), runSentiment(text), runReply(text) ]);
});

els.btnSummary.addEventListener("click", () => {
  const text = currentText(); if(text) runSummary(text);
});
els.btnSentiment.addEventListener("click", () => {
  const text = currentText(); if(text) runSentiment(text);
});
els.btnReply.addEventListener("click", () => {
  const text = currentText(); if(text) runReply(text);
});

els.btnUseManual.addEventListener("click", () => {
  const t = trim(els.manualText.value);
  if(!t) return;
  state.emails.unshift(t);
  renderList();
  selectEmail(0);
  els.manualText.value = "";
});

/* Init */
loadEmails();
