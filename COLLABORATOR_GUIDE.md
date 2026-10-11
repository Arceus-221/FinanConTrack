# FinanConTrack: Collaborator Guide

Welcome! This guide gets you from "just got access" to "making a useful change" without needing to
ask the original author. Read sections 1 to 4 first (about 10 minutes). Section 6 is the menu of things you can work on.

> **Heads-up about how this project was built.** Almost all of the code was written by AI coding agents
> (planner, implementer, tester, reviewer) coordinated by a script, not typed by hand. It works and its
> tests pass, but nobody has read every line with fresh eyes. Treat the code as a first draft by a fast
> junior developer: your careful review is one of the most valuable contributions you can make.

---

## 1. What the app does today

A small **Streamlit** web app that acts as a personal finance consultant.

1. The user fills in a **profile**: occupation, city, monthly income, currency, savings goal.
2. The user provides **expenses**, either by uploading a CSV/XLSX file or by typing rows into a table.
3. The app shows a **spending summary**, all computed in code with pandas:
   total spend, totals per category and per month, each category's share, total income for the period,
   amount saved and savings rate.
4. It compares spending to the **50/30/20 rule** (needs / wants / savings) and shows unusual-spend flags
   (e.g. the largest single expense, or a category that spiked in one month).
5. It reports **problem rows** (bad dates, non-numeric amounts) instead of crashing. Refunds are negative
   amounts and reduce totals; a blank category becomes "Uncategorized".
6. It shows **advice** (review, rebalance, adjust) with a "general guidance, not professional financial
   advice" label. The advice comes from **Gemini** if an API key is configured, otherwise (or if the
   call fails or times out) from an **offline rule-based advisor**. The source is shown under the advice.

What it does **not** do yet: advice currently appears automatically with the summary (there is no
"Get advice" button), the UI is very basic, there are no charts, and it has no Docker/CI setup.

> This section describes the intended behaviour from the project's spec plus what has been checked by
> hand. If you find that the code does something different, trust the code and fix this guide.

## 2. Get it running locally

You need **Git** and **uv** (a fast Python package/project manager). Python 3.11+ is required; uv will
fetch a suitable Python for you.

**Install uv** (once):

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Clone, install, test, run:**

```bash
git clone https://github.com/Arceus-221/FinanConTrack.git
cd <repo-folder>
uv sync                                  # creates .venv and installs everything
uv run pytest -q                         # expect all tests to pass (47 at the time of writing)
uv run ruff check .                      # expect "All checks passed!"
uv run streamlit run app.py              # opens the app in your browser
```

If `uv sync` is slow or times out on a weak connection, retry; completed downloads are cached. On Windows
you can also try `$env:UV_HTTP_TIMEOUT=600` first.

**Try it:** enter a profile with monthly income `1900`, upload `data/sample_expenses.csv`. The total spend
should be `4782.97` and the savings rate about `16.1%`. Those numbers are checked by an automated test
against `data/expected_summary.json`.

### Optional: Gemini advice

