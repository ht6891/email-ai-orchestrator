from flask import Flask, request, jsonify
from transformers import pipeline
import subprocess
import shlex
import json

app = Flask(__name__)

# 1) Summarisation pipeline
summarizer = pipeline(
    "summarization",
    model="sshleifer/distilbart-cnn-6-6",
    device=-1  # set to -1 if no GPU
)

# 2) Sentiment pipeline
# sentiment_analyzer = pipeline(
#     "sentiment-analysis",
#     model="tabularis/multilingual-sentiment-analysis",
#     device=0
# )

sentiment_analyzer = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")


# 3) Reply generation via Ollama Gemma-3
def generate_reply_with_gemma3(prompt: str) -> str:
    # requires `ollama` CLI installed and gemma3 model pulled locally:
    #   ollama pull gemma3
    cmd = f'ollama generate gemma3 --prompt "{prompt}" --json'
    proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    if proc.returncode != 0:
        return f"Error: {proc.stderr}"
    data = json.loads(proc.stdout)
    # Ollama JSON format: {"id":..,"model":..,"text":..}
    return data.get("text","")

@app.route("/summarize", methods=["POST"])
def summarize():
    payload = request.get_json()
    text = payload.get("text","")
    if not text:
        return jsonify({"error":"no text provided"}), 400
    # run summariser
    out = summarizer(text, max_length=150, min_length=40, do_sample=False)
    return jsonify({"summary": out[0]["summary_text"]})

@app.route("/sentiment", methods=["POST"])
def sentiment():
    payload = request.get_json()
    text = payload.get("text","")
    if not text:
        return jsonify({"error":"no text provided"}), 400
    out = sentiment_analyzer(text)
    # returns list like [{"label":"POSITIVE","score":0.97}]
    return jsonify(out[0])

@app.route("/reply", methods=["POST"])
def reply():
    payload = request.get_json()
    text = payload.get("text","")
    if not text:
        return jsonify({"error":"no text provided"}), 400
    reply_text = generate_reply_with_gemma3(text)
    return jsonify({"reply": reply_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
