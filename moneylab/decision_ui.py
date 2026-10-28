"""Decision-first Streamlit experience: see a tradeoff, then choose a next step.

The UI doesn't call external AI and never persists unapproved what-if choices.
Every value is computed in moneylab.decisions, backed by the projection engine.
"""
import streamlit as st

from moneylab.cadence import FREQUENCIES
from moneylab.decisions import (
    decision_check, emergency_readiness, goal_next_step, next_best_step,
)
from moneylab.ui_app import context, dollars, render_explore

DECISIONS = (
    "💳 Can I take on a cost?",
    "🛟 How prepared am I?",
    "🎯 How do I reach a goal?",
    "🔍 Explore an existing expense",
)


def _context_note(blocks, reviewed):
    kinds = {b["kind"] for b in blocks}
    missing = []
    if "income" not in kinds:
        missing.append("take-home income")
    if "expense" not in kinds:
        missing.append("regular living expenses")
    if "cash" not in kinds:
        missing.append("checking/cash balance")
    if missing:
        st.warning(
            "This is a **partial profile**. Add or confirm "
            + ", ".join(missing)
            + " before treating any comparison as a complete financial picture."
        )
    if not reviewed:
        st.info(
            "Your financial entries have not been marked as reviewed. "
            "The calculations below are preliminary and not a verified "
            "bank balance or a recommendation to spend."
        )


def _cost_check(blocks, months, reviewed):
    st.markdown("### Can I take on this cost?")
    st.caption(
        "Try a one-time purchase or a new recurring commitment. "
        "MoneyLab compares it with the plan you entered; it won't decide for you."
    )
    a, b = st.columns([2, 1])
    with a:
        cost_kind = st.radio(
            "Type of cost", ["One-time purchase", "Recurring commitment"],
            horizontal=True, key="dc_cost_kind",
        )
    with b:
        proposed = st.number_input(
            "Cost amount ($)", min_value=0.0, max_value=1000000000.0,
            value=200.0, step=25.0, format="%.2f",
            key="dc_cost_value",
        )
    freq = "monthly"
    if cost_kind == "Recurring commitment":
        freq = st.selectbox(
            "How frequently does this cost occur?",
            options=list(FREQUENCIES),
            index=list(FREQUENCIES).index("monthly"),
            format_func=lambda key: FREQUENCIES[key][0],
            key="dc_cost_frequency",
        )
    st.caption(
        "For major purchases, include any taxes or extra costs. For a car, "
        "consider insurance, fuel, registration and maintenance; for moving, "
        "consider deposits and utilities."
    )
    if st.button(
        "Check this decision", type="primary", key="dc_run_cost",
        disabled=proposed <= 0,
    ):
        try:
            check = decision_check(
                blocks, cost=proposed, months=months,
                cost_type=("one_time" if cost_kind == "One-time purchase"
                           else "recurring"),
                frequency=freq, reviewed=reviewed,
            )
        except ValueError as exc:
            st.error(f"Could not calculate this comparison: {exc}")
            return
        if not check["comparable"]:
            st.warning(check["reason"])
            st.metric("Checking/cash recorded", dollars(check["available_checking"]))
            st.caption(
                "You could edit your profile to account for how the expense would "
                "actually be funded. MoneyLab does not assume borrowing."
            )
            return
        st.markdown("#### What changes in your modeled plan?")
        if check["needs_attention"]:
            st.warning(
                "**This decision introduces or worsens a modeled financial issue.** "
                "Review the costs and tradeoffs before taking on this commitment."
            )
        elif check["preliminary"]:
            st.info(
                "**Preliminary comparison:** some financial inputs are missing "
                "or unreviewed. No affordability conclusion can be drawn yet."
            )
        else:
            st.info(
                "This scenario does not introduce the modeled warning conditions "
                "we check, but that **does not mean the cost is affordable in real "
                "life**. Missing expenses and bill timing may change the answer."
            )
        a, b, c = st.columns(3)
        if check["cost_type"] == "one_time":
            a.metric(
                "Checking immediately after",
                dollars(check["remaining_checking_now"]),
                delta=dollars(-check["cost"]),
            )
        else:
            a.metric(
                "Cost per month (average)",
                dollars(check["monthly_equivalent"]),
            )
        b.metric(
            "Modeled monthly flexibility",
            dollars(check["monthly_buffer_after"]),
            delta=dollars(check["monthly_buffer_change"]),
        )
        c.metric(
            f"Net position change (month {months})",
            dollars(check["ending_net_change"]),
        )
        st.caption(
            f"Cash change at month {months}: "
            f"{dollars(check['ending_cash_change'])}. "
            "Scenarios use static monthly averages and assume no unexpected events."
        )
        if check["goals_affected"]:
            st.markdown("#### Savings goals affected")
            for goal in check["goals_affected"]:
                before = (
                    "not assessed" if goal["before"] is None
                    else dollars(goal["before"])
                )
                after = (
                    "not assessed" if goal["after"] is None
                    else dollars(goal["after"])
                )
                st.write(f"**{goal['name']}**: {before} → {after} at its deadline")
        with st.expander("Important assumptions and limitations", expanded=True):
            for note in check["cautions"]:
                st.write(f"• {note}")
            st.write(
                "No live accounts, tax withholding, one-off reimbursement, "
                "intra-month bill timing or financing terms are inferred."
            )
        st.markdown("#### What now?")
        st.write(
            "Check that all relevant costs are included, then compare another "
            "scenario or update your recorded expenses. This comparison does "
            "not change your saved profile."
        )


