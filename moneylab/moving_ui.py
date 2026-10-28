"""Decision-first Moving Out Lab for the five-minute Streamlit alpha.

Standalone from account creation; preserves all existing financial blocks.
"""
import pandas as pd
import streamlit as st

from moneylab.moving import FIELDS, LABELS, compare_moving, comparison_csv
from moneylab.ui_app import dollars

EXAMPLE = {
    "income": 3600, "current_housing": 400,
    "other_living": 850, "minimum_debt": 150,
    "checking": 4500, "savings": 3000,
    "rent": 1400, "utilities": 110, "internet": 50,
    "renters_insurance": 20, "transport_change": 45,
    "groceries_change": 100, "other_change": 0,
    "security_deposit": 1400, "moving_cost": 600,
    "furniture": 400, "other_upfront": 0,
}
ISSUE_URL = (
    "https://github.com/jbj-02/moneylab/issues/new"
    "?template=alpha_feedback.yml"
)


def _switch_mode():
    """Reset only this isolated comparison; never change the financial profile."""
    for field in FIELDS:
        st.session_state.pop(f"move_{field}", None)
    st.session_state.pop("move_result", None)
    st.session_state.pop("move_confirm", None)
    st.session_state.pop("move_include_goals", None)
    st.session_state.pop("move_use_savings", None)


def _money(field, title=None, *, required=False, signed=False, help_text=None):
    sample = st.session_state.get("move_start_mode") == "Try fictional example"
    value = EXAMPLE[field] if sample else None
    return st.number_input(
        title or LABELS[field].capitalize(),
        min_value=-100000000.0 if signed else 0.0,
        max_value=100000000.0, value=float(value) if value is not None else None,
        step=25.0, format="%.2f",
        placeholder="Required" if required else "Optional — enter if known",
        key=f"move_{field}", help=help_text,
    )


