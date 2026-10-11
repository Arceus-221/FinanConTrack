"""T007: ground-truth check of the committed sample data.

Loads ``data/sample_expenses.csv`` and ``data/sample_profile.json`` through
``src.loader``, builds the summary with ``src.analysis.build_summary``, and
asserts the authoritative keys match ``data/expected_summary.json``: ``months``,
``total_spend``, ``by_category``, ``by_month``, ``total_income``, ``savings``,
``savings_rate`` and ``largest_single_expense`` (floats within ``1e-6``;
``savings_rate`` at 4 dp per the data-model's ground-truth contract).

Only local files are read — this module makes no network calls.
"""

import json
from pathlib import Path

from src.analysis import build_summary
from src.loader import load_expenses, load_profile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TOL = 1e-6


def _approx(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= TOL


def _load() -> tuple[dict, list, dict]:
    df, issues = load_expenses(DATA / "sample_expenses.csv")
    profile = load_profile(DATA / "sample_profile.json")
    expected = json.loads((DATA / "expected_summary.json").read_text(encoding="utf-8"))
    return build_summary(profile, df), issues, expected


def test_sample_data_loads_without_issues():
    _, issues, _ = _load()

    assert issues == []


def test_sample_summary_matches_expected_summary():
    summary, _, expected = _load()

    assert summary["months"] == expected["months"]
    assert _approx(summary["total_spend"], expected["total_spend"])

    assert set(summary["by_category"]) == set(expected["by_category"])
    for category, value in expected["by_category"].items():
        assert _approx(summary["by_category"][category], value), category

    assert set(summary["by_month"]) == set(expected["by_month"])
    for month, value in expected["by_month"].items():
        assert _approx(summary["by_month"][month], value), month

    assert _approx(summary["total_income"], expected["total_income"])
    assert _approx(summary["savings"], expected["savings"])

    # savings_rate is compared at 4 dp.
    assert _approx(round(summary["savings_rate"], 4), expected["savings_rate"])

    largest = summary["largest_single_expense"]
    expected_largest = expected["largest_single_expense"]
    assert largest["description"] == expected_largest["description"]
    assert _approx(largest["amount"], expected_largest["amount"])
