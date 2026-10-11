"""Streamlit UI for the Personal Finance Consultant (T008).

UI only. Every figure is computed in :mod:`src.analysis`, advice comes from
:mod:`src.advisor` and all input handling lives in :mod:`src.loader`; this file
just collects widgets and lays out the results. The optional local ``.env`` is
read once here through ``advisor.load_env`` (never inside ``get_advice``), so
the app keeps working fully offline when no key is configured.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from src import advisor
from src.analysis import build_summary
from src.loader import load_expenses, load_manual_rows, load_profile

#: Key of the manual-entry editor (the AppTest smoke test writes rows here).
EXPENSE_EDITOR_KEY = "expense_editor"
MANUAL_COLUMNS = ["date", "description", "category", "amount"]


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
                "Bucket": bucket,
                "Target": f"{comparison['targets'][bucket]:.0%}",
                "Actual": "Not available" if actual is None else f"{actual:.0%}",
                "Gap": "Not available" if gap is None else f"{gap:+.0%}",
            }
        )
    return pd.DataFrame(rows)


def _render_summary(summary: dict, issues: list[dict]) -> None:
    """Render the computed summary, comparison, flags and problem rows."""
    currency = summary["currency"]

    if issues:
        st.warning("These rows were skipped:")
        st.dataframe(pd.DataFrame(issues), hide_index=True)

    st.header("Spending summary")
    total, income, savings, rate = st.columns(4)
    total.metric("Total spend", f"{summary['total_spend']:,.2f} {currency}")
    income.metric("Total income", f"{summary['total_income']:,.2f} {currency}")
    savings.metric("Savings", f"{summary['savings']:,.2f} {currency}")
    savings_rate = summary["savings_rate"]
    rate_label = "Not available" if savings_rate is None else f"{savings_rate:.1%}"
    rate.metric("Savings rate", rate_label)
    st.caption(f"Covered months: {summary['months']}")

    left, right = st.columns(2)
    with left:
        st.subheader("By category")
        st.dataframe(_category_table(summary), hide_index=True)
    with right:
        st.subheader("By month")
        st.dataframe(_month_table(summary), hide_index=True)

    st.subheader("50/30/20 comparison")
    st.dataframe(_comparison_table(summary), hide_index=True)

    st.subheader("Unusual spending")
    flags = summary["unusual_flags"]
    if flags:
        for flag in flags:
            st.markdown(f"- **{flag['label']}** — {flag['detail']}")
    else:
        st.caption("No unusual spending detected.")


def main() -> None:
    advisor.load_env()
    st.set_page_config(page_title="Personal Finance Consultant", layout="wide")
    st.title("Personal Finance Consultant")
    st.caption(
        "Every figure is computed from your data in code. Advice is general guidance, "
        "not professional financial advice."
    )

    st.header("Your profile")
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

    if expenses.empty:
        for issue in issues or [{"reason": "no expense rows were provided"}]:
            st.info(issue["reason"])
        st.stop()

    summary = build_summary(profile, expenses)
    advice = advisor.get_advice(profile, summary)

    _render_summary(summary, issues)

    st.header("Advice")
    st.markdown(advice.text)
    st.caption(f"Advice source: {advice.source}.")


main()
