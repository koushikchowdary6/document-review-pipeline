"""Long untrusted candidate secrets should use one symbol-frequency pass."""

import pytest

from redactor import MAX_INPUT_CHARS, redact, shannon_entropy


@pytest.mark.parametrize("text, expected", [
    ("", 0.0),
    ("a" * 1000, 0.0),
    ("aabb", 1.0),
    ("aabbccdd", 2.0),
])
def test_entropy_matches_exact_frequency_examples(text, expected):
    assert shannon_entropy(text) == pytest.approx(expected)


def test_long_mixed_secret_redacts_without_exposing_raw_value():
    # A long token with many distinct symbols previously triggered one full
    # string scan per symbol in the entropy fallback. Exercise the public
    # redaction API and confirm the safe-by-default findings contract.
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
    secret = alphabet * 3000
    assert len(secret) < MAX_INPUT_CHARS
    sanitized, findings = redact("before " + secret + " after")
    assert secret not in sanitized
    assert "[REDACTED:HIGH_ENTROPY_SECRET]" in sanitized
    assert sanitized.startswith("before ") and sanitized.endswith(" after")
    assert any(f.kind == "HIGH_ENTROPY_SECRET" for f in findings)
    assert all(secret not in f.value for f in findings)
