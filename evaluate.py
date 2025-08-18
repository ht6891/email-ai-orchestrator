# evaluate.py
# -----------------------------------------------------------------------------
# Email AI Assistant 평가 스크립트
# - 로컬 Flask API(app.py)와 통신하여 요약/감정/응답/번역 품질 및 성능 측정
# - 결과를 CSV와 Markdown 리포트로 저장
# -----------------------------------------------------------------------------
# 사용법:
#   1) Flask 서버 실행:  python app.py
#   2) 이 스크립트 실행: python evaluate.py --limit 20
#      (옵션) --source gmail  : gmail_service에서 최근 메일 사용
#      (옵션) --source file   : ./test_emails.json 사용 (기본)
#
# test_emails.json 포맷(옵션):
# [
#   {"text": "원문 이메일 내용...", "ref_summary": "사람이 쓴 정답 요약(있으면)", "lang":"ko|en"},
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

# ---- 선택 의존성: 없으면 자동 폴백 ------------------------------------------------
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
    source == 'gmail'  : /api/emails에서 가져옴
    source == 'file'   : ./test_emails.json에서 로드 (없으면 /api/emails 폴백)
    """
    items: List[Dict[str, Any]] = []

    if source == "gmail":
        res = safe_get("/api/emails")
        if res["ok"]:
            for it in res["json"][:limit]:
                items.append({"text": it.get("text", ""), "subject": it.get("subject", "")})
        else:
            print("[warn] /api/emails 실패:", res.get("error"))
    else:
        # file 우선
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
                print("[warn] test_emails.json 로드 실패:", e)

        # 폴백: API
        if not items:
            res = safe_get("/api/emails")
            if res["ok"]:
                for it in res["json"][:limit]:
                    items.append({"text": it.get("text", ""), "subject": it.get("subject", "")})
            else:
                print("[warn] /api/emails 실패:", res.get("error"))

    # 간단 정리
    items = [it for it in items if (it.get("text") or "").strip()]
    return items[:limit]


def detect_lang(text: str) -> str:
    if not LANG_OK:
        # 간단 휴리스틱
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
    # F1 기준만 취합
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

    # 4) Reply (영/한 모두 측정)
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

    # 5) 번역(양방향) — 짧게 측정
    #   감점/보너스용 단순 품질 신호: 번역 후 언어 변화 여부
    # 영어로
    tr_en = safe_post("/translate_llm", {"text": text, "target_lang": "en"})
    out["tr_en_ok"] = tr_en["ok"]
    out["tr_en_latency"] = round(tr_en.get("latency", 0.0), 3)
    tr_en_txt = (tr_en.get("json", {}) or {}).get("translated", "") if tr_en["ok"] else ""
    out["tr_en_lang"] = detect_lang(tr_en_txt) if tr_en_txt else ""

    # 한국어로
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
    # 성공률
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

    # 지연시간
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

    # 요약 압축률(낮을수록 더 축약)
    for key, label in [
        ("sum_fast_comp", "Compression(Fast)"),
        ("sum_llm_comp", "Compression(LLM)"),
    ]:
        if key in df.columns:
            vals = [v for v in df[key].tolist() if isinstance(v, (int, float))]
            if vals:
                lines.append(f"- {label}: mean **{round(statistics.mean(vals),3)}**")

    # ROUGE (있을 경우)
    if "sum_fast_rouge1" in df.columns:
        for rkey in ["sum_fast_rouge1","sum_fast_rouge2","sum_fast_rougeL",
                     "sum_llm_rouge1","sum_llm_rouge2","sum_llm_rougeL"]:
            if rkey in df.columns:
                vals = [v for v in df[rkey].tolist() if isinstance(v, (int, float))]
                if vals:
                    lines.append(f"- {rkey}: mean **{round(statistics.mean(vals),3)}**")

    # Reply 다양성
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
        "- Fast Summary: 사전 구축된 추출/압축 요약 파이프라인 호출\n"
        "- LLM Summary: LLM을 이용한 요약 API(`/summarize_llm`) 호출\n"
        "- Sentiment: 다국어 감정 모델 + 휴리스틱 사후보정(`/sentiment`)\n"
        "- Reply: 영어/한국어 2종 생성(`/reply?lang=en|ko`) 후 길이/다양성 지표 산출\n"
        "- Translate: LLM 번역(`/translate_llm`) 후 언어감지로 결과 확인\n"
        "- 지연시간: 각 API 호출 벽시계 기준 측정\n"
        "- (선택) ROUGE: test_emails.json에 ref_summary가 있을 경우 계산\n"
    )

    md.append("## Sample Rows (first 5)\n")
    md.append(df.head(5).to_markdown(index=False))

    with open(path_md, "w", encoding="utf-8") as f:
        f.write("\n\n".join(md))
    print(f"[ok] Markdown report saved -> {path_md}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["file","gmail"], default="file",
                    help="평가 데이터 소스(file: test_emails.json, gmail: /api/emails)")
    ap.add_argument("--limit", type=int, default=20, help="평가할 샘플 개수")
    ap.add_argument("--out_csv", default="evaluation_results.csv")
    ap.add_argument("--out_md", default="evaluation_report.md")
    args = ap.parse_args()

    print(f"[info] BASE_URL = {BASE_URL}")
    print(f"[info] loading dataset from: {args.source}")

    items = load_dataset(args.source, args.limit)
    if not items:
        print("[error] 평가할 데이터가 없습니다.")
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