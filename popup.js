const API = "http://localhost:5000";

const $ = (sel) => document.querySelector(sel);
const list = $("#list");
const summaryBox = $("#summaryBox");
const sentPills = $("#sentPills");
const replyBox = $("#replyBox");

// Progress elements
const progWrap = $("#replyProgress");
const progBar  = $("#replyBar");
const progText = $("#replyPct");
let progTimer  = null;
let progValue  = 0;

function showProgress() {
  progValue = 0;
  progWrap.style.display = "flex";
  tickProgress(8); // 시작점
  if (progTimer) clearInterval(progTimer);
  // 느리게 95%까지 자동 증가(응답 오면 100%로 마감)
  progTimer = setInterval(() => {
    if (progValue < 95) tickProgress(progValue + Math.max(1, (98 - progValue) * 0.03));
  }, 300);
}
function hideProgress(done=false) {
  if (progTimer) clearInterval(progTimer);
  if (done) tickProgress(100);
  setTimeout(() => { progWrap.style.display = "none"; tickProgress(0); }, 400);
}
function tickProgress(v) {
  progValue = Math.max(0, Math.min(100, v));
  // bar 너비 조절 (inset-right를 줄여가며 확장)
  const right = 100 - progValue;
  progBar.style.inset = `0 ${right}% 0 0`;
  progText.textContent = `Generating… ${Math.round(progValue)}%`;
}

async function api(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body || {})
  });
  if (!res.ok) throw new Error(`${path} failed`);
  return res.json();
}

async function loadEmails() {
  list.innerHTML = "<div class='item'><div class='subject'>Loading…</div></div>";
  try {
    const res = await fetch(`${API}/api/emails`);
    const items = await res.json();
    if (!Array.isArray(items) || items.length === 0) {
      list.innerHTML = "<div class='item'><div class='subject'>(empty)</div></div>";
      return;
    }
    list.innerHTML = "";
    items.forEach((it, idx) => {
      const div = document.createElement("div");
      div.className = "item";
      div.dataset.idx = idx;
      div.innerHTML = `
        <div class="subject">${escapeHtml(it.subject || "(no subject)")}</div>
        <div class="snippet">${escapeHtml(it.snippet || "")}</div>`;
      div.addEventListener("click", () => onSelect(it));
      list.appendChild(div);
    });
  } catch (e) {
    list.innerHTML = `<div class='item'><div class='subject'>Load failed</div><div class='snippet'>${e.message}</div></div>`;
  }
}

let currentText = "";

async function onSelect(item) {
  currentText = item.text || item.snippet || "";
  replyBox.textContent = "";
  sentPills.innerHTML = "";
  summaryBox.textContent = "Summarizing…";

  // Summary
  const s = await api("/summarize", { text: currentText });
  summaryBox.textContent = s.summary || "(no summary)";

  // Sentiment
  const se = await api("/sentiment", { text: currentText });
  renderSentiment(se);
}

function renderSentiment(se){
  sentPills.innerHTML = "";
  const p1 = pill(se.label || "");
  const p2 = pill(String(se.score ?? ""), true);
  const p3 = pill(se.mapped_category || "");
  sentPills.append(p1,p2,p3);
}

function pill(text, subtle){
  const el = document.createElement("span");
  el.className = "pill";
  if (subtle) el.style.opacity = 0.8;
  el.textContent = text;
  return el;
}

function escapeHtml(s){
  return (s||"").replace(/[&<>"]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
}

// Actions
$("#btnRefresh").addEventListener("click", loadEmails);
$("#btnRunAll").addEventListener("click", async () => {
  const first = list.querySelector(".item");
  if (first) first.click();
});

$("#btnReply").addEventListener("click", async () => {
  if (!currentText) return;
  replyBox.textContent = "";
  showProgress();
  try {
    const r = await api("/reply", { text: currentText });
    replyBox.textContent = r.reply || "(empty)";
    hideProgress(true);
  } catch (e) {
    replyBox.textContent = "⚠️ Reply failed: " + e.message;
    hideProgress(false);
  }
});

// Manual
$("#btnManualSumm").addEventListener("click", async () => {
  const t = $("#manual").value.trim();
  if (!t) return;
  const s = await api("/summarize", { text:t });
  summaryBox.textContent = s.summary || "(no summary)";
});
$("#btnManualSent").addEventListener("click", async () => {
  const t = $("#manual").value.trim();
  if (!t) return;
  const se = await api("/sentiment", { text:t });
  renderSentiment(se);
});
$("#btnManualReply").addEventListener("click", async () => {
  const t = $("#manual").value.trim();
  if (!t) return;
  replyBox.textContent = "";
  showProgress();
  try{
    const r = await api("/reply", { text:t });
    replyBox.textContent = r.reply || "(empty)";
    hideProgress(true);
  }catch(e){
    replyBox.textContent = "⚠️ Reply failed: " + e.message;
    hideProgress(false);
  }
});

// init
loadEmails();
