# email_cleaner.py

SIGNATURE_STARTERS = [
    "CONFIDENTIALITY",  # Existing English Signatures
    "Sekyee Business ICT Solutions",
    "173 Junction Road",
    "Facebook icon", "LinkedIn icon", "Twitter icon", "Logo",
    "*From:*", "*Sent:*", "*To:*", "*Subject:*",
    "Email:", "www.sekyee.co.uk",
    "이 전자우편", "기밀한 정보", "귀하가 이 전자우편", "KB국민은행", "https://www.kbstar.com"
]


def remove_signature(text):
    """
    Remove signatures/addresses/footers from email body
    Remove everything from the line containing specific keywords onward
    """
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        # Search keywords after trimming spaces and converting to lowercase
        stripped_line = line.strip().lower()
        if any(kw.lower() in stripped_line for kw in SIGNATURE_STARTERS):
            break  # Signature Start
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()

