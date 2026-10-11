# Implementation Plan: Personal Finance Consultant

**Branch**: `main` (feature dir `001-personal-finance-consultant`) | **Date**: 2026-10-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-personal-finance-consultant/spec.md`

## Summary

A single-user Streamlit app that reads a profile and an expense table (CSV/XLSX upload or manual entry),
computes a full spending summary in pandas, compares it to the 50/30/20 budget rule, flags unusual
spending, and shows practical advice. All numbers are computed in `src/analysis.py`; the advice layer
(`src/advisor.py`) only turns the pre-computed summary into prose and falls back to rule-based advice
when no Gemini API key is present or the call fails. `app.py` contains UI only and calls into `src/`.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: pandas (analysis + file reading), streamlit (UI), openpyxl (XLSX reading via pandas), pytest + ruff (dev). Gemini advice uses the standard library `urllib.request` — no extra dependency.

**Storage**: N/A — in-memory only; no database, no persistence between sessions.

**Testing**: pytest (`streamlit.testing.v1.AppTest` for the UI smoke test). Tests never touch the network.

**Target Platform**: Local desktop / laptop browser session (Streamlit), Windows and Linux.

**Project Type**: Single project — small web app (Streamlit) with a pure-Python library under `src/`.

**Performance Goals**: Summary + budget comparison + advice within 5 seconds for a few thousand expense rows (SC-007).

**Constraints**: Must work fully offline (no API key → rule-based advice). Secrets only from a gitignored `.env`. Must never crash on bad input. No extra services or databases.

**Scale/Scope**: Single user, single session; datasets up to a few thousand rows; 1 UI page.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Deterministic Numbers, LLM Words | Every figure (totals, by category, by month, percentages, savings rate, budget comparison, flags) is computed in `src/analysis.py` with pandas. The advisor receives the summary dict and performs no arithmetic. | PASS |
| II. Offline-First Advisor | `src/advisor.py` returns rule-based advice when the key is absent or the request fails/times out. Tests never call the network (no key set; HTTP layer monkeypatched). | PASS |
| III. Test-First (NON-NEGOTIABLE) | Each task ships at least one test; ground truth is `data/sample_expenses.csv` + `data/sample_profile.json` checked against `data/expected_summary.json`. | PASS |
| IV. Simplicity | Only pandas, streamlit, openpyxl, pytest, ruff; stdlib for HTTP and `.env` parsing. No DB, no services, no framework beyond Streamlit. | PASS |
| V. Safe Input Handling and Privacy | Refunds are negative and reduce totals; blank category → "Uncategorized"; bad rows are skipped and reported, never fatal; `.env` is gitignored; only synthetic data in `data/`; advice labelled general guidance. | PASS |

**Result**: No violations. Complexity Tracking table intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-personal-finance-consultant/
├── plan.md              # This file
├── research.md          # Phase 0 output (decisions only, kept short)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

No `contracts/` directory: this app exposes no external API, CLI, or library contract — its only
interface is the Streamlit UI, which is covered by the UI smoke test in tasks.md. Per the request,
no contracts or extra research artifacts are produced.

### Source Code (repository root)

```text
app.py                      # Streamlit UI only — layout, widgets, DESIGN.md styling, calls src/
src/
├── __init__.py
├── loader.py               # CSV/XLSX + manual rows → normalized DataFrame; validation & issue report
├── analysis.py             # ALL numbers: totals, by-category, by-month, %, savings rate,
│                           #   50/30/20 budget comparison, unusual-spend flags
└── advisor.py              # summary dict → advice text; Gemini via urllib; offline rule-based fallback
tests/
├── test_loader.py
├── test_analysis.py
├── test_advisor.py
├── test_app.py             # AppTest UI smoke test
└── test_sample_data.py     # sample_expenses.csv vs expected_summary.json ground truth
data/
├── sample_expenses.csv     # committed synthetic data (exists)
├── sample_profile.json     # committed synthetic profile (exists)
└── expected_summary.json   # committed ground truth (exists)
pyproject.toml              # project metadata, deps, ruff + pytest config
.env                        # GEMINI_API_KEY=... (gitignored, never committed)
```

**Structure Decision**: Single-project layout exactly as requested. `src/` holds pure, importable,
network-free logic; `app.py` holds only UI and calls `src/` functions. No `src/models/` or service
layer — data flows as a plain dict summary, which is the simplest thing that keeps the LLM away from
arithmetic.

## Phase 0: Research

See [research.md](./research.md). Decisions resolved: Gemini access method, `.env` loading, budget
rule definition and category mapping, unusual-spend thresholds, and loader validation strategy.
No open NEEDS CLARIFICATION items remain.

## Phase 1: Design

- [data-model.md](./data-model.md) — Profile, ExpenseRow, InputIssues, SpendingSummary, BudgetComparison, Advice.
- [quickstart.md](./quickstart.md) — how to run the app and the ground-truth check.

## Post-Design Constitution Re-check

| Principle | Re-check after design | Status |
|-----------|-----------------------|--------|
| I. Deterministic Numbers | Summary dict produced solely in `analysis.py`; advisor signature is `get_advice(profile, summary) -> Advice` with no numeric computation. | PASS |
| II. Offline-First Advisor | Advisor checks key presence / failure / timeout and returns `rule_based_advice(profile, summary)`; HTTP isolated in one function. | PASS |
| III. Test-First | `test_sample_data.py` reproduces every key in `expected_summary.json`; each module has its own test file. | PASS |
| IV. Simplicity | Four source files, one UI file; no abstractions beyond plain functions. | PASS |
| V. Safe Input Handling | Loader returns `(DataFrame, issues)`; UI shows issues; no crashing path. | PASS |

**Result**: All gates pass. Ready for `/speckit.tasks`.

## Complexity Tracking

> No constitution violations; table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| — | — | — |
