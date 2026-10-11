# Data Model: Personal Finance Consultant

All entities are plain Python values (dataclasses / dicts). Nothing is persisted — every entity lives
only for the running session.

## 1. Profile

The user's context. Entered in the UI, or loaded from `data/sample_profile.json`.

| Field | Type | Required | Validation | Source |
|-------|------|----------|------------|--------|
| `occupation` | str | no | trimmed; empty → `"unspecified"` | FR-001 |
| `city` | str | no | trimmed; empty → `"unspecified"` | FR-001 |
| `monthly_income` | float | no | coerced; blank/None → `0.0`; negative → `0.0`; must never block the summary | FR-002 |
| `currency` | str | yes | 3-letter code, uppercased, default `"USD"` | FR-001, FR-003 |
| `savings_goal` | str | no | free text; empty → `"no goal set"`; accepts the key `goal` as an alias | FR-001 |

**Sample** (`data/sample_profile.json`, committed): `occupation` `"software engineer"`, `city`
`"Example City"`, `monthly_income` `1900`, `currency` `"USD"`, `goal` `"save 20% of income"`, plus an
extra `household` key. The loader MUST accept this file as-is: `goal` is read into `savings_goal`, and
unknown keys (`household`) are ignored rather than causing an error. `total_income = monthly_income × months`.

## 2. ExpenseRow

One spending record.

| Field | Type | Required | Validation | Source |
|-------|------|----------|------------|--------|
| `date` | datetime64 | yes | parseable; unparseable → row rejected + reported | FR-005, FR-008 |
| `description` | str | no | trimmed; default `""` | FR-005 |
| `category` | str | no | trimmed; blank/missing → `"Uncategorized"` | FR-007 |
| `amount` | float | yes | numeric; negative = refund reducing totals; non-numeric → rejected + reported | FR-006, FR-008 |

Derived: `month` = `"YYYY-MM"` string from `date`.

## 3. InputIssues

The user-facing record of everything that could not be used.

| Field | Type | Notes |
|-------|------|-------|
| `issues` | list[dict] | each: `{ "row": int \| null, "reason": str }` |

Special input-level issues (no row): missing required column (`date` or `amount`), unreadable file,
unsupported file type, empty file, no manual rows entered. When any input-level issue occurs the
summary is not presented as valid (FR-009).

## 4. SpendingSummary

Computed **only** in `src/analysis.py`. This dict is the single input to the advisor (FR-015, FR-010–FR-014).

| Field | Type | Definition |
|-------|------|------------|
| `months` | int | number of distinct `YYYY-MM` values present |
| `total_spend` | float | sum of all amounts (refunds subtract) — FR-010 |
| `by_category` | dict[str, float] | sum of amounts per category — FR-011 |
| `by_category_percent` | dict[str, float] | category total ÷ `total_spend`, 4 dp (0 when total is 0) — FR-011 |
| `by_month` | dict[str, float] | sum of amounts per `YYYY-MM`, only months present — FR-012 |
| `total_income` | float | `monthly_income × months` — FR-013 |
| `savings` | float | `total_income − total_spend` — FR-013 |
| `savings_rate` | float \| null | `savings ÷ total_income`, 4 dp; `null` when income is 0 — FR-002, FR-013 |
| `largest_single_expense` | dict \| null | `{ "description": str, "amount": float }` for the max positive amount (FR-014) |
| `currency` | str | echoes the profile currency for display |

### Ground-truth contract

`data/expected_summary.json` is the authoritative fixture. For `data/sample_expenses.csv` +
`data/sample_profile.json`, the keys `months`, `total_spend`, `by_category`, `by_month`, `total_income`,
`savings`, `savings_rate`, and `largest_single_expense` must match **exactly** (floats compared with a
tolerance of `1e-6`; `savings_rate` rounded to 4 dp). Any additional keys the implementation adds
(e.g. `by_category_percent`, `currency`) are ignored by that comparison but must not change the
authoritative values.

## 5. BudgetComparison

Derived from the summary; also computed in `src/analysis.py` (FR-014).

| Field | Type | Definition |
|-------|------|------------|
| `targets` | dict[str, float] | `{"needs": 0.50, "wants": 0.30, "savings": 0.20}` |
| `actual` | dict[str, float] | `{"needs": needs/total_income, "wants": wants/total_income, "savings": savings/total_income}`, 4 dp |
| `gaps` | dict[str, float] | `actual − target`, 4 dp (positive = over budget) |
| `buckets` | dict[str, list[str]] | the category → bucket mapping actually used, for transparency |

Category → bucket mapping (see research.md §3): needs = Rent, Utilities, Food, Transport, Health,
Education; wants = Entertainment, Shopping, Uncategorized; anything else → wants.

## 6. UnusualSpendFlag

Produced by `src/analysis.py` (FR-014). Each flag is a dict:

| Field | Type | Definition |
|-------|------|------------|
| `type` | str | `"largest_expense"` \| `"large_vs_income"` \| `"month_outlier"` \| `"category_outlier"` |
| `label` | str | short human label, e.g. `"Shopping in 2026-08"` |
| `detail` | str | one-line explanation citing the computed values |
| `amount` | float | the value that triggered the flag |

Thresholds are module constants (`UNUSUAL_MONTH_RATIO = 1.5`, `UNUSUAL_CATEGORY_RATIO = 2.0`,
`LARGE_EXPENSE_INCOME_RATIO = 0.20`). The large-vs-income flag applies only to expenses in the
wants bucket, as defined in §5. An empty flag list is a valid, non-error outcome (FR-015 scenario 3).

## 7. Advice

Plain text (Markdown) returned by `src/advisor.py`. Not persisted.

| Field | Type | Notes |
|-------|------|-------|
| `text` | str | explanations + actionable suggestions (review / rebalance / adjust) |
| `source` | str | `"gemini"` or `"offline"` — used for the UI note and tests |

Contract: `get_advice(profile, summary) -> Advice`. The function receives only the summary dict and
must not compute any number itself (Principle I). Offline path used when the API key is absent, the
request fails/times out, or the response cannot be parsed (FR-021). Every figure mentioned must already
exist in the summary (SC-005). Output is labelled general guidance (FR-022).
