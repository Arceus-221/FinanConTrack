# FinanConTrack Constitution

## Core Principles

### I. Deterministic Numbers, LLM Words
Every financial figure (totals, per-category and per-month sums, percentages, savings rate, budget comparison, unusual-spend flags) is computed in code with pandas in `src/analysis.py`. The LLM never does arithmetic. It receives the computed summary as JSON and only writes explanations and advice.

### II. Offline-First Advisor
`src/advisor.py` must work without a network or API key by falling back to rule-based advice. Tests never call the network.

### III. Test-First (NON-NEGOTIABLE)
Write a failing test, then implement, then pass. Every task has at least one test for its acceptance criterion. Ground truth for the analysis is `data/sample_expenses.csv` checked against `data/expected_summary.json`.

### IV. Simplicity
Use the smallest design that works: Python 3.11+, uv, pandas, streamlit, pytest, ruff. `app.py` only calls functions in `src/`. No extra services or databases.

### V. Safe Input Handling and Privacy
Refunds are negative amounts, a blank category becomes "Uncategorized", and bad rows are reported rather than crashing the app. Secrets live only in a gitignored `.env`. Only synthetic data is committed. Output is general guidance, not professional financial advice.

## Technology and Layout
Files: `app.py`, `src/`, `tests/`, `data/`. The UI follows the style described in `DESIGN.md`.

## Development Workflow
Work proceeds one small task at a time through planner, implementer, tester and reviewer. A task is done when `pytest` passes and `ruff` is clean. The reviewer never edits code. One commit per approved task.

## Governance
This constitution supersedes other practices, and `AGENTS.md` is its day-to-day form. Amendments require editing this file and bumping the version.

**Version**: 1.0.0 | **Ratified**: 2026-10-11 | **Last Amended**: 2026-10-11