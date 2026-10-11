"""T002: loader tests.

Covers the acceptance criteria for ``src/loader.py``:

* file/manual input is normalized (trimmed, lowercased columns; only ``date``
  and ``amount`` required), blank categories become ``"Uncategorized"``, and
  refunds stay negative;
* malformed rows are dropped and reported exactly once each;
* missing required columns, unreadable/unsupported/empty input yield a single
  input-level issue and an empty DataFrame;
* ``load_profile`` handles the ``goal`` alias, ignores unknown keys, coerces
  blank/negative income to ``0.0`` and uppercases the currency (default USD).
"""

import io
import json
from pathlib import Path

import pandas as pd
from src.loader import load_expenses, load_manual_rows, load_profile

ROOT = Path(__file__).resolve().parents[1]

MESSY_CSV = (
    "Date , Description,CATEGORY,Amount\n"
    "2026-07-01,Coffee,Food,3.5\n"
    "not-a-date,Tea,Food,2.0\n"
    "2026-07-03,Refund: returned shoes,,-10\n"
    "2026-07-04,Broken,Shopping,abc\n"
)


class _NamedBuffer(io.StringIO):
    """A StringIO with a ``name`` so the loader can detect the file type."""

    def __init__(self, text: str, name: str) -> None:
        super().__init__(text)
        self.name = name


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --- load_expenses: acceptance criterion ---------------------------------------


def test_load_expenses_keeps_only_good_rows(tmp_path):
    path = _write(tmp_path, "expenses.csv", MESSY_CSV)

    df, issues = load_expenses(path)

    # Only the well-formed rows survive, in order, refund still negative.
    assert list(df["description"]) == ["Coffee", "Refund: returned shoes"]
    assert list(df["category"]) == ["Food", "Uncategorized"]
    assert list(df["amount"]) == [3.5, -10.0]
    assert df["amount"].iloc[1] < 0

    # Each bad row is reported exactly once.
    reported = [issue["row"] for issue in issues]
    assert reported == [1, 3]
    assert len(reported) == len(set(reported)) == 2
    assert all(isinstance(issue["reason"], str) and issue["reason"] for issue in issues)


def test_load_expenses_normalizes_columns_and_derives_month(tmp_path):
    path = _write(tmp_path, "expenses.csv", MESSY_CSV)

    df, _ = load_expenses(path)

    assert list(df.columns) == ["date", "description", "category", "amount", "month"]
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df["month"].tolist() == ["2026-07", "2026-07"]


def test_row_with_two_problems_is_reported_once(tmp_path):
    path = _write(
        tmp_path,
        "expenses.csv",
        "date,description,category,amount\nbad,Oops,Food,abc\n",
    )

    df, issues = load_expenses(path)

    assert df.empty
    assert len(issues) == 1
    assert issues[0]["row"] == 0


def test_load_expenses_accepts_upload_buffer():
    buffer = _NamedBuffer(MESSY_CSV, "expenses.csv")

    df, issues = load_expenses(buffer)

    assert len(df) == 2
    assert [issue["row"] for issue in issues] == [1, 3]


# --- load_expenses: input-level issues -----------------------------------------


def test_missing_required_column_is_single_input_issue(tmp_path):
    path = _write(
        tmp_path,
        "no_amount.csv",
        "date,description,category\n2026-07-01,Coffee,Food\n",
    )

    df, issues = load_expenses(path)

    assert df.empty
    assert len(issues) == 1
    assert issues[0]["row"] is None
    assert "amount" in issues[0]["reason"]


def test_empty_file_is_single_input_issue(tmp_path):
    path = _write(
        tmp_path, "empty.csv", "date,description,category,amount\n"
    )

    df, issues = load_expenses(path)

    assert df.empty
    assert len(issues) == 1
    assert issues[0]["row"] is None


def test_unsupported_file_type_is_single_input_issue(tmp_path):
    path = _write(tmp_path, "expenses.txt", "date,amount\n2026-07-01,5\n")

    df, issues = load_expenses(path)

    assert df.empty
    assert len(issues) == 1
    assert issues[0]["row"] is None


