# gmail_service.py

import os.path
import base64
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API에서 사용할 권한 범위
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_gmail_service():
    """OAuth 인증 후 Gmail API 서비스 객체 생성"""
    creds = None

    # token.json에 이전 인증 토큰이 있으면 사용
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # 없거나 만료되었으면 새로 인증
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # 인증 후 저장
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Gmail 서비스 객체 생성
    service = build('gmail', 'v1', credentials=creds)
    return service


def extract_body_from_payload(payload):
    """다양한 구조에 대응하여 이메일 본문(text/plain 또는 html) 추출"""
    def decode_base64(data):
        return base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8', errors='ignore')

    def get_plain_text(part):
        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")
        if mime_type == "text/plain" and data:
            return decode_base64(data)
        elif mime_type == "text/html" and data:
            html = decode_base64(data)
            return re.sub('<[^<]+?>', '', html)
        return ""

    # 1. 가장 바깥쪽 본문 추출 시도
    if "body" in payload and payload["body"].get("data"):
        return decode_base64(payload["body"]["data"])

    # 2. 단일 레벨 parts 처리
    if "parts" in payload:
        for part in payload["parts"]:
            body = get_plain_text(part)
            if body:
                return body.strip()

            # 3. 중첩 parts 재귀 처리
            if "parts" in part:
                for subpart in part["parts"]:
                    body = get_plain_text(subpart)
                    if body:
                        return body.strip()

    return "(No readable body found)"



def get_recent_emails(max_results=5):
    """최근 이메일 본문 max_results 개 가져오기"""
    service = get_gmail_service()

    results = service.users().messages().list(
        userId='me', labelIds=['INBOX'], maxResults=max_results).execute()
    messages = results.get('messages', [])

    email_bodies = []
    for msg in messages:
        msg_data = service.users().messages().get(
            userId='me', id=msg['id'], format='full').execute()
        payload = msg_data.get('payload', {})
        body = extract_body_from_payload(payload)
        email_bodies.append(body)

    return email_bodies


# 테스트 실행용
if __name__ == "__main__":
    emails = get_recent_emails()
    for i, email in enumerate(emails, 1):
        print(f"\n----- Email {i} -----\n{email[:500]}...\n")
