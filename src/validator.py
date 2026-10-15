"""Validate that advice text invents no numbers (spec criterion SC-005).

``extract_numbers`` pulls every numeric token from a string. ``validate_advice``
checks that every number appearing in the advice text can be traced back to a
value already present in the computed summary.
"""

from __future__ import annotations

import math
import re
from typing import Any


def extract_numbers(text: str) -> set[float]:
    """Return the set of numeric values found in *text*.

    Handles integers, decimals, comma-grouped numbers (e.g. ``4,782.97``), and
    percentage literals (e.g. ``16%`` → ``16.0``). Currency symbols and sign
    prefixes are stripped before parsing.
    """
    numbers: set[float] = set()
    # Match numbers that may have commas as thousand separators and optional
    # decimal part, optionally followed by a percent sign.
    for match in re.finditer(r"-?\d[\d,]*\.?\d*%?", text):
        token = match.group()
        is_percent = token.endswith("%")
        raw = token.rstrip("%").replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        numbers.add(value)
        if is_percent:
            # Also add the decimal form so "16%" matches 0.16 in the summary.
            numbers.add(round(value / 100, 6))
    return numbers


def _flatten_summary_values(obj: Any, depth: int = 0) -> set[float]:
    """Recursively extract every numeric value from a summary structure."""
    if depth > 10:
        return set()
    values: set[float] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            values |= _flatten_summary_values(v, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            values |= _flatten_summary_values(v, depth + 1)
    elif isinstance(obj, (int, float)):
        if not math.isnan(obj):
            values.add(float(obj))
            # Common display forms: percentage (×100) and rounded variants.
            values.add(round(obj * 100, 6))
            for dp in range(5):
                values.add(round(float(obj), dp))
            # Percentage display: e.g. 0.7105 → "71%" produces 71.0 in the text.
            # Add the rounded-then-scaled form for all common rounding depths.
            for dp in range(5):
                values.add(round(round(float(obj), dp) * 100, 6))
    return values


def validate_advice(advice_text: str, summary: dict[str, Any]) -> list[str]:
    """Return a list of problems, empty when every number traces back to the summary.

    Each problem string names the invented number. An empty list means the
    advice passes SC-005.
    """
    advice_numbers = extract_numbers(advice_text)
    summary_numbers = _flatten_summary_values(summary)

    # Numbers that are universally expected in natural language (0, 1, 100, etc.)
    # and the 50/30/20 rule constants are not considered "invented".
    well_known = {
        0.0, 1.0, 2.0, 3.0, 100.0,
        50.0, 30.0, 20.0,  # 50/30/20 rule
        0.5, 0.3, 0.2,     # as decimals
        1.5, 2.0,           # unusual-spend thresholds
    }
    summary_numbers |= well_known

    problems = []
    for number in sorted(advice_numbers):
        if number not in summary_numbers:
            problems.append(f"invented number: {number}")
    return problems
