const API = "http://localhost:5000";

async function callEndpoint(path, text) {
  let resp = await fetch(API + path, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({text})
  });
  let j = await resp.json();
  return JSON.stringify(j, null, 2);
}

document.getElementById("btnSumm").onclick = async () => {
  let txt = document.getElementById("inputText").value;
  document.getElementById("output").textContent = "⏳ Summarizing…";
  let out = await callEndpoint("/summarize", txt);
  document.getElementById("output").textContent = out;
};

document.getElementById("btnSent").onclick = async () => {
  let txt = document.getElementById("inputText").value;
  document.getElementById("output").textContent = "⏳ Analyzing…";
  let out = await callEndpoint("/sentiment", txt);
  document.getElementById("output").textContent = out;
};

document.getElementById("btnReply").onclick = async () => {
  let txt = document.getElementById("inputText").value;
  document.getElementById("output").textContent = "⏳ Generating reply…";
  let out = await callEndpoint("/reply", txt);
  document.getElementById("output").textContent = out;
};
