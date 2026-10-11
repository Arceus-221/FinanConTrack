"""T003: ``src/analysis.build_summary`` tests.

Covers the acceptance criterion: a hand-checked 2-month DataFrame is turned
into a JSON-serializable summary whose every documented key matches the
hand-computed value within ``1e-6``, and ``savings_rate`` is ``None`` when the
profile's monthly income is 0.
"""

import json

import pandas as pd
from src.analysis import build_summary

TOL = 1e-6

# Hand-checked 2-month fixture.
# 2026-07: July rent 850 + groceries 100 + cinema 50 = 1000
# 2026-08: August rent 900 + groceries 200 + jacket 300 + refund -100 = 1300
ROWS = [
    {"date": "2026-07-01", "description": "July rent", "category": "Rent", "amount": 850},
    {"date": "2026-07-05", "description": "Groceries", "category": "Food", "amount": 100},
    {"date": "2026-07-10", "description": "Cinema", "category": "Entertainment", "amount": 50},
    {"date": "2026-08-01", "description": "August rent", "category": "Rent", "amount": 900},
    {"date": "2026-08-05", "description": "Groceries", "category": "Food", "amount": 200},
    {"date": "2026-08-12", "description": "Jacket", "category": "Shopping", "amount": 300},
    {"date": "2026-08-20", "description": "Refund: jacket", "category": "Shopping", "amount": -100},
]

PROFILE = {"monthly_income": 2000.0, "currency": "USD"}


def _frame() -> pd.DataFrame:
    df = pd.DataFrame(ROWS)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _approx(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= TOL


def test_build_summary_matches_hand_checked_values():
    summary = build_summary(PROFILE, _frame())

    # Income for the period: 2000/month x 2 months.
    assert summary["months"] == 2

    # 1750 rent + 300 food + 50 entertainment + 200 shopping (300 - 100 refund).
    assert _approx(summary["total_spend"], 2300.0)

    expected_categories = {
        "Entertainment": 50.0,
        "Food": 300.0,
        "Rent": 1750.0,
        "Shopping": 200.0,
    }
    assert set(summary["by_category"]) == set(expected_categories)
    for category, value in expected_categories.items():
        assert _approx(summary["by_category"][category], value)

    # Percentages are each category's share of total spend, rounded to 4 dp.
    expected_percent = {
        "Entertainment": round(50.0 / 2300.0, 4),
        "Food": round(300.0 / 2300.0, 4),
        "Rent": round(1750.0 / 2300.0, 4),
        "Shopping": round(200.0 / 2300.0, 4),
    }
    for category, value in expected_percent.items():
        assert _approx(summary["by_category_percent"][category], value)

    expected_months = {"2026-07": 1000.0, "2026-08": 1300.0}
    assert set(summary["by_month"]) == set(expected_months)
    for month, value in expected_months.items():
        assert _approx(summary["by_month"][month], value)

    assert _approx(summary["total_income"], 4000.0)
    assert _approx(summary["savings"], 1700.0)
    assert _approx(summary["savings_rate"], 0.425)

    assert summary["largest_single_expense"] == {
        "description": "August rent",
        "amount": 900.0,
    }
    assert summary["currency"] == "USD"


def test_savings_rate_is_none_when_income_is_zero():
    summary = build_summary({"monthly_income": 0.0, "currency": "USD"}, _frame())

    assert summary["savings_rate"] is None
    assert _approx(summary["total_income"], 0.0)
    assert _approx(summary["savings"], -2300.0)
    # The rest of the summary is still produced.
    assert summary["months"] == 2
    assert _approx(summary["total_spend"], 2300.0)


def test_summary_is_json_serializable():
    summary = build_summary(PROFILE, _frame())
    assert json.loads(json.dumps(summary))["months"] == 2