def _render_result(report):
    st.divider()
    st.subheader("Your moving decision, side by side")
    move_delta, upfront = report["monthly_change"], report["upfront"]
    if move_delta >= 0:
        st.markdown(
            f"**Moving would increase your recorded monthly expenses by "
            f"{dollars(move_delta)} and require {dollars(upfront)} upfront.**"
        )
    else:
        st.markdown(
            f"**Moving would reduce your recorded monthly expenses by "
            f"{dollars(-move_delta)}, but require {dollars(upfront)} upfront.**"
        )
    if report["missing"] or not report["reviewed"]:
        st.info(
            "This is a **preliminary comparison**, not a conclusion about "
            "what you can afford. Unentered costs and incomplete bills could "
            "change these figures."
        )

    with st.container(border=True):
        st.markdown("#### What changes each month?")
        st.dataframe(pd.DataFrame([
            {"Measure": "Recorded monthly expenses",
             "Stay": dollars(report["current_monthly"]),
             "Move": dollars(report["proposed_monthly"])},
            {"Measure": "Remaining before optional savings transfers",
             "Stay": dollars(report["monthly_margin_before"]),
             "Move": dollars(report["monthly_margin_after"])},
        ]), hide_index=True, use_container_width=True)
        st.caption(
            "Monthly remainder = take-home income minus entered housing, "
            "living costs, and minimum debt payments. It is **not** verified "
            "spendable cash. Any separate goal transfers reduce available money."
        )

    if not report["fundable"]:
        st.warning(
            f"**The entered upfront costs exceed the funds you've allowed "
            f"for the move by {dollars(report['funding_gap'])}.** "
            "MoneyLab will not invent a credit card, loan, overdraft, or "
            "withdrawal from savings to cover that difference."
        )
        st.metric("Eligible funds entered", dollars(report["available_for_upfront"]))
        st.caption(
            "Review your cash and savings assumptions or change the move "
            "costs and compare again. No post-move balance projection is shown "
            "until the upfront amount has a stated funding source."
        )
    else:
        st.markdown("#### What happens to your cash?")
        a, b = st.columns(2)
        a.metric("Liquid funds before moving", dollars(report["current_liquid"]))
        b.metric("Liquid funds after upfront costs",
                 dollars(report["remaining_liquid"]),
                 delta=dollars(-upfront))
        st.markdown("#### What could change over time?")
        st.caption(
            "Modeled liquid funds include checking/cash and unearmarked "
            "savings. They can go negative in the model when there's a "
            "cash deficit; negative values are **not available funds**."
        )
        rows = []
        for horizon, data in report["timeframes"].items():
            rows.append({
                "Period": f"{horizon} months",
                "Stay": float(data["stay_liquid"]),
                "Move": float(data["move_liquid"]),
                "Difference": dollars(data["liquid_change"]),
            })
        st.dataframe(pd.DataFrame([
            {"Period": r["Period"], "Stay": dollars(report["timeframes"][month]["stay_liquid"]),
             "Move": dollars(report["timeframes"][month]["move_liquid"]),
             "Difference": r["Difference"]}
            for r, month in zip(rows, (6, 12, 24))
        ]), hide_index=True, use_container_width=True)
        chart = pd.DataFrame(rows).set_index("Period")[["Stay", "Move"]]
        st.bar_chart(chart, height=250)
        if report["goals_included"]:
            st.markdown("#### Your existing savings goals")
            if report["goals_affected"]:
                for item in report["goals_affected"]:
                    b_value = (
                        dollars(item["before"]) if item["before"] is not None
                        else "Not assessed"
                    )
                    a_value = (
                        dollars(item["after"]) if item["after"] is not None
                        else "Not assessed"
                    )
                    st.write(
                        f"**{item['name']}** · By month {item['deadline_months']}: "
                        f"{b_value} if you stay versus {a_value} if you move"
                    )
                    if item["previous_on_track"] and not item["on_track"]:
                        st.warning(
                            f"Your modeled plan for {item['name']} would fall "
                            "behind its deadline after moving."
                        )
            else:
                st.info(
                    "No change to assessed savings-goal outcomes under these "
                    "assumptions. This is not a guarantee of future returns."
                )
        st.download_button(
            "Download this comparison (CSV)",
            data=comparison_csv(report), mime="text/csv",
            file_name="moneylab-moving-comparison.csv",
            key="move_csv",
            use_container_width=True,
        )

    with st.expander(
        "Costs and assumptions to double-check",
        expanded=bool(report["missing"] or not report["fundable"]),
    ):
        if report["missing"]:
            st.warning(
                "Not provided: " + ", ".join(LABELS[k] for k in report["missing"])
                + ". Blank costs were temporarily modeled as zero for this "
                  "comparison, **not confirmed as zero**."
            )
        else:
            st.write("All listed categories have a value, but costs may still be missing.")
        st.write(
            "Consider application fees, first/last month's rent, parking, "
            "renter's insurance, heating, utilities, furniture, groceries, "
            "transportation, healthcare, phone bills, subscriptions, taxes, "
            "emergencies and annual or irregular bills."
        )
        for note in report["warnings"]:
            st.write(f"• {note}")
    with st.expander("How MoneyLab calculated this"):
        st.write(
            f"Current recorded expenses = current housing + other living costs "
            f"+ debt minimums = {dollars(report['current_monthly'])}/month."
        )
        st.write(
            f"Proposed recorded expenses = rent + utilities + internet + "
            f"renter's insurance + current other living costs + debt minimums "
            f"+ changes in transportation, groceries and other spending "
            f"= {dollars(report['proposed_monthly'])}/month."
        )
        st.write(
            "The difference in the monthly remainder is the change in recorded "
            "expenses, with take-home pay held constant. Upfront deposits and "
            "move-in purchases are subtracted once from eligible checking, "
            "then—only if you opt in—from savings."
        )
        st.write(
            "Security deposits are treated as upfront cash reductions; "
            "any eventual refund is excluded. If first month's rent is "
            "already prepaid, this simplified model may double-count it "
            "in the first month's recurring rent. Do not treat the "
            "longer-run figures as a precise lease cash schedule."
        )
        st.write(
            "Month 6, 12 and 24 comparisons reuse MoneyLab's validated Decimal "
            "monthly projection engine. The model assumes constant income and "
            "monthly-average expenses, zero savings-account yield for this "
            "comparison, and no automatically inferred financing. Optional "
            "existing goal blocks are projected at their entered rates and "
            "contribution schedules."
        )
        st.write(
            "This is **not a dated bank-ledger forecast**. Actual bill and "
            "paycheck timing, taxes, changing costs, unexpected spending, "
            "account restrictions and rate changes are not modeled."
        )
    st.caption(
        "Change any number above and select **Compare stay vs move** again "
        "to recalculate. This lab never updates your saved MoneyLab blocks."
    )


