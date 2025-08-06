import requests
from gmail_service import get_recent_emails
from email_cleaner import remove_signature
from db import save_email  # ✅ DB 모듈 추가

API_URL = "http://localhost:5000"

def process_email(email_text):
    # 1. 요약
    summ_res = requests.post(f"{API_URL}/summarize", json={"text": email_text})
    summary = summ_res.json().get("summary", "N/A")

    # 2. 감정 분석
    sent_res = requests.post(f"{API_URL}/sentiment", json={"text": email_text})
    sentiment = sent_res.json()

    # 3. 답장 생성
    reply_res = requests.post(f"{API_URL}/reply", json={"text": email_text})
    reply = reply_res.json().get("reply", "N/A")

    return summary, sentiment, reply

if __name__ == "__main__":
    from db import init_db
    init_db()  # ✅ 테이블 생성 (한 번만 실행되면 됨)

    emails = get_recent_emails()

    for i, email in enumerate(emails, 1):
        print(f"\n===== Email {i} =====")
        print(f"📩 Original:\n{email[:500]}...\n")

        # ✅ 시그니처 제거
        cleaned_email = remove_signature(email)
        print(f"📩 Cleaned:\n{cleaned_email[:500]}...\n")

        summary, sentiment, reply = process_email(cleaned_email)

        print(f"📝 Summary:\n{summary}")
        print(f"📊 Sentiment: {sentiment.get('label')} ({sentiment.get('score'):.2f})")
        print(f"💬 Suggested Reply:\n{reply}\n")

        # ✅ DB 저장
        email_data = {
            "email_id": f"email_{i}",
            "sender": "Unknown",         # 추출 가능하면 수정
            "subject": f"Email Subject {i}",  # 추출 가능하면 수정
            "original_body": email,
            "cleaned_body": cleaned_email,
            "summary": summary,
            "sentiment_label": sentiment.get("label"),
            "sentiment_score": sentiment.get("score"),
            "reply": reply,
        }
        save_email(email_data)
