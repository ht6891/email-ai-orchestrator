# app.py
import sys
sys.dont_write_bytecode = True

import re
import time
import shlex
import subprocess
from typing import List

from flask import Flask, request, jsonify, Response, stream_with_context
from transformers import pipeline

# Use Built-in Signature Remover
try:
    from email_cleaner import remove_signature
except Exception:
    def remove_signature(x: str) -> str:
        return (x or "").strip()
    
# --- SPEED OPTIONS (add near the top of app.py) ---
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # tokenizer 경합 방지

# ===== Device Autodetect (GPU Priority) =====
try:
    import torch
    _torch_ok = True
except Exception:
    _torch_ok = False
    torch = None  # Safety

USE_CUDA = bool(_torch_ok and torch.cuda.is_available())
if USE_CUDA:
    DEVICE = 0          # Using GPU in Transformers Pipeline
else:
    DEVICE = -1         # Using CPU in Transformers Pipeline
    # Limit threads only when using CPU (adjust number if desired)
    try:
        n_threads = min(4, (os.cpu_count() or 4))
        torch.set_num_threads(n_threads)
    except Exception:
        pass
# =======================================

# Ollama Settings: Smaller Model + Shorter Output + Lower Temperature
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")  # Replace with smaller installed model if needed (e.g., llama3.2:3b, qwen2:1.5b)
OLLAMA_OPTS  = os.getenv("OLLAMA_OPTS",
                         "-o num_predict=120 -o temperature=0.2 -o top_p=0.9 -o num_thread=4 -o stop=Reply:")
# num_predict: Lower max generated tokens  / num_thread: Match CPU cores

app = Flask(__name__)

# ----------------------------
# Summarization models (EN / KO)
# ----------------------------
EN_SUM_MODEL = "philschmid/bart-large-cnn-samsum"          # English Conversation/Email Summarisation
KO_SUM_MODEL = "csebuetnlp/mT5_multilingual_XLSum"         # Multilingual Summarization (including ko)

def _load_pipe(task, model):
    try:
        p = pipeline(task, model=model)
        print(f"[load] {task} <- {model}")
        return p
    except Exception as e:
        print(f"[load] FAILED: {task} <- {model} :: {e}")
        return None

en_summarizer = _load_pipe("summarization", EN_SUM_MODEL)
ko_summarizer = _load_pipe("summarization", KO_SUM_MODEL)

# ----------------------------
# Summarization helpers
# ----------------------------
def _is_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text or ""))

def _fallback_extractive(text: str, max_sent=2) -> str:
    sents = re.split(r'(?<=[\.\?\!])\s+', (text or "").strip())
    sents = [s.strip() for s in sents if s.strip()]
    return " ".join(sents[:max_sent]) if sents else (text or "").strip()

def _safe_model_max(pipe, default_cap: int) -> int:
    try:
        ml = getattr(pipe, "tokenizer", None).model_max_length
        if isinstance(ml, int) and ml < 100000:
            return ml
    except Exception:
        pass
    return default_cap

def _chunk_by_tokens(text: str, tokenizer, max_tokens: int, overlap: int = 50) -> List[str]:
    ids = tokenizer.encode(text, add_special_tokens=False)
    if not ids:
        return []
    step = max(1, max_tokens - overlap)
    chunks = []
    for i in range(0, len(ids), step):
        piece = ids[i:i + max_tokens]
        chunk = tokenizer.decode(piece, skip_special_tokens=True)
        if chunk.strip():
            chunks.append(chunk.strip())
        if i + max_tokens >= len(ids):
            break
    return chunks

def _summarize_once(pipe, text: str, *, max_len: int, min_len: int) -> str:
    out = pipe(text, max_length=max_len, min_length=min_len, do_sample=False, truncation=True)
    return (out[0]["summary_text"] or "").strip()

