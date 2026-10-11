# Personal Finance Consultant (course project)

Tiny Streamlit app. The user enters a profile (occupation, city, monthly income, currency, goal),
then uploads a CSV/XLSX of expenses or types them in. The app shows a spending summary and gives
practical advice: how to review spending, how to rebalance, what to adjust.

## Non-negotiable architecture rules
- **All numbers are computed in code**, in `src/analysis.py` (pandas): totals, per-category and per-month
  sums, percentages, savings rate, budget comparison, unusual-spend flags. The LLM never does arithmetic.
- The LLM only receives the computed summary as JSON and writes explanations and advice (`src/advisor.py`).
- `src/advisor.py` must work offline: if there is no API key or the call fails, return rule-based advice.
  Tests never call the network.
- `app.py` (Streamlit) only calls functions from `src/`. No logic in the UI file.
- Input handling: refunds are negative amounts, blank category becomes "Uncategorized", bad rows are
  reported, never crash.
- Stack: Python 3.11+, `uv`, pandas, streamlit, pytest, ruff. Layout: `app.py`, `src/`, `tests/`, `data/`.
- Secrets live only in `.env` (gitignored). Never print or commit keys. Use only synthetic data in `data/`.

## Definition of done for a task
1. `uv run pytest -q` passes and `uv run ruff check .` is clean.
2. The task's acceptance criteria (in tasks.md / spec.md) are covered by at least one test.
3. No unrelated files changed.

## How agents behave (the model quota is small, so be economical)
- Do exactly the one task you are given. Do not touch checkboxes in tasks.md; the loop script does that.
- Read only the files you need. Prefer a few large edits over many tiny ones. Run the full test suite at most
  twice per task.
- Never run streamlit run (it never exits and would hang the loop). Test the UI only with AppTest.
- Do not ask the human questions. If something is ambiguous, pick the simplest reasonable option and
  state it in one line.
- End your reply with the status line your role requires (see your agent file).
