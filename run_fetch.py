# run_fetch.py
from gmail_service import get_recent_emails

emails = get_recent_emails()
for i, email in enumerate(emails, 1):
    print(f"\n----- Email {i} -----\n{email[:500]}...\n")
