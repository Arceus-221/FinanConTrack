"""T008: AppTest smoke test for the UI-only Streamlit app.

Runs ``app.py`` with ``GEMINI_API_KEY`` removed from the environment, so the app
must take the offline rule-based advice path. Manual-entry rows are supplied
through the ``st.data_editor`` widget state (AppTest does not expose a
``data_editor`` accessor, but the widget's ``added_rows`` state can be set), and
the test then checks that the app renders without raising an exception and shows
the computed total spend and the general-guidance advice text.

The HTTP layer is guarded so the test can never reach the network even if a
local ``.env`` happened to hold a key.
"""

from pathlib import Path

from src import advisor
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"

#: Key of the manual-entry editor in ``app.py``.
EDITOR_KEY = "expense_editor"

#: Two months, hand-checked: total spend = 900 + 300 + 900 = 2100.
MANUAL_ROWS = [
    {"date": "2026-07-01", "description": "Apartment rent", "category": "Rent", "amount": 900.0},
    {"date": "2026-07-05", "description": "Groceries", "category": "Food", "amount": 300.0},
    {"date": "2026-08-01", "description": "Apartment rent", "category": "Rent", "amount": 900.0},
]


def _boom(*args, **kwargs):
    raise AssertionError("the network must not be called in tests")


def _add_manual_rows(at: AppTest) -> None:
    at.session_state[EDITOR_KEY] = {
        "edited_rows": {},
        "added_rows": MANUAL_ROWS,
        "deleted_rows": [],
    }


def test_app_renders_without_exception(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(advisor, "urlopen", _boom)

    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()

    assert not at.exception

    _add_manual_rows(at)
    at.run()

    assert not at.exception


def test_app_shows_total_spend_and_offline_advice(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(advisor, "urlopen", _boom)

    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    _add_manual_rows(at)
    at.run()

    # The total spend is rendered as a metric.
    labels = [str(metric.label).lower() for metric in at.metric]
    assert any("total spend" in label for label in labels), labels

    total = sum(row["amount"] for row in MANUAL_ROWS)
    values = " ".join(str(metric.value) for metric in at.metric)
    assert f"{total:,.2f}" in values, values

    # The advice text is rendered and labelled as general guidance.
    markdown = " ".join(str(block.value) for block in at.markdown).lower()
    assert "how to review your spending" in markdown
    assert "general guidance" in markdown
    assert "not professional" in markdown
