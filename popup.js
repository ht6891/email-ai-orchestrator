// popup.js
const API = "http://localhost:5000";

const el = (id) => document.getElementById(id);
const emailList = el("emailList");
const inputText = el("inputText");
const btnSumm = el("btnSumm");
const btnSent = el("btnSent");
const btnReply = el("btnReply");
const outSummary = el("outSummary");
const outReply = el("outReply");
const sentTag = el("sentTag");
const langSel = el("langSel");
const modeSel = el("modeSel");
const toEN = el("toEN");
const toKO = el("toKO");
const prog = el("prog");
const progbar = el("progbar");

function setProgress(show) {
  prog.style.display = show ? "block" : "none";
  progbar.style.width = "0%";
  if (show) {
    let w = 0;
    const id = setInterval(() => {
      w = (w + 5) % 105;
      progbar.style.width = w + "%";
      if (prog.style.display === "none") clearInterval(id);
    }, 120);
  }
}

async function loadEmails() {
  emailList.innerHTML = "<div class='item'><p>Loading…</p></div>";
  try {
    const res = await fetch(`${API}/api/emails`);
    const items = await res.json();
    emailList.innerHTML = "";
    items.forEach((m, i) => {
      const div = document.createElement("div");
      div.className = "item";
      div.innerHTML = `<h4 title="${escapeHtml(m.subject)}">${escapeHtml(m.subject)}</h4>
                       <p>${escapeHtml(m.snippet)}</p>`;
      div.addEventListener("click", () => {
        inputText.value = m.text || "";
        outSummary.textContent = "";
        outReply.textContent = "";
        sentTag.className = "tag";
        sentTag.textContent = "sentiment: -";
      });
      emailList.appendChild(div);
    });
  } catch (e) {
    emailList.innerHTML = `<div class='item'><p style="color:#fca5a5">Failed to load emails: ${e}</p></div>`;
  }
}

function escapeHtml(s="") {
  return s.replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

// Summarize
btnSumm.addEventListener("click", async () => {
  const text = (inputText.value || "").trim();
  if (!text) return;
  const lang = langSel.value;   // auto|en|ko
  const mode = modeSel.value;   // hybrid|llm|fast
  outSummary.textContent = "Summarizing…";
  try {
    const res = await fetch(`${API}/summarize`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ text, lang, mode })
    });
    const data = await res.json();
    outSummary.textContent = (data.summary || "").trim();
  } catch (e) {
    outSummary.textContent = "Error: " + e;
  }
});

// Sentiment
btnSent.addEventListener("click", async () => {
  const text = (inputText.value || "").trim();
  if (!text) return;
  sentTag.textContent = "sentiment: …";
  try {
    const res = await fetch(`${API}/sentiment`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    const lab = (data.label || "").toLowerCase();
    sentTag.textContent = `sentiment: ${data.label} (${data.score ?? "-"})`;
    sentTag.className = "tag " + (lab.includes("5") || lab.includes("pos") ? "good" :
                                  lab.includes("1") || lab.includes("neg") ? "bad" : "neu");
  } catch (e) {
    sentTag.textContent = "sentiment: error";
    sentTag.className = "tag";
  }
});

// Reply (SSE streaming)
btnReply.addEventListener("click", async () => {
  const text = (inputText.value || "").trim();
  if (!text) return;
  const lang = langSel.value === "ko" ? "ko" : "en";
  outReply.textContent = "";
  setProgress(true);

  try {
    const res = await fetch(`${API}/reply_stream`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ text, lang })
    });

    if (!res.ok || !res.body) {
      outReply.textContent = "Error: failed to open stream";
      setProgress(false);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let got = 0, est = 600;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE 프레임 분리
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);

        // keep-alive (":") 프레임은 무시
        if (frame.startsWith(":")) continue;

        // event: done
        if (frame.startsWith("event: done")) {
          got = est;
          break;
        }

        // event: error
        if (frame.startsWith("event: error")) {
          const msg = frame.split("\n").find(l => l.startsWith("data: "))?.slice(6) || "unknown";
          outReply.textContent += `\n[error] ${msg}`;
          break;
        }

        // data: <chunk>
        const line = frame.split("\n").find(l => l.startsWith("data: "));
        if (line) {
          const chunk = line.slice(6);
          outReply.textContent += chunk;
          got += chunk.length;
          const ratio = Math.min(100, Math.floor((got / est) * 100));
          progbar.style.width = ratio + "%";
        }
      }
    }

    progbar.style.width = "100%";
    setTimeout(() => setProgress(false), 300);

  } catch (e) {
    outReply.textContent = "Error: " + e;
    setProgress(false);
  }
});

// Translate → EN
toEN.addEventListener("click", async () => {
  const text = (inputText.value || "").trim();
  if (!text) return;
  toEN.disabled = true;
  try {
    const res = await fetch(`${API}/translate`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ text, target_lang: "en" })
    });
    const data = await res.json();
    if (data.translated) inputText.value = data.translated;
  } catch (e) {
    alert("Translate error: " + e);
  } finally {
    toEN.disabled = false;
  }
});

// Translate → KO
toKO.addEventListener("click", async () => {
  const text = (inputText.value || "").trim();
  if (!text) return;
  toKO.disabled = true;
  try {
    const res = await fetch(`${API}/translate`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ text, target_lang: "ko" })
    });
    const data = await res.json();
    if (data.translated) inputText.value = data.translated;
  } catch (e) {
    alert("Translate error: " + e);
  } finally {
    toKO.disabled = false;
  }
});

// init
loadEmails();