# Phase 0 Research: Personal Finance Consultant

All decisions below close the open questions in the Technical Context. No `NEEDS CLARIFICATION`
items remain.

## 1. How to call Gemini for advice

- **Decision**: Call the Gemini REST endpoint with the standard library (`urllib.request`) inside a
  single function `_call_gemini(prompt, api_key) -> str`, using
  `POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent`, sending
  the key in the `x-goog-api-key` header, with body
  `{"contents": [{"parts": [{"text": "<prompt>"}]}]}` and reading
  `candidates[0].content.parts[0].text`.
- Never include the request URL or key in error messages.
- **Rationale**: Adds no dependency, cannot drift with SDK versions, is trivially monkeypatched in
  tests, and is easy to disable for the offline path. The constitution favours minimal design.
- **Alternatives considered**: `google-genai` SDK (extra dependency and version churn for one call);
  `google-generativeai` (legacy/deprecated); `httpx` (extra dependency for a single POST).
- **Default model**: `big-pickle`, overridable with `GEMINI_MODEL` in `.env`.

## 2. Loading secrets from `.env` without a dependency

- **Decision**: A tiny stdlib reader in `src/advisor.py` that reads `.env` if present and merges into
  `os.environ` (never overwriting an already-set variable). No `python-dotenv`.
- **Rationale**: One small function vs. a dependency; satisfies "secrets live only in a gitignored `.env`".
- **Alternatives considered**: `python-dotenv` (extra dependency), Streamlit `st.secrets` (would move
  secret handling into the UI file, contrary to "UI only").

## 3. Budget rule and category → bucket mapping

- **Decision**: Use the standard **50/30/20** (needs / wants / savings) rule measured as shares of
  **total income**. Categories map to buckets via a constant `CATEGORY_BUCKETS` dict in `analysis.py`:

  | Bucket | Categories | Target |
  |--------|------------|--------|
  | needs | Rent, Utilities, Food, Transport, Health, Education | 50% |
  | wants | Entertainment, Shopping, Uncategorized | 30% |
  | savings | (income − total spend, not a category) | 20% |

  Any category not in the map defaults to **wants**.
- **Rationale**: 50/30/20 is the widely taught rule and produces a meaningful comparison on the sample
  data (needs ≈ 71%, wants ≈ 13%, savings ≈ 16% of income). Deterministic and simple to test.
- **Alternatives considered**: 70/20/10 (less common), zero-based category targets (requires
  per-category user input the spec does not ask for).

## 4. Unusual-spend detection thresholds

- **Decision**: Deterministic, self-referential thresholds expressed as module constants:
  - `UNUSUAL_MONTH_RATIO = 1.5` — a month whose total exceeds 1.5× the **median** month total.
  - `UNUSUAL_CATEGORY_RATIO = 2.0` — a category-month whose amount exceeds 2.0× the **median** of
    that category's monthly totals (only when the category has ≥ 2 months of data).
  - `LARGE_EXPENSE_INCOME_RATIO = 0.20` — a single expense in the **wants** bucket exceeding 20%
    of monthly income.
  - `largest_single_expense` is always reported.
- **Rationale**: Comparing the user against their own median avoids inventing external benchmarks, is
  stable with few months of data, and is trivially unit-testable. On the sample data, these rules
  produce the largest-expense and large-vs-income flags for Laptop repair, the Shopping 2026-08
  category outlier, and no month outlier.
- **Alternatives considered**: fixed currency thresholds (currency-blind, brittle), z-scores
  (unstable with 3 data points).

## 5. Loader validation strategy

- **Decision**: Normalize column names (trim + lowercase) and require only `date` and `amount`.
  `description` defaults to `""` and `category` defaults to `"Uncategorized"`. Rows with an
  unparseable date or non-numeric amount are dropped and reported. Returns `(DataFrame, issues)` where
  `issues` is a list of `{row, reason}`. Missing required column or unreadable/empty file → a single
  input-level issue and an empty DataFrame.
- **Rationale**: Matches FR-005..FR-009 and the "never crash" rule; keeps the issue report a plain
  data structure the UI can render.
- **Alternatives considered**: raising exceptions (user-hostile), `pandas` schema validation libs
  (extra dependency, overkill).

## 6. Advice contract between analysis and advisor

- **Decision**: `analysis.build_summary(profile, df) -> dict` (pure, JSON-serializable) is the only
  thing passed to `advisor.get_advice(profile, summary) -> Advice`. The summary dict is also the payload
  sent to Gemini as JSON. No numbers are computed in the advisor.
- **Rationale**: Enforces Principle I structurally: the advisor literally cannot see raw rows.
- **Alternatives considered**: passing the DataFrame (lets the LLM-adjacent code do math — rejected).

## 7. UI testing approach

- **Decision**: Use `streamlit.testing.v1.AppTest` for one end-to-end UI smoke test; keep all other
  tests at the pure-function level.
- **Rationale**: No extra dependency (ships with Streamlit), and it verifies the "app.py has no logic
  and wires src/ correctly" requirement without a browser.
- **Alternatives considered**: Playwright (heavy, needs a browser), manual-only testing (no regression
  safety).
