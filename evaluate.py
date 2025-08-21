# evaluate.py
# -----------------------------------------------------------------------------
# Email AI Assistant Evaluation Script
# - Communicates with local Flask API (app.py) to measure quality/performance of summarization, sentiment, reply, and translation
# - Saves results as CSV and Markdown report
# -----------------------------------------------------------------------------
# Usage:
#   1) Run Flask server:  python app.py
#   2) Run this script:  python evaluate.py --limit 20
#      (option) --source gmail  : use recent emails from gmail_service
#      (option) --source file   : use ./test_emails.json (default)
#
# test_emails.json format (optional):
# [
#   {"text": "original email content...", "ref_summary": "human-written reference summary (if available)", "lang":"ko|en"},
#   ...
# ]
# -----------------------------------------------------------------------------

import os
import json
import time
import argparse
import statistics
from typing import List, Dict, Any

import requests
import pandas as pd

# ---- Optional Dependencies: auto-fallback if not available -------------------
try:
    from rouge_score import rouge_scorer
    ROUGE_OK = True
except Exception:
    ROUGE_OK = False

try:
    from langdetect import detect as lang_detect
    LANG_OK = True
except Exception:
    LANG_OK = False

BASE_URL = os.environ.get("EAA_BASE_URL", "http://localhost:5000")


def safe_post(path: str, payload: Dict[str, Any], timeout=300) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    t0 = time.perf_counter()
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        latency = time.perf_counter() - t0
        r.raise_for_status()
        return {"ok": True, "json": r.json(), "latency": latency}
    except Exception as e:
        return {"ok": False, "error": str(e), "latency": time.perf_counter() - t0}


def safe_get(path: str, timeout=300) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    t0 = time.perf_counter()
    try:
        r = requests.get(url, timeout=timeout)
        latency = time.perf_counter() - t0
        r.raise_for_status()
        return {"ok": True, "json": r.json(), "latency": latency}
    except Exception as e:
        return {"ok": False, "error": str(e), "latency": time.perf_counter() - t0}


def load_dataset(source: str, limit: int) -> List[Dict[str, Any]]:
    """
    source == 'gmail'  : fetch from /api/emails
    source == 'file'   : load from ./test_emails.json (fallback to /api/emails if missing)
    """
    items: List[Dict[str, Any]] = []

    if source == "gmail":
        res = safe_get("/api/emails")
        if res["ok"]:
            for it in res["json"][:limit]:
                items.append({"text": it.get("text", ""), "subject": it.get("subject", "")})
        else:
            print("[warn] /api/emails failed:", res.get("error"))
    else:
        # Prefer file first
        if os.path.exists("test_emails.json"):
            try:
                arr = json.load(open("test_emails.json", "r", encoding="utf-8"))
                for it in arr[:limit]:
                    items.append({
                        "text": it.get("text", ""),
                        "ref_summary": it.get("ref_summary", ""),
                        "lang": it.get("lang", ""),
                        "subject": it.get("subject", ""),
                    })
            except Exception as e:
                print("[warn] Failed to load test_emails.json:", e)

        # Fallback: API
        if not items:
            res = safe_get("/api/emails")
            if res["ok"]:
                for it in res["json"][:limit]:
                    items.append({"text": it.get("text", ""), "subject": it.get("subject", "")})
            else:
                print("[warn] /api/emails failed:", res.get("error"))

    # Simple Summary
    items = [it for it in items if (it.get("text") or "").strip()]
    return items[:limit]


def detect_lang(text: str) -> str:
    if not LANG_OK:
        # Simple Heuristic
        return "ko" if any("\uac00" <= ch <= "\ud7af" for ch in text) else "en"
    try:
        return lang_detect(text)
    except Exception:
        return "unknown"


def compute_rouge(sys_sum: str, ref_sum: str) -> Dict[str, float]:
    if not ROUGE_OK or not ref_sum or not sys_sum:
        return {}
    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    scores = scorer.score(ref_sum, sys_sum)
    # Collect only F1 scores
    return {k: round(v.fmeasure, 4) for k, v in scores.items()}


def compression_ratio(src: str, summ: str) -> float:
    src_len = max(1, len((src or "").split()))
    summ_len = max(1, len((summ or "").split()))
    return round(summ_len / src_len, 4)


def distinct_n(text: str, n: int) -> float:
    tokens = (text or "").split()
    if len(tokens) < n:
        return 0.0
    ngrams = set(tuple(tokens[i:i+n]) for i in range(len(tokens)-n+1))
    return round(len(ngrams) / max(1, (len(tokens)-n+1)), 4)


