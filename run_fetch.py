# run_fetch.py
from gmail_service import get_recent_emails

def fetch_emails(max_results=10):
    emails = get_recent_emails(max_results=max_results)
    # Preview output to console
    for i, email in enumerate(emails, 1):
        print(f"\n----- Email {i} -----\n{(email or '')[:500]}...\n")
    return emails