def test_corrupt_file_is_single_input_issue(tmp_path):
    path = tmp_path / "corrupt.xlsx"
    path.write_bytes(b"this is not a real workbook")

    df, issues = load_expenses(path)

    assert df.empty
    assert len(issues) == 1
    assert issues[0]["row"] is None


def test_nonexistent_path_is_single_input_issue(tmp_path):
    df, issues = load_expenses(tmp_path / "missing.csv")

    assert df.empty
    assert len(issues) == 1
    assert issues[0]["row"] is None


# --- load_manual_rows ----------------------------------------------------------


def test_load_manual_rows_matches_equivalent_file(tmp_path):
    path = _write(tmp_path, "expenses.csv", MESSY_CSV)
    df_file, _ = load_expenses(path)

    rows = [
        {"date": "2026-07-01", "description": "Coffee", "category": "Food", "amount": 3.5},
        {
            "date": "2026-07-03",
            "description": "Refund: returned shoes",
            "category": "",
            "amount": -10,
        },
    ]
    df_manual, issues = load_manual_rows(rows)

    assert issues == []
    for column in ("date", "description", "category", "amount"):
        assert df_manual[column].tolist() == df_file[column].tolist()


def test_load_manual_rows_rejects_bad_rows():
    rows = [
        {"date": "2026-07-01", "description": "ok", "category": "Food", "amount": 1},
        {"date": "bad", "description": "no date", "category": "Food", "amount": 2},
        {"date": "2026-07-02", "description": "no amount", "category": "Food", "amount": "x"},
    ]

    df, issues = load_manual_rows(rows)

    assert len(df) == 1
    assert [issue["row"] for issue in issues] == [1, 2]


def test_load_manual_rows_empty_is_single_input_issue():
    df, issues = load_manual_rows([])

    assert df.empty
    assert len(issues) == 1
    assert issues[0]["row"] is None


# --- load_profile --------------------------------------------------------------


def test_load_profile_reads_sample_file_and_ignores_unknown_keys():
    profile = load_profile(ROOT / "data" / "sample_profile.json")

    assert profile == {
        "occupation": "software engineer",
        "city": "Example City",
        "monthly_income": 1900.0,
        "currency": "USD",
        "savings_goal": "save 20% of income",
    }


def test_load_profile_goal_alias_and_unknown_keys():
    profile = load_profile({"goal": "save more", "household": "single", "nickname": "x"})

    assert profile["savings_goal"] == "save more"
    assert set(profile) == {
        "occupation",
        "city",
        "monthly_income",
        "currency",
        "savings_goal",
    }


def test_load_profile_savings_goal_key_wins_over_goal():
    profile = load_profile({"savings_goal": "explicit", "goal": "alias"})

    assert profile["savings_goal"] == "explicit"


def test_load_profile_blank_and_negative_income_become_zero():
    assert load_profile({"monthly_income": ""})["monthly_income"] == 0.0
    assert load_profile({"monthly_income": None})["monthly_income"] == 0.0
    assert load_profile({"monthly_income": -500})["monthly_income"] == 0.0
    assert load_profile({"monthly_income": "not a number"})["monthly_income"] == 0.0
    assert load_profile({})["monthly_income"] == 0.0


def test_load_profile_currency_defaults_and_uppercases():
    assert load_profile({})["currency"] == "USD"
    assert load_profile({"currency": ""})["currency"] == "USD"
    assert load_profile({"currency": "eur"})["currency"] == "EUR"


def test_load_profile_text_defaults():
    profile = load_profile({"occupation": "  ", "city": "  ", "savings_goal": "  "})

    assert profile["occupation"] == "unspecified"
    assert profile["city"] == "unspecified"
    assert profile["savings_goal"] == "no goal set"


def test_load_profile_reads_json_file(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"city": "Sylhet", "goal": "travel"}), encoding="utf-8")

    profile = load_profile(path)

    assert profile["city"] == "Sylhet"
    assert profile["savings_goal"] == "travel"
