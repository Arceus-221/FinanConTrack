"""Input handling for the Personal Finance Consultant.

``load_expenses`` and ``load_manual_rows`` turn a CSV/XLSX upload or manually
entered rows into a normalized pandas DataFrame plus a list of input issues.
``load_profile`` normalizes a profile dict or JSON file.

Column names are trimmed and lowercased and only ``date`` and ``amount`` are
required: ``description`` defaults to ``""`` and ``category`` to
``"Uncategorized"``. Rows with an unparseable date or a non-numeric amount are
dropped and reported once each as ``{"row": int, "reason": str}``. Missing
required columns and unreadable/unsupported/empty input produce a single
input-level issue (``row`` is ``None``) and an empty DataFrame. Nothing here
raises on bad input.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xls"}
REQUIRED_COLUMNS = ("date", "amount")

UNCATEGORIZED = "Uncategorized"
DEFAULT_DESCRIPTION = ""
DEFAULT_CURRENCY = "USD"
DEFAULT_OCCUPATION = "unspecified"
DEFAULT_CITY = "unspecified"
DEFAULT_GOAL = "no goal set"

#: Column order of a normalized expense frame (``month`` is derived from ``date``).
EXPENSE_COLUMNS = ["date", "description", "category", "amount", "month"]


def _issue(row: int | None, reason: str) -> dict[str, Any]:
    return {"row": row, "reason": reason}


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=EXPENSE_COLUMNS)


def _is_blank(value: Any) -> bool:
    """True for ``None``, ``NaN`` and whitespace-only strings."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


# --- expense input -------------------------------------------------------------


def _read_table(path_or_buffer: Any) -> tuple[pd.DataFrame | None, dict | None]:
    """Read CSV/XLSX into a DataFrame, or return a single input-level issue."""
    if hasattr(path_or_buffer, "read"):
        name = getattr(path_or_buffer, "name", "")
        suffix = Path(str(name)).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            return None, _issue(None, "unsupported or unrecognised file type")
        try:
            if hasattr(path_or_buffer, "seek"):
                path_or_buffer.seek(0)
            reader = pd.read_excel if suffix in {".xlsx", ".xls"} else pd.read_csv
            return reader(path_or_buffer), None
        except Exception:
            return None, _issue(None, "could not read the uploaded file")

    path = Path(path_or_buffer)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        label = suffix or "unknown"
        return None, _issue(None, f"unsupported file type: {label}")
    try:
        reader = pd.read_excel if suffix in {".xlsx", ".xls"} else pd.read_csv
        return reader(path), None
    except Exception:
        return None, _issue(None, "could not read the file")


def _clean_category(value: Any) -> str:
    if _is_blank(value):
        return UNCATEGORIZED
    return str(value).strip()


def _clean_description(value: Any) -> str:
    if _is_blank(value):
        return DEFAULT_DESCRIPTION
    return str(value).strip()


def _normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    df = df.copy()
    df.columns = [str(column).strip().lower() for column in df.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        reason = "missing required column(s): " + ", ".join(missing)
        return _empty_frame(), [_issue(None, reason)]

    if df.empty:
        return _empty_frame(), [_issue(None, "no expense rows were provided")]

    if "description" not in df.columns:
        df["description"] = ""
    if "category" not in df.columns:
        df["category"] = ""

    issues: list[dict[str, Any]] = []
    good_rows: list[dict[str, Any]] = []
    for position, (_, row) in enumerate(df.iterrows()):
        problems: list[str] = []

        parsed_date = pd.to_datetime(row["date"], errors="coerce")
        if pd.isna(parsed_date):
            problems.append(f"unparseable date: {row['date']!r}")

        amount = pd.to_numeric(row["amount"], errors="coerce")
        if pd.isna(amount):
            problems.append(f"non-numeric amount: {row['amount']!r}")

        if problems:
            issues.append(_issue(position, "; ".join(problems)))
            continue

        good_rows.append(
            {
                "date": parsed_date,
                "description": _clean_description(row["description"]),
                "category": _clean_category(row["category"]),
                "amount": float(amount),
            }
        )

    if not good_rows:
        return _empty_frame(), issues

    clean = pd.DataFrame(good_rows)
    clean["date"] = pd.to_datetime(clean["date"])
    clean["month"] = clean["date"].dt.strftime("%Y-%m")
    clean = clean[EXPENSE_COLUMNS]
    return clean, issues


def load_expenses(path_or_buffer: Any) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Load a CSV/XLSX path or file-like buffer into ``(DataFrame, issues)``."""
    df, issue = _read_table(path_or_buffer)
    if issue is not None:
        return _empty_frame(), [issue]
    return _normalize(df)


def load_manual_rows(rows: Any) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Normalize manually entered rows (list of dicts or a DataFrame)."""
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if df.empty:
        return _empty_frame(), [_issue(None, "no manual rows were entered")]
    return _normalize(df)


# --- profile -------------------------------------------------------------------


def _coerce_income(value: Any) -> float:
    if _is_blank(value):
        return 0.0
    try:
        numeric = float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if numeric < 0 else numeric


def _clean_text(value: Any, default: str) -> str:
    if _is_blank(value):
        return default
    return str(value).strip()


def _clean_currency(value: Any) -> str:
    text = _clean_text(value, DEFAULT_CURRENCY).upper()
    return text or DEFAULT_CURRENCY


def _read_profile_json(source: Any) -> Any:
    try:
        if hasattr(source, "read"):
            if hasattr(source, "seek"):
                source.seek(0)
            return json.load(source)
        with open(Path(source), encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def load_profile(source: Any) -> dict[str, Any]:
    """Normalize a profile dict or JSON file into the profile data model.

    ``goal`` is accepted as an alias for ``savings_goal``; unknown keys are
    ignored; blank or negative income becomes ``0.0``; the currency is
    uppercased and defaults to ``"USD"``.
    """
    data = source if isinstance(source, dict) else _read_profile_json(source)
    if not isinstance(data, dict):
        data = {}

    goal = data.get("savings_goal")
    if _is_blank(goal):
        goal = data.get("goal")

    return {
        "occupation": _clean_text(data.get("occupation"), DEFAULT_OCCUPATION),
        "city": _clean_text(data.get("city"), DEFAULT_CITY),
        "monthly_income": _coerce_income(data.get("monthly_income")),
        "currency": _clean_currency(data.get("currency")),
        "savings_goal": _clean_text(goal, DEFAULT_GOAL),
    }