def summarize_text(text: str, lang: str = "auto", mode: str = "hybrid") -> str:
    """
    lang: auto|en|ko
    mode: hybrid|llm|fast  (This value is only a hint for length/speed tuning)
    """
    raw = (text or "").strip()
    if not raw:
        return ""

    # Language Detection
    use_ko = (lang == "ko") or (lang == "auto" and _is_korean(raw))
    pipe = ko_summarizer if use_ko else en_summarizer
    if pipe is None:
        return _fallback_extractive(raw)

    # Input Limits per Model
    default_cap = 512 if use_ko else 1024
    max_in = _safe_model_max(pipe, default_cap)
    max_chunk_tokens = max(128, min(max_in - 32, default_cap - 32))

    # Summary Length by Mode (approximate, based on experience)
    if mode == "fast":
        first_pass_max = 45 if use_ko else 48
        first_pass_min = 10
        final_max = 55 if use_ko else 58
        final_min = 14
    elif mode == "llm":
        first_pass_max = 70 if use_ko else 68
        first_pass_min = 18
        final_max = 80 if use_ko else 75
        final_min = 20
    else:  # hybrid(default)
        first_pass_max = 55 if use_ko else 58
        first_pass_min = 14
        final_max = 68 if use_ko else 65
        final_min = 18

    try:
        # Token Splitting
        chunks = _chunk_by_tokens(raw, pipe.tokenizer, max_chunk_tokens, overlap=50)
        if not chunks:
            return _fallback_extractive(raw)

        # Single summary if only 1 chunk
        if len(chunks) == 1:
            return _summarize_once(pipe, chunks[0], max_len=final_max, min_len=final_min)

        # Step 1: Summarize Each Chunk
        part_sums = []
        for c in chunks:
            try:
                s = _summarize_once(pipe, c, max_len=first_pass_max, min_len=first_pass_min)
            except Exception:
                s = _fallback_extractive(c, max_sent=1)
            if s:
                part_sums.append(s)

        combined = " ".join(part_sums)

        # Step 2: If combined summary is too long, shorten again
        if len(part_sums) > 2 or len(combined) > 1500:
            comb_chunks = _chunk_by_tokens(combined, pipe.tokenizer, max_chunk_tokens, overlap=20)
            comb_sums = []
            for cc in comb_chunks:
                try:
                    comb_sums.append(_summarize_once(pipe, cc, max_len=first_pass_max, min_len=first_pass_min))
                except Exception:
                    comb_sums.append(_fallback_extractive(cc, max_sent=1))
            combined = " ".join([s for s in comb_sums if s.strip()])

        # Final Refinement
        final = _summarize_once(pipe, combined, max_len=final_max, min_len=final_min)
        return final or _fallback_extractive(raw)

    except Exception as e:
        print("[summarize] error -> fallback:", e)
        return _fallback_extractive(raw)

# ----------------------------
# Sentiment (multilingual + rules)
# ----------------------------
try:
    sentiment_pipe = pipeline("sentiment-analysis", model="cardiffnlp/twitter-xlm-roberta-base-sentiment")
    print("[sentiment] xlm-roberta loaded")
except Exception as e:
    sentiment_pipe = None
    print("[sentiment] fallback rules only:", e)

NEG_PATTERNS = [
    r"\bnot (working|able|available)\b",
    r"\b(can't|cannot)\b",
    r"\b(fail(ed|ing)?|error|down|crash(ed)?|unavailable)\b",
    r"\burgent\b",
    r"\bissue(s)?\b",
    r"\bproblem(s)?\b",
    r"\bblocked\b",
]
POS_KEYWORDS = {
    "thanks", "thank you", "appreciate", "great", "resolved", "fixed", "awesome", "good news", "well done"
}

def analyze_sentiment(text: str) -> dict:
    t = (text or "").lower()
    neg_hits = sum(1 for pat in NEG_PATTERNS if re.search(pat, t))
    if neg_hits >= 2 or ("urgent" in t and ("help" in t or "asap" in t)):
        return {"label": "1 star", "score": 0.95, "mapped_category": "negative"}

    if sentiment_pipe:
        try:
            res = sentiment_pipe(t[:512])[0]
            raw_label = (res["label"] or "").lower()
            score = float(res["score"])
            mapped = "positive" if "positive" in raw_label else ("negative" if "negative" in raw_label else "neutral")

            if mapped != "negative" and neg_hits >= 1:
                mapped, score = "negative", max(score, 0.85)
            if mapped == "neutral" and any(k in t for k in POS_KEYWORDS):
                mapped, score = "positive", max(score, 0.80)

            star_map = {"positive": "5 stars", "neutral": "3 stars", "negative": "1 star"}
            return {"label": star_map[mapped], "score": round(score, 2), "mapped_category": mapped}
        except Exception as e:
            print("[sentiment] model error -> rules:", e)

    if neg_hits > 0:
        return {"label": "1 star", "score": 0.85, "mapped_category": "negative"}
    if any(k in t for k in POS_KEYWORDS):
        return {"label": "5 stars", "score": 0.90, "mapped_category": "positive"}
    return {"label": "3 stars", "score": 0.75, "mapped_category": "neutral"}


