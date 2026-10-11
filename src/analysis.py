"""Deterministic spending analysis for the Personal Finance Consultant.

Every number shown to the user is computed here with pandas; the advisor layer
only turns the resulting summary into prose. ``build_summary(profile, df)``
returns a JSON-serializable dict describing the covered period: number of
months, total spend, per-category totals and percentages, per-month totals,
total income for the period, savings and savings rate (``None`` when income is
0), and the single largest positive expense.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

UNCATEGORIZED = "Uncategorized"
DEFAULT_CURRENCY = "USD"

#: All ratios and percentages are rounded to 4 decimal places.
PERCENT_DP = 4


def _month_series(df: pd.DataFrame) -> pd.Series:
    """Return a ``YYYY-MM`` string series, using the loader's column if present."""
    if "month" in df.columns:
        return df["month"].astype(str)
    return pd.to_datetime(df["date"]).dt.strftime("%Y-%m")


def _empty_summary(currency: str) -> dict[str, Any]:
    return {
        "months": 0,
        "total_spend": 0.0,
        "by_category": {},
        "by_category_percent": {},
        "by_month": {},
        "total_income": 0.0,
        "savings": 0.0,
        "savings_rate": None,
        "largest_single_expense": None,
        "currency": currency,
    }


def build_summary(profile: dict[str, Any] | None, df: pd.DataFrame | None) -> dict[str, Any]:
    """Compute the spending summary from a normalized expense DataFrame.

    ``df`` is expected to come from ``src.loader`` (with a ``month`` column) but
    a plain frame with ``date`` and ``amount`` also works. Refunds (negative
    amounts) reduce totals; blank categories fold into ``"Uncategorized"``.
    """
    profile = profile or {}
    currency = profile.get("currency") or DEFAULT_CURRENCY
    try:
        monthly_income = float(profile.get("monthly_income") or 0.0)
    except (TypeError, ValueError):
        monthly_income = 0.0

    if df is None or len(df) == 0:
        return _empty_summary(currency)

    df = df.copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    if "category" not in df.columns:
        df["category"] = UNCATEGORIZED
    df["category"] = df["category"].where(df["category"].notna(), UNCATEGORIZED)
    df["category"] = df["category"].astype(str).str.strip().replace("", UNCATEGORIZED)
    if "description" not in df.columns:
        df["description"] = ""

    month = _month_series(df)
    months = int(month.nunique())
    total_spend = float(df["amount"].sum())

    category_totals = df.groupby("category")["amount"].sum().sort_index()
    by_category = {str(name): float(value) for name, value in category_totals.items()}
    if total_spend != 0:
        by_category_percent = {
            name: round(value / total_spend, PERCENT_DP) for name, value in by_category.items()
        }
    else:
        by_category_percent = {name: 0.0 for name in by_category}

    month_totals = df.assign(month=month).groupby("month")["amount"].sum().sort_index()
    by_month = {str(name): float(value) for name, value in month_totals.items()}

    total_income = monthly_income * months
    savings = total_income - total_spend
    savings_rate = None if total_income == 0 else round(savings / total_income, PERCENT_DP)

    largest_single_expense = None
    positives = df[df["amount"] > 0]
    if not positives.empty:
        index = positives["amount"].idxmax()
        largest_single_expense = {
            "description": str(df.loc[index, "description"]),
            "amount": float(df.loc[index, "amount"]),
        }

    return {
        "months": months,
        "total_spend": total_spend,
        "by_category": by_category,
        "by_category_percent": by_category_percent,
        "by_month": by_month,
        "total_income": total_income,
        "savings": savings,
        "savings_rate": savings_rate,
        "largest_single_expense": largest_single_expense,
        "currency": currency,
    }
