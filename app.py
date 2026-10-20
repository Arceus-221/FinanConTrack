"""Streamlit UI for the Personal Finance Consultant.

Presentation layer only. Every figure is computed in :mod:`src.analysis`, advice
comes from :mod:`src.advisor` and all input handling lives in :mod:`src.loader`;
this file collects widgets and lays out the results. The optional local ``.env``
is read once here through ``advisor.load_env`` (never inside ``get_advice``), so
the app keeps working fully offline when no key is configured.

Advice is gated behind a "Get advice" button (T009) and cached in
``st.session_state`` keyed by the JSON-serialized summary so that Streamlit
reruns do not re-invoke the advisor.

Styled with a refined dark theme: system font stack, tabular numerals, steel
blue charts, amber accent button, muted semantic indicators for budget gaps,
no emoji, and responsive card layouts.
"""

from __future__ import annotations

import html
import json

import altair as alt
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

#: Dark theme palette tokens.
_PAGE_BG = "#0E1116"
_SURFACE = "#151A21"
_SURFACE_RAISED = "#1B2129"
_BORDER_HAIRLINE = "#262E38"
_TEXT_PRIMARY = "#E6EAF0"
_TEXT_SECONDARY = "#9AA6B2"
_TEXT_MUTED = "#6B7683"
_DATA_STEEL_BLUE = "#7C9CBF"
_ACCENT_AMBER = "#E0A458"
_STATUS_CORAL = "#D9685F"
_STATUS_TEAL = "#4FB3A5"