# ----------------------------
# Reply generation (Ollama / stream)
# ----------------------------
ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

def _strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)

def _ollama_stream(prompt: str):
    """
    Read Ollama output line/chunk by line and deliver via SSE.
    """
    cmd = "ollama run gemma3:4b"
    proc = subprocess.Popen(
        shlex.split(cmd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()

        last_ping = time.time()
        for line in proc.stdout:
            chunk = _strip_ansi(line.rstrip("\r\n"))
            if chunk:
                yield f"data: {chunk}\n\n"
            # Heartbeat every 3 seconds
            now = time.time()
            if now - last_ping > 3:
                yield "event: ping\ndata: keepalive\n\n"
                last_ping = now

        proc.wait(timeout=300)
        yield "event: done\ndata: [DONE]\n\n"
    except Exception as e:
        yield f"event: error\ndata: {str(e)}\n\n"
    finally:
        try:
            proc.kill()
        except Exception:
            pass

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
        out = _strip_ansi((proc.stdout or "").strip())
        if "Reply:" in out:
            out = out.split("Reply:", 1)[-1].strip()
        if out.lower().startswith("please provide"):
            return "⚠️ The model did not return a valid reply."
        return out or "⚠️ The model returned an empty response."
    except subprocess.TimeoutExpired:
        return "⚠️ Reply generation timed out. Please try again."
    except Exception as e:
        return f"⚠️ Unexpected error: {e}"
    

# --- Add: LLM Summarization Function ---
def summarize_llm_ollama(text: str, max_chars: int = 2000) -> str:
    """
    More precise summarization with Ollama local LLM.
    - Input after signature removal and length limit
    - Instruct to summarize in 2–3 sentences while keeping the original language
    """
    cleaned = remove_signature(text or "").strip()
    if not cleaned:
        return ""

    # Cut overly long input for speed/quality stability
    cleaned = cleaned[:max_chars]

    prompt = f"""You are a helpful assistant.
Summarize the following email in the SAME language as the original.
Be concise but keep key details (dates, deadlines, requests, numbers).
Write 2–3 sentences.

--- EMAIL START ---
{cleaned}
--- EMAIL END ---

Summary:
"""

    try:
        cmd = "ollama run gemma3:4b"
        proc = subprocess.run(
            shlex.split(cmd),
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120
        )
        if proc.returncode != 0:
            # Ollama Runtime Error
            return f"⚠️ LLM error: {proc.stderr.strip() or 'unknown error'}"
        out = (proc.stdout or "").strip()

        # Clean up if the model echoed part of the prompt
        if "Summary:" in out:
            out = out.split("Summary:", 1)[-1].strip()

        # Clean up occasional template phrases
        bad_heads = ("Please provide", "I cannot")
        if any(out.startswith(h) for h in bad_heads):
            return "⚠️ The model did not return a valid summary. Try again with clearer input."

        return out or "⚠️ (empty response from model)"
    except subprocess.TimeoutExpired:
        return "⚠️ LLM summarization timed out."
    except Exception as e:
        return f"⚠️ Unexpected error: {e}"
    
# --- Add: LLM Translation Function ---
def translate_llm_ollama(text: str, target_lang: str = "en", max_chars: int = 2000) -> str:
    """
    Simple translation using Ollama LLM.
    - target_lang: 'en' or 'ko'
    - Limit input length for speed/stability
    - Output translation only (no explanations/notes)
    """
    source = (text or "").strip()
    if not source:
        return ""

    target_lang = (target_lang or "en").lower()
    if target_lang not in ("en", "ko"):
        return "⚠️ target_lang must be 'en' or 'ko'"

    source = source[:max_chars]
    instruction = "Translate into English only. Output ONLY the translation." if target_lang == "en" \
                  else "Translate into Korean only. Output ONLY the translation."

    prompt = f"""{instruction}
Preserve key details such as names, dates, times, amounts, and URLs. Keep formatting when helpful.

--- TEXT START ---
{source}
--- TEXT END ---
"""

    try:
        cmd = "ollama run gemma3:4b"
        proc = subprocess.run(
            shlex.split(cmd),
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300
        )
        if proc.returncode != 0:
            return f"⚠️ LLM error: {proc.stderr.strip() or 'unknown error'}"

        out = (proc.stdout or "").strip()

        # Attempt to remove unnecessary preface if model adds one
        bad_heads = ("Translation:", "Result:", "Output:", "Please provide")
        for h in bad_heads:
            if out.startswith(h):
                out = out[len(h):].strip()

        return out or "⚠️ (empty response from model)"
    except subprocess.TimeoutExpired:
        return "⚠️ LLM translation timed out."
    except Exception as e:
        return f"⚠️ Unexpected error: {e}"

# --- Add: Flask Endpoint ---
@app.route("/translate_llm", methods=["POST"])
def translate_llm_endpoint():
    data = (request.json or {})
    text = (data.get("text") or "").strip()
    target = (data.get("target_lang") or "en").lower()
    if not text:
        return jsonify({"translated": ""})
    translated = translate_llm_ollama(text, target_lang=target)
    return jsonify({"translated": translated})

@app.route("/summarize_llm", methods=["POST"])
def summarize_llm_endpoint():
    data = (request.json or {})
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"summary": ""})
    summary = summarize_llm_ollama(text)
    return jsonify({"summary": summary})