def _emergency_check(blocks, months, reviewed):
    st.markdown("### How prepared am I for an unexpected expense?")
    st.caption(
        "Compare listed liquid funds with a savings buffer you choose. "
        "This is not a universal emergency-fund rule or a forecast of bank balances."
    )
    target = st.slider(
        "My reserve target (months of listed outflows)", min_value=1,
        max_value=12, value=3, key="dc_reserve_target",
    )
    build = st.slider(
        "Time I want to build the remaining amount (months)",
        min_value=1, max_value=60, value=12, key="dc_build_timeline",
    )
    report = emergency_readiness(
        blocks, target_months=target, build_months=build,
        reviewed=reviewed, horizon=months,
    )
    if not report["evaluable"]:
        st.info(report["reason"])
        return
    a, b, c = st.columns(3)
    a.metric("Recorded accessible funds",
             dollars(report["eligible_starting_funds"]))
    b.metric("Listed outflows per month",
             dollars(report["recorded_monthly_outflow"]))
    c.metric("Months of listed outflows",
             f"{report['coverage_months']:.1f}")
    if report["gap"] == 0:
        st.info(
            "Recorded liquid funds currently meet this **selected arithmetic "
            "target**. This does not verify your balances or completeness."
        )
    else:
        st.markdown(
            f"**Difference to your {target}-month target:** "
            f"{dollars(report['gap'])}"
        )
        st.metric(
            f"Average additional saving over {build} months",
            dollars(report["average_additional_monthly_amount"]),
        )
        if not report["within_first_month_buffer"]:
            st.warning(
                "That additional amount exceeds your first month's modeled "
                "unallocated buffer. Try a longer savings timeline, a smaller "
                "target, or review expenses before making a contribution plan."
            )
        else:
            st.info(
                "That additional amount fits within the first month's recorded "
                "unallocated buffer in the model; it is not a funded transfer plan."
            )
    if report["preliminary"]:
        st.caption(
            "This is a preliminary estimate based on missing or unreviewed entries."
        )
    st.caption(
        "Liquid coverage includes modeled checking/cash and eligible savings; "
        "it excludes earmarked goals, retirement, brokerage, CDs, HSA and 529 "
        "balances. It assumes recorded spending is complete and ignores exact due dates."
    )


