// 이메일 리스트 가져오기 및 UI 렌더링
fetch("http://localhost:5000/api/emails")
  .then(res => res.json())
  .then(data => {
    const list = document.getElementById("email-list");
    list.innerHTML = ""; // 초기 메시지 제거

    data.forEach((email, idx) => {
      const item = document.createElement("div");
      item.textContent = `${idx + 1}. ${email.subject || "(No Subject)"}`;
      item.addEventListener("click", () => {
        document.getElementById("email-details").style.display = "block";
        document.getElementById("summary-result").innerText = email.summary;
        document.getElementById("sentiment-result").innerText = email.sentiment;
      });
      list.appendChild(item);
    });
  })
  .catch(err => {
    document.getElementById("email-list").innerText = "❌ Failed to load emails.";
    console.error(err);
  });

// 수동 입력 분석
document.getElementById("analyze-manual").addEventListener("click", () => {
  const text = document.getElementById("manual-input").value.trim();
  if (!text) return alert("Please enter some email text.");

  fetch("http://localhost:5000/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text })
  })
    .then(res => res.json())
    .then(data => {
      document.getElementById("email-details").style.display = "block";
      document.getElementById("summary-result").innerText = data.summary;
      document.getElementById("sentiment-result").innerText = data.sentiment;
    })
    .catch(err => {
      alert("Error processing input.");
      console.error(err);
    });
});
