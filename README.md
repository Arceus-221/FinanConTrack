# FinanConTrack — Personal Finance Consultant

## Team Members

| Name                 | Student ID |
| -------------------- | ---------- |
| Aakash Abdullah      | 220041221  |
| Md. Sazidur Rahman   | 220041226  |

## Project Description

**FinanConTrack** is a personal finance consultant web application built with
Python and Streamlit. Users create a financial profile (occupation, city, monthly
income, currency, and savings goal), then upload a CSV/XLSX file of expenses or
enter them manually. The app computes a full spending summary — totals,
per-category and per-month breakdowns, percentages, savings rate, 50/30/20
budget comparison, and unusual-spend flags — entirely in code using pandas. It
then generates practical, human-readable advice on how to review, rebalance, and
adjust spending. Advice is produced by rule-based logic offline, or optionally
enhanced by Google Gemini when an API key is provided.

## Tools & Technologies

| Category           | Technology                                              |
| ------------------ | ------------------------------------------------------- |
| Language           | Python 3.12                                             |
| UI Framework       | Streamlit                                               |
| Data Processing    | pandas, openpyxl                                       |
| AI (optional)      | Google Gemini API (falls back to rule-based advice)     |
| Package Manager    | uv                                                      |
| Testing            | pytest                                                  |
| Linting            | ruff                                                    |
| Version Control    | Git & GitHub                                            |

## How to Run (Setup Instructions for Judges)

### Prerequisites

- **Python 3.11+** — [Download Python](https://www.python.org/downloads/)
- **uv** (Python package manager) — install with:
  ```bash
  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Arceus-221/FinanConTrack.git
cd FinanConTrack

# 2. Install all dependencies
uv sync

# 3. (Optional) Enable AI-powered advice — create a .env file:
#    GEMINI_API_KEY=your-api-key-here
#    Without this, the app still works fully with rule-based advice.

# 4. Run the app
uv run streamlit run app.py
```

The app will open in your browser at **http://localhost:8501**.

### Testing the App

1. Fill in your **profile** (occupation, city, monthly income, currency, savings goal).
2. **Upload** the sample file `data/sample_expenses.csv`, or enter expenses manually.
3. View the **spending summary** — category breakdowns, monthly trends, 50/30/20 budget comparison.
4. Click **Get Advice** to receive personalised financial suggestions.

### Running Tests & Linting

```bash
uv run pytest -q        # Run the test suite
uv run ruff check .     # Run the linter
```

## GitHub Repository

🔗 **https://github.com/Arceus-221/FinanConTrack**

## Project Layout

```
app.py              Streamlit UI (calls src/ only, no logic)
src/
  loader.py         CSV/XLSX/manual-row parsing and profile normalisation
  analysis.py       Deterministic spending analysis (pandas)
  advisor.py        Advice generation (offline rules + optional Gemini)
  validator.py      Advice number validator
tests/              pytest suite
data/               Synthetic sample data
.streamlit/         Streamlit theme config
```

## Architecture

- **All numbers are computed in code** (`src/analysis.py`). The LLM never does arithmetic.
- **Offline-first**: if there is no API key or the Gemini call fails, rule-based advice is returned.
- **Clean separation**: `app.py` only calls functions from `src/`. No logic in the UI file.
- **Secrets**: live only in `.env` (gitignored). Never printed or committed.
