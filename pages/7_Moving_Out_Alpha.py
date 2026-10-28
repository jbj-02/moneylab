"""Decision-first moving-out alpha. No account connection or persistence."""
from decimal import Decimal
import streamlit as st
from moneylab.blocks import project_blocks, validate_blocks
from moneylab.decisions import decision_check
from moneylab.ui_app import dollars

def _money(label, value=0.0, help=None):
    return Decimal(str(st.number_input(label, min_value=0.0, max_value=10000000.0, value=float(value), step=50.0, format="%.2f", help=help)))

def render():
    st.title("Can I afford to move out?")
    st.caption("Compare two living situations in minutes. No bank connection or account required.")
    st.info("Alpha: figures are estimates, not verified balances or financial advice. Nothing is saved automatically.")
    use_example = st.toggle("Try with fictional example figures", value=True)
    st.subheader("1 · Your starting point")
    a,b=st.columns(2)
    with a:
        income=_money("Monthly take-home pay", 3600 if use_example else 0)
        cash=_money("Checking / cash available today", 6500 if use_example else 0)
    with b:
        other=_money("Other monthly expenses and minimum debt payments", 900 if use_example else 0,
                     help="Include groceries, transportation, insurance, loan minimums and other expenses not listed below.")
        current=_money("Current monthly housing cost", 400 if use_example else 0)
    st.subheader("2 · Your proposed move")
    a,b=st.columns(2)
    with a:
        rent=_money("Your share of new monthly rent", 1400 if use_example else 0)
        utilities=_money("Monthly utilities, internet and renter's insurance", 180 if use_example else 0)
        additional=_money("Other new monthly costs", 120 if use_example else 0,
                          help="Examples: higher transportation costs, parking or increased groceries.")
    with b:
        deposit=_money("Security deposit and upfront fees", 1400 if use_example else 0)
        moving=_money("Moving, furniture and other one-time costs", 650 if use_example else 0)
        horizon=st.selectbox("Compare over", [6,12,24,36], index=1, format_func=lambda n:f"{n} months")
    if st.button("Compare my options", type="primary", use_container_width=True):
        if income <= 0:
            st.error("Enter take-home income to make a meaningful comparison.")
            return
        if rent <= 0:
            st.error("Enter proposed rent to compare housing options.")
            return
        upfront=deposit+moving
        current_monthly=other+current
        proposed_monthly=other+rent+utilities+additional
        change=proposed_monthly-current_monthly
        baseline=[
            {"id":"income","kind":"income","name":"Take-home pay","monthly_amount":str(income)},
            {"id":"cash","kind":"cash","name":"Checking / cash","balance":str(cash)},
            {"id":"living","kind":"expense","name":"Current housing and other costs","monthly_amount":str(current_monthly)}
        ]
        alternative=[
            {"id":"income","kind":"income","name":"Take-home pay","monthly_amount":str(income)},
            {"id":"cash","kind":"cash","name":"Checking / cash","balance":str(cash-upfront)},
            {"id":"living","kind":"expense","name":"Proposed housing and other costs","monthly_amount":str(proposed_monthly)}
        ]
        st.subheader("3 · What changes?")
        if upfront>cash:
            st.warning("Upfront costs exceed the checking/cash entered. The comparison cannot assume borrowing or transfers from unspecified accounts.")
            st.metric("Upfront funding gap",dollars(upfront-cash))
            return
        before=project_blocks(validate_blocks(baseline),horizon)
        after=project_blocks(validate_blocks(alternative),horizon)
        before_buffer=before["summary"]["unallocated_monthly_buffer"]
        after_buffer=after["summary"]["unallocated_monthly_buffer"]
        x,y,z=st.columns(3)
        x.metric("Monthly flexibility after moving", dollars(after_buffer), delta=dollars(after_buffer-before_buffer))
        y.metric("Cash after upfront costs", dollars(cash-upfront), delta=dollars(-upfront))
        z.metric(f"Modeled cash change at month {horizon}",
                 dollars(after["summary"]["ending_cash_savings"]-before["summary"]["ending_cash_savings"]))
        st.write("**Stay vs. move**")
        st.dataframe([
            {"Measure":"Monthly recorded costs","Stay":dollars(current_monthly),"Move":dollars(proposed_monthly)},
            {"Measure":"Monthly flexibility (before savings transfers)","Stay":dollars(before_buffer),"Move":dollars(after_buffer)},
            {"Measure":"Starting cash after upfront expenses","Stay":dollars(cash),"Move":dollars(cash-upfront)},
            {"Measure":f"Modeled cash at month {horizon}","Stay":dollars(before["summary"]["ending_cash_savings"]),"Move":dollars(after["summary"]["ending_cash_savings"])}
        ], hide_index=True, use_container_width=True)
        if after_buffer < 0:
            st.warning("Recorded monthly expenses exceed take-home pay after moving. Review the assumptions and missing costs.")
        elif cash-upfront < proposed_monthly:
            st.warning("Remaining cash is less than one month of the entered expenses. This is a caution, not a universal reserve threshold.")
        else:
            st.info("No immediate monthly gap appears in the entered figures. This is not a guarantee that moving is affordable.")
        with st.expander("Costs and limitations to double-check", expanded=True):
            st.write("Consider groceries, transport, renter's insurance, utilities, application fees, first/last month's rent, furnishings, health costs, irregular bills, loan payments and emergencies.")
            st.write("Monthly averages ignore actual payday and bill timing. Income and costs are assumed constant. No taxes, inflation, credit approval, reimbursements, savings-account transfers or unexpected events are modeled.")
        st.download_button("Download comparison (CSV)", data=(
            "metric,stay,move\n"
            f"monthly_costs,{current_monthly},{proposed_monthly}\n"
            f"monthly_flexibility,{before_buffer},{after_buffer}\n"
            f"cash_after_upfront,{cash},{cash-upfront}\n"
            f"cash_month_{horizon},{before['summary']['ending_cash_savings']},{after['summary']['ending_cash_savings']}\n"
        ), file_name="moneylab-moving-comparison.csv", mime="text/csv")
        st.caption("Do not include personally identifying or bank-login information in feedback.")
    st.divider()
    st.markdown("**Help improve the alpha:** What was confusing? Which expense did we miss? Would you use this for a real decision?")
render()
