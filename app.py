"""MoneyLab: financial projection, loan strategy comparison, and CSV export."""

import calendar
from datetime import date

import pandas as pd
import streamlit as st

from moneylab.reporting import comparison_to_csv, projection_to_csv
from moneylab.strategies import compare_financial_strategies


st.set_page_config(page_title="MoneyLab", page_icon="💰", layout="wide")


def dollars(value):
    """Render exact Decimal values consistently in metric cards."""
    return f"${value:,.2f}" if value >= 0 else f"-${abs(value):,.2f}"


def payoff_description(month, start_date):
    """Identify an approximate calendar payoff month, not a guaranteed date."""
    if month is None:
        return "Not within projection"
    if month == 0:
        return "No starting debt"
    month_index = start_date.month - 1 + month
    year = start_date.year + month_index // 12
    month_name = calendar.month_name[month_index % 12 + 1]
    return f"Month {month} ({month_name} {year})"


def chart_dataframe(projection):
    """Convert Decimal results for visualization only, not for arithmetic."""
    return pd.DataFrame(
        {
            "Month": row["month"],
            "Cash savings": float(row["savings"]),
            "Loan debt": float(row["loan_balance"]),
            "Modeled net position": float(row["net_position"]),
        }
        for row in projection["monthly_records"]
    ).set_index("Month")


def details_dataframe(projection):
    """Human-readable monthly data table; financial engine stays unchanged."""
    labels = {
        "month": "Month",
        "income": "Income",
        "living_expenses": "Living expenses",
        "regular_loan_payment": "Required payment",
        "extra_loan_payment": "Extra payment",
        "loan_payment": "Total loan payment",
        "interest_charged": "Interest",
        "principal_paid": "Principal paid",
        "net_cash_flow": "Net cash flow",
        "savings": "Cash savings",
        "unfunded_shortfall": "Unfunded shortfall",
        "loan_balance": "Loan debt",
        "net_position": "Net position",
    }
    return pd.DataFrame(
        {
            label: row[key] if key == "month" else float(row[key])
            for key, label in labels.items()
        }
        for row in projection["monthly_records"]
    )


def risk_messages(projection):
    """Show model limitations exactly where a user makes a decision."""
    records = projection["monthly_records"]
    if any(row["negative_amortization"] for row in records[1:]):
        st.warning(
            "One or more payments fail to cover monthly interest. "
            "This scenario includes an increasing loan balance."
        )
    highest_shortfall = max(row["unfunded_shortfall"] for row in records)
    if highest_shortfall > 0:
        st.warning(
            f"Cash runs short by as much as {dollars(highest_shortfall)}. "
            "MoneyLab records this as an *unfunded shortfall*; it does not "
            "assume a real overdraft or a new interest-bearing loan."
        )


st.title("💰 MoneyLab")
st.caption("Personal Financial Planning & Decision Simulator  •  Version 1")
st.write(
    "See where your money could go. Project savings and debt, then compare "
    "saving your monthly surplus against paying a loan down faster."
)

with st.sidebar:
    st.header("Your financial profile")
    st.caption("Figures are monthly and in USD unless otherwise indicated.")
    with st.form("financial_profile"):
        savings = st.number_input(
            "Current cash savings ($)", min_value=0.0, value=5000.0,
            step=100.0, format="%.2f",
        )
        income = st.number_input(
            "Monthly take-home income ($)", min_value=0.0, value=3000.0,
            step=100.0, format="%.2f",
        )
        expenses = st.number_input(
            "Monthly living expenses ($)", min_value=0.0, value=2000.0,
            step=100.0, format="%.2f",
            help="Exclude all loan payments from this number to avoid double-counting.",
        )
        st.markdown("#### Loan details")
        balance = st.number_input(
            "Outstanding loan balance ($)", min_value=0.0, value=12000.0,
            step=100.0, format="%.2f",
        )
        annual_rate = st.number_input(
            "Annual loan interest rate (%)", min_value=0.0, value=5.0,
            step=0.1, format="%.3f", help="Enter 5 for 5%, not 0.05.",
        )
        payment = st.number_input(
            "Required monthly loan payment ($)", min_value=0.0,
            value=250.0, step=25.0, format="%.2f",
        )
        st.markdown("#### Projection")
        months = st.slider("Projection duration (months)", 1, 600, 60)
        start_date = st.date_input(
            "Starting date (for payoff estimate)", value=date.today(),
            help="Used only to label the approximate payoff month.",
        )
        extra_payment = st.number_input(
            "Optional extra loan payment ($/month)", min_value=0.0,
            value=150.0, step=25.0, format="%.2f",
            help="Used only in the strategy comparison. Extra payments never "
                 "exceed the affordable monthly surplus.",
        )
        st.form_submit_button("Recalculate", use_container_width=True)

