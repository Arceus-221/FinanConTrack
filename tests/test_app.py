"""T008/T009: AppTest smoke test for the UI-only Streamlit app.

Runs ``app.py`` with ``GEMINI_API_KEY`` removed from the environment, so the app
must take the offline rule-based advice path. Manual-entry rows are supplied
through the ``st.data_editor`` widget state (AppTest does not expose a
``data_editor`` accessor, but the widget's ``added_rows`` state can be set), and
the test then checks that the app renders without raising an exception and shows
the computed total spend and the general-guidance advice text.

T009 adds a "Get advice" button: tests verify the advisor is NOT called before
the click, is called exactly once after one click and one further rerun, and
the advice text and its source label are shown after the click.

The HTTP layer is guarded so the test can never reach the network even if a
local ``.env`` happened to hold a key.
"""

import sys
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


def _all_markdown_text(at: AppTest) -> str:
    """Join all markdown blocks, excluding raw HTML/style blocks."""
    parts = []
    for block in at.markdown:
        text = str(block.value)
        if text.strip().startswith("<style"):
            continue
        parts.append(text)
    return " ".join(parts).lower()


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

    # Total spend (2,100.00 USD) is visible in the metrics before clicking.
    metrics = " ".join(str(m.value) for m in at.metric)
    assert "2,100" in metrics or "2100" in metrics

    # Click 'Get advice' while preserving manual rows in session_state.
    _add_manual_rows(at)
    at.button[0].click().run()

    # The advice text is rendered and labelled as general guidance.
    markdown = _all_markdown_text(at)
    assert "how to review your spending" in markdown
    assert "general guidance" in markdown
    assert "not professional" in markdown


def test_advisor_not_called_before_button_click(monkeypatch):
    """T009: the advisor is not invoked until the user clicks 'Get advice'."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(advisor, "urlopen", _boom)

    call_log: list[tuple] = []
    _real_get_advice = advisor.get_advice

    def tracking_get_advice(*args, **kwargs):
        call_log.append(args)
        return _real_get_advice(*args, **kwargs)

    # Patch on the actual module in sys.modules so the running script sees it.
    monkeypatch.setattr(sys.modules["src.advisor"], "get_advice", tracking_get_advice)

    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    _add_manual_rows(at)
    at.run()

    # Before clicking, the advisor must not have been called.
    assert len(call_log) == 0, f"advisor was called {len(call_log)} times before click"


def test_advisor_called_once_after_click_and_rerun(monkeypatch):
    """T009: the advisor is called exactly once after a click + a rerun."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(advisor, "urlopen", _boom)

    call_log: list[tuple] = []
    _real_get_advice = advisor.get_advice

    def tracking_get_advice(*args, **kwargs):
        call_log.append(args)
        return _real_get_advice(*args, **kwargs)

    monkeypatch.setattr(sys.modules["src.advisor"], "get_advice", tracking_get_advice)

    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    _add_manual_rows(at)
    at.run()

    # Click the button — should call the advisor exactly once.
    _add_manual_rows(at)
    at.button[0].click().run()
    assert len(call_log) == 1, f"expected 1 call, got {len(call_log)}"

    # Re-run without clicking again — cached, advisor not called again.
    _add_manual_rows(at)
    at.run()
    assert len(call_log) == 1, f"expected still 1 call after rerun, got {len(call_log)}"

    # Advice text and source label should still be visible after the rerun.
    markdown = _all_markdown_text(at)
    assert "how to review your spending" in markdown

    captions = " ".join(str(c.value) for c in at.caption).lower()
    assert "advice source" in captions