The app works fully offline. To try the Gemini path you need your **own** key (never ask for someone else's):

1. Create a free API key in Google AI Studio.
2. Create a file named exactly `.env` in the project root (same folder as `app.py`) with two lines, no
   quotes, no spaces around `=`:

   ```
   GEMINI_API_KEY=your-key-here
   GEMINI_MODEL=<a model id that your key can use>
   ```
3. `.env` is gitignored. **Never commit it, paste it into chats, or print it in logs.** Check with
   `git status` before every commit.
4. Restart the app after changing `.env`. If the advice source still says "offline", the model is
   probably out of free quota (HTTP 429), so try another model ID. Use the bare model id here (no
   `google/` prefix; that prefix is only used by the OpenCode agent tooling).

The free tier has small **per-model daily request limits**. Streamlit reruns the script on every
interaction, so avoid clicking around heavily while a key is set (see improvement #1).

## 3. Repository map

| Path | What it is |
|------|-----------|
| `app.py` | Streamlit UI only (layout and widgets). No business logic. |
| `src/loader.py` | CSV/XLSX and manual rows → clean DataFrame plus a list of issues; profile normalization. |
| `src/analysis.py` | **All numbers**: totals, by-category/month, percentages, savings rate, 50/30/20 comparison, unusual-spend flags. |
| `src/advisor.py` | Turns the computed summary into advice: Gemini call (stdlib `urllib`), `.env` reader, offline rule-based fallback. |
| `tests/` | pytest suite, including `test_sample_data.py` (ground truth) and an AppTest UI smoke test. |
| `data/` | Synthetic sample data: `sample_expenses.csv`, `sample_profile.json`, `expected_summary.json`. |
| `specs/001-personal-finance-consultant/` | The spec-kit documents: `spec.md` (what and why), `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `tasks.md`. **Read `spec.md` and `data-model.md` before changing behaviour.** |
| `DESIGN.md` | A Stripe-style design reference, intended as the style guide for the UI (not applied yet). |
| `AGENTS.md` | The project rules the AI agents follow. Humans should follow them too. |
| `.opencode/agents/`, `scripts/`, `agents.env`, `PROGRESS.md`, `interventions.md`, `.specify/` | The AI build tooling and its logs. You can ignore these unless you use the agent loop (section 5). |

Data flow: `UI → loader → analysis.build_summary → advisor.get_advice → Advice(text, source)`.

## 4. Ground rules (please keep these)

1. **Numbers are computed in code, never by the LLM.** Every figure lives in `src/analysis.py`. The advisor
   only sees the computed summary dict and must not do arithmetic. Every number quoted in advice must
   already appear in the summary.
2. **Offline always works.** No key, no network, or a failing call → rule-based advice, never an error panel.
3. **Tests never touch the network.** Monkeypatch the HTTP layer and remove `GEMINI_API_KEY` in tests, so
   a developer's real `.env` cannot change test results.
4. **`app.py` is UI only.** New logic goes in `src/` with tests.
5. **Bad input never crashes the app.** Report it to the user instead.
6. **Secrets and data:** `.env` stays local; only synthetic data is committed; the key must never appear
   in URLs, logs or error messages (it is sent in the `x-goog-api-key` header).
7. **Definition of done** for any change: `uv run pytest -q` passes, `uv run ruff check .` is clean, and
   there is at least one test for the new behaviour. Write the failing test first when you can.
8. Don't run `streamlit run` inside automated scripts or agents (it never exits). Test the UI with AppTest.

**Suggested Git workflow:** work on a branch (`git switch -c feature/<short-name>`), commit small, push, and
open a pull request. Don't push straight to `main` unless you've agreed that with the owner. Line endings
are managed by `.gitattributes`; on Windows, let git handle them and don't convert files by hand.

## 5. Two ways to work: by hand, or with the agent loop

**By hand (recommended to start):** edit code, run the tests, open a PR. Nothing else needed.

**With the agent loop (optional, advanced):** the project includes a script that has AI agents implement
tasks from `specs/.../tasks.md` (implementer → tester → reviewer per task, one commit per approved task).
You need the OpenCode CLI configured with a model provider, Git Bash (on Windows) or a Unix shell, and
your own model IDs in `agents.env` (`provider/model` format, as printed by `opencode models`; list backups in
`FALLBACK_MODELS`). Edit `agents.env` locally and don't commit your personal settings.

To queue a job, add one line to `tasks.md` in exactly this format (the script parses it), then run
`./scripts/run-loop.sh`:

```
- [ ] T0NN <imperative description> | accept: <one testable acceptance criterion>
```

While the loop runs, don't edit files or start other agent sessions in the same folder (the reviewer judges
the uncommitted `git diff`). Free-tier model quotas run out quickly; the script rotates through your fallback
models and stops cleanly when all are exhausted, and you can simply rerun it later. Read the resulting diff
yourself before merging. Agents (especially when the same model writes and reviews) can approve weak work.

## 6. Ideas for improvement (pick what interests you)

**High value, small**

1. **"Get advice" button + caching.** Show advice only after a click and cache it in `st.session_state`
   keyed by the summary, so reruns don't spend API requests. The summary and budget comparison stay visible
   without it. Suggested task line:
   ```
   - [ ] T009 In app.py, show advice only after the user clicks a "Get advice" button and cache the result in st.session_state keyed by the summary so reruns do not call the advisor again; the summary, budget comparison and flags stay visible without it | accept: tests/test_app.py (AppTest, advisor monkeypatched, GEMINI_API_KEY removed) asserts the advisor is not called before the click, is called exactly once after one click and one further rerun, and the advice text and its source label are shown after the click
   ```
2. **Improve the UI.** It is currently very basic. Ideas: metric cards for total spend, income, savings rate;
   a category bar chart and a monthly trend chart; a side-by-side 50/30/20 target-vs-actual visual with colour
   for over/under budget; clearer sections and spacing; a friendly empty state; a loading indicator. Apply
   `DESIGN.md` (colours, typography, spacing), using `.streamlit/config.toml` for the theme and small CSS
   where needed. Keep logic in `src/`, UI in `app.py`.
3. **Update stale docs and defaults.** `research.md` names an old default Gemini model; make the default
   configurable and current. Add a proper `README.md`.
4. **Check that advice invents no numbers** (spec criterion SC-005): write a validator that extracts numbers
   from the advice text and checks that each exists in the summary, and test both advisors with it.

**Medium**

5. **Make the budget rule configurable:** choose 50/30/20 or another split, and let users edit the
   category → bucket mapping (`CATEGORY_BUCKETS` in `analysis.py`).
6. **More flexible input:** column mapping for CSVs with different headers, more date formats, multi-sheet
   XLSX, clearer messages per problem row, currency symbols and number formatting.
7. **Export:** download the summary (CSV) or a printable report.
8. **Gemini robustness:** confirm response parsing works across model types (some models return extra parts),
   configurable timeout and one retry, friendlier "using offline advice because…" note in the UI.
9. **Better advice prompts:** more specific, shorter, structured sections (review / rebalance / adjust),
   tested against fixed sample summaries.

**Engineering hygiene**

10. **Docker:** a `Dockerfile` (base image with Python, install uv, `uv sync`, run Streamlit on `0.0.0.0`),
    a `.dockerignore` that excludes `.env`, `.venv`, `.git`, and a note on passing `GEMINI_API_KEY` at run time
    (never bake it into the image). The project is not Dockerized yet.
11. **CI:** a GitHub Actions workflow running `uv sync`, `uv run pytest -q` and `uv run ruff check .` on every
    pull request.
12. **More tests** for the edge cases in `spec.md`: single month, empty file, unreadable file, duplicate rows,
    zero income, very large values, date gaps, and a performance check for a few thousand rows.

## 7. Checks you can run to find real bugs

Work through the scenarios in `specs/001-personal-finance-consultant/quickstart.md`, plus these:

- Upload the sample CSV, then enter the same rows manually: are all figures identical?
- Upload a CSV with a bad date, a non-numeric amount, a blank category and a refund. Are all bad rows listed,
  the refund subtracted, the blank category shown as "Uncategorized", and the app still running?
- Set monthly income to 0 or blank. Does the savings rate show as unavailable rather than failing?
- Use a single month of data, an empty file, and a non-CSV file.
- With no `.env`, is advice offline and labelled as general guidance? With a key, does it say "gemini"?
- Search the code for anything that could print or log the API key, the request URL, or user expense data.
- Read the tests with suspicion: do they assert real values, or could they pass while the code is wrong?
  (The same AI tooling wrote both the code and most of the tests.)

## 8. Getting unstuck

- Behaviour questions → `specs/001-personal-finance-consultant/spec.md` and `data-model.md`.
- "Why is it built this way?" → `plan.md` and `research.md` (each decision lists the alternatives considered).
- Free-tier Gemini errors: HTTP 429 means quota (switch model or wait for the daily reset); 404 means a bad
  model id; 400/403 means a bad key.
- Anything unclear or wrong in this guide: fix it in a pull request. Future contributors will thank you.