def evaluate_item(item: Dict[str, Any]) -> Dict[str, Any]:
    text = item.get("text", "")
    subject = item.get("subject", "")
    ref_summary = item.get("ref_summary", "")
    lang_hint = item.get("lang", "")  # optional

    out: Dict[str, Any] = {
        "subject": subject[:80],
        "lang_detected": detect_lang(text),
        "len_words": len(text.split()),
    }

    # 1) Fast summary
    r1 = safe_post("/summarize", {"text": text})
    out["sum_fast_ok"] = r1["ok"]
    out["sum_fast_latency"] = round(r1.get("latency", 0.0), 3)
    sum_fast = (r1.get("json", {}) or {}).get("summary", "") if r1["ok"] else ""
    out["sum_fast"] = sum_fast
    out["sum_fast_comp"] = compression_ratio(text, sum_fast)
    if ref_summary:
        rouge = compute_rouge(sum_fast, ref_summary)
        out["sum_fast_rouge1"] = rouge.get("rouge1", "")
        out["sum_fast_rouge2"] = rouge.get("rouge2", "")
        out["sum_fast_rougeL"] = rouge.get("rougeL", "")

    # 2) LLM summary
    r2 = safe_post("/summarize_llm", {"text": text})
    out["sum_llm_ok"] = r2["ok"]
    out["sum_llm_latency"] = round(r2.get("latency", 0.0), 3)
    sum_llm = (r2.get("json", {}) or {}).get("summary", "") if r2["ok"] else ""
    out["sum_llm"] = sum_llm
    out["sum_llm_comp"] = compression_ratio(text, sum_llm)
    if ref_summary:
        rouge = compute_rouge(sum_llm, ref_summary)
        out["sum_llm_rouge1"] = rouge.get("rouge1", "")
        out["sum_llm_rouge2"] = rouge.get("rouge2", "")
        out["sum_llm_rougeL"] = rouge.get("rougeL", "")

    # 3) Sentiment
    r3 = safe_post("/sentiment", {"text": text})
    out["sent_ok"] = r3["ok"]
    out["sent_latency"] = round(r3.get("latency", 0.0), 3)
    if r3["ok"]:
        js = r3.get("json", {})
        out["sent_label"] = js.get("label", "")
        out["sent_score"] = js.get("score", "")
        out["sent_category"] = js.get("mapped_category", "")

    # 4) Reply (measure both English and Korean)
    r4_en = safe_post("/reply", {"text": text, "lang": "en"})
    out["reply_en_ok"] = r4_en["ok"]
    out["reply_en_latency"] = round(r4_en.get("latency", 0.0), 3)
    reply_en = (r4_en.get("json", {}) or {}).get("reply", "") if r4_en["ok"] else ""
    out["reply_en"] = reply_en
    out["reply_en_len"] = len(reply_en.split())
    out["reply_en_dist1"] = distinct_n(reply_en, 1)
    out["reply_en_dist2"] = distinct_n(reply_en, 2)

    r4_ko = safe_post("/reply", {"text": text, "lang": "ko"})
    out["reply_ko_ok"] = r4_ko["ok"]
    out["reply_ko_latency"] = round(r4_ko.get("latency", 0.0), 3)
    reply_ko = (r4_ko.get("json", {}) or {}).get("reply", "") if r4_ko["ok"] else ""
    out["reply_ko"] = reply_ko
    out["reply_ko_len"] = len(reply_ko.split())
    out["reply_ko_dist1"] = distinct_n(reply_ko, 1)
    out["reply_ko_dist2"] = distinct_n(reply_ko, 2)

    # 5) Translation (both directions) — quick evaluation
    # Simple quality signal for penalty/bonus: check if language changes after translation

    # in English
    tr_en = safe_post("/translate_llm", {"text": text, "target_lang": "en"})
    out["tr_en_ok"] = tr_en["ok"]
    out["tr_en_latency"] = round(tr_en.get("latency", 0.0), 3)
    tr_en_txt = (tr_en.get("json", {}) or {}).get("translated", "") if tr_en["ok"] else ""
    out["tr_en_lang"] = detect_lang(tr_en_txt) if tr_en_txt else ""

    # in Korean
    tr_ko = safe_post("/translate_llm", {"text": text, "target_lang": "ko"})
    out["tr_ko_ok"] = tr_ko["ok"]
    out["tr_ko_latency"] = round(tr_ko.get("latency", 0.0), 3)
    tr_ko_txt = (tr_ko.get("json", {}) or {}).get("translated", "") if tr_ko["ok"] else ""
    out["tr_ko_lang"] = detect_lang(tr_ko_txt) if tr_ko_txt else ""

    return out


