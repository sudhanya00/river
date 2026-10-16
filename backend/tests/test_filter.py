import pytest

from app.content_filter import BLOCKED_PII, BLOCKED_WORDS, check


@pytest.mark.parametrize("text", ["what the fuck", "Shit happens", "please KYS", "just kill yourself"])
def test_blocks_wordlist_terms(text):
    assert check(text) == BLOCKED_WORDS


@pytest.mark.parametrize(
    "text",
    ["call me 9876543210", "ring 98765 43210", "+91 98765-43210", "(987) 654-3210 x", "mail me a.b@example.com"],
)
def test_blocks_phone_numbers_and_emails(text):
    assert check(text) == BLOCKED_PII


@pytest.mark.parametrize(
    "text",
    [
        "Shitake mushrooms are underrated.",  # word boundary
        "Rode 400 km alone this weekend.",
        "Met at 3rd Feb, 2026 at 10:30.",
        "I scored 98 in maths and 87 in science",
    ],
)
def test_allows_clean_text(text):
    assert check(text) is None
