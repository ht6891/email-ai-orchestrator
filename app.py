# app.py
import sys
sys.dont_write_bytecode = True

from flask import Flask, request, jsonify
app = Flask(__name__)
from transformers import pipeline
from email_cleaner import remove_signature
import subprocess, shlex, re

# ----------------------------
# Summarization (EN/KR router)
# ----------------------------
EN_SUM_MODEL = "philschmid/bart-large-cnn-samsum"          # 영어 대화/이메일 요약
KO_SUM_MODEL = "csebuetnlp/mT5_multilingual_XLSum"         # 다국어 요약(XLSum, ko 포함)

try:
    en_summarizer = pipeline("summarization", model=EN_SUM_MODEL)
    print("[summarize] EN model loaded.")
except Exception as e:
    en_summarizer = None
    print("[summarize] EN model load failed:", e)

try:
    ko_summarizer = pipeline("summarization", model=KO_SUM_MODEL)
    print("[summarize] KO model loaded.")
except Exception as e:
    ko_summarizer = None
    print("[summarize] KO model load failed:", e)

def _fallback_extractive(text: str, max_sent: int = 2) -> str:
    sents = re.split(r'(?<=[\.\?\!])\s+', (text or "").strip())
    sents = [s.strip() for s in sents if s.strip()]
    return " ".join(sents[:max_sent]) if sents else (text or "").strip()

def _is_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text or ""))

def summarize_text(text: str, lang: str = "auto") -> str:
    if not text or not text.strip():
        return ""
    raw = text.strip().replace("\n", " ")[:1200]

    try:
        # 강제 언어
        if lang == "ko" and ko_summarizer:
            out = ko_summarizer(f"summarize: {raw}", max_length=70, min_length=18, do_sample=False)
            return out[0]["summary_text"].strip()
        if lang == "en" and en_summarizer:
            out = en_summarizer(f"Summarize the following email in 1–2 sentences, concise and specific:\n{raw}",
                                max_length=65, min_length=18, do_sample=False)
            return out[0]["summary_text"].strip()

        # 자동 판단
        if _is_korean(raw) and ko_summarizer:
            out = ko_summarizer(f"summarize: {raw}", max_length=70, min_length=18, do_sample=False)
            return out[0]["summary_text"].strip()
        if en_summarizer:
            out = en_summarizer(f"Summarize the following email in 1–2 sentences, concise and specific:\n{raw}",
                                max_length=65, min_length=18, do_sample=False)
            return out[0]["summary_text"].strip()

        return _fallback_extractive(raw)
    except Exception as e:
        print("[summarize] error -> fallback:", e)
        return _fallback_extractive(raw)

# ----------------------------
# Sentiment (multilingual + rules)
# ----------------------------
try:
    sentiment_pipe = pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-xlm-roberta-base-sentiment"  # multilingual
    )
    print("[sentiment] using xlm-roberta model")
except Exception as e:
    sentiment_pipe = None
    print("[sentiment] fallback to rules only:", e)

NEG_PATTERNS = [
    r"\bnot (working|able|available)\b",
    r"\b(can't|cannot)\b",
    r"\b(fail(ed|ing)?|error|down|crash(ed)?|unavailable)\b",
    r"\burgent\b",
    r"\bissue(s)?\b",
    r"\bproblem(s)?\b",
    r"\bblocked\b"
]
POS_KEYWORDS = {
    "thanks", "thank you", "appreciate", "great", "resolved", "fixed",
    "awesome", "good news", "well done"
}

def analyze_sentiment(text: str) -> dict:
    t = (text or "").lower()
    neg_hits = sum(1 for pat in NEG_PATTERNS if re.search(pat, t))
    if neg_hits >= 2 or ("urgent" in t and ("help" in t or "asap" in t)):
        return {"label": "1 star", "score": 0.95, "mapped_category": "negative"}

    if sentiment_pipe:
        try:
            res = sentiment_pipe(t[:512])[0]
            raw_label = res["label"].lower()
            score = float(res["score"])
            mapped = "positive" if "positive" in raw_label else ("negative" if "negative" in raw_label else "neutral")

            if mapped != "negative" and neg_hits >= 1:
                mapped, score = "negative", max(score, 0.85)
            if mapped == "neutral" and any(k in t for k in POS_KEYWORDS):
                mapped, score = "positive", max(score, 0.80)

            star_map = {"positive": "5 stars", "neutral": "3 stars", "negative": "1 star"}
            return {"label": star_map[mapped], "score": round(score, 2), "mapped_category": mapped}
        except Exception as e:
            print("[sentiment] model error, fallback to rules:", e)

    if neg_hits > 0:
        return {"label": "1 star", "score": 0.85, "mapped_category": "negative"}
    if any(k in t for k in POS_KEYWORDS):
        return {"label": "5 stars", "score": 0.90, "mapped_category": "positive"}
    return {"label": "3 stars", "score": 0.75, "mapped_category": "neutral"}

