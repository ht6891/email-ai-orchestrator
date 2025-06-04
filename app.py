from flask import Flask, request, jsonify
from transformers import pipeline
import subprocess
import shlex
import json
import sys
import locale

app = Flask(__name__)

# 1) Summarisation pipeline
summarizer = pipeline(
    "summarization",
    model="sshleifer/distilbart-cnn-6-6",
    device=-1
)

# 2) Sentiment pipeline
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model="nlptown/bert-base-multilingual-uncased-sentiment"
)

# 3) Reply generation via Ollama with UTF-8 safe encoding

def generate_reply_with_gemma3(prompt: str) -> str:
    cmd = f'ollama run gemma3:4b'
    try:
        proc = subprocess.run(
            shlex.split(cmd),
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',  # Force UTF-8 to handle en dash and other symbols
            timeout=30
        )
        if proc.returncode != 0:
            return f"Error: {proc.stderr.strip()}"
        return proc.stdout.strip()
    except Exception as e:
        return f"Exception: {str(e)}"

@app.route("/summarize", methods=["POST"])
def summarize():
    payload = request.get_json()
    text = payload.get("text", "")
    if not text:
        return jsonify({"error": "no text provided"}), 400
    out = summarizer(text, max_length=150, min_length=40, do_sample=False)
    return jsonify({"summary": out[0]["summary_text"]})

@app.route("/sentiment", methods=["POST"])
def sentiment():
    payload = request.get_json()
    text = payload.get("text", "")
    if not text:
        return jsonify({"error": "no text provided"}), 400
    out = sentiment_analyzer(text)
    return jsonify(out[0])

@app.route("/reply", methods=["POST"])
def reply():
    payload = request.get_json()
    text = payload.get("text", "")
    if not text:
        return jsonify({"error": "no text provided"}), 400
    reply_text = generate_reply_with_gemma3(text)
    return jsonify({"reply": reply_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
