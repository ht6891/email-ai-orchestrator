import os.path
import base64
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Permission scopes for Gmail API
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_gmail_service():
    """Create Gmail API service object after OAuth authentication"""
    creds = None

    # Use token.json
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If missing or expired, perform new authentication
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save after authentication
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Create Gmail service object
    service = build('gmail', 'v1', credentials=creds)
    return service


def extract_body_from_payload(payload):
    """Extract email body (text/plain or HTML) handling various structures"""
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

    # 1. Attempt to extract outermost body
    if "body" in payload and payload["body"].get("data"):
        return decode_base64(payload["body"]["data"])

    # 2. Handle single-level parts
    if "parts" in payload:
        for part in payload["parts"]:
            body = get_plain_text(part)
            if body:
                return body.strip()

            # 3. Recursively handle nested parts
            if "parts" in part:
                for subpart in part["parts"]:
                    body = get_plain_text(subpart)
                    if body:
                        return body.strip()

    return "(No readable body found)"



def get_recent_emails(max_results=5):
    """Fetch the most recent email bodies (max_results)"""
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


# For test execution
if __name__ == "__main__":
    emails = get_recent_emails()
    for i, email in enumerate(emails, 1):
        print(f"\n----- Email {i} -----\n{email[:500]}...\n")
