# Feature Specification: Personal Finance Consultant

**Feature Branch**: `001-personal-finance-consultant`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "A small Streamlit app that acts as a personal finance consultant. The user enters a profile (occupation, city, monthly income, currency, savings goal), then uploads a CSV/XLSX of expenses or types them in. The app computes a spending summary in code (totals by category and month, savings rate, comparison to a budget rule) and then gives practical advice on how to review, rebalance and adjust spending. The LLM only writes the advice from the computed summary, and there is an offline rule-based fallback."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a spending summary from a profile and expenses (Priority: P1)

A user opens the app, fills in a short profile (occupation, city, monthly income, currency, savings goal), then provides their expenses either by uploading a CSV/XLSX file or by typing rows into a table. The app shows a spending summary: total spend for the period, totals per category, totals per month, each category's share of spend, total income for the period, and the savings rate against the stated goal.

**Why this priority**: This is the foundation of the whole product. Without a trustworthy, self-consistent summary, no advice can be meaningful. Everything else builds on it, and it already delivers standalone value (a clear picture of where money went).

**Independent Test**: Provide the reference synthetic dataset and a sample profile, then confirm the displayed total spend, per-category totals, per-month totals, total income, and savings rate match the independently expected values exactly. No advice is required for this story to be valuable.

**Acceptance Scenarios**:

1. **Given** a valid profile and a valid expense file, **When** the user submits them, **Then** the app displays total spend, a per-category breakdown, a per-month breakdown, category percentages, total income for the period, and the savings rate.
2. **Given** a valid profile and expenses entered manually in the table, **When** the user submits them, **Then** the app produces the same summary as the equivalent file upload.
3. **Given** a profile without a monthly income (zero or blank), **When** the user submits, **Then** the app still shows spend totals and marks the savings rate as not available instead of failing.

---

### User Story 2 - Compare spending to a budget rule and spot unusual spending (Priority: P2)

After seeing the summary, the user wants context: is this spending "normal"? The app compares the spending mix against a standard budgeting rule (needs / wants / savings) and highlights unusual activity such as the single largest expense and categories or months that stand out from the rest.

**Why this priority**: Comparison turns raw numbers into judgment. It is the bridge between the summary and the advice, but the summary alone (P1) is already useful, so this is a second slice.

**Independent Test**: With the reference dataset and profile, confirm the app reports the largest single expense, the budget-rule target versus actual proportions for needs/wants/savings, and at least one unusual-spend flag, all consistent with the independently expected values.

**Acceptance Scenarios**:

1. **Given** a completed summary, **When** the user views the budget comparison, **Then** the app shows the standard rule's target proportions and the user's actual proportions side by side.
2. **Given** a completed summary, **When** the app evaluates unusual spending, **Then** it identifies the largest single expense and any category or month that deviates notably from the user's own pattern.
3. **Given** expenses that fit the rule well, **When** the app evaluates unusual spending, **Then** it reports no unusual-spend flags without error.

---

### User Story 3 - Receive practical, personalized advice (Priority: P3)

The user wants guidance, not just numbers: how to review their spending, how to rebalance it toward their savings goal, and what to adjust. The app writes plain-language explanations and concrete suggestions that reference the user's own figures, occupation, city, currency, and savings goal.

**Why this priority**: This is the "consultant" payoff, but it is only credible once the summary and comparison exist, and it must remain available even when no advice service is reachable.

**Independent Test**: With the reference dataset and profile, confirm the app produces advice that references actual computed figures (e.g., the largest expense, the savings-rate gap versus the goal). Then run the app with no advice service configured or with the service failing, and confirm it still returns useful, coherent advice.

**Acceptance Scenarios**:

1. **Given** a completed summary and budget comparison, **When** the user requests advice, **Then** the app returns explanations and specific, actionable suggestions (review, rebalance, adjust) that cite the user's computed figures and goal.
2. **Given** no advice service is configured, or the advice service fails or times out, **When** the user requests advice, **Then** the app returns rule-based advice instead of an error or an empty panel.
3. **Given** advice has been generated, **When** it is displayed, **Then** it presents itself as general guidance and not as professional financial advice.

---

### Edge Cases

- **Refunds / negative amounts**: a negative amount is a refund and reduces total spend and the relevant category/month totals.
- **Blank or missing category**: the expense is grouped under "Uncategorized".
- **Malformed rows** (missing date, non-numeric amount, unparseable date): the row is skipped and reported to the user in a "problem rows" list; the app does not crash.
- **Empty input** (no rows at all): the app tells the user it needs expense data and does not show a misleading zero summary as if it were valid.
- **Unsupported or unreadable file** (wrong type, corrupt file, empty file): the app reports the problem clearly and keeps the app running.
- **Single month of data**: monthly breakdown, savings rate, and "unusual month" detection degrade gracefully rather than erroring.
- **Currency mismatch**: the app treats all amounts as being in the profile currency; it does not convert and it states this assumption rather than silently mislabeling.
- **Extremely large or tiny values**: totals and percentages still compute and display without overflow or formatting failures.
- **Duplicate rows**: duplicates are included in the totals as-is; the app does not silently deduplicate.
- **Date range with gaps**: months present in the data are reported; missing months are not invented.

## Requirements *(mandatory)*

### Functional Requirements

**Profile capture**

