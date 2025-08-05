# process_emails.py

import requests
from gmail_service import get_recent_emails

API_URL = "http://localhost:5000"  # Flask 앱이 실행 중이어야 함

def process_email(email_text):
    # 1. 요약 요청
    summ_res = requests.post(f"{API_URL}/summarize", json={"text": email_text})
    summary = summ_res.json().get("summary", "N/A")

    # 2. 감정 분석 요청
    sent_res = requests.post(f"{API_URL}/sentiment", json={"text": email_text})
    sentiment = sent_res.json()

    # 3. 답장 생성 요청
    reply_res = requests.post(f"{API_URL}/reply", json={"text": email_text})
    reply = reply_res.json().get("reply", "N/A")

    return summary, sentiment, reply

if __name__ == "__main__":
    emails = get_recent_emails()

    for i, email in enumerate(emails, 1):
        print(f"\n===== Email {i} =====")
        print(f"📩 Original:\n{email[:500]}...\n")

        summary, sentiment, reply = process_email(email)

        print(f"📝 Summary:\n{summary}")
        print(f"📊 Sentiment: {sentiment.get('label')} ({sentiment.get('score'):.2f})")
        print(f"💬 Suggested Reply:\n{reply}\n")