try:
    comparison = compare_financial_strategies(
        current_savings=savings,
        monthly_income=income,
        monthly_living_expenses=expenses,
        outstanding_loan_balance=balance,
        annual_loan_interest_rate=annual_rate,
        required_monthly_loan_payment=payment,
        extra_monthly_loan_payment=extra_payment,
        months=months,
    )
except ValueError as exc:
    st.error(f"Please correct the financial inputs: {exc}")
    st.stop()

baseline = comparison["saving"]
accelerated = comparison["accelerated"]
summary = baseline["summary"]
results = comparison["comparison"]
first_month = baseline["monthly_records"][1]

overview_tab, compare_tab, data_tab, about_tab = st.tabs(
    ["Overview", "Compare strategies", "Monthly data & export", "Assumptions"]
)

with overview_tab:
    st.subheader("Your financial position today")
    col1, col2, col3 = st.columns(3)
    col1.metric("Cash savings", dollars(summary["starting_savings"]))
    col2.metric("Loan debt", dollars(summary["starting_loan_balance"]))
    col3.metric("Modeled net position", dollars(summary["starting_net_position"]))

    st.subheader("Month 1 cash flow")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Take-home income", dollars(first_month["income"]))
    col2.metric("Living expenses", dollars(first_month["living_expenses"]))
    col3.metric("Actual loan payment", dollars(first_month["loan_payment"]))
    col4.metric("Monthly surplus / deficit", dollars(first_month["net_cash_flow"]))
    st.caption(
        "Living expenses exclude debt payments. Loan payments stop after the "
        "loan is paid off. This overview assumes all remaining surplus is saved."
    )

    st.divider()
    st.subheader(f"Projected results after {months} months")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Projected savings", dollars(summary["ending_savings"]))
    col2.metric("Remaining loan debt", dollars(summary["ending_loan_balance"]))
    col3.metric("Modeled net position", dollars(summary["ending_net_position"]))
    col4.metric("Total interest charged", dollars(summary["total_interest_charged"]))

    st.info(
        "Estimated loan payoff: "
        + payoff_description(summary["loan_payoff_month"], start_date)
    )
    risk_messages(baseline)
    st.subheader("Savings, debt, and financial position")
    st.line_chart(chart_dataframe(baseline), height=360)
    st.caption(
        "Month 0 is today. Net position is a partial estimate based only on "
        "cash, the modeled loan, and any unfunded shortfall."
    )