_CUSTOM_CSS = """
<style>
/* Reset and System Font Stack (Offline-only, no external web fonts) */
html, body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
        "Helvetica Neue", Arial, sans-serif;
    background-color: #0E1116;
    color: #E6EAF0;
}

/* Page container constraints (max ~1100px, centered) */
.block-container {
    max-width: 1100px !important;
    padding-top: 2rem !important;
    padding-bottom: 4rem !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Headings Hierarchy */
h1 {
    font-size: 26px !important;
    font-weight: 500 !important;
    letter-spacing: -0.02em !important;
    color: #E6EAF0 !important;
    margin-bottom: 4px !important;
}

h2 {
    font-size: 13px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: #9AA6B2 !important;
    border-bottom: 1px solid #262E38 !important;
    padding-bottom: 8px !important;
    margin-top: 36px !important;
    margin-bottom: 16px !important;
}

h3 {
    font-size: 15px !important;
    font-weight: 500 !important;
    letter-spacing: -0.01em !important;
    color: #E6EAF0 !important;
    margin-top: 20px !important;
    margin-bottom: 10px !important;
}

/* Subtitle and Disclaimer note */
.disclaimer-note {
    border: 1px solid #262E38;
    background: #151A21;
    border-radius: 6px;
    padding: 10px 14px;
    color: #9AA6B2;
    font-size: 13px;
    line-height: 1.5;
    margin-top: 8px;
    margin-bottom: 16px;
}

/* Metric card styling */
div[data-testid="stMetric"] {
    background: #151A21;
    border: 1px solid #262E38;
    border-radius: 8px;
    padding: 16px 18px;
    box-shadow: none;
}
div[data-testid="stMetric"] label,
div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
    color: #9AA6B2 !important;
    font-weight: 500 !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-weight: 400 !important;
    font-size: clamp(1.2rem, 2.2vw, 1.6rem) !important;
    letter-spacing: -0.02em !important;
    font-variant-numeric: tabular-nums !important;
    font-feature-settings: "tnum" 1 !important;
    color: #E6EAF0 !important;
    white-space: nowrap !important;
}

/* Inputs styling */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    background-color: #151A21 !important;
    border: 1px solid #262E38 !important;
    color: #E6EAF0 !important;
    border-radius: 6px !important;
    font-size: 14px !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus {
    border-color: #E0A458 !important;
    box-shadow: 0 0 0 1px #E0A458 !important;
}
div[data-testid="stTextInput"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stFileUploader"] label {
    color: #9AA6B2 !important;
    font-size: 13px !important;
}

/* File uploader container */
div[data-testid="stFileUploader"] section {
    background-color: #151A21 !important;
    border: 1px dashed #262E38 !important;
    border-radius: 6px !important;
}
div[data-testid="stFileUploader"] section:hover {
    border-color: #E0A458 !important;
}

/* Primary Accent Button — Amber */
div.stButton > button {
    background-color: #E0A458 !important;
    color: #0E1116 !important;
    border-radius: 6px !important;
    border: 1px solid #E0A458 !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 8px 22px !important;
    letter-spacing: 0.02em !important;
    transition: background-color 0.15s ease, border-color 0.15s ease !important;
}
div.stButton > button:hover {
    background-color: #ECC082 !important;
    border-color: #ECC082 !important;
    color: #0E1116 !important;
}
div.stButton > button:focus {
    box-shadow: 0 0 0 2px #0E1116, 0 0 0 4px #E0A458 !important;
}

/* Tabs styling */
div[data-testid="stTabs"] button[role="tab"] {
    color: #9AA6B2 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    border-bottom: 2px solid transparent !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #E6EAF0 !important;
    border-bottom: 2px solid #E0A458 !important;
}

/* Tables and DataFrames */
div[data-testid="stDataFrame"] {
    border: 1px solid #262E38 !important;
    border-radius: 6px !important;
    background: #151A21 !important;
}
div[data-testid="stDataFrame"] td {
    font-variant-numeric: tabular-nums !important;
    font-feature-settings: "tnum" 1 !important;
    letter-spacing: -0.01em !important;
}

/* Alerts and Notices */
div[data-testid="stAlert"] {
    background-color: #151A21 !important;
    border: 1px solid #262E38 !important;
    border-radius: 6px !important;
    color: #E6EAF0 !important;
}
div[data-testid="stAlert"] [data-testid="stAlertContentWarning"] {
    border-left: 3px solid #D9685F !important;
}
div[data-testid="stAlert"] [data-testid="stAlertContentInfo"] {
    border-left: 3px solid #7C9CBF !important;
}

/* Captions and Muted text */
div[data-testid="stCaptionContainer"] {
    color: #9AA6B2 !important;
    font-size: 13px !important;
}

/* Budget Comparison Visuals */
.budget-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 12px;
}
.budget-card {
    background: #151A21;
    border: 1px solid #262E38;
    border-radius: 6px;
    padding: 12px 16px;
}
.budget-card-meta {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
    font-size: 13px;
}
.budget-bucket-name {
    font-weight: 600;
    color: #E6EAF0;
}
.budget-card-figures {
    color: #9AA6B2;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum" 1;
}
.budget-card-status {
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum" 1;
}
.budget-bar-track {
    position: relative;
    height: 6px;
    background: #1B2129;
    border-radius: 3px;
}
.budget-bar-fill {
    height: 100%;
    background: #7C9CBF;
    border-radius: 3px;
}
.budget-bar-tick {
    position: absolute;
    top: -4px;
    width: 2px;
    height: 14px;
    background: #E0A458;
    transform: translateX(-50%);
    border-radius: 1px;
}

/* Unusual Spending List */
.unusual-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
}
.unusual-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    background: #151A21;
    border: 1px solid #262E38;
    border-radius: 6px;
    padding: 10px 14px;
    gap: 12px;
}
.unusual-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.unusual-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9AA6B2;
    background: #1B2129;
    border: 1px solid #262E38;
    border-radius: 4px;
    padding: 2px 6px;
    align-self: flex-start;
}
.unusual-desc {
    color: #E6EAF0;
    font-size: 13px;
    line-height: 1.4;
}
.unusual-amount {
    font-weight: 500;
    font-size: 13px;
    color: #E6EAF0;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum" 1;
    white-space: nowrap;
}

/* Advice Container */
.advice-column {
    max-width: 70ch;
    line-height: 1.65;
    color: #E6EAF0;
    font-size: 15px;
    margin-top: 16px;
}
.advice-column h2 {
    font-size: 16px !important;
    font-weight: 600 !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    color: #E6EAF0 !important;
    border-bottom: none !important;
    padding-bottom: 0 !important;
    margin-top: 20px !important;
    margin-bottom: 6px !important;
}
.advice-column h3 {
    font-size: 14px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: #E0A458 !important;
    margin-top: 18px !important;
    margin-bottom: 6px !important;
}
.advice-column ul {
    margin-top: 4px !important;
    margin-bottom: 14px !important;
    padding-left: 20px !important;
}
.advice-column li {
    margin-bottom: 6px !important;
    color: #E6EAF0 !important;
}
.advice-column em {
    color: #9AA6B2 !important;
    font-size: 13px !important;
    display: block !important;
    margin-top: 14px !important;
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
        rows.append({"Category": name, "Amount": f"{amount:,.2f}", "Share": f"{share:.1%}"})
    return pd.DataFrame(rows)


def _month_table(summary: dict) -> pd.DataFrame:
    """Presentation-only rows for the per-month breakdown."""
    return pd.DataFrame(
        [
            {"Month": month, "Amount": f"{amount:,.2f}"}
            for month, amount in summary["by_month"].items()
        ]
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


def _render_category_chart(summary: dict) -> alt.Chart:
    """Altair horizontal bar chart sorted descending in steel blue with direct labels."""
    cat_df = pd.DataFrame(
        [
            {"Category": name, "Amount": amount}
            for name, amount in summary["by_category"].items()
        ]
    )
    if cat_df.empty:
        return alt.Chart(pd.DataFrame()).mark_bar()

    bars = (
        alt.Chart(cat_df)
        .mark_bar(color=_DATA_STEEL_BLUE, cornerRadiusEnd=3, height=18)
        .encode(
            y=alt.Y(
                "Category:N",
                sort="-x",
                title=None,
                axis=alt.Axis(
                    labelColor=_TEXT_SECONDARY,
                    domainColor=_BORDER_HAIRLINE,
                    tickColor=_BORDER_HAIRLINE,
                    labelFontSize=12,
                ),
            ),
            x=alt.X(
                "Amount:Q",
                title=None,
                axis=alt.Axis(labels=False, grid=False, domain=False, ticks=False),
            ),
            tooltip=[
                alt.Tooltip("Category:N", title="Category"),
                alt.Tooltip("Amount:Q", format=",.2f", title=f"Amount ({summary['currency']})"),
            ],
        )
    )

    text = bars.mark_text(
        align="left",
        baseline="middle",
        dx=6,
        color=_TEXT_SECONDARY,
        fontSize=11,
    ).encode(
        text=alt.Text("Amount:Q", format=",.2f"),
    )

    return (
        (bars + text)
        .properties(
            background="transparent",
            height=alt.Step(26),
        )
        .configure_view(strokeWidth=0)
    )


def _render_trend_chart(summary: dict) -> alt.Chart:
    """Altair line chart for monthly trend in steel blue with visible points and data labels."""
    month_df = pd.DataFrame(
        [
            {"Month": month, "Amount": amount}
            for month, amount in summary["by_month"].items()
        ]
    )
    if month_df.empty:
        return alt.Chart(pd.DataFrame()).mark_line()

    base = alt.Chart(month_df).encode(
        x=alt.X(
            "Month:N",
            title=None,
            axis=alt.Axis(
                labelColor=_TEXT_SECONDARY,
                domainColor=_BORDER_HAIRLINE,
                tickColor=_BORDER_HAIRLINE,
                labelFontSize=12,
            ),
        ),
        y=alt.Y(
            "Amount:Q",
            title=None,
            axis=alt.Axis(
                labelColor=_TEXT_SECONDARY,
                domainColor=_BORDER_HAIRLINE,
                tickColor=_BORDER_HAIRLINE,
                gridColor=_SURFACE_RAISED,
                labelFontSize=11,
            ),
        ),
        tooltip=[
            alt.Tooltip("Month:N", title="Month"),
            alt.Tooltip("Amount:Q", format=",.2f", title=f"Amount ({summary['currency']})"),
        ],
    )

    line = base.mark_line(
        color=_DATA_STEEL_BLUE,
        strokeWidth=2,
        point=alt.OverlayMarkDef(color=_DATA_STEEL_BLUE, size=50, filled=True),
    )

    text = base.mark_text(
        align="center",
        baseline="bottom",
        dy=-10,
        color=_TEXT_SECONDARY,
        fontSize=11,
    ).encode(
        text=alt.Text("Amount:Q", format=",.2f"),
    )

    return (
        (line + text)
        .properties(
            background="transparent",
            height=250,
        )
        .configure_view(strokeWidth=0)
    )


def _render_budget_bars(summary: dict) -> None:
    """Render a target-vs-actual visual for the 50/30/20 rule with thin tick and fill."""
    comparison = summary["budget_comparison"]
    cards_html = []
    for bucket in ("needs", "wants", "savings"):
        target = comparison["targets"][bucket]
        actual = comparison["actual"][bucket]
        gap = comparison["gaps"][bucket]

        label = bucket.capitalize()

        if actual is None:
            cards_html.append(
                f"""<div class="budget-card">
                    <div class="budget-card-meta">
                        <span class="budget-bucket-name">{label}</span>
                        <span class="budget-card-figures">Target {target:.0%} · Actual N/A</span>
                        <span class="budget-card-status" style="color: {_TEXT_MUTED};">N/A</span>
                    </div>
                    <div class="budget-bar-track"></div>
                </div>"""
            )
            continue

        target_pct = min(max(float(target) * 100, 0.0), 100.0)
        fill_pct = min(max(float(actual) * 100, 0.0), 100.0)

        if gap is not None and gap > 0.01:
            status_text = f"+{gap:.0%} over"
            status_color = _STATUS_CORAL
        elif gap is not None and gap < -0.01:
            status_text = f"{abs(gap):.0%} under"
            status_color = _STATUS_TEAL
        else:
            status_text = "on target"
            status_color = _TEXT_SECONDARY

        tick_html = (
            f'<div class="budget-bar-tick" style="left: {target_pct:.1f}%;" '
            f'title="Target: {target:.0%}"></div>'
        )
        cards_html.append(
            f"""<div class="budget-card">
                <div class="budget-card-meta">
                    <span class="budget-bucket-name">{label}</span>
                    <span class="budget-card-figures">
                        Target {target:.0%} · Actual {actual:.0%}
                    </span>
                    <span class="budget-card-status" style="color: {status_color};">
                        {status_text}
                    </span>
                </div>
                <div class="budget-bar-track">
                    <div class="budget-bar-fill" style="width: {fill_pct:.1f}%;"></div>
                    {tick_html}
                </div>
            </div>"""
        )

    content = "".join(cards_html)
    st.markdown(f'<div class="budget-container">{content}</div>', unsafe_allow_html=True)


def _render_unusual_spending(summary: dict) -> None:
    """Render unusual spending flags and largest single expense without emoji."""
    flags = summary.get("unusual_flags", [])
    currency = summary["currency"]

    if flags:
        rows_html = []
        for flag in flags:
            type_label = html.escape(str(flag.get("type", "flag")).replace("_", " ").upper())
            label = html.escape(str(flag.get("label", "")))
            detail = html.escape(str(flag.get("detail", "")))
            amount = flag.get("amount")
            amount_str = f"{float(amount):,.2f} {currency}" if amount is not None else ""
            rows_html.append(
                f"""<div class="unusual-row">
                    <div class="unusual-meta">
                        <span class="unusual-badge">{type_label}</span>
                        <div class="unusual-desc"><strong>{label}</strong> — {detail}</div>
                    </div>
                    <div class="unusual-amount">{amount_str}</div>
                </div>"""
            )
        st.markdown(f'<div class="unusual-list">{"".join(rows_html)}</div>', unsafe_allow_html=True)
    else:
        st.caption("No unusual spending detected.")

    largest = summary.get("largest_single_expense")
    if largest:
        desc = html.escape(str(largest["description"]))
        st.caption(
            f"Largest single expense: **{desc}** at {largest['amount']:,.2f} {currency}"
        )


def _render_summary(summary: dict, issues: list[dict]) -> None:
    """Render the computed summary, comparison, flags and problem rows."""
    currency = summary["currency"]

    if issues:
        st.warning("These rows were skipped:")
        st.dataframe(pd.DataFrame(issues), hide_index=True, use_container_width=True)

    # --- Key metrics row ---
    st.header("Spending summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"Total spend ({currency})", f"{summary['total_spend']:,.2f}")
    col2.metric(f"Total income ({currency})", f"{summary['total_income']:,.2f}")
    col3.metric(f"Savings ({currency})", f"{summary['savings']:,.2f}")
    savings_rate = summary["savings_rate"]
    rate_label = "N/A" if savings_rate is None else f"{savings_rate:.1%}"
    col4.metric("Savings rate", rate_label)
    st.caption(f"Covered months: {summary['months']}")

    # --- Charts row ---
    chart_left, chart_right = st.columns(2)

    with chart_left:
        st.subheader("Spending by category")
        cat_tab_chart, cat_tab_table = st.tabs(["Chart", "Table"])
        with cat_tab_chart:
            cat_chart = _render_category_chart(summary)
            st.altair_chart(cat_chart, use_container_width=True)
        with cat_tab_table:
            st.dataframe(
                _category_table(summary),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Amount": st.column_config.TextColumn(alignment="right"),
                    "Share": st.column_config.TextColumn(alignment="right"),
                },
            )

    with chart_right:
        st.subheader("Monthly trend")
        month_tab_chart, month_tab_table = st.tabs(["Chart", "Table"])
        with month_tab_chart:
            trend_chart = _render_trend_chart(summary)
            st.altair_chart(trend_chart, use_container_width=True)
        with month_tab_table:
            st.dataframe(
                _month_table(summary),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Amount": st.column_config.TextColumn(alignment="right"),
                },
            )

    # --- 50/30/20 budget comparison ---
    st.subheader("50 / 30 / 20 budget comparison")

    budget_left, budget_right = st.columns([3, 2])
    with budget_left:
        _render_budget_bars(summary)
    with budget_right:
        st.dataframe(
            _comparison_table(summary),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Target": st.column_config.TextColumn(alignment="right"),
                "Actual": st.column_config.TextColumn(alignment="right"),
                "Gap": st.column_config.TextColumn(alignment="right"),
            },
        )

    # --- Unusual spending ---
    st.subheader("Unusual spending")
    _render_unusual_spending(summary)


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
        page_icon=None,
        layout="wide",
    )

    # Inject refined dark CSS.
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    st.title("Personal Finance Consultant")
    st.markdown(
        '<div class="disclaimer-note">'
        "Every figure is computed from your data in code. Advice is general guidance, "
        "not professional financial advice."
        "</div>",
        unsafe_allow_html=True,
    )

    # --- Profile section ---
    st.header("Your profile")
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        occupation = st.text_input("Occupation", value="software engineer")
        city = st.text_input("City", value="Example City")
    with col_p2:
        monthly_income = st.number_input(
            "Monthly income", min_value=0.0, value=1900.0, step=100.0, format="%.2f"
        )
        currency_input = st.text_input("Currency", value="USD")
    with col_p3:
        savings_goal = st.text_input("Savings goal", value="save 20% of income")

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
    st.header("Expenses")
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
            "**Welcome!** Upload a CSV/XLSX file or enter expense rows above to get started. "
            "Your spending summary and personalized advice will appear here."
        )
        for issue in issues or []:
            if issue.get("reason"):
                st.caption(f"{issue['reason']}")
        st.stop()

    summary = build_summary(profile, expenses)

    # Summary, budget comparison and flags are always visible (T009 / FR-023).
    _render_summary(summary, issues)

    # --- Advice section (gated by button, T009) ---
    st.header("Advice")
    clicked = st.button("Get advice")
    cached = _get_cached_advice(profile, summary)

    if clicked:
        with st.spinner("Generating advice..."):
            advice_obj = advisor.get_advice(profile, summary)
        _store_advice(summary, advice_obj)
        st.markdown(
            f'<div class="advice-column">\n\n{advice_obj.text}\n\n</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Advice source: {advice_obj.source}.")
    elif cached is not None:
        st.markdown(
            f'<div class="advice-column">\n\n{cached.text}\n\n</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Advice source: {cached.source}.")


main()
