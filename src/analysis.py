"""Deterministic spending analysis for the Personal Finance Consultant.

Every number shown to the user is computed here with pandas; the advisor layer
only turns the resulting summary into prose. ``build_summary(profile, df)``
returns a JSON-serializable dict describing the covered period: number of
months, total spend, per-category totals and percentages, per-month totals,
total income for the period, savings and savings rate (``None`` when income is
0), the single largest positive expense, the 50/30/20 budget comparison, and
unusual-spend flags.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

UNCATEGORIZED = "Uncategorized"
DEFAULT_CURRENCY = "USD"

#: All ratios and percentages are rounded to 4 decimal places.
PERCENT_DP = 4

#: Category -> 50/30/20 bucket. Any category not listed here defaults to
#: ``wants`` (see the spec's budget-rule decision).
CATEGORY_BUCKETS: dict[str, str] = {
    "Rent": "needs",
    "Utilities": "needs",
    "Food": "needs",
    "Transport": "needs",
    "Health": "needs",
    "Education": "needs",
    "Entertainment": "wants",
    "Shopping": "wants",
    UNCATEGORIZED: "wants",
}

#: Unusual-spend detection thresholds (see the spec's decision note).
UNUSUAL_MONTH_RATIO = 1.5
UNUSUAL_CATEGORY_RATIO = 2.0
LARGE_EXPENSE_INCOME_RATIO = 0.20


def _bucket_for(category: str) -> str:
    """Map a category name to a 50/30/20 bucket (unknown -> ``wants``)."""
    return CATEGORY_BUCKETS.get(category, "wants")


def _month_series(df: pd.DataFrame) -> pd.Series:
    """Return a ``YYYY-MM`` string series, using the loader's column if present."""
    if "month" in df.columns:
        return df["month"].astype(str)
    return pd.to_datetime(df["date"]).dt.strftime("%Y-%m")


