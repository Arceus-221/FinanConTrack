"""Advice generation for the Personal Finance Consultant.

``rule_based_advice(profile, summary)`` turns a pre-computed summary dict into
plain-language advice. It performs no arithmetic: every figure it mentions is
read directly from the summary produced by ``src.analysis``. ``get_advice``
dispatches to the rule-based path whenever ``GEMINI_API_KEY`` is absent, so the
app keeps working fully offline. All advice is labelled general guidance rather
than professional financial advice.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

#: Shown with every piece of advice (FR-022).
DISCLAIMER = (
    "This is general guidance, not professional financial advice. "
    "For decisions about debt, taxes or investments, consult a qualified professional."
)


@dataclass(frozen=True)
class Advice:
    """Advice text plus where it came from (``"offline"`` or ``"gemini"``)."""

    text: str
    source: str


def _format_amount(value: Any, currency: str) -> str:
    try:
        return f"{float(value):,.2f} {currency}"
    except (TypeError, ValueError):
        return f"0.00 {currency}"


def _review_lines(summary: dict[str, Any]) -> list[str]:
    """How to review spending, citing the summary's own figures."""
    currency = summary.get("currency") or "USD"
    lines: list[str] = []

    months = summary.get("months") or 0
    total_spend = summary.get("total_spend")
    total_income = summary.get("total_income")
    lines.append(
        f"Across {months} month(s) you spent {_format_amount(total_spend, currency)} "
        f"against {_format_amount(total_income, currency)} of income."
    )

    largest = summary.get("largest_single_expense")
    if largest:
        description = largest.get("description") or "an unnamed expense"
        lines.append(
            f"Your largest single expense was {description} at "
            f"{_format_amount(largest.get('amount'), currency)} - start your review there."
        )

    by_category = summary.get("by_category") or {}
    if by_category:
        top_category = max(by_category, key=lambda name: by_category[name])
        percent = (summary.get("by_category_percent") or {}).get(top_category)
        share = f" ({percent:.0%} of spend)" if percent is not None else ""
        lines.append(
            f"Your biggest category was {top_category} at "
            f"{_format_amount(by_category[top_category], currency)}{share}."
        )
    else:
        lines.append(
            "No category totals were available yet - export a few months of transactions to review."
        )
    return lines


def _rebalance_lines(profile: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    """How to rebalance toward the savings goal, using computed shares only."""
    currency = summary.get("currency") or "USD"
    goal = profile.get("savings_goal") or "no goal set"
    lines: list[str] = []

    rate = summary.get("savings_rate")
    if rate is None:
        lines.append(
            "Your savings rate is unavailable because no monthly income was recorded; "
            f"add your income to track progress toward '{goal}'."
        )
    else:
        lines.append(
            f"Your savings rate is {rate:.0%} and you saved "
            f"{_format_amount(summary.get('savings'), currency)}; your goal is '{goal}'."
        )

    actual = (summary.get("budget_comparison") or {}).get("actual") or {}
    if actual.get("needs") is not None:
        lines.append(
            f"Against the 50/30/20 rule your mix is needs {actual['needs']:.0%} "
            f"(target 50%), wants {actual['wants']:.0%} (target 30%) and "
            f"savings {actual['savings']:.0%} (target 20%)."
        )
    return lines


def _adjust_lines(summary: dict[str, Any]) -> list[str]:
    """What to adjust, driven by the pre-computed budget gaps and flags."""
    lines: list[str] = []

    gaps = (summary.get("budget_comparison") or {}).get("gaps") or {}
    for bucket in ("needs", "wants"):
        gap = gaps.get(bucket)
        if gap is not None and gap > 0:
            lines.append(
                f"Reduce {bucket} spending by about {gap:.0%} of income to return to its target."
            )
    savings_gap = gaps.get("savings")
    if savings_gap is not None and savings_gap < 0:
        lines.append(
            f"Increase savings by about {abs(savings_gap):.0%} of income to reach the 20% target."
        )

    for flag in (summary.get("unusual_flags") or [])[:3]:
        lines.append(f"Watch this: {flag.get('detail')}.")

    if not lines:
        lines.append(
            "Your spending is close to the targets - keep tracking monthly and revisit if a "
            "category or month grows."
        )
    return lines


def _bullets(lines: list[str]) -> list[str]:
    return [f"- {line}" for line in lines]


def rule_based_advice(
    profile: dict[str, Any] | None, summary: dict[str, Any] | None
) -> Advice:
    """Turn the computed summary into offline advice (no network, no arithmetic)."""
    profile = profile or {}
    summary = summary or {}
    occupation = profile.get("occupation") or "you"
    city = profile.get("city") or "your city"

    text = "\n".join(
        [
            f"## Advice for a {occupation} in {city}",
            "",
            "### How to review your spending",
            *_bullets(_review_lines(summary)),
            "",
            "### How to rebalance toward your savings goal",
            *_bullets(_rebalance_lines(profile, summary)),
            "",
            "### What to adjust",
            *_bullets(_adjust_lines(summary)),
            "",
            f"_{DISCLAIMER}_",
        ]
    )
    return Advice(text=text, source="offline")


def get_advice(
    profile: dict[str, Any] | None, summary: dict[str, Any] | None
) -> Advice:
    """Return advice for the profile and computed summary.

    With no ``GEMINI_API_KEY`` in the environment the rule-based advisor is used.
    The Gemini request path is added in the next task; a configured key still
    resolves to the offline rules for now.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return rule_based_advice(profile, summary)
    return rule_based_advice(profile, summary)