def _goal_check(blocks, months, reviewed):
    st.markdown("### How do I get closer to a goal?")
    goals = [b for b in blocks if b["kind"] == "goal"]
    if not goals:
        st.info("Add a savings goal in Goals to compare a concrete target and deadline.")
        if st.button("Go to Goals", key="dc_go_to_goals"):
            st.switch_page("pages/2_Goals.py")
        return
    picked = st.selectbox(
        "Choose a goal", [g["id"] for g in goals],
        format_func=lambda ident: next(g["name"] for g in goals if g["id"] == ident),
        key="dc_goal_choice",
    )
    report = goal_next_step(blocks, picked, months=months, reviewed=reviewed)
    goal = report["goal"]
    st.metric(
        "Planned monthly contribution",
        dollars(goal["monthly_contribution"]),
    )
    existing = report["goal_projection"]
    st.caption(
        f"Target {dollars(goal['target'])} in {goal['target_months']} months. "
        f"Projected at deadline: {dollars(existing['projected_at_deadline'])}."
    )
    if report["on_track"]:
        st.success(
            "This goal reaches its target in the current model. "
            "You can explore other decisions while keeping this contribution."
        )
    else:
        st.warning(
            f"Your current modeled contribution leaves "
            f"{dollars(report['gap'])} to the target at the deadline."
        )
        if report["feasible_with_buffer"]:
            st.metric(
                "Additional monthly contribution to test",
                dollars(report["additional_monthly"]),
            )
            st.write(
                f"Try raising your planned goal contribution to "
                f"**{dollars(report['proposed_contribution'])}/month**. "
                "MoneyLab found the smallest cent-level additional contribution "
                "within your modeled first-month unallocated buffer that reaches "
                "the target under the current fixed assumptions."
            )
        else:
            st.info(
                "The goal does not reach its target with additional monthly "
                "contributions limited to the currently modeled first-month "
                "unallocated buffer. Consider extending the deadline, adjusting "
                "the target, or revisiting other planned spending."
            )
    st.caption(
        "Projections use constant illustrative rates, modeled affordable transfers, "
        "and no verified bank balances. This screen never edits your contribution."
    )
    if st.button("Review or edit this goal", key="dc_edit_goal"):
        st.switch_page("pages/2_Goals.py")


def _empty_profile_decision(choice):
    """A low-input decision preview, without requiring full Quick Start.

    The preview is explicitly incomplete and never saves synthetic blocks.
    """
    from moneylab.blocks import project_blocks
    st.info(
        "You can test a decision without making a profile. "
        "These figures are **incomplete assumptions**, not a verified budget. "
        "You can refine your financial picture later."
    )
    if choice in (DECISIONS[2], DECISIONS[3]):
        st.write(
            "For goal coaching or editing a recorded expense, first add "
            "the relevant financial blocks."
        )
        if st.button("Set up only what I need", key="dc_quick_setup"):
            st.switch_page("pages/5_Quick_Start.py")
        return
    with st.form("dc_no_profile_form", border=False):
        income = st.number_input(
            "Take-home pay each month ($)", value=None,
            min_value=0.0, max_value=10000000.0,
            step=50.0, format="%.2f",
            placeholder="Optional for emergency comparison",
        )
        spending = st.number_input(
            "Recorded monthly expenses ($)", value=None,
            min_value=0.0, max_value=10000000.0,
            step=50.0, format="%.2f",
            placeholder="Required",
            help="Include rent, groceries, insurance, bills and minimum loan payments.",
        )
        checking = st.number_input(
            "Checking / cash balance ($)", value=None,
            min_value=0.0, max_value=10000000.0, step=50.0,
            format="%.2f", placeholder="Required",
        )
        savings = None
        if choice == DECISIONS[1]:
            savings = st.number_input(
                "Accessible savings balance ($)", value=None,
                min_value=0.0, max_value=10000000.0,
                step=50.0, format="%.2f",
                placeholder="Optional",
            )
        expense = None
        kind = "one_time"
        if choice == DECISIONS[0]:
            kind = st.radio(
                "New cost", ("one_time", "recurring"), horizontal=True,
                format_func=lambda x: (
                    "One-time purchase" if x == "one_time"
                    else "Monthly commitment"
                ),
            )
            expense = st.number_input(
                "Proposed additional cost ($)", value=None,
                min_value=0.0, max_value=10000000.0,
                step=25.0, format="%.2f", placeholder="Required",
            )
        submit = st.form_submit_button(
            "Check with these assumptions", type="primary",
            use_container_width=True,
        )
    if not submit:
        st.caption(
            "Unentered bills, irregular expenses, income changes, "
            "and exact payment dates are not modeled."
        )
        return
    if spending is None or checking is None:
        st.error("Enter the monthly expenses and available checking/cash.")
        return
    if choice == DECISIONS[0] and (
        income is None or income <= 0 or expense is None or expense <= 0
    ):
        st.error("Add positive take-home income and the new cost.")
        return
    blocks = [
        {"id": "temp_costs", "kind": "expense", "name": "Entered costs",
         "monthly_amount": str(spending)},
        {"id": "temp_cash", "kind": "cash", "name": "Entered checking",
         "balance": str(checking)},
    ]
    if income is not None and income > 0:
        blocks.append({
            "id": "temp_income", "kind": "income",
            "name": "Entered take-home pay", "monthly_amount": str(income),
        })
    if savings is not None and savings > 0:
        blocks.append({
            "id": "temp_savings", "kind": "hysa", "name": "Entered savings",
            "balance": str(savings),
            "monthly_contribution": 0, "annual_rate": 0,
        })
    if choice == DECISIONS[0]:
        report = decision_check(
            blocks, cost=expense, cost_type=kind, reviewed=False,
        )
        if not report["comparable"]:
            st.warning(report["reason"])
            st.metric("Recorded checking available", dollars(report["available_checking"]))
            return
        st.markdown("### Your preliminary result")
        before = report["monthly_buffer_before"]
        after = report["monthly_buffer_after"]
        if kind == "one_time":
            st.metric(
                "Checking after this one-time cost",
                dollars(report["remaining_checking_now"]),
            )
            st.write(
                f"The purchase would use {dollars(report['cost'])} of the "
                "checking/cash amount entered."
            )
        else:
            st.metric(
                "Monthly flexibility after the new cost",
                dollars(after), delta=dollars(after - before),
            )
        if report["needs_attention"]:
            st.warning(
                "This hypothetical cost introduces a modeled warning. "
                "Include more expenses before interpreting it."
            )
        st.caption(
            "No savings goals, annual bills, outstanding loans, or other "
            "accounts were assumed unless included in your expense total. "
            "This is an educational comparison, not approval to spend."
        )
    else:
        report = emergency_readiness(blocks, reviewed=False)
        if not report["evaluable"]:
            st.info(report["reason"])
            return
        st.markdown("### Your preliminary liquid-savings picture")
        st.metric("Months of recorded expenses covered",
                  str(report["coverage_months"]))
        st.metric(
            "Difference to a sample three-month target",
            dollars(report["gap"]),
        )
        st.caption(
            "This sample target is adjustable with a complete profile. "
            "It is not a universal recommendation, and missing expenses "
            "may overstate your apparent reserves."
        )


