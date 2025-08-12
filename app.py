# app.py
import sys
sys.dont_write_bytecode = True

from flask import Flask, request, jsonify
app = Flask(__name__)
from transformers import pipeline
from email_cleaner import remove_signature
import subprocess, shlex, re, email, imaplib, json

# ----------------------------
# 1) Summarization “Model”  (EN/KR router + safe fallbacks)
# ----------------------------
import re
from transformers import pipeline

# 모델 이름
EN_SUM_MODEL = "philschmid/bart-large-cnn-samsum"          # 영어 대화/이메일 요약
KO_SUM_MODEL = "csebuetnlp/mT5_multilingual_XLSum"         # 다국어 요약(XLSum, ko 포함)

# 파이프라인 로드 (가능한 것만)
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
    """아주 단순한 추출 요약: 문장 분리 후 앞쪽 1~2문장 반환"""
    # 마침표/물음표/느낌표 기준 대략적 분리
    sents = re.split(r'(?<=[\.\?\!])\s+', text.strip())
    sents = [s.strip() for s in sents if s.strip()]
    return " ".join(sents[:max_sent]) if sents else text.strip()

def _is_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text))

def summarize_text(text: str) -> str:
    if not text or not text.strip():
        return ""

    # 입력 정리/길이 제한
    raw = text.strip().replace("\n", " ")
    raw = raw[:1200]  # 너무 길면 자르기(속도/메모리 보호)

    try:
        if _is_korean(raw) and ko_summarizer:
            # mT5-XLSum은 일반적으로 prefix 없이도 동작하지만,
            # 안정성을 위해 간단한 프롬프트를 붙임
            prompt = f"summarize: {raw}"
            out = ko_summarizer(prompt, max_length=70, min_length=18, do_sample=False)
            return out[0]["summary_text"].strip()

        if en_summarizer:
            prompt = f"Summarize the following email in 1–2 sentences, concise and specific:\n{raw}"
            out = en_summarizer(prompt, max_length=65, min_length=18, do_sample=False)
            return out[0]["summary_text"].strip()

        # 모델이 하나도 없을 때
        return _fallback_extractive(raw)

    except Exception as e:
        # 에러 시 안전 폴백
        print("[summarize] error -> fallback:", e)
        return _fallback_extractive(raw)


# 멀티링구얼(한/영 포함) 감정 모델 로드 (가능하면)
try:
    sentiment_pipe = pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-xlm-roberta-base-sentiment"  # multilingual
    )
    print("[sentiment] using xlm-roberta model")
except Exception as e:
    sentiment_pipe = None
    print("[sentiment] fallback to rules only:", e)

# 하드 네거티브 신호 (긴급/불능/오류)
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

    # 1) 하드 룰: 명확한 네거티브 신호 우선 반영
    neg_hits = sum(1 for pat in NEG_PATTERNS if re.search(pat, t))
    if neg_hits >= 2 or ("urgent" in t and ("help" in t or "asap" in t)):
        return {"label": "1 star", "score": 0.95, "mapped_category": "negative"}

    # 2) 모델 예측 (가능하면)
    if sentiment_pipe:
        try:
            res = sentiment_pipe(t[:512])[0]   # 너무 긴 입력은 잘라서
            raw_label = res["label"].lower()   # e.g. 'positive' / 'neutral' / 'negative'
            score = float(res["score"])
            mapped = (
                "positive" if "positive" in raw_label else
                "negative" if "negative" in raw_label else
                "neutral"
            )

            # 3) 사후 보정: 네거티브 신호가 있으면 네거티브로 강등
            if mapped != "negative" and neg_hits >= 1:
                mapped, score = "negative", max(score, 0.85)

            # 4) 사후 보정: 긍정 키워드가 있으면 뉴트럴→포지티브
            if mapped == "neutral" and any(k in t for k in POS_KEYWORDS):
                mapped, score = "positive", max(score, 0.80)

            star_map = {"positive": "5 stars", "neutral": "3 stars", "negative": "1 star"}
            return {"label": star_map[mapped], "score": round(score, 2), "mapped_category": mapped}

        except Exception as e:
            print("[sentiment] model error, fallback to rules:", e)

    # 3) 모델 사용 불가/오류 시 룰만으로 판단
    if neg_hits > 0:
        return {"label": "1 star", "score": 0.85, "mapped_category": "negative"}
    if any(k in t for k in POS_KEYWORDS):
        return {"label": "5 stars", "score": 0.90, "mapped_category": "positive"}
    return {"label": "3 stars", "score": 0.75, "mapped_category": "neutral"}
def generate_reply_with_gemma3(prompt: str) -> str:
    refined_prompt = f"""You are an assistant that writes polite, professional email replies.
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

# ----- Endpoints -----
@app.route("/summarize", methods=["POST"])
def summarize_endpoint():
    text = (request.json or {}).get("text","").strip()
    if not text: return jsonify({"summary": ""})
    return jsonify({"summary": summarize_text(text)})

@app.route("/sentiment", methods=["POST"])
def sentiment_endpoint():
    text = (request.json or {}).get("text","").strip()
    return jsonify(analyze_sentiment(text))

@app.route("/reply", methods=["POST"])
def reply_endpoint():
    text = (request.json or {}).get("text","").strip()
    if not text: return jsonify({"reply": ""})
    return jsonify({"reply": generate_reply_with_gemma3(text)})

# 리스트 API: subject/snippet/text 모두 제공
@app.route("/api/emails", methods=["GET"])
def api_emails():
    from run_fetch import fetch_emails
    raw_emails = fetch_emails(max_results=20)  # bodies only
    items = []
    for idx, raw in enumerate(raw_emails):
        raw = raw or ""
        cleaned = remove_signature(raw).strip()
        # 제목: 비어있지 않은 첫 줄을 사용
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
    text = (request.json or {}).get("text", "")
    cleaned = remove_signature(text)
    return jsonify({
        "summary": summarize_text(cleaned),
        "sentiment": analyze_sentiment(cleaned)["mapped_category"]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
