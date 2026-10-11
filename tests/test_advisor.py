"""T005/T006: offline rule-based advice and the Gemini path from ``src/advisor``.

Every test removes ``GEMINI_API_KEY`` from the environment, so ``get_advice``
must resolve to the offline rules (``source == "offline"``) unless a test opts
in by setting a key. The advice must cover how to review spending, how to
rebalance toward the savings goal, and what to adjust, cite figures already
present in the summary (the largest single expense and the savings rate), and
label itself general guidance rather than professional advice. The HTTP layer
is monkeypatched throughout: no test ever touches the network.
"""

import json
import os

import pandas as pd
import pytest
from src import advisor
from src.advisor import Advice, get_advice, rule_based_advice
from src.analysis import build_summary

# Hand-checked 2-month fixture. Largest positive expense is "Apartment rent".
ROWS = [
    {"date": "2026-07-01", "description": "Apartment rent", "category": "Rent", "amount": 900},
    {"date": "2026-07-05", "description": "Groceries", "category": "Food", "amount": 300},
    {
        "date": "2026-07-10",
        "description": "Cinema night",
        "category": "Entertainment",
        "amount": 120,
    },
    {"date": "2026-08-01", "description": "Apartment rent", "category": "Rent", "amount": 900},
    {"date": "2026-08-05", "description": "Groceries", "category": "Food", "amount": 320},
]

PROFILE = {
    "occupation": "software engineer",
    "city": "Example City",
    "monthly_income": 1900.0,
    "currency": "USD",
    "savings_goal": "save 20% of income",
}


@pytest.fixture(autouse=True)
def _remove_api_key(monkeypatch):
    """Tests never call the network: ensure no Gemini key is configured."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def _summary() -> dict:
    return build_summary(PROFILE, pd.DataFrame(ROWS))


def test_rule_based_advice_returns_advice_with_offline_source():
    advice = rule_based_advice(PROFILE, _summary())

    assert isinstance(advice, Advice)
    assert advice.source == "offline"
    assert advice.text.strip()


def test_get_advice_is_offline_when_api_key_is_absent():
    advice = get_advice(PROFILE, _summary())

    assert advice.source == "offline"


def test_text_cites_largest_expense_and_general_guidance_label():
    summary = _summary()
    text = get_advice(PROFILE, summary).text

    largest = summary["largest_single_expense"]
    assert largest["description"] in text
    assert "general guidance" in text.lower()
    assert "not professional" in text.lower()


def test_text_covers_review_rebalance_and_adjust():
    text = get_advice(PROFILE, _summary()).text.lower()

    assert "review" in text
    assert "rebalance" in text
    assert "adjust" in text


def test_text_cites_the_savings_rate_figure():
    summary = _summary()
    text = get_advice(PROFILE, summary).text

    assert f"{summary['savings_rate']:.0%}" in text
    assert summary["largest_single_expense"]["description"] in text


def test_offline_advice_handles_empty_summary_without_error():
    advice = get_advice({}, build_summary(None, None))

    assert advice.source == "offline"
    assert "general guidance" in advice.text.lower()


class _FakeResponse:
    """Minimal stand-in for the object returned by ``urlopen``."""

    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> None:
        return None


def _gemini_body(text: str) -> bytes:
    payload = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return json.dumps(payload).encode("utf-8")


def _headers_lower(request) -> dict:
    return {key.lower(): value for key, value in request.headers.items()}


def test_get_advice_uses_gemini_when_key_is_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["request"] = request
        captured["timeout"] = timeout
        captured["body"] = request.data
        return _FakeResponse(_gemini_body("Gemini review and rebalance advice."))

    monkeypatch.setattr(advisor, "urlopen", fake_urlopen)

    advice = get_advice(PROFILE, _summary())

    assert advice.source == "gemini"
    assert "Gemini review and rebalance advice." in advice.text
    # The 10-second timeout is passed through to urlopen exactly.
    assert captured["timeout"] == 10
    # The key travels in the x-goog-api-key header and never in the URL.
    assert _headers_lower(captured["request"])["x-goog-api-key"] == "test-key"
    assert "test-key" not in captured["request"].full_url
    # The summary is serialized into the POST body, not computed here.
    assert b"contents" in captured["body"]


def test_get_advice_falls_back_to_offline_on_timeout(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    captured_timeout = []

    def fake_urlopen(request, timeout=None):
        captured_timeout.append(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(advisor, "urlopen", fake_urlopen)

    advice = get_advice(PROFILE, _summary())

    assert advice.source == "offline"
    assert "general guidance" in advice.text.lower()
    assert captured_timeout == [10]


def test_get_advice_falls_back_to_offline_on_unparseable_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        advisor,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(b"not json at all"),
    )

    advice = get_advice(PROFILE, _summary())

    assert advice.source == "offline"


def test_get_advice_does_not_call_network_without_key(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("network must not be called without a key")

    monkeypatch.setattr(advisor, "urlopen", boom)

    assert get_advice(PROFILE, _summary()).source == "offline"


def test_load_env_merges_without_overwriting(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment line\nGEMINI_API_KEY=from-file\nGEMINI_MODEL=from-file-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "kept-model")

    advisor.load_env(str(env_file))

    assert os.environ["GEMINI_API_KEY"] == "from-file"
    # An already-set value is kept, never overwritten by the file.
    assert os.environ["GEMINI_MODEL"] == "kept-model"
