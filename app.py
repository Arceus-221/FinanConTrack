"""Streamlit UI for the Personal Finance Consultant.

UI only. Every figure is computed in :mod:`src.analysis`, advice comes from
:mod:`src.advisor` and all input handling lives in :mod:`src.loader`; this file
just collects widgets and lays out the results. The optional local ``.env`` is
read once here through ``advisor.load_env`` (never inside ``get_advice``), so
the app keeps working fully offline when no key is configured.

Advice is gated behind a "Get advice" button (T009) and cached in
``st.session_state`` keyed by the JSON-serialized summary so that Streamlit
reruns do not re-invoke the advisor.

UI is styled per DESIGN.md (T010): Inter font, indigo primary, metric cards,
category bar chart, monthly trend chart, 50/30/20 target-vs-actual visual.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st
from src import advisor
from src.analysis import build_summary
from src.loader import load_expenses, load_manual_rows, load_profile

#: Key of the manual-entry editor (the AppTest smoke test writes rows here).
EXPENSE_EDITOR_KEY = "expense_editor"
MANUAL_COLUMNS = ["date", "description", "category", "amount"]

#: Session-state key holding the cached (summary_key, Advice) pair.
_ADVICE_CACHE_KEY = "_advice_cache"

#: Session-state key persisting manual rows across AppTest widget reruns.
_MANUAL_ROWS_CACHE_KEY = "_manual_rows_cache"

#: DESIGN.md colours.
_PRIMARY = "#533afd"
_PRIMARY_SOFT = "#665efd"
_RUBY = "#ea2261"
_INK = "#0d253d"
_INK_MUTE = "#64748d"
_CANVAS_SOFT = "#f6f9fc"
_HAIRLINE = "#e3e8ee"

#: Bucket display colours (DESIGN.md palette).
_BUCKET_COLOURS = {
    "needs": "#533afd",
    "wants": "#ea2261",
    "savings": "#2ecc71",
}

_CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

html, body, .stApp {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-feature-settings: "ss01";
}

/* Ensure Material Symbols icons retain their font and ligatures instead of rendering as text */
[data-testid="stIconMaterial"], [data-testid*="Icon"], .material-symbols-rounded {
    font-family: "Material Symbols Rounded" !important;
    font-feature-settings: "liga" 1 !important;
    letter-spacing: normal !important;
}

/* Metric card styling */
div[data-testid="stMetric"] {
    background: #f6f9fc;
    border: 1px solid #e3e8ee;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: rgba(0,55,112,0.05) 0 1px 3px;
}
div[data-testid="stMetric"] label {
    color: #64748d;
    font-weight: 400;
    font-size: 13px;
    letter-spacing: -0.39px;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-weight: 300;
    letter-spacing: -0.64px;
    font-feature-settings: "tnum";
    color: #0d253d;
}

/* Section headers */
h1 {
    font-weight: 300 !important;
    letter-spacing: -1.4px !important;
    color: #0d253d !important;
}
h2 {
    font-weight: 300 !important;
    letter-spacing: -0.64px !important;
    color: #0d253d !important;
    border-bottom: 1px solid #e3e8ee;
    padding-bottom: 8px;
}
h3 {
    font-weight: 300 !important;
    letter-spacing: -0.22px !important;
    color: #0d253d !important;
}

/* Primary button styling — indigo pill */
div.stButton > button[kind="secondary"] {
    background-color: #533afd;
    color: #ffffff;
    border-radius: 9999px;
    border: none;
    font-weight: 400;
    padding: 8px 24px;
    font-size: 16px;
    transition: background-color 0.15s ease;
}
div.stButton > button[kind="secondary"]:hover {
    background-color: #4434d4;
    color: #ffffff;
    border: none;
}
div.stButton > button[kind="secondary"]:active {
    background-color: #2e2b8c;
    color: #ffffff;
}

/* Tabular figures on data */
div[data-testid="stDataFrame"] td {
    font-feature-settings: "tnum";
    letter-spacing: -0.42px;
}

/* Caption muting */
div[data-testid="stCaptionContainer"] {
    color: #64748d;
}
</style>
"""


def _summary_key(summary: dict) -> str:
    """Stable string key derived from the summary dict (for cache comparison)."""
    return json.dumps(summary, sort_keys=True, default=str)


