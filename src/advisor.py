"""Advice generation for the Personal Finance Consultant.

``rule_based_advice(profile, summary)`` turns a pre-computed summary dict into
plain-language advice. It performs no arithmetic: every figure it mentions is
read directly from the summary produced by ``src.analysis``. ``get_advice``
prefers the Gemini REST API when ``GEMINI_API_KEY`` is present and silently
falls back to the rule-based path on a missing key, an exception, a timeout or
an unparseable response, so the app keeps working fully offline. The request
key is sent in the ``x-goog-api-key`` header (never in the URL) and never
printed. ``load_env`` parses a local ``.env`` into ``os.environ`` and is called
only from ``app.py``; ``get_advice`` never reads the file itself. All advice is
labelled general guidance rather than professional financial advice.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

#: Shown with every piece of advice (FR-022).
DISCLAIMER = (
    "This is general guidance, not professional financial advice. "
    "For decisions about debt, taxes or investments, consult a qualified professional."
)

#: Gemini defaults (FR-021, research.md §1). No URL or key ever sees an error message.
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_TIMEOUT = 10
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


@dataclass(frozen=True)
class Advice:
    """Advice text plus where it came from (``"offline"`` or ``"gemini"``)."""

    text: str
    source: str


def load_env(path: str = ".env") -> None:
    """Merge ``KEY=VALUE`` pairs from a local ``.env`` into ``os.environ``.

    Existing environment variables win: a value already set is never
    overwritten. The file is optional and a missing or unreadable file is
    ignored. Called only from ``app.py``, never from ``get_advice``.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


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


def _build_prompt(profile: dict[str, Any] | None, summary: dict[str, Any] | None) -> str:
    """Frame the advice request; the summary is serialized, never recomputed."""
    return (
        "You are a personal finance consultant. Write plain-language advice that covers "
        "how to review spending, how to rebalance toward the savings goal, and what to adjust. "
        "Use only the figures in the computed summary below and never do your own arithmetic. "
        "Present the advice as general guidance, not professional financial advice.\n\n"
        f"Profile:\n{json.dumps(profile or {}, ensure_ascii=False, default=str)}\n\n"
        f"Computed summary:\n{json.dumps(summary or {}, ensure_ascii=False, default=str)}"
    )


def _call_gemini(prompt: str, api_key: str) -> str:
    """POST to Gemini and return ``candidates[0].content.parts[0].text``.

    The API key travels in the ``x-goog-api-key`` header, never in the URL, and
    no error raised here repeats the key or the URL. Errors propagate so
    ``get_advice`` can fall back to the offline rules.
    """
    model = os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    url = GEMINI_ENDPOINT.format(model=model)
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urlopen(request, timeout=GEMINI_TIMEOUT) as response:
        payload = response.read()
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    data = json.loads(payload)
    return data["candidates"][0]["content"]["parts"][0]["text"]


def get_advice(
    profile: dict[str, Any] | None, summary: dict[str, Any] | None
) -> Advice:
    """Return advice for the profile and computed summary.

    When ``GEMINI_API_KEY`` is set the Gemini path is tried first; any
    exception, timeout or unparseable response falls back to the offline rules.
    The key and request URL are never printed.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            text = _call_gemini(_build_prompt(profile, summary), api_key).strip()
        except Exception:
            text = ""
        if text:
            if "general guidance" not in text.lower():
                text = f"{text}\n\n_{DISCLAIMER}_"
            return Advice(text=text, source="gemini")
    return rule_based_advice(profile, summary)