- **FR-001**: The app MUST let the user enter a profile with occupation, city, monthly income, currency, and savings goal.
- **FR-002**: The app MUST accept a monthly income of zero or blank and MUST clearly mark derived values (such as savings rate) as unavailable rather than failing.
- **FR-003**: The app MUST display all monetary values in the currency selected in the profile.

**Expense input**

- **FR-004**: The app MUST let the user provide expenses either by uploading a CSV/XLSX file or by entering rows manually, and both paths MUST produce identical results for identical data.
- **FR-005**: Each expense MUST carry a date, a description, a category, and an amount; the app MUST identify which of these a file provides.
- **FR-006**: The app MUST treat a negative amount as a refund that reduces total spend and the affected category and month totals.
- **FR-007**: The app MUST group expenses with a blank or missing category under "Uncategorized".
- **FR-008**: The app MUST skip malformed rows, keep running, and report the skipped rows (with the reason) to the user.
- **FR-009**: The app MUST report an empty or unreadable file (or no manual rows) as an input problem rather than showing a misleading summary.

**Computed spending summary (all figures computed in code, never by the advice layer)**

- **FR-010**: The app MUST compute total spend for the covered period.
- **FR-011**: The app MUST compute total spend per category.
- **FR-012**: The app MUST compute total spend per month, using only the months actually present in the data.
- **FR-013**: The app MUST compute each category's percentage share of total spend.
- **FR-014**: The app MUST compute total income for the covered period from the profile's monthly income and the number of covered months.
- **FR-015**: The app MUST compute the amount saved and the savings rate (saved amount divided by total income), marking the rate unavailable when income is zero or blank.
- **FR-016**: The app MUST compare the spending mix against a standard needs/wants/savings budget rule and show target versus actual proportions.
- **FR-017**: The app MUST identify the single largest expense and flag categories or months that deviate notably from the user's own pattern.
- **FR-018**: The app MUST produce the entire summary as structured data that is the sole numeric input to the advice layer.

**Advice**

- **FR-019**: The app MUST present plain-language advice covering how to review spending, how to rebalance it, and what to adjust, referencing the user's computed figures, occupation, city, currency, and savings goal.
- **FR-020**: The advice layer MUST NOT perform arithmetic; it MUST derive its statements only from the pre-computed summary.
- **FR-021**: The app MUST provide advice even when no advice service is configured, or when the service fails or times out, by using rule-based advice derived from the same summary.
- **FR-022**: The app MUST label all advice as general guidance, not professional financial advice.
- **FR-023**: The app MUST keep working and remain usable when advice generation is unavailable; the summary and budget comparison remain visible.

**Privacy & safety**

- **FR-024**: The app MUST NOT require or expose any secret in the user interface or in logs, and any advice-service credentials MUST be read only from a non-committed local configuration.
- **FR-025**: The app MUST NOT persist user expense data beyond the running session.

### Key Entities *(include if feature involves data)*

- **Profile**: the user's context — occupation, city, monthly income, currency, savings goal. Used for framing and for income/savings-rate math.
- **Expense**: one spending record — date, description, category, amount (negative = refund). Blank category resolves to "Uncategorized".
- **Spending Summary**: the computed picture — total spend, per-category totals and percentages, per-month totals, covered months, total income, saved amount, savings rate, largest expense, and unusual-spend flags.
- **Budget Comparison**: the standard needs/wants/savings rule targets beside the user's actual proportions, with the gaps between them.
- **Advice**: plain-language explanations and actionable suggestions (review, rebalance, adjust) generated from the Spending Summary and Budget Comparison, either by the advice service or by the offline rule-based path.
- **Input Issues**: the list of skipped/problem rows and input-level problems reported to the user.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can go from opening the app to seeing a spending summary in under 3 minutes, using either file upload or manual entry.
- **SC-002**: For the reference synthetic dataset and sample profile, every displayed figure (total spend, each category total, each month total, each percentage, total income, saved amount, savings rate, largest expense) matches the independently expected values exactly.
- **SC-003**: For a dataset containing malformed rows and refunds, the app completes without crashing, includes refunds in the totals, and reports 100% of the malformed rows to the user.
- **SC-004**: Advice is available in 100% of runs, including runs with no advice service configured or with the service failing, with the offline path producing coherent advice.
- **SC-005**: For any run, every number appearing anywhere in the advice can be traced back to a value already present in the computed summary (no figure is invented by the advice layer).
- **SC-006**: Identical expense data provided by file upload and by manual entry yields identical summaries in 100% of tested cases.
- **SC-007**: The summary, budget comparison, and advice are produced within 5 seconds for datasets of up to a few thousand expense rows on a typical laptop.

## Assumptions

- **Budget rule default**: the "budget rule" is the widely used 50/30/20 needs / wants / savings split; this is the default target and is shown as a reference, not a hard requirement.
- **Income period**: total income is the profile's monthly income multiplied by the number of months present in the expense data (e.g., 3 months of data at a monthly income of 1900 yields 5700).
- **Single currency, no conversion**: all amounts are assumed to be in the profile currency; no exchange-rate conversion is performed.
- **Single user, local session**: one user at a time, no accounts, login, or multi-user persistence; data lives only for the running session.
- **Language**: user-facing text is in English.
- **Advice framing**: advice is educational and generic to the user's numbers; it is not regulated financial, tax, or investment advice.
- **Data**: only synthetic data is used during development; any real user data stays local and is not committed.
- **Reference ground truth**: the analysis is validated against the committed synthetic dataset and its expected summary.