def summarize_table(df: pd.DataFrame) -> str:
    lines = []
    n = len(df)

    def m(series, f):
        vals = [v for v in series if isinstance(v, (int, float))]
        return round(f(vals), 3) if vals else "-"

    lines.append(f"- Samples evaluated: **{n}**")
    # Success Rate
    for key, label in [
        ("sum_fast_ok", "Summary(Fast) success"),
        ("sum_llm_ok", "Summary(LLM) success"),
        ("sent_ok", "Sentiment success"),
        ("reply_en_ok", "Reply EN success"),
        ("reply_ko_ok", "Reply KO success"),
        ("tr_en_ok", "Translate→EN success"),
        ("tr_ko_ok", "Translate→KO success"),
    ]:
        if key in df.columns:
            rate = round(100 * df[key].fillna(False).mean(), 1)
            lines.append(f"- {label}: **{rate}%**")

    # Latency
    for key, label in [
        ("sum_fast_latency", "Latency Summary(Fast) [s]"),
        ("sum_llm_latency", "Latency Summary(LLM) [s]"),
        ("sent_latency", "Latency Sentiment [s]"),
        ("reply_en_latency", "Latency Reply EN [s]"),
        ("reply_ko_latency", "Latency Reply KO [s]"),
        ("tr_en_latency", "Latency Translate→EN [s]"),
        ("tr_ko_latency", "Latency Translate→KO [s]"),
    ]:
        if key in df.columns:
            vals = [v for v in df[key].tolist() if isinstance(v, (int, float))]
            if vals:
                lines.append(f"- {label}: mean **{round(statistics.mean(vals),3)}**, median **{round(statistics.median(vals),3)}**")

    # Summarisation Compression Ratio (lower = more compressed)
    for key, label in [
        ("sum_fast_comp", "Compression(Fast)"),
        ("sum_llm_comp", "Compression(LLM)"),
    ]:
        if key in df.columns:
            vals = [v for v in df[key].tolist() if isinstance(v, (int, float))]
            if vals:
                lines.append(f"- {label}: mean **{round(statistics.mean(vals),3)}**")

    # ROUGE (if avaliable)
    if "sum_fast_rouge1" in df.columns:
        for rkey in ["sum_fast_rouge1","sum_fast_rouge2","sum_fast_rougeL",
                     "sum_llm_rouge1","sum_llm_rouge2","sum_llm_rougeL"]:
            if rkey in df.columns:
                vals = [v for v in df[rkey].tolist() if isinstance(v, (int, float))]
                if vals:
                    lines.append(f"- {rkey}: mean **{round(statistics.mean(vals),3)}**")

    # Reply Diversity
    for key, label in [
        ("reply_en_dist1","Reply EN Dist-1"),
        ("reply_en_dist2","Reply EN Dist-2"),
        ("reply_ko_dist1","Reply KO Dist-1"),
        ("reply_ko_dist2","Reply KO Dist-2"),
    ]:
        if key in df.columns:
            vals = [v for v in df[key].tolist() if isinstance(v, (int, float))]
            if vals:
                lines.append(f"- {label}: mean **{round(statistics.mean(vals),3)}**")

    return "\n".join(lines)


def write_markdown_report(df: pd.DataFrame, path_md="evaluation_report.md"):
    md = []
    md.append("# Email AI Assistant — Evaluation Report\n")
    md.append(f"Generated at: `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n")
    md.append("## Summary\n")
    md.append(summarize_table(df) + "\n")

    md.append("## Methodology\n")
    md.append(
        "- Fast Summary: Call pre-built extractive/compressive summarization pipeline\n"
        "- LLM Summary: Summarization API using LLM (`/summarize_llm`)\n"
        "- Sentiment: Multilingual sentiment model + heuristic post-adjustment (`/sentiment`)\n"
        "- Reply: Generate in both English/Korean (`/reply?lang=en|ko`) and evaluate length/diversity metrics\n"
        "- Translate: Use LLM translation (`/translate_llm`) and verify result with language detection\n"
        "- Latency: Measure wall-clock time for each API call\n"
        "- (Optional) ROUGE: Calculate if `ref_summary` is provided in test_emails.json\n"
    )

    md.append("## Sample Rows (first 5)\n")
    md.append(df.head(5).to_markdown(index=False))

    with open(path_md, "w", encoding="utf-8") as f:
        f.write("\n\n".join(md))
    print(f"[ok] Markdown report saved -> {path_md}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["file","gmail"], default="file",
                    help="Evaluation Data Sources(file: test_emails.json, gmail: /api/emails)")
    ap.add_argument("--limit", type=int, default=20, help="Number of samples to evaluate")
    ap.add_argument("--out_csv", default="evaluation_results.csv")
    ap.add_argument("--out_md", default="evaluation_report.md")
    args = ap.parse_args()

    print(f"[info] BASE_URL = {BASE_URL}")
    print(f"[info] loading dataset from: {args.source}")

    items = load_dataset(args.source, args.limit)
    if not items:
        print("[error] No data available for evaluation.")
        return

    rows = []
    for i, it in enumerate(items, 1):
        print(f"  - evaluating {i}/{len(items)} …")
        try:
            rows.append(evaluate_item(it))
        except Exception as e:
            print("    [warn] item failed:", e)
            rows.append({"subject":"(error)", "error": str(e)})

    df = pd.DataFrame(rows)
    df.to_csv(args.out_csv, index=False, encoding="utf-8-sig")
    print(f"[ok] CSV saved -> {args.out_csv}")

    write_markdown_report(df, args.out_md)

    print("\n[done] Evaluation complete.")
    print("  - Use the Markdown report for your project write-up.")
    print("  - Attach CSV as raw results appendix if needed.")


if __name__ == "__main__":
    main()