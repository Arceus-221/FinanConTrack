"""T003/T004: ``src/analysis`` tests.

T003: a hand-checked 2-month DataFrame is turned into a JSON-serializable
summary whose every documented key matches the hand-computed value within
``1e-6``, and ``savings_rate`` is ``None`` when the profile's monthly income
is 0.

T004: the 50/30/20 budget comparison matches hand-computed
targets/actual/gaps, a wants expense over 20% of monthly income yields a
``large_vs_income`` flag, and a balanced dataset returns an empty flag list
without error. The ground-truth keys stay unchanged.
"""

import json

import pandas as pd
from src.analysis import build_summary, unusual_spend_flags

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


def test_budget_comparison_matches_hand_checked_values():
    comparison = build_summary(PROFILE, _frame())["budget_comparison"]

    assert comparison["targets"] == {"needs": 0.50, "wants": 0.30, "savings": 0.20}

    # needs = Rent 1750 + Food 300 = 2050; wants = Entertainment 50 + Shopping 200 = 250;
    # savings = 4000 income - 2300 spend = 1700; each as a share of 4000 income.
    expected_actual = {
        "needs": round(2050.0 / 4000.0, 4),
        "wants": round(250.0 / 4000.0, 4),
        "savings": round(1700.0 / 4000.0, 4),
    }
    assert comparison["actual"] == expected_actual

    expected_gaps = {
        bucket: round(expected_actual[bucket] - target, 4)
        for bucket, target in comparison["targets"].items()
    }
    assert comparison["gaps"] == expected_gaps
    assert comparison["gaps"]["needs"] > 0  # over the 50% target
    assert comparison["gaps"]["wants"] < 0  # under the 30% target
    assert comparison["gaps"]["savings"] > 0  # over the 20% target

    # The mapping actually used, for transparency.
    assert comparison["buckets"] == {
        "Entertainment": "wants",
        "Food": "needs",
        "Rent": "needs",
        "Shopping": "wants",
    }


def test_wants_expense_over_income_ratio_yields_large_vs_income_flag():
    df = pd.DataFrame(
        [
            {
                "date": "2026-07-05",
                "description": "Cinema tickets",
                "category": "Entertainment",
                "amount": 250,
            },
        ]
    )
    flags = unusual_spend_flags({"monthly_income": 1000.0}, df)

    assert [flag["type"] for flag in flags] == ["large_vs_income"]
    assert flags[0]["amount"] == 250.0
    assert "250.00" in flags[0]["detail"]
    assert flags[0]["label"].startswith("Entertainment in 2026-07")


def test_balanced_dataset_returns_empty_flag_list():
    rows = [
        {"date": "2026-07-01", "description": "Rent", "category": "Rent", "amount": 2000},
        {"date": "2026-07-05", "description": "Groceries", "category": "Food", "amount": 500},
        {"date": "2026-07-10", "description": "Cinema", "category": "Entertainment", "amount": 100},
        {"date": "2026-08-01", "description": "Rent", "category": "Rent", "amount": 2000},
        {"date": "2026-08-05", "description": "Groceries", "category": "Food", "amount": 500},
        {"date": "2026-08-10", "description": "Cinema", "category": "Entertainment", "amount": 100},
    ]
    profile = {"monthly_income": 5000.0, "currency": "USD"}
    summary = build_summary(profile, pd.DataFrame(rows))

    # Wants expenses (100) are far below 20% of income (1000); months and
    # category months are identical, so no outlier flags and no error.
    assert summary["unusual_flags"] == []


def test_month_outlier_flag():
    # Median is 1000. 1.5 * 1000 = 1500 threshold.
    # 2026-07: 1000, 2026-08: 1000, 2026-09: 2000
    rows = [
        {"date": "2026-07-01", "description": "1", "category": "Rent", "amount": 1000},
        {"date": "2026-08-01", "description": "2", "category": "Rent", "amount": 1000},
        {"date": "2026-09-01", "description": "3", "category": "Rent", "amount": 2000},
    ]
    flags = unusual_spend_flags(None, pd.DataFrame(rows))

    assert any(f["type"] == "month_outlier" for f in flags)
    assert any(f["label"] == "Total in 2026-09" for f in flags)


def test_category_outlier_flag():
    # Category "Rent"
    # Median is 1000. 2.0 * 1000 = 2000 threshold.
    # 2026-07: 1000, 2026-08: 1000, 2026-09: 3000
    rows = [
        {"date": "2026-07-01", "description": "1", "category": "Rent", "amount": 1000},
        {"date": "2026-08-01", "description": "2", "category": "Rent", "amount": 1000},
        {"date": "2026-09-01", "description": "3", "category": "Rent", "amount": 3000},
    ]
    flags = unusual_spend_flags(None, pd.DataFrame(rows))

    assert any(f["type"] == "category_outlier" for f in flags)
    assert any(f["label"] == "Rent in 2026-09" for f in flags)


def test_empty_summary_has_budget_comparison_and_flags_keys():
    summary = build_summary(None, None)

    assert summary["budget_comparison"]["targets"] == {
        "needs": 0.50,
        "wants": 0.30,
        "savings": 0.20,
    }
    assert summary["budget_comparison"]["actual"] == {"needs": None, "wants": None, "savings": None}
    assert summary["budget_comparison"]["gaps"] == {"needs": None, "wants": None, "savings": None}
    assert summary["unusual_flags"] == []
