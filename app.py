# app.py
#
# A Flask prototype that:
#  - strips quoted text / signatures (very basic)
#  - summarizes with DistilBART or dummy fallback
#  - rates sentiment via BERT star model or dummy heuristic
#  - generates a reply via Ollama Gemma3 or dummy template
#  - includes a dummy IMAP stub function as a placeholder
#
# To run:
#   $ pip install flask pandas transformers torch requests
#   $ pip install ollama              # if you have Ollama installed
#   $ python app.py
#

from flask import Flask, request, jsonify
from transformers import pipeline
import subprocess, shlex, re, email, imaplib, json
import pandas as pd
import time

# 이메일/대화 요약 특화 모델
summarizer = pipeline("summarization", model="philschmid/bart-large-cnn-samsum")
app = Flask(__name__)

#
# ----------------------------
# 1) Summarization “Model”
# ----------------------------
#
# If you install transformers + torch, uncomment the two lines below:
#    from transformers import pipeline
#    summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-6-6", device=-1)

def summarize_text(text: str) -> str:
    # 긴 이메일을 자르고 요약을 짧게 유도
    text = text.strip().replace("\n", " ")
    text = text[:1000]  # 입력 길이 제한

    try:
        result = summarizer(
            f"Summarize the following email briefly in 1-2 sentences:\n{text}",
            max_length=60,
            min_length=15,
            do_sample=False
        )
        return result[0]['summary_text']
    except Exception as e:
        return f"Summary Error: {e}"


#
# ----------------------------
# 2) Sentiment “Model”
# ----------------------------
#
# If you install transformers + torch, uncomment the two lines below:
#    from transformers import pipeline
#    sentiment_analyzer = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")

NEGATIVE_KEYWORDS = {"disappointed", "frustrated", "error", "late", "delay", "problem", "unable", "fail"}

def analyze_sentiment(text: str) -> dict:
    """
    Real mode (uncomment above pipeline):
        out = sentiment_analyzer(text)[0]
        stars = int(out['label'].split()[0])   # e.g. "4 stars"
        if stars >= 4:
            cat = "positive"
        elif stars <= 2:
            cat = "negative"
        else:
            cat = "neutral"
        return {'label': out['label'], 'score': out['score'], 'mapped_category': cat}

    Dummy mode:
      If any NEGATIVE_KEYWORDS in the text → 'negative' (1 star)
      Else if text contains '?' → 'neutral' (3 stars)
      Else → 'positive' (5 stars)
    """
    lower = text.lower()
    for kw in NEGATIVE_KEYWORDS:
        if kw in lower:
            return {'label': '1 star', 'score': 0.90, 'mapped_category': 'negative'}
    if '?' in text:
        return {'label': '3 stars', 'score': 0.75, 'mapped_category': 'neutral'}
    return {'label': '5 stars', 'score': 0.85, 'mapped_category': 'positive'}

#
# ----------------------------
# 3) Reply Generation “Model”
# ----------------------------
#
import subprocess
import shlex

def generate_reply_with_gemma3(prompt: str) -> str:
    # 프롬프트 명확화
    refined_prompt = f"""You are an assistant that writes polite, professional email replies.
Based on the following email, please write a short and relevant reply.

--- EMAIL START ---
{prompt}
--- EMAIL END ---

Reply:
"""

    try:
        cmd = "ollama run gemma3:4b"
        proc = subprocess.run(
            shlex.split(cmd),
            input=refined_prompt,
            capture_output=True,
            text=True,               # 텍스트 모드
            encoding='utf-8',        # ✅ 정확한 인코딩 명시
            timeout=60               # 모델 타임아웃
        )

        if proc.returncode != 0:
            print(f"[Gemma Error] stderr: {proc.stderr}")
            return "⚠️ Error generating reply. Please try again."

        output = proc.stdout.strip()

        # 모델이 프롬프트 자체를 그대로 반환한 경우 제거
        if "Please provide me" in output or output.lower().startswith("please provide"):
            return "⚠️ The model did not return a valid reply. Try with a longer or clearer email."

        # Gemma가 프롬프트 포함시켰을 경우 제거
        if "Reply:" in output:
            output = output.split("Reply:", 1)[-1].strip()

        return output or "⚠️ The model returned an empty response."

    except subprocess.TimeoutExpired:
        return "⚠️ Reply generation timed out. Please try again."

    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)}"


#
# ----------------------------
# 4) Dummy IMAP Stub
# ----------------------------
#
def fetch_latest_email_dummy():
    """
    Placeholder for future IMAP or Gmail integration.
    Real IMAP outline (not executed):
        M = imaplib.IMAP4_SSL("imap.gmail.com")
        M.login("myemail@gmail.com", "app_password")
        M.select("inbox")
        typ, data = M.search(None, 'UNSEEN')
        for num in data[0].split():
            typ, msg_data = M.fetch(num, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body += part.get_payload(decode=True).decode()
                return body
            else:
                return msg.get_payload(decode=True).decode()
        return ""
    Dummy: just return one fixed sample email.
    """
    return (
        "Hello Team,\n\n"
        "The project deadline is next Friday at 5 PM. "
        "Please send your draft by Tuesday at noon. Additionally, "
        "we had a delay due to server issues. Let me know if you have any questions.\n\n"
        "Thanks,\nProject Manager"
    )

#
# ----------------------------
# Flask Endpoints
# ----------------------------
#
@app.route("/summarize", methods=["POST"])
def summarize_endpoint():
    payload = request.get_json()
    text = payload.get("text", "").strip()
    if not text:
        return jsonify({"error": "no text provided"}), 400
    summary = summarize_text(text)
    return jsonify({"summary": summary})

@app.route("/sentiment", methods=["POST"])
def sentiment_endpoint():
    payload = request.get_json()
    text = payload.get("text", "").strip()
    if not text:
        return jsonify({"error": "no text provided"}), 400
    result = analyze_sentiment(text)
    return jsonify(result)

@app.route("/reply", methods=["POST"])
def reply_endpoint():
    payload = request.get_json()
    text = payload.get("text", "").strip()
    if not text:
        return jsonify({"error": "no text provided"}), 400
    reply_text = generate_reply_with_gemma3(text)
    return jsonify({"reply": reply_text})

@app.route("/fetch_latest_email", methods=["GET"])
def fetch_email_endpoint():
    """
    Returns a dummy email body as JSON. In future, this would fetch from IMAP.
    """
    body = fetch_latest_email_dummy()
    return jsonify({"email_body": body})

if __name__ == "__main__":
    # Runs on http://0.0.0.0:5000 by default
    app.run(host="0.0.0.0", port=5000, debug=True)