with compare_tab:
    st.subheader("Save the surplus or pay extra toward debt?")
    st.write(
        "Both scenarios share your exact financial inputs. The first saves all "
        "monthly surplus; the second directs up to "
        f"**{dollars(results['requested_extra_monthly_payment'])}** per month "
        "toward additional loan repayment."
    )
    if results["actual_total_extra_payments"] == 0:
        st.info(
            "No extra debt payment was affordable or applicable over this "
            "timeline. Increase the available monthly surplus or choose a "
            "loan with an outstanding balance to see a difference."
        )

    col1, col2, col3 = st.columns(3)
    col1.metric("Interest avoided", dollars(results["interest_avoided"]))
    col2.metric("Extra amount paid to debt",
                dollars(results["actual_total_extra_payments"]))
    col3.metric("Change in net position",
                dollars(results["ending_net_position_gain"]))

    summary_rows = [
        {
            "Strategy": "Save monthly surplus",
            "Ending savings": float(summary["ending_savings"]),
            "Ending loan debt": float(summary["ending_loan_balance"]),
            "Ending net position": float(summary["ending_net_position"]),
            "Interest charged": float(summary["total_interest_charged"]),
            "Estimated payoff": payoff_description(
                summary["loan_payoff_month"], start_date
            ),
        },
        {
            "Strategy": "Pay extra toward debt",
            "Ending savings": float(accelerated["summary"]["ending_savings"]),
            "Ending loan debt": float(accelerated["summary"]["ending_loan_balance"]),
            "Ending net position": float(accelerated["summary"]["ending_net_position"]),
            "Interest charged": float(accelerated["summary"]["total_interest_charged"]),
            "Estimated payoff": payoff_description(
                accelerated["summary"]["loan_payoff_month"], start_date
            ),
        },
    ]
    st.dataframe(
        pd.DataFrame(summary_rows), hide_index=True, use_container_width=True,
        column_config={
            field: st.column_config.NumberColumn(field, format="$%.2f")
            for field in (
                "Ending savings", "Ending loan debt",
                "Ending net position", "Interest charged",
            )
        },
    )
    st.caption(
        "Optional payments are limited by current monthly surplus, earlier "
        "unfunded shortfalls, and remaining loan debt; existing savings "
        "are never spent to make extra payments."
    )

    months_index = [row["month"] for row in baseline["monthly_records"]]
    debt_compare = pd.DataFrame({
        "Month": months_index,
        "Save surplus": [
            float(row["loan_balance"]) for row in baseline["monthly_records"]
        ],
        "Pay extra": [
            float(row["loan_balance"]) for row in accelerated["monthly_records"]
        ],
    }).set_index("Month")
    st.subheader("Debt balance comparison")
    st.line_chart(debt_compare, height=310)

    net_compare = pd.DataFrame({
        "Month": months_index,
        "Save surplus": [
            float(row["net_position"]) for row in baseline["monthly_records"]
        ],
        "Pay extra": [
            float(row["net_position"]) for row in accelerated["monthly_records"]
        ],
    }).set_index("Month")
    st.subheader("Net position comparison")
    st.line_chart(net_compare, height=310)
    risk_messages(accelerated)

with data_tab:
    st.subheader("Explore the monthly calculations")
    selected_strategy = st.selectbox(
        "Choose scenario", ["Save monthly surplus", "Pay extra toward debt"]
    )
    selected = (
        baseline if selected_strategy == "Save monthly surplus" else accelerated
    )
    table = details_dataframe(selected)
    monetary_columns = {
        column: st.column_config.NumberColumn(column, format="$%.2f")
        for column in table.columns if column != "Month"
    }
    st.dataframe(
        table, hide_index=True, use_container_width=True,
        column_config=monetary_columns,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download this scenario (CSV)",
            projection_to_csv(selected),
            file_name="moneylab_projection.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "Download both strategies (CSV)",
            comparison_to_csv(comparison),
            file_name="moneylab_strategies.csv",
            mime="text/csv",
            use_container_width=True,
        )
    st.caption(
        "CSV exports keep exact cent amounts and include Month 0. "
        "Downloaded data is generated locally by the app."
    )

with about_tab:
    st.subheader("How MoneyLab calculates your projection")
    st.markdown(
        """
        1. **Cash flow:** Take-home income minus living expenses and actual
           loan payments, counting each expense only once.
        2. **Loan interest:** Start-of-month loan balance × annual interest
           rate ÷ 12. Interest is rounded to cents.
        3. **Loan payments:** The required payment pays interest first, then
           principal. It is capped at the balance plus interest remaining.
        4. **Extra loan payments:** In the comparison only, these use at most
           the *current month's surplus*, after covering earlier unfunded
           shortfalls, and cannot exceed the remaining loan balance.
        5. **Savings:** Positive cash flow is saved, unless allocated to extra
           loan payments. Any earlier unfunded shortfall is covered first.
        6. **Net position:** Savings − loan debt − unfunded shortfall.
           This is not an estimate of total household net worth.
        """
    )
    st.subheader("Important limitations")
    st.markdown(
        """
        - All monthly income, living expenses, and loan terms remain constant.
          The model excludes unexpected costs, inflation, changing income,
          multiple loans, and investment growth.
        - Savings do not earn interest. This deliberately isolates the impact
          of paying down debt. Future versions may compare loan interest with
          savings or investment returns.
        - The model capitalizes unpaid loan interest each month. Real loan
          agreements, especially some student loans, may treat unpaid
          interest differently.
        - Payments are assumed to occur even if cash is insufficient. The
          unfunded shortfall is a **planning indicator**, not an overdraft or
          another loan with modeled interest.
        - Calendar payoff results are approximate months, not exact payoff
          dates. A loan may not be paid off within the selected horizon.
        - MoneyLab is a scenario simulator, **not a financial forecast,
          lending calculator, or individualized financial advice**.
        """
    )
