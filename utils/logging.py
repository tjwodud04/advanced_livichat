# utils/logging.py
import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b\d{2,3}-\d{3,4}-\d{4}\b")

def redact_pii(s: str) -> str:
    s = EMAIL_RE.sub("[email]", s or "")
    s = PHONE_RE.sub("[phone]", s)
    return s
