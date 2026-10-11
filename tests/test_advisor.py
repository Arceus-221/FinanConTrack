"""T005: offline rule-based advice from ``src/advisor``.

Every test removes ``GEMINI_API_KEY`` from the environment, so ``get_advice``
must resolve to the offline rules (``source == "offline"``). The advice must
cover how to review spending, how to rebalance toward the savings goal, and
what to adjust, cite figures already present in the summary (the largest
single expense and the savings rate), and label itself general guidance rather
than professional advice. No network call is made anywhere in this module.
"""

import pandas as pd
import pytest
from src.advisor import Advice, get_advice, rule_based_advice
from src.analysis import build_summary

# Hand-checked 2-month fixture. Largest positive expense is "Apartment rent".
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
    """Tests never call the network: ensure no Gemini key is configured."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def _summary() -> dict:
    return build_summary(PROFILE, pd.DataFrame(ROWS))


def test_rule_based_advice_returns_advice_with_offline_source():
    advice = rule_based_advice(PROFILE, _summary())

    assert isinstance(advice, Advice)
    assert advice.source == "offline"
    assert advice.text.strip()


def test_get_advice_is_offline_when_api_key_is_absent():
    advice = get_advice(PROFILE, _summary())

    assert advice.source == "offline"


def test_text_cites_largest_expense_and_general_guidance_label():
    summary = _summary()
    text = get_advice(PROFILE, summary).text

    largest = summary["largest_single_expense"]
    assert largest["description"] in text
    assert "general guidance" in text.lower()
    assert "not professional" in text.lower()


def test_text_covers_review_rebalance_and_adjust():
    text = get_advice(PROFILE, _summary()).text.lower()

    assert "review" in text
    assert "rebalance" in text
    assert "adjust" in text


def test_text_cites_the_savings_rate_figure():
    summary = _summary()
    text = get_advice(PROFILE, summary).text

    assert f"{summary['savings_rate']:.0%}" in text
    assert summary["largest_single_expense"]["description"] in text


def test_offline_advice_handles_empty_summary_without_error():
    advice = get_advice({}, build_summary(None, None))

    assert advice.source == "offline"
    assert "general guidance" in advice.text.lower()
