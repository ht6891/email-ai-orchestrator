# email_cleaner.py

SIGNATURE_STARTERS = [
    "CONFIDENTIALITY AND DISCLAIMER NOTICE",
    "Sekyee Business ICT Solutions",
    "173 Junction Road",
    "Email:",
    "www.sekyee.co.uk",
    "icon",
    "*From:*",
    "*Sent:*",
    "*To:*",
    "*Subject:*"
]

def remove_signature(text):
    """
    이메일 본문에서 시그니처/주소/푸터 등 불필요한 정보 제거
    시그니처 시작 키워드가 발견되면 해당 줄부터 모두 제거
    """
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        if any(kw.lower() in line.lower() for kw in SIGNATURE_STARTERS):
            break  # 여기서부터 시그니처 시작이라고 간주하고 제거
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
