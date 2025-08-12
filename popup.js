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
    spSummary: $("loadingSummary"),
    spSummaryLlm: $("loadingSummaryLlm"),
    spSent: $("loadingSentiment"),
    spReply: $("loadingReply"),
  };

  let emails = [];
  let selected = -1;

  function esc(s = "") {
    return s.replace(/[&<>"']/g, (m) => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[m]));
  }

  async function fetchEmails() {
    disableToolbar(true);
    try {
      const res = await fetch(`${baseUrl}/api/emails`);
      const data = await res.json();
      emails = Array.isArray(data) ? data : [];
      renderList();
      if (emails[0]) selectEmail(0);
    } catch (e) {
      console.error(e);
      alert("Failed to load emails from API.");
    } finally {
      disableToolbar(false);
    }
  }

  function renderList() {
    els.list.innerHTML = "";
    if (!emails.length) {
      els.listEmpty.style.display = "block";
      return;
    }
    els.listEmpty.style.display = "none";
    emails.forEach((item, idx) => {
      const div = document.createElement("div");
      div.className = "email-item";
      div.dataset.id = String(idx);
      div.innerHTML = `
        <div class="subj">${esc(item.subject || "(no subject)")}</div>
        <div class="meta">${esc(item.snippet || "")}</div>
      `;
      div.addEventListener("click", () => selectEmail(idx));
      els.list.appendChild(div);
    });
  }

  function selectEmail(idx) {
    selected = idx;
    const item = emails[idx];
    els.original.textContent = item?.text || "(empty)";
    resetOutputs();
  }

  function resetOutputs() {
    els.summary.textContent = "";
    els.summaryLlm.textContent = "";
    els.reply.textContent = "";
    els.sentLabel.textContent = "-";
    els.sentScore.textContent = "-";
    els.sentCat.textContent = "-";
    const wrap = document.querySelector(".analysis.card.sentiment");
    wrap.classList.remove("positive","neutral","negative");
  }

  function getSelectedText() {
    if (selected >= 0 && emails[selected]?.text) return emails[selected].text;
    const t = ($("manualText").value || "").trim();
    return t || "";
  }

  async function runSummaryFast() {
    const t = getSelectedText(); if (!t) return;
    toggle(els.spSummary, true);
    try {
      const res = await fetch(`${baseUrl}/summarize`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t })
      });
      const data = await res.json();
      els.summary.textContent = data.summary || "(no summary)";
    } finally { toggle(els.spSummary, false); }
  }

  async function runSummaryLlm() {
    const t = getSelectedText(); if (!t) return;
    toggle(els.spSummaryLlm, true);
    try {
      const res = await fetch(`${baseUrl}/summarize_llm`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t })
      });
      const data = await res.json();
      els.summaryLlm.textContent = data.summary || "(no summary)";
    } finally { toggle(els.spSummaryLlm, false); }
  }

  async function runSentiment() {
    const t = getSelectedText(); if (!t) return;
    toggle(els.spSent, true);
    try {
      const res = await fetch(`${baseUrl}/sentiment`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t })
      });
      const data = await res.json();
      els.sentLabel.textContent = data.label || "-";
      els.sentScore.textContent = typeof data.score === "number" ? data.score.toFixed(2) : "-";
      els.sentCat.textContent = data.mapped_category || "-";
      const wrap = document.querySelector(".analysis.card.sentiment");
      wrap.classList.remove("positive","neutral","negative");
      if (data.mapped_category) wrap.classList.add(data.mapped_category);
    } finally { toggle(els.spSent, false); }
  }

  async function runReply() {
    const t = getSelectedText(); if (!t) return;
    toggle(els.spReply, true);
    try {
      const res = await fetch(`${baseUrl}/reply`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t })
      });
      const data = await res.json();
      els.reply.textContent = data.reply || "(no reply)";
    } finally { toggle(els.spReply, false); }
  }

  async function translateLLM(target_lang) {
    const t = getSelectedText(); if (!t) return;
    disableToolbar(true);
    try {
      const res = await fetch(`${baseUrl}/translate_llm`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text: t, target_lang })
      });
      const data = await res.json();
      const translated = (data.translated || "").trim();
      if (!translated) return;

      // 선택된 이메일을 번역문으로 대체 (없으면 수동 텍스트 교체)
      if (selected >= 0 && emails[selected]) {
        emails[selected].text = translated;
        // 스니펫도 업데이트
        emails[selected].snippet = translated.slice(0, 80).replace(/\n/g, " ");
        renderList();
        selectEmail(selected);
      } else {
        $("manualText").value = translated;
        els.original.textContent = translated;
      }
      resetOutputs();
    } catch (e) {
      alert("Translate error: " + e);
    } finally {
      disableToolbar(false);
    }
  }

  function toggle(el, on) { el.classList.toggle("hidden", !on); }
  function disableToolbar(on) {
    ["btnRefresh","btnRunAll","btnSummary","btnSummaryLlm","btnSentiment","btnReply","btnUseManual","btnToEN","btnToKO"]
      .forEach(id => { const b = $(id); if (b) b.disabled = on; });
  }

  // buttons
  $("btnRefresh").addEventListener("click", fetchEmails);
  $("btnSummary").addEventListener("click", runSummaryFast);
  $("btnSummaryLlm").addEventListener("click", runSummaryLlm);
  $("btnSentiment").addEventListener("click", runSentiment);
  $("btnReply").addEventListener("click", runReply);
  $("btnRunAll").addEventListener("click", async () => {
    await runSummaryFast(); await runSentiment(); await runReply();
  });
  $("btnUseManual").addEventListener("click", () => {
    const t = $("manualText").value || "";
    emails = [{ subject: "Manual Text", snippet: t.slice(0,80).replace(/\n/g," "), text: t }];
    renderList();
    selectEmail(0);
  });
  $("btnToEN").addEventListener("click", () => translateLLM("en"));
  $("btnToKO").addEventListener("click", () => translateLLM("ko"));

  // init
  fetchEmails();
})();