def _category_table(summary: dict) -> pd.DataFrame:
    """Presentation-only rows for the per-category breakdown (no arithmetic)."""
    rows = []
    for name, amount in summary["by_category"].items():
        share = summary["by_category_percent"].get(name, 0.0)
        rows.append({"Category": name, "Amount": amount, "Share": f"{share:.1%}"})
    return pd.DataFrame(rows)


def _month_table(summary: dict) -> pd.DataFrame:
    """Presentation-only rows for the per-month breakdown."""
    return pd.DataFrame(
        [{"Month": month, "Amount": amount} for month, amount in summary["by_month"].items()]
    )


def _comparison_table(summary: dict) -> pd.DataFrame:
    """Presentation-only rows for the 50/30/20 comparison (target vs actual)."""
    comparison = summary["budget_comparison"]
    rows = []
    for bucket in ("needs", "wants", "savings"):
        actual = comparison["actual"][bucket]
        gap = comparison["gaps"][bucket]
        rows.append(
            {
                "Bucket": bucket.capitalize(),
                "Target": f"{comparison['targets'][bucket]:.0%}",
                "Actual": "N/A" if actual is None else f"{actual:.0%}",
                "Gap": "N/A" if gap is None else f"{gap:+.0%}",
            }
        )
    return pd.DataFrame(rows)


def _render_budget_bars(summary: dict) -> None:
    """Render a side-by-side target-vs-actual visual for the 50/30/20 rule."""
    comparison = summary["budget_comparison"]
    for bucket in ("needs", "wants", "savings"):
        target = comparison["targets"][bucket]
        actual = comparison["actual"][bucket]
        gap = comparison["gaps"][bucket]

        label = bucket.capitalize()

        if actual is None:
            st.caption(f"**{label}** — target {target:.0%} · actual N/A")
            st.progress(0.0)
            continue

        # Determine if over/under budget.
        if gap is not None and gap > 0.01:
            status = f"🔴 +{gap:.0%} over"
        elif gap is not None and gap < -0.01:
            status = f"🟢 {abs(gap):.0%} under"
        else:
            status = "✅ on target"

        # Use bar-like display with st.progress capped at 1.0.
        bar_value = min(float(actual), 1.0)
        st.caption(
            f"**{label}** — target {target:.0%} · actual {actual:.0%} · {status}"
        )
        st.progress(bar_value)


def _render_summary(summary: dict, issues: list[dict]) -> None:
    """Render the computed summary, comparison, flags and problem rows."""
    currency = summary["currency"]

    if issues:
        st.warning("⚠️ These rows were skipped:")
        st.dataframe(pd.DataFrame(issues), hide_index=True, use_container_width=True)

    # --- Key metrics row ---
    st.header("📊 Spending summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total spend", f"{summary['total_spend']:,.2f} {currency}")
    col2.metric("Total income", f"{summary['total_income']:,.2f} {currency}")
    col3.metric("Savings", f"{summary['savings']:,.2f} {currency}")
    savings_rate = summary["savings_rate"]
    rate_label = "N/A" if savings_rate is None else f"{savings_rate:.1%}"
    col4.metric("Savings rate", rate_label)
    st.caption(f"Covered months: {summary['months']}")

    # --- Charts row ---
    chart_left, chart_right = st.columns(2)

    with chart_left:
        st.subheader("Spending by category")
        cat_df = pd.DataFrame(
            [
                {"Category": name, "Amount": amount}
                for name, amount in summary["by_category"].items()
            ]
        )
        if not cat_df.empty:
            st.bar_chart(cat_df, x="Category", y="Amount", color=_PRIMARY)
        st.dataframe(_category_table(summary), hide_index=True, use_container_width=True)

    with chart_right:
        st.subheader("Monthly trend")
        month_df = pd.DataFrame(
            [
                {"Month": month, "Amount": amount}
                for month, amount in summary["by_month"].items()
            ]
        )
        if not month_df.empty:
            st.line_chart(month_df, x="Month", y="Amount", color=_RUBY)
        st.dataframe(_month_table(summary), hide_index=True, use_container_width=True)

    # --- 50/30/20 budget comparison ---
    st.subheader("50 / 30 / 20 budget comparison")

    budget_left, budget_right = st.columns([3, 2])
    with budget_left:
        _render_budget_bars(summary)
    with budget_right:
        st.dataframe(_comparison_table(summary), hide_index=True, use_container_width=True)

    # --- Unusual spending ---
    st.subheader("⚡ Unusual spending")
    flags = summary["unusual_flags"]
    if flags:
        for flag in flags:
            st.markdown(f"- **{flag['label']}** — {flag['detail']}")
    else:
        st.caption("No unusual spending detected. 🎉")

    # --- Largest single expense ---
    largest = summary.get("largest_single_expense")
    if largest:
        st.caption(
            f"💰 Largest single expense: **{largest['description']}** "
            f"at {largest['amount']:,.2f} {currency}"
        )