# ----------------------------
# Translation EN <-> KO
# ----------------------------
try:
    trans_en_ko = pipeline("translation", model="Helsinki-NLP/opus-mt-en-ko")
    print("[translate] en->ko loaded")
except Exception as e:
    trans_en_ko = None
    print("[translate] en->ko load failed:", e)

try:
    trans_ko_en = pipeline("translation", model="Helsinki-NLP/opus-mt-ko-en")
    print("[translate] ko->en loaded")
except Exception as e:
    trans_ko_en = None
    print("[translate] ko->en load failed:", e)

def translate_text(text: str, target_lang: str):
    text = (text or "").strip()
    if not text:
        return ""
    try:
        if target_lang == "ko":
            if trans_en_ko:
                out = trans_en_ko(text[:1000])
                return out[0]["translation_text"]
            # 대충 fallback
            return text
        elif target_lang == "en":
            if trans_ko_en:
                out = trans_ko_en(text[:1000])
                return out[0]["translation_text"]
            return text
        else:
            return text
    except Exception as e:
        print("[translate] error:", e)
        return text

# ----------------------------
# Reply (Gemma) with language control
# ----------------------------
def generate_reply_with_gemma3(prompt: str, lang: str = "en") -> str:
    lang_instruction = "Reply in Korean." if lang == "ko" else "Reply in English."
    refined_prompt = f"""You are an assistant that writes polite, professional email replies.
{lang_instruction}
Based on the following email, write a short relevant reply.

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
            text=True,
            encoding="utf-8",
            timeout=300
        )
        if proc.returncode != 0:
            print(f"[Gemma Error] {proc.stderr}")
            return "⚠️ Error generating reply. Please try again."
        out = (proc.stdout or "").strip()
        if "Reply:" in out:
            out = out.split("Reply:", 1)[-1].strip()
        if out.lower().startswith("please provide"):
            return "⚠️ The model did not return a valid reply."
        return out or "⚠️ The model returned an empty response."
    except subprocess.TimeoutExpired:
        return "⚠️ Reply generation timed out. Please try again."
    except Exception as e:
        return f"⚠️ Unexpected error: {e}"

# ----------------------------
# API endpoints
# ----------------------------
@app.route("/summarize", methods=["POST"])
def summarize_endpoint():
    data = (request.json or {})
    text = (data.get("text") or "").strip()
    lang = (data.get("lang") or "auto").lower()
    return jsonify({"summary": summarize_text(text, lang)})

@app.route("/sentiment", methods=["POST"])
def sentiment_endpoint():
    text = (request.json or {}).get("text","").strip()
    return jsonify(analyze_sentiment(text))

@app.route("/reply", methods=["POST"])
def reply_endpoint():
    data = (request.json or {})
    text = (data.get("text") or "").strip()
    lang = (data.get("lang") or "en").lower()
    return jsonify({"reply": generate_reply_with_gemma3(text, lang)})

@app.route("/translate", methods=["POST"])
def translate_endpoint():
    data = (request.json or {})
    text = (data.get("text") or "").strip()
    target = (data.get("target_lang") or "").lower()
    if target not in ("en","ko"):
        return jsonify({"error":"target_lang must be 'en' or 'ko'"}), 400
    return jsonify({"translated": translate_text(text, target)})

# 리스트 API (기존)
@app.route("/api/emails", methods=["GET"])
def api_emails():
    from run_fetch import fetch_emails
    raw_emails = fetch_emails(max_results=20)
    items = []
    for idx, raw in enumerate(raw_emails):
        raw = raw or ""
        cleaned = remove_signature(raw).strip()
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        subject = (lines[0] if lines else "(no subject)")[:80]
        snippet = (cleaned or raw).replace("\n", " ")[:160]
        items.append({
            "id": idx,
            "subject": subject,
            "snippet": snippet,
            "text": cleaned or raw
        })
    return jsonify(items)

# 수동 텍스트 처리
@app.route("/process", methods=["POST"])
def process_input():
    data = (request.json or {})
    text = (data.get("text") or "")
    cleaned = remove_signature(text)
    lang = (data.get("lang") or "auto").lower()
    return jsonify({
        "summary": summarize_text(cleaned, lang),
        "sentiment": analyze_sentiment(cleaned)["mapped_category"]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