def render():
    st.title("Can I afford to move out?")
    st.caption(
        "Make your next money decision with a clearer picture. "
        "Compare staying and moving without building a complete financial profile."
    )
    st.radio(
        "How would you like to start?",
        ("Try fictional example", "Enter my own numbers"),
        key="move_start_mode", horizontal=True, on_change=_switch_mode,
    )
    example = st.session_state["move_start_mode"] == "Try fictional example"
    if example:
        st.info(
            "**Fictional demonstration.** These values aren't your finances. "
            "Edit any number, or switch to your own numbers for a personal "
            "comparison."
        )
    else:
        st.info(
            "Only take-home income and proposed rent must be positive. "
            "Enter zero for costs you have confirmed are zero. Leave "
            "unknown optional figures blank so MoneyLab can flag them."
        )

    with st.form("move_alpha_form", border=False):
        st.markdown("### 1. Your situation today")
        a, b = st.columns(2, gap="medium")
        with a:
            income = _money("income", "Monthly take-home pay ($)", required=True)
            current = _money(
                "current_housing", "What you pay for housing now ($/month)",
                required=True, help_text="Enter $0 if you currently live rent-free.",
            )
        with b:
            other = _money(
                "other_living", "Other spending each month ($)",
                help_text="Groceries, phone, transportation, subscriptions, "
                          "insurance, and other everyday expenses combined.",
            )
            checking = _money(
                "checking", "Checking / cash available today ($)",
                help_text="Do not include investments or retirement money.",
            )
        with st.expander("Add loan payments and existing savings (optional)"):
            a, b = st.columns(2)
            with a:
                debt = _money(
                    "minimum_debt", "Minimum debt payments ($/month)",
                    help_text="Student loans, car loans, credit cards, etc. "
                              "Don't also include them in other spending.",
                )
            with b:
                savings = _money(
                    "savings", "Accessible savings balance ($)",
                    help_text="Excludes retirement and earmarked goals.",
                )
            use_savings = st.checkbox(
                "I may use available savings to cover move-in costs",
                key="move_use_savings",
                help=(
                    "If checked, cash is used first and savings cover only "
                    "the remaining upfront costs. Unchecked by default."
                ),
            )

        st.markdown("### 2. The place you're considering")
        a, b = st.columns(2, gap="medium")
        with a:
            rent = _money("rent", "Your share of the new rent ($/month)", required=True)
            deposit = _money(
                "security_deposit", "Security deposit and fees ($)",
                help_text="Enter cash needed upfront. MoneyLab conservatively "
                          "does not model a future deposit refund.",
            )
        with b:
            moving = _money("moving_cost", "Moving / transport costs ($)")
            st.caption("Add utilities and other costs for a more realistic comparison.")
        with st.expander("Add monthly bills and lifestyle changes (recommended)"):
            a, b = st.columns(2, gap="medium")
            with a:
                utilities = _money("utilities", "Utilities ($/month)")
                internet = _money("internet", "Internet ($/month)")
                insurance = _money("renters_insurance", "Renter's insurance ($/month)")
            with b:
                transport = _money(
                    "transport_change",
                    "Transportation change ($/month)", signed=True,
                    help_text="Positive if commuting gets more expensive; "
                              "negative if it gets cheaper.",
                )
                groceries = _money(
                    "groceries_change",
                    "Groceries change ($/month)", signed=True,
                )
                other_change = _money(
                    "other_change",
                    "Other living-cost change ($/month)", signed=True,
                )
        with st.expander("Add furniture and other one-time costs (optional)"):
            a, b = st.columns(2)
            with a:
                furniture = _money("furniture", "Furniture and supplies ($)")
            with b:
                other_upfront = _money(
                    "other_upfront", "Other one-time costs ($)",
                )

        user_goals = [
            g for g in st.session_state.get("ml_blocks", [])
            if isinstance(g, dict) and g.get("kind") == "goal"
        ]
        include_goals = False
        if user_goals:
            include_goals = st.checkbox(
                f"Compare against my {len(user_goals)} existing savings goal(s)",
                key="move_include_goals",
                help=(
                    "Only existing goal blocks are used. Income, account balances "
                    "and expenses are taken exclusively from the figures above "
                    "to avoid double-counting them."
                ),
            )
        reviewed = st.checkbox(
            "I've included the main costs I know (optional)",
            key="move_confirm",
            help=(
                "This confirms only that you reviewed these entries, not "
                "that every real-world cost or bank balance has been verified."
            ),
        )
        submitted = st.form_submit_button(
            "Compare stay vs move", type="primary", use_container_width=True,
        )

    if submitted:
        values = {field: st.session_state.get(f"move_{field}") for field in FIELDS}
        try:
            report = compare_moving(
                values,
                existing_goals=user_goals if include_goals else None,
                reviewed=bool(reviewed),
                use_savings_for_upfront=bool(use_savings),
            )
        except ValueError as exc:
            st.session_state.pop("move_result", None)
            st.error(f"Please review your inputs: {exc}")
        else:
            st.session_state.move_result = report
    if st.session_state.get("move_result") is not None:
        _render_result(st.session_state.move_result)
    else:
        st.caption(
            "This preview uses your browser session only. No bank connection "
            "or external AI request is made."
        )
    st.divider()
    st.markdown("### Help make MoneyLab better")
    st.write(
        "Was an input confusing, a cost missing, or a calculation surprising? "
        "Your feedback will improve the alpha."
    )
    st.link_button(
        "Report a problem or request a feature",
        url=ISSUE_URL, use_container_width=False,
    )
    st.caption(
        "Feedback uses a **public GitHub issue** and requires a GitHub account. "
        "Do not share actual financial amounts, names, addresses, bank details "
        "or other identifying information in feedback."
    )
