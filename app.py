"""Streamlit interface for the MoneyLab Phase 1 financial projection engine."""

import pandas as pd
import streamlit as st

from moneylab.engine import project_finances


st.set_page_config(page_title="MoneyLab", page_icon="💰", layout="wide")


def dollars(amount):
    """Format a Decimal amount for display; preserve negative values."""
    return f"${amount:,.2f}" if amount >= 0 else f"-${abs(amount):,.2f}"


st.title("💰 MoneyLab")
st.caption("Personal Financial Planning & Decision Simulator · Phase 1")
st.write(
    "Explore how a fixed monthly budget and a single loan affect cash savings "
    "and your financial position over time. Change the figures to model a "
    "different situation."
)

with st.sidebar:
    st.header("Financial profile")
    st.caption("Use monthly take-home income and living expenses **excluding loan payments**.")

    with st.form("financial_profile"):
        savings = st.number_input(
            "Current cash savings ($)", min_value=0.0, value=5000.0,
            step=100.0, format="%.2f"
        )
        income = st.number_input(
            "Monthly take-home income ($)", min_value=0.0, value=3000.0,
            step=100.0, format="%.2f"
        )
        expenses = st.number_input(
            "Monthly living expenses ($)", min_value=0.0, value=2000.0,
            step=100.0, format="%.2f",
            help="Do not include the loan payment here; it is entered separately."
        )
        st.divider()
        balance = st.number_input(
            "Outstanding loan balance ($)", min_value=0.0, value=12000.0,
            step=100.0, format="%.2f"
        )
        annual_rate = st.number_input(
            "Annual loan interest rate (%)", min_value=0.0, value=5.0,
            step=0.1, format="%.3f",
            help="Enter 5 for 5% APR, not 0.05."
        )
        payment = st.number_input(
            "Required monthly loan payment ($)", min_value=0.0,
            value=250.0, step=25.0, format="%.2f"
        )
        months = st.slider("Projection duration (months)", 1, 600, 60)
        st.form_submit_button("Update projection", use_container_width=True)

try:
    projection = project_finances(
        current_savings=savings,
        monthly_income=income,
        monthly_living_expenses=expenses,
        outstanding_loan_balance=balance,
        annual_loan_interest_rate=annual_rate,
        required_monthly_loan_payment=payment,
        months=months,
    )
except ValueError as error:
    st.error(f"Please check your inputs: {error}")
    st.stop()

records = projection["monthly_records"]
summary = projection["summary"]
first_month = records[1]

st.subheader("Your financial position today")
c1, c2, c3 = st.columns(3)
c1.metric("Cash savings", dollars(summary["starting_savings"]))
c2.metric("Loan debt", dollars(summary["starting_loan_balance"]))
c3.metric("Modeled net position", dollars(summary["starting_net_position"]))

st.subheader("Month 1 cash flow")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Take-home income", dollars(first_month["income"]))
c2.metric("Living expenses", dollars(first_month["living_expenses"]))
c3.metric("Actual loan payment", dollars(first_month["loan_payment"]))
c4.metric("Monthly surplus / deficit", dollars(first_month["net_cash_flow"]))
st.caption(
    "The debt payment is separate from living expenses. The actual payment "
    "is capped when the loan is paid off; future months then have no loan payment."
)

st.divider()
st.subheader(f"Projected results after {months} month{'s' if months != 1 else ''}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Projected savings", dollars(summary["ending_savings"]))
c2.metric("Remaining loan debt", dollars(summary["ending_loan_balance"]))
c3.metric("Modeled net position", dollars(summary["ending_net_position"]))
c4.metric("Total interest charged", dollars(summary["total_interest_charged"]))

payoff = summary["loan_payoff_month"]
if payoff == 0:
    st.info("No starting loan balance: there is no loan to repay.")
elif payoff is None:
    st.info("The modeled loan is not fully repaid within the selected timeline.")
else:
    st.success(f"The loan reaches a zero balance in month {payoff}.")

if any(row["negative_amortization"] for row in records[1:]):
    st.warning(
        "In at least one month, the loan payment does not cover interest, "
        "so the modeled loan balance increases."
    )

peak_shortfall = max(row["unfunded_shortfall"] for row in records)
if peak_shortfall > 0:
    st.warning(
        "The projection has insufficient cash in at least one month. "
        f"Maximum modeled unfunded shortfall: {dollars(peak_shortfall)}. "
        "This is a planning warning, not a bank account balance or new loan."
    )

st.subheader("How your financial position changes")
chart = pd.DataFrame(
    {
        "Month": row["month"],
        "Savings": float(row["savings"]),
        "Loan balance": float(row["loan_balance"]),
        "Net position": float(row["net_position"]),
    }
    for row in records
).set_index("Month")
st.line_chart(chart, height=360)
st.caption("Amounts are shown in USD. Month 0 represents your starting position.")

with st.expander("See month-by-month calculations", expanded=False):
    columns = {
        "month": "Month",
        "income": "Income",
        "living_expenses": "Living expenses",
        "loan_payment": "Loan payment",
        "interest_charged": "Interest charged",
        "net_cash_flow": "Cash flow",
        "savings": "Savings",
        "unfunded_shortfall": "Unfunded shortfall",
        "loan_balance": "Loan balance",
        "net_position": "Net position",
    }
    table = pd.DataFrame(
        {label: row[key] if key == "month" else float(row[key])
         for key, label in columns.items()}
        for row in records
    )
    money_columns = {
        label: st.column_config.NumberColumn(label, format="$%.2f")
        for key, label in columns.items() if key != "month"
    }
    st.dataframe(table, hide_index=True, use_container_width=True,
                 column_config=money_columns)

with st.expander("Model assumptions and limitations"):
    st.markdown(
        """
        - **Fixed inputs:** Monthly take-home income, living expenses, loan
          interest rate, and scheduled payment stay constant.
        - **Cash:** All available surplus stays in cash; no savings interest,
          investment growth, inflation, or taxes beyond take-home pay are modeled.
        - **Loans:** One loan is modeled, using monthly interest on the opening
          balance. Unpaid interest is added to the balance monthly, which might
          not match the terms of your actual loan.
        - **Affordability:** Loan payments are assumed to occur even during
          cash deficits. When cash runs out, an *unfunded shortfall* is tracked
          separately and must be covered by future surpluses before cash savings
          can increase again.
        - **Net position:** Savings minus modeled loan debt and unfunded
          shortfall is only a **partial** measure of net worth. Other assets,
          debts, and obligations are excluded.
        - **Purpose:** This is a mathematical projection for exploring
          assumptions, **not a prediction or financial advice**.
        """
    )