# ----------------------------
# API endpoints
# ----------------------------
@app.route("/summarize", methods=["POST"])
def summarize_endpoint():
    data = (request.json or {})
    text = (data.get("text") or "").strip()
    lang = (data.get("lang") or "auto").lower()
    mode = (data.get("mode") or "hybrid").lower()
    cleaned = remove_signature(text)
    return jsonify({"summary": summarize_text(cleaned, lang, mode)})

@app.route("/sentiment", methods=["POST"])
def sentiment_endpoint():
    text = (request.json or {}).get("text","").strip()
    cleaned = remove_signature(text)
    return jsonify(analyze_sentiment(cleaned))

@app.route("/reply", methods=["POST"])
def reply_endpoint():
    data = (request.json or {})
    text = (data.get("text") or "").strip()
    lang = (data.get("lang") or "en").lower()
    cleaned = remove_signature(text)
    return jsonify({"reply": generate_reply_with_gemma3(cleaned, lang)})

@app.route("/reply_stream", methods=["POST"])
def reply_stream():
    data = (request.json or {})
    text = (data.get("text") or "").strip()
    lang = (data.get("lang") or "en").lower()
    if not text:
        return Response("data: \n\n", mimetype="text/event-stream")

    lang_instruction = "Reply in Korean." if lang == "ko" else "Reply in English."
    refined_prompt = f"""You are an assistant that writes polite, professional email replies.
{lang_instruction}
Based on the following email, write a short relevant reply.

--- EMAIL START ---
{remove_signature(text)}
--- EMAIL END ---

Reply:
"""

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return Response(stream_with_context(_ollama_stream(refined_prompt)),
                    mimetype="text/event-stream", headers=headers)

# Email List (before summarisation)
@app.route("/api/emails", methods=["GET"])
def api_emails():
    # Assume fetch_emails(max_results=N) function exists in run_fetch.py
    from run_fetch import fetch_emails
    raw_emails = fetch_emails(max_results=20)
    items = []
    for idx, raw in enumerate(raw_emails):
        raw = raw or ""
        cleaned = remove_signature(raw).strip()
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        subject = (lines[0] if lines else "(no subject)")[:120]
        snippet = (cleaned or raw).replace("\n", " ")[:200]
        items.append({
            "id": idx,
            "subject": subject,
            "snippet": snippet,
            "text": cleaned or raw
        })
    return jsonify(items)

# Manual Text Processing (Summarisation + Sentiment)
@app.route("/process", methods=["POST"])
def process_input():
    data = (request.json or {})
    text = (data.get("text") or "")
    lang = (data.get("lang") or "auto").lower()
    mode = (data.get("mode") or "hybrid").lower()
    cleaned = remove_signature(text)
    return jsonify({
        "summary": summarize_text(cleaned, lang, mode),
        "sentiment": analyze_sentiment(cleaned)["mapped_category"]
    })

if __name__ == "__main__":
    # If needed, enable simple CORS:
    # from flask_cors import CORS; CORS(app)
    app.run(host="0.0.0.0", port=5000, debug=True)