def _get_cached_advice(
    profile: dict, summary: dict
) -> advisor.Advice | None:
    """Return cached advice if the summary hasn't changed, else ``None``."""
    cache = st.session_state.get(_ADVICE_CACHE_KEY)
    if cache is None:
        return None
    cached_key, cached_advice = cache
    if cached_key == _summary_key(summary):
        return cached_advice
    return None


def _store_advice(summary: dict, advice_obj: advisor.Advice) -> None:
    st.session_state[_ADVICE_CACHE_KEY] = (_summary_key(summary), advice_obj)


def main() -> None:
    advisor.load_env()
    st.set_page_config(
        page_title="Personal Finance Consultant",
        page_icon="💼",
        layout="wide",
    )

    # Inject DESIGN.md-aligned CSS.
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    st.title("💼 Personal Finance Consultant")
    st.caption(
        "Every figure is computed from your data in code. Advice is general guidance, "
        "not professional financial advice."
    )

    # --- Profile section ---
    st.header("👤 Your profile")
    left, middle, right = st.columns(3)
    occupation = left.text_input("Occupation", value="software engineer")
    city = left.text_input("City", value="Example City")
    monthly_income = middle.number_input(
        "Monthly income", min_value=0.0, value=1900.0, step=100.0, format="%.2f"
    )
    currency_input = middle.text_input("Currency", value="USD")
    savings_goal = right.text_input("Savings goal", value="save 20% of income")

    profile = load_profile(
        {
            "occupation": occupation,
            "city": city,
            "monthly_income": monthly_income,
            "currency": currency_input,
            "savings_goal": savings_goal,
        }
    )
    currency = profile["currency"]

    # --- Expense input section ---
    st.header("📁 Expenses")
    st.caption(
        f"Upload a CSV/XLSX or type rows below. All amounts are assumed to be in {currency}; "
        "no currency conversion is applied."
    )
    uploaded = st.file_uploader("Upload expenses (CSV or XLSX)", type=["csv", "xlsx", "xls"])
    st.caption("Or enter expenses manually:")
    manual = st.data_editor(
        pd.DataFrame(columns=MANUAL_COLUMNS),
        key=EXPENSE_EDITOR_KEY,
        num_rows="dynamic",
    )

    if uploaded is not None:
        expenses, issues = load_expenses(uploaded)
    else:
        expenses, issues = load_manual_rows(manual)
        if not expenses.empty or issues:
            st.session_state[_MANUAL_ROWS_CACHE_KEY] = (expenses, issues)
        elif _MANUAL_ROWS_CACHE_KEY in st.session_state:
            expenses, issues = st.session_state[_MANUAL_ROWS_CACHE_KEY]

    if expenses.empty:
        # Friendly empty state.
        st.info(
            "👋 **Welcome!** Upload a CSV/XLSX file or enter expense rows above to get started. "
            "Your spending summary and personalized advice will appear here."
        )
        for issue in issues or []:
            if issue.get("reason"):
                st.caption(f"ℹ️ {issue['reason']}")
        st.stop()

    summary = build_summary(profile, expenses)

    # Summary, budget comparison and flags are always visible (T009 / FR-023).
    _render_summary(summary, issues)

    # --- Advice section (gated by button, T009) ---
    st.header("💡 Advice")
    clicked = st.button("Get advice")
    cached = _get_cached_advice(profile, summary)

    if clicked:
        with st.spinner("Generating advice..."):
            advice_obj = advisor.get_advice(profile, summary)
        _store_advice(summary, advice_obj)
        st.markdown(advice_obj.text)
        st.caption(f"Advice source: {advice_obj.source}.")
    elif cached is not None:
        st.markdown(cached.text)
        st.caption(f"Advice source: {cached.source}.")


main()
