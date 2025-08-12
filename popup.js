(() => {
  const baseUrl = "http://localhost:5000";

  const $ = (id) => document.getElementById(id);
  const els = {
    list: $("emailList"),
    listEmpty: $("listEmpty"),
    original: $("original"),
    summary: $("summary"),
    summaryLlm: $("summaryLlm"),
    reply: $("reply"),
    sentLabel: $("sentLabel"),
    sentScore: $("sentScore"),
    sentCat: $("sentCat"),
    spinFast: $("spinSummaryFast"),
    spinLlm: $("spinSummaryLlm"),
    spinSent: $("spinSentiment"),
    spinReply: $("spinReply"),
    spinToEN: $("spinToEN"),
    spinToKO: $("spinToKO"),
    topbar: $("topProgress"),
    toast: $("toast"),
    subjectLine: $("subjectLine"),
    metaLine: $("metaLine"),
    search: $("searchBox"),
  };

  let emails = [];
  let filtered = [];
  let selected = -1;
  let topBarTimer = null;

  // utils
  const esc = (s="") => s.replace(/[&<>"']/g, (m) => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[m]));
  const toggle = (el, on) => el.classList.toggle("hidden", !on);
  const disableAll = (on) => [
      "btnRefresh","btnRunAll","btnUseManual",
      "btnSummaryFast","btnSummaryLlm","btnSentiment","btnReply",
      "btnToEN","btnToKO","btnCopyReply","copySummaryFast","copySummaryLlm"
    ].forEach(id => { const b = $(id); if (b) b.disabled = on; });

  function toast(msg, ms=1500){
    els.toast.textContent = msg || "";
    els.toast.classList.add("show");
    setTimeout(()=> els.toast.classList.remove("show"), ms);
  }

  // top progress
  function topProgress(on){
    clearInterval(topBarTimer);
    if(!on){ els.topbar.style.width = "0%"; return; }
    let w = 0; els.topbar.style.width = "0%";
    topBarTimer = setInterval(() => {
      w = (w + 7) % 105;
      els.topbar.style.width = `${w}%`;
    }, 110);
  }

  // load emails
  async function fetchEmails() {
    disableAll(true); topProgress(true);
    try {
      const res = await fetch(`${baseUrl}/api/emails`);
      const data = await res.json();
      emails = Array.isArray(data) ? data : [];
      filtered = emails.slice();
      renderList();
      if (filtered[0]) selectEmail(0);
      toast("Inbox refreshed");
    } catch (e) {
      console.error(e);
      alert("Failed to load emails from API.");
    } finally { disableAll(false); topProgress(false); }
  }

  function formatDate(dStr){
    try {
      const d = new Date(dStr);
      if (isNaN(d.getTime())) return "";
      return d.toLocaleDateString(undefined, { month:"short", day:"numeric" });
    } catch { return ""; }
  }

  function renderList() {
    els.list.innerHTML = "";
    if (!filtered.length) {
      els.listEmpty.style.display = "block";
      els.subjectLine.textContent = "No results";
      els.metaLine.textContent = "—";
      selected = -1;
      els.original.textContent = "";
      return;
    }
    els.listEmpty.style.display = "none";

    filtered.forEach((item, idx) => {
      const div = document.createElement("div");
      div.className = "item" + (selected===idx ? " active" : "");
      div.dataset.id = String(idx);
      const from = item.from || item.sender || "";
      const date = formatDate(item.date || item.internalDate);
      div.innerHTML = `
        <div class="subj">${esc(item.subject || "(no subject)")}</div>
        <div class="snippet">${esc(from ? from + " · " : "")}${esc(item.snippet || "")}</div>
        <div class="meta">${esc(date)}</div>
      `;
      div.addEventListener("click", () => selectEmail(idx));
      els.list.appendChild(div);
    });
  }

  function selectEmail(idx) {
    selected = idx;
    const item = filtered[idx];
    els.original.textContent = item?.text || "(empty)";
    els.subjectLine.textContent = item?.subject || "(no subject)";
    const from = item?.from || item?.sender || "unknown";
    const date = item?.date ? new Date(item.date).toLocaleString() : "";
    els.metaLine.textContent = `${from}${date ? " • " + date : ""}`;
    resetOutputs();
    // update list active state
    [...els.list.querySelectorAll(".item")].forEach((n,i) => n.classList.toggle("active", i===idx));
  }

  function resetOutputs() {
    els.summary.textContent = "";
    els.summaryLlm.textContent = "";
    els.reply.textContent = "";
    els.sentLabel.textContent = "-";
    els.sentScore.textContent = "-";
    els.sentCat.textContent = "-";
    const wrap = document.querySelector(".analysis.sentiment");
    wrap.classList.remove("positive","neutral","negative");
  }

  function getSelectedText() {
    if (selected >= 0 && filtered[selected]?.text) return filtered[selected].text;
    const t = ($("manualText").value || "").trim();
    return t || "";
  }

  // actions
  async function runSummaryFast() {
    const t = getSelectedText(); if (!t) return;
    toggle(els.spinFast, true); topProgress(true);
    try {
      const res = await fetch(`${baseUrl}/summarize`, {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t })
      });
      const data = await res.json();
      els.summary.textContent = data.summary || "(no summary)";
    } catch(e){ alert("Summary (Fast) error: " + e); }
    finally { toggle(els.spinFast, false); topProgress(false); }
  }

  async function runSummaryLlm() {
    const t = getSelectedText(); if (!t) return;
    toggle(els.spinLlm, true); topProgress(true);
    try {
      const res = await fetch(`${baseUrl}/summarize_llm`, {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t })
      });
      const data = await res.json();
      els.summaryLlm.textContent = data.summary || "(no summary)";
    } catch(e){ alert("Summary (LLM) error: " + e); }
    finally { toggle(els.spinLlm, false); topProgress(false); }
  }

  async function runSentiment() {
    const t = getSelectedText(); if (!t) return;
    toggle(els.spinSent, true); topProgress(true);
    try {
      const res = await fetch(`${baseUrl}/sentiment`, {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t })
      });
      const data = await res.json();
      els.sentLabel.textContent = data.label || "-";
      els.sentScore.textContent = typeof data.score === "number" ? data.score.toFixed(2) : "-";
      els.sentCat.textContent = data.mapped_category || "-";
      const wrap = document.querySelector(".analysis.sentiment");
      wrap.classList.remove("positive","neutral","negative");
      if (data.mapped_category) wrap.classList.add(data.mapped_category);
    } catch(e){ alert("Sentiment error: " + e); }
    finally { toggle(els.spinSent, false); topProgress(false); }
  }

  async function runReply() {
    const t = getSelectedText(); if (!t) return;
    toggle(els.spinReply, true); topProgress(true);
    try {
      const res = await fetch(`${baseUrl}/reply`, {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t })
      });
      const data = await res.json();
      els.reply.textContent = data.reply || "(no reply)";
    } catch(e){ alert("Reply error: " + e); }
    finally { toggle(els.spinReply, false); topProgress(false); }
  }

  async function translateLLM(target_lang, spinnerEl) {
    const t = getSelectedText(); if (!t) return;
    toggle(spinnerEl, true); disableAll(true); topProgress(true);
    try {
      const res = await fetch(`${baseUrl}/translate_llm`, {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t, target_lang })
      });
      const data = await res.json();
      const translated = (data.translated || "").trim();
      if (!translated) return;

      // update data in-place for selected item
      if (selected >= 0 && filtered[selected]) {
        const globalIndex = emails.indexOf(filtered[selected]);
        const patch = { text: translated, snippet: translated.slice(0,80).replace(/\n/g," ") };
        Object.assign(filtered[selected], patch);
        if (globalIndex >= 0) Object.assign(emails[globalIndex], patch);
        renderList();
        selectEmail(selected);
      } else {
        $("manualText").value = translated;
        els.original.textContent = translated;
      }
      resetOutputs();
      toast(target_lang === "en" ? "Translated to English" : "한국어로 번역 완료");
    } catch(e){ alert("Translate error: " + e); }
    finally { toggle(spinnerEl, false); disableAll(false); topProgress(false); }
  }

  async function copyText(text, label){
    if(!text.trim()) return;
    try { await navigator.clipboard.writeText(text); toast(`${label} copied`); }
    catch { /* ignore */ }
  }

  // search filter
  function applyFilter() {
    const q = (els.search.value || "").toLowerCase();
    if (!q) { filtered = emails.slice(); renderList(); return; }
    filtered = emails.filter(e => {
      const hay = `${e.subject||""}\n${e.snippet||""}\n${e.text||""}`.toLowerCase();
      return hay.includes(q);
    });
    selected = -1;
    renderList();
  }

  // buttons
  $("btnRefresh").addEventListener("click", fetchEmails);
  $("btnRunAll").addEventListener("click", async () => { await runSummaryFast(); await runSentiment(); await runReply(); });
  $("btnUseManual").addEventListener("click", () => {
    const t = $("manualText").value || "";
    emails = [{ subject: "Manual Text", snippet: t.slice(0,80).replace(/\n/g," "), text: t }];
    filtered = emails.slice();
    renderList(); selectEmail(0);
  });

  $("btnSummaryFast").addEventListener("click", runSummaryFast);
  $("btnSummaryLlm").addEventListener("click", runSummaryLlm);
  $("btnSentiment").addEventListener("click", runSentiment);
  $("btnReply").addEventListener("click", runReply);

  $("btnToEN").addEventListener("click", () => translateLLM("en", els.spinToEN));
  $("btnToKO").addEventListener("click", () => translateLLM("ko", els.spinToKO));

  $("btnCopyReply").addEventListener("click", () => copyText(els.reply.textContent || "", "Reply"));
  $("copySummaryFast").addEventListener("click", () => copyText(els.summary.textContent || "", "Fast summary"));
  $("copySummaryLlm").addEventListener("click", () => copyText(els.summaryLlm.textContent || "", "LLM summary"));

  els.search.addEventListener("input", applyFilter);

  // init
  fetchEmails();
})();