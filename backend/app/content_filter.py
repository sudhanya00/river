"""Server-side content filter for messages and notes. The client mirrors it for instant feedback."""
import re
from pathlib import Path

_WORDLIST = Path(__file__).with_name("wordlist.txt")

BLOCKED_WORDS = "That includes words the river doesn’t carry. Try rewording it."
BLOCKED_PII = "Remove phone numbers and email addresses. Messages stay anonymous."

_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_PHONE = re.compile(r"\d{10,}")


def _load_terms() -> list[re.Pattern[str]]:
    terms = []
    for line in _WORDLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            terms.append(re.compile(r"\b" + re.escape(line) + r"\b"))
    return terms


_TERMS = _load_terms()


def check(text: str) -> str | None:
    """Return a user-facing reason if the text is blocked, else None."""
    low = text.lower()
    if any(t.search(low) for t in _TERMS):
        return BLOCKED_WORDS
    if _PHONE.search(re.sub(r"[\s\-().+]", "", text)) or _EMAIL.search(text):
        return BLOCKED_PII
    return None