def _income_from(profile: dict[str, Any] | None) -> float:
    """Monthly income as a non-negative float (``0.0`` on blank/negative/bad input)."""
    try:
        return max(0.0, float((profile or {}).get("monthly_income") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce amounts, categories and descriptions to the analysis form."""
    df = df.copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    if "category" not in df.columns:
        df["category"] = UNCATEGORIZED
    df["category"] = df["category"].where(df["category"].notna(), UNCATEGORIZED)
    df["category"] = df["category"].astype(str).str.strip().replace("", UNCATEGORIZED)
    if "description" not in df.columns:
        df["description"] = ""
    return df


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
        "budget_comparison": budget_comparison({}),
        "unusual_flags": [],
    }


def budget_comparison(summary: dict[str, Any]) -> dict[str, Any]:
    """Compare the spending mix to the standard 50/30/20 needs/wants/savings rule.

    ``targets`` are the rule's shares, ``actual`` is each bucket's share of the
    period's total income (rounded to 4 dp), and ``gaps`` is ``actual - target``
    (positive = over budget). Savings is ``income - spend``, never a category.
    When income is 0 the shares are unavailable (``None``), mirroring
    ``savings_rate``.
    """
    targets = {"needs": 0.50, "wants": 0.30, "savings": 0.20}
    by_category = summary.get("by_category") or {}
    needs = sum(
        amount for category, amount in by_category.items() if _bucket_for(str(category)) == "needs"
    )
    wants = sum(
        amount for category, amount in by_category.items() if _bucket_for(str(category)) == "wants"
    )
    savings = float(summary.get("savings") or 0.0)
    total_income = float(summary.get("total_income") or 0.0)

    if total_income != 0:
        actual = {
            "needs": round(needs / total_income, PERCENT_DP),
            "wants": round(wants / total_income, PERCENT_DP),
            "savings": round(savings / total_income, PERCENT_DP),
        }
        gaps = {
            bucket: round(actual[bucket] - target, PERCENT_DP)
            for bucket, target in targets.items()
        }
    else:
        actual = {"needs": None, "wants": None, "savings": None}
        gaps = {"needs": None, "wants": None, "savings": None}

    buckets = {str(category): _bucket_for(str(category)) for category in by_category}
    return {"targets": targets, "actual": actual, "gaps": gaps, "buckets": buckets}


def unusual_spend_flags(
    profile: dict[str, Any] | None, df: pd.DataFrame | None
) -> list[dict[str, Any]]:
    """Flag expenses that stand out from the user's own pattern.

    Emits ``large_vs_income`` flags for single *wants*-bucket expenses above
    ``LARGE_EXPENSE_INCOME_RATIO`` of monthly income, ``month_outlier`` flags
    for months whose total exceeds ``UNUSUAL_MONTH_RATIO`` x the median month,
    and ``category_outlier`` flags for a category-month exceeding
    ``UNUSUAL_CATEGORY_RATIO`` x that category's median monthly total (only
    when the category has >= 2 months of data). An empty flag list is a valid,
    non-error outcome.
    """
    monthly_income = _income_from(profile)
    if df is None or len(df) == 0:
        return []

    df = _normalize_frame(df)
    df["month"] = _month_series(df)
    flags: list[dict[str, Any]] = []

    if monthly_income > 0:
        threshold = LARGE_EXPENSE_INCOME_RATIO * monthly_income
        wants = df[df["category"].map(_bucket_for) == "wants"]
        for _, row in wants[wants["amount"] > threshold].iterrows():
            flags.append(
                {
                    "type": "large_vs_income",
                    "label": f"{row['category']} in {row['month']}",
                    "detail": (
                        f"{row['description'] or row['category']} ({row['amount']:.2f}) exceeds "
                        f"{LARGE_EXPENSE_INCOME_RATIO:.0%} of monthly income"
                    ),
                    "amount": float(row["amount"]),
                }
            )

    month_totals = df.groupby("month")["amount"].sum()
    if len(month_totals) >= 2:
        median_month = float(month_totals.median())
        month_threshold = UNUSUAL_MONTH_RATIO * median_month
        for month_name, total in month_totals.items():
            if total > month_threshold:
                flags.append(
                    {
                        "type": "month_outlier",
                        "label": f"Total in {month_name}",
                        "detail": (
                            f"{month_name} spending ({total:.2f}) exceeds "
                            f"{UNUSUAL_MONTH_RATIO:.1f}x the median month ({median_month:.2f})"
                        ),
                        "amount": float(total),
                    }
                )

    for category, group in df.groupby("category"):
        category_months = group.groupby("month")["amount"].sum()
        if len(category_months) >= 2:
            median_category = float(category_months.median())
            category_threshold = UNUSUAL_CATEGORY_RATIO * median_category
            for month_name, total in category_months.items():
                if total > category_threshold:
                    flags.append(
                        {
                            "type": "category_outlier",
                            "label": f"{category} in {month_name}",
                            "detail": (
                                f"{category} spending ({total:.2f}) in {month_name} exceeds "
                                f"{UNUSUAL_CATEGORY_RATIO:.1f}x its median month "
                                f"({median_category:.2f})"
                            ),
                            "amount": float(total),
                        }
                    )

    return flags


def build_summary(profile: dict[str, Any] | None, df: pd.DataFrame | None) -> dict[str, Any]:
    """Compute the spending summary from a normalized expense DataFrame.

    ``df`` is expected to come from ``src.loader`` (with a ``month`` column) but
    a plain frame with ``date`` and ``amount`` also works. Refunds (negative
    amounts) reduce totals; blank categories fold into ``"Uncategorized"``. The
    ground-truth keys (from the T003 contract) are unchanged; ``budget_comparison``
    and ``unusual_flags`` are added on top.
    """
    profile = profile or {}
    currency = profile.get("currency") or DEFAULT_CURRENCY
    monthly_income = _income_from(profile)

    if df is None or len(df) == 0:
        return _empty_summary(currency)

    df = _normalize_frame(df)
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

    summary = {
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
    summary["budget_comparison"] = budget_comparison(summary)
    summary["unusual_flags"] = unusual_spend_flags(profile, df)
    return summary