def render_decision_page():
    blocks, result, summary, months, _, checkin, _ = context()
    reviewed = checkin["reviewed"]
    st.title("MoneyLab Decision Check")
    st.caption("Understand the tradeoff behind your next money decision.")
    if not blocks:
        st.caption("Start with a few relevant numbers. A full profile is optional.")
    else:
        _context_note(blocks, reviewed)
    choice = st.radio(
        "What would you like to figure out?",
        DECISIONS, key="dc_decision_type",
    )
    if not blocks:
        _empty_profile_decision(choice)
        return
    if choice == DECISIONS[0]:
        _cost_check(blocks, months, reviewed)
    elif choice == DECISIONS[1]:
        _emergency_check(blocks, months, reviewed)
    elif choice == DECISIONS[2]:
        _goal_check(blocks, months, reviewed)
    else:
        st.caption(
            "Advanced what-if comparisons let you change an existing expense "
            "and optionally save named scenarios."
        )
        render_explore(embedded=True)
    st.divider()
    with st.expander("Before deciding, check for missing costs"):
        st.write(
            "Many first-time budgets miss electricity, heating, phone plans, "
            "insurance, transportation, subscriptions, minimum debt payments, "
            "medical spending, and annual or irregular bills such as car repairs "
            "and registration. MoneyLab does not know what you have omitted."
        )
        st.caption(
            "You can add weekly, biweekly, monthly or yearly expense blocks "
            "in My Money. An annual bill is divided into a monthly planning "
            "average, but MoneyLab does not track its actual cash due date "
            "in these scenarios."
        )
        if st.button("Add or review my expenses", key="dc_review_expenses"):
            st.switch_page("pages/1_My_Money.py")
    with st.expander("Why this isn't a definitive affordability answer"):
        st.write(
            "MoneyLab uses financial figures you entered manually. It does not "
            "know every expense, exact account transaction date, taxes, live "
            "account balance, or unplanned cost. Its results are educational "
            "scenario comparisons, not promises or individualized financial advice."
        )
    lesson = (
        "budget" if choice in (DECISIONS[0], DECISIONS[3]) else
        "savings" if choice == DECISIONS[1] else "goals"
    )
    if st.button("Learn the concept behind this decision", key="dc_learn_context"):
        st.session_state.ml_lesson = lesson
        st.switch_page("pages/4_Learn.py")
