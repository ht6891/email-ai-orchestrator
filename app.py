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
import subprocess, shlex, re, email, imaplib, json
import pandas as pd
import time

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
    """
    Real mode (uncomment the two lines above):
        out = summarizer(text, max_length=150, min_length=40, do_sample=False)
        return out[0]['summary_text']

    Dummy fallback:
      Very naive: return the first two sentences separated by “. ”
    """
    sentences = re.split(r'\. ', text.strip(), maxsplit=2)
    if len(sentences) <= 2:
        return text.strip()
    return sentences[0].strip() + ". " + sentences[1].strip() + "."

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
def generate_reply_with_gemma3(prompt: str) -> str:
    """
    Real mode (requires Ollama CLI + Gemma3:4b):
        cmd = "ollama run gemma3:4b"
        try:
            proc = subprocess.run(
                shlex.split(cmd),
                input=prompt,
                capture_output=True,
                text=True,
                timeout=60
            )
            if proc.returncode != 0:
                return f"Error: {proc.stderr.strip()}"
            return proc.stdout.strip()
        except subprocess.TimeoutExpired:
            return "Error: Model timed out."
        except Exception as e:
            return f"Exception: {e}"

    Dummy fallback:
       Return a generic “thanks and I’ll get back” template.
    """
    return ("Thank you for your email. I appreciate the update. "
            "I will review and get back to you by end of day.")

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
@app.route('/summarize', methods=['POST'])
def summarize():
    text = request.json['text']
    prompt = (
        "Summarize the following email into 1–2 concise sentences. "
        "Focus only on the core request or issue. "
        "Ignore footers, signatures, disclaimers, and repeated context.\n\n"
        f"{text}"
    )
    response = model.generate(prompt)
    return jsonify({'summary': response})


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
