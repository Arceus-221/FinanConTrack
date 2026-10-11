# Quickstart: Personal Finance Consultant

Validation scenarios that prove the feature works end-to-end. Entity and field details live in
[data-model.md](./data-model.md); decisions live in [research.md](./research.md).

## Prerequisites

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) installed.
- No API key is required — the app must work fully offline.

## Setup

```bash
uv sync                       # create the venv and install pandas, streamlit, openpyxl, pytest, ruff
```

Optional (only to use the Gemini advice path):

```bash
# create .env in the project root — it is gitignored. Never commit it.
GEMINI_API_KEY=your-key-here
```

## Run the app

```bash
uv run streamlit run app.py
```

Then, in the browser:

1. Enter the profile (occupation, city, monthly income, currency, savings goal).
2. Upload `data/sample_expenses.csv` — or type a few rows by hand.
3. Confirm the spending summary appears before any advice.

**Expected**: total spend, per-category totals, per-month totals, percentages, total income, savings
and savings rate, plus the 50/30/20 comparison and at least one unusual-spend flag (Shopping in
`2026-08` on the sample data).

## Scenario A — Ground truth (SC-002)

```bash
uv run pytest tests/test_sample_data.py -q
```

**Expected**: `data/sample_expenses.csv` + `data/sample_profile.json` produce a summary whose
`months`, `total_spend`, `by_category`, `by_month`, `total_income`, `savings`, `savings_rate`, and
`largest_single_expense` match `data/expected_summary.json`.

## Scenario B — File upload and manual entry agree (SC-006)

Add rows for the same expenses via the UI table instead of the file, and compare the rendered summary
figures with Scenario A. **Expected**: identical figures.

## Scenario C — Bad input never crashes (SC-003)

Upload a CSV that mixes a missing category, a refund (negative amount), a non-numeric amount, and an
unparseable date. **Expected**: the app renders the summary from the good rows, subtracts the refund,
groups the blank category as `Uncategorized`, lists every bad row with a reason, and does not crash.

## Scenario D — Offline advice (SC-004)

With no `.env` and no `GEMINI_API_KEY`, run the app and request advice. **Expected**: rule-based
advice appears, drawn from the computed summary, labelled as general guidance.

## Scenario E — Advice invents no numbers (SC-005)

Compare the figures quoted in the advice text with the on-screen summary. **Expected**: every quoted
number already exists in the summary.

## Scenario F — Full gate

```bash
uv run pytest -q && uv run ruff check .
```

**Expected**: all tests pass and lint is clean (the project's definition of done).
