# email_cleaner.py

SIGNATURE_STARTERS = [
    "CONFIDENTIALITY",  # 기존 영문 시그니처
    "Sekyee Business ICT Solutions",
    "173 Junction Road",
    "Facebook icon", "LinkedIn icon", "Twitter icon", "Logo",
    "*From:*", "*Sent:*", "*To:*", "*Subject:*",
    "Email:", "www.sekyee.co.uk",
    "이 전자우편", "기밀한 정보", "귀하가 이 전자우편", "KB국민은행", "https://www.kbstar.com"
]


def remove_signature(text):
    """
    이메일 본문에서 시그니처/주소/푸터 제거
    키워드가 포함된 줄부터 이후 전체 제거
    """
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        # 공백 제거 후 소문자로 키워드 탐색
        stripped_line = line.strip().lower()
        if any(kw.lower() in stripped_line for kw in SIGNATURE_STARTERS):
            break  # 시그니처 시작
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()

