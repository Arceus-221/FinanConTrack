"""T012: Ensure advice invents no numbers (spec criterion SC-005).

Tests both the offline rule-based advisor and a mocked Gemini advisor through
the ``src.validator.validate_advice`` function. Every number that appears in
the generated advice text must trace back to the computed summary.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from src import advisor
from src.advisor import get_advice, rule_based_advice
from src.analysis import build_summary
from src.validator import extract_numbers, validate_advice

# Hand-checked fixture — same as test_advisor.py.
ROWS = [
    {"date": "2026-07-01", "description": "Apartment rent", "category": "Rent", "amount": 900},
    {"date": "2026-07-05", "description": "Groceries", "category": "Food", "amount": 300},
    {
        "date": "2026-07-10",
        "description": "Cinema night",
        "category": "Entertainment",
        "amount": 120,
    },
    {"date": "2026-08-01", "description": "Apartment rent", "category": "Rent", "amount": 900},
    {"date": "2026-08-05", "description": "Groceries", "category": "Food", "amount": 320},
]

PROFILE = {
    "occupation": "software engineer",
    "city": "Example City",
    "monthly_income": 1900.0,
    "currency": "USD",
    "savings_goal": "save 20% of income",
}


@pytest.fixture(autouse=True)
def _remove_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def _summary() -> dict:
    return build_summary(PROFILE, pd.DataFrame(ROWS))


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> None:
        return None


def _gemini_body(text: str) -> bytes:
    payload = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return json.dumps(payload).encode("utf-8")


# --- extract_numbers unit tests ---


def test_extract_numbers_integers_and_decimals():
    nums = extract_numbers("You spent 4,782.97 USD across 3 months.")
    assert 4782.97 in nums
    assert 3.0 in nums


def test_extract_numbers_percentages():
    nums = extract_numbers("Your savings rate is 16%.")
    assert 16.0 in nums
    # The decimal form should also be present.
    assert 0.16 in nums


def test_extract_numbers_empty_string():
    assert extract_numbers("") == set()


# --- validate_advice integration tests ---


def test_rule_based_advice_invents_no_numbers():
    """SC-005: rule-based advice uses only summary figures."""
    summary = _summary()
    advice = rule_based_advice(PROFILE, summary)
    problems = validate_advice(advice.text, summary)
    assert problems == [], f"rule-based advice invented numbers: {problems}"


def test_get_advice_offline_invents_no_numbers():
    """SC-005: get_advice in offline mode uses only summary figures."""
    summary = _summary()
    advice = get_advice(PROFILE, summary)
    assert advice.source == "offline"
    problems = validate_advice(advice.text, summary)
    assert problems == [], f"offline advice invented numbers: {problems}"


def test_gemini_advice_invents_no_numbers(monkeypatch):
    """SC-005: when Gemini returns text using summary figures, validation passes."""
    summary = _summary()
    total = summary["total_spend"]
    rate_pct = round(summary["savings_rate"] * 100)
    gemini_text = (
        f"You spent {total:,.2f} USD. Your savings rate is {rate_pct}%. "
        "This is general guidance, not professional financial advice."
    )
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        advisor,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(_gemini_body(gemini_text)),
    )

    advice = get_advice(PROFILE, summary)
    assert advice.source == "gemini"
    problems = validate_advice(advice.text, summary)
    assert problems == [], f"gemini advice invented numbers: {problems}"


def test_gemini_advice_with_invented_number_fails_validation(monkeypatch):
    """SC-005: a Gemini response that invents a number is detected."""
    summary = _summary()
    gemini_text = "You should save exactly 42,999.00 USD per month. General guidance."
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        advisor,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(_gemini_body(gemini_text)),
    )

    advice = get_advice(PROFILE, summary)
    assert advice.source == "gemini"
    problems = validate_advice(advice.text, summary)
    assert len(problems) > 0, "should have detected invented numbers"
