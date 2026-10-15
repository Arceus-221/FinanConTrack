# Personal Finance Consultant

A Streamlit app that acts as a personal finance consultant. Enter a profile
(occupation, city, monthly income, currency, savings goal), then upload a
CSV/XLSX of expenses or type them in. The app computes a spending summary in
code and gives practical advice on how to review, rebalance and adjust spending.

## Quick start

```bash
# Install dependencies (Python 3.11+, uv)
uv sync

# Run the app
uv run streamlit run app.py

# Run tests
uv run pytest -q

# Lint
uv run ruff check .
```

## Project layout

```
app.py              Streamlit UI (no logic)
src/
  loader.py         CSV/XLSX/manual-row parsing and profile normalization
  analysis.py       Deterministic spending analysis (pandas)
  advisor.py        Advice generation (offline rules + optional Gemini)
  validator.py      Advice number validator (SC-005)
tests/              pytest suite
data/               Synthetic sample data and expected summary
.streamlit/         Streamlit theme config (DESIGN.md colours)
specs/              Feature specification and research notes
```

## How it works

1. **Profile capture** — occupation, city, monthly income, currency, savings goal.
2. **Expense input** — upload CSV/XLSX or type rows manually. Refunds are negative
   amounts, blank category becomes "Uncategorized", bad rows are reported.
3. **Computed summary** — all numbers are computed in `src/analysis.py` with pandas:
   totals, per-category and per-month sums, percentages, savings rate, 50/30/20
   budget comparison, unusual-spend flags. The LLM never does arithmetic.
4. **Advice** — the advisor receives only the computed summary as JSON and writes
   explanations and suggestions. Works offline with rule-based advice; optionally
   calls Gemini when `GEMINI_API_KEY` is set.

## Configuration

Create a `.env` file (gitignored) for optional settings:

```
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-2.5-flash
```

- `GEMINI_API_KEY` — enables the Gemini advice path. Without it, the app uses
  rule-based offline advice.
- `GEMINI_MODEL` — override the default model (`gemini-2.5-flash`).

The API key is sent in the `x-goog-api-key` header, never in the URL, and is
never printed or logged.

## Sample data

The `data/` directory contains synthetic sample data for development and testing:

- `sample_expenses.csv` — 3 months of expenses
- `sample_profile.json` — sample user profile
- `expected_summary.json` — ground-truth expected summary for validation

## Design

The UI follows [DESIGN.md](DESIGN.md) — an indigo-primary, deep-navy-ink design
system with Inter font, metric cards, category bar charts, monthly trend charts,
and a 50/30/20 budget comparison visual.

## Architecture rules

- All numbers are computed in code (`src/analysis.py`). The LLM never does arithmetic.
- The advisor works offline: if there is no API key or the call fails, rule-based
  advice is returned. Tests never call the network.
- `app.py` only calls functions from `src/`. No logic in the UI file.
- Secrets live only in `.env` (gitignored). Never print or commit keys.
