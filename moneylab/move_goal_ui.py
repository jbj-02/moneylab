"""Compare move timing options without editing the underlying plan."""
from decimal import Decimal

import streamlit as st

from moneylab.move_goal import move_goal_timing


def _amount(label, key, *, value=0.0, maximum=100_000_000.0, help_text=None):
    number = st.number_input(label, min_value=0.0, max_value=maximum, value=value,
                             step=0.01, format="%.2f", key=key, help=help_text)
    return Decimal(str(number)).quantize(Decimal("0.01"))


def _timing(months):
    if months is None:
        return "No date at this savings pace"
    if months == 0:
        return "Target met today"
    return f"In {months:,} month{'s' if months != 1 else ''}"


def _impact(current, option):
    if option["months"] is None or current["months"] is None:
        return _timing(option["months"])
    sooner = current["months"] - option["months"]
    if sooner > 0:
        return f"{sooner:,} month{'s' if sooner != 1 else ''} sooner"
    if sooner < 0:
        return f"{-sooner:,} month{'s' if sooner != -1 else ''} later"
    return "Same target timing"


def render_move_goal(report, inputs, money):
    st.markdown("### When could I move?")
    if report["missing"]:
        st.caption("This estimate uses the amounts entered. Check the missing costs before relying on the timing.")
    a, b, c = st.columns(3)
    with a:
        savings = _amount(
            "Amount you plan to save each month ($)", "move_goal_savings",
            help_text="Enter a new monthly transfer while you stay. Existing included goal transfers are reserved separately.",
        )
    with b:
        cushion = _amount("Cash to keep after moving ($)", "move_goal_cushion")
    with c:
        deadline = st.number_input("Target in how many months?", 1, 120, 6, key="move_goal_deadline")

    try:
        current = move_goal_timing(report, monthly_savings=savings, cushion=cushion, deadline=deadline)
    except ValueError as exc:
        st.info(str(exc))
        return

    left, right = st.columns(2)
    left.metric("Current plan · move-in costs plus cushion", _timing(current["months"]))
    right.metric("Monthly cash left after moving", money(current["monthly_after"]))
    if current["deadline_gap"]:
        st.write(f"At month {deadline}, you’d still need {money(current['deadline_gap'])}.")
        st.write(f"The target would take {money(current['required_monthly'])} in monthly savings by that deadline.")
        if current["required_monthly"] > current["saving_capacity"]:
            st.caption("That amount exceeds the monthly room in your current plan.")
    if current["monthly_after"] < 0:
        st.warning("The target covers the move and your chosen cushion. The ongoing plan still shows a monthly shortfall.")

    st.markdown("#### What could you change?")
    living = next(row["amount"] for row in report["details"]["current"] if row["field"] == "other_living")
    options = {"Keep my current plan": current}
    if living > 0:
        with st.expander("Redirect part of your current spending"):
            name = st.text_input("Expense to reduce", placeholder="e.g. Going out", key="move_goal_expense")
            recorded = _amount("Monthly amount already included in other living expenses ($)",
                               "move_goal_expense_total", maximum=float(living))
            room = report["monthly_margin_before"] - report["details"]["planned_goal_contributions"]
            additional_needed = current["required_monthly"] - min(savings, room)
            if current["deadline_gap"] and additional_needed > 0:
                if additional_needed <= recorded:
                    st.button(f"Try cutting {money(additional_needed)} per month to meet the target",
                              key="move_goal_try_cut", on_click=st.session_state.update,
                              kwargs={"move_goal_cut": float(additional_needed)})
                elif recorded > 0:
                    st.caption("This expense alone cannot close the gap by your target month.")
            cut = _amount("Amount to redirect each month ($)", "move_goal_cut")
            if cut > recorded:
                st.error("The amount you redirect must fit within what you already spend on this expense.")
            elif cut > 0:
                option = move_goal_timing(report, monthly_savings=savings, cushion=cushion,
                                          deadline=deadline, spending_cut=cut)
                options["Reduce an expense"] = option
                st.write(f"**{_impact(current, option)}**")
                st.text(f"Reduce {name.strip() or 'this expense'} by {money(cut)} per month.")
                st.write(f"Monthly savings toward the move would be {money(option['monthly_savings'])}.")

    rent = Decimal(str(inputs["rent"]))
    with st.expander("Try lower rent or a roommate"):
        new_rent = _amount("Alternative share of monthly rent ($)", "move_goal_rent")
        upfront = _amount("Alternative total move-in costs ($)", "move_goal_alt_upfront",
                          value=float(report["upfront"]), maximum=400_000_000.0)
        if new_rent > 0 and new_rent < rent:
            alternative = {
                **report,
                "upfront": upfront,
                "monthly_margin_after": report["monthly_margin_after"] + rent - new_rent,
            }
            option = move_goal_timing(alternative, monthly_savings=savings,
                                      cushion=cushion, deadline=deadline)
            options["Pay lower rent"] = option
            st.write(f"**{_impact(current, option)}**")
            st.write(f"Monthly cash left after moving would be {money(option['monthly_after'])}.")
            st.caption("Update the total move-in costs if the alternative changes the deposit or fees.")
        elif new_rent >= rent:
            st.info("Enter a positive rent share below the original amount to compare.")

    if st.session_state.get("move_goal_comparison") not in options:
        st.session_state.pop("move_goal_comparison", None)
    selected = st.selectbox("Compare with my current plan", list(options), key="move_goal_comparison")
    option = options[selected]
    if selected != "Keep my current plan":
        baseline, changed = st.columns(2)
        for column, label, plan in ((baseline, "Current plan", current), (changed, selected, option)):
            with column:
                st.markdown(f"**{label}**")
                st.metric("Move-in costs plus cushion", _timing(plan["months"]))
                st.metric("Cash left per month after moving", money(plan["monthly_after"]))
                st.metric(f"Still needed at month {deadline}", money(plan["deadline_gap"]))
                st.metric("Cash just after moving",
                          money(plan["cash_after"]) if plan["cash_after"] is not None else "—")
        if option["monthly_after"] < 0:
            st.warning("This option still leaves a monthly shortfall after moving.")
    elif current["cash_after"] is not None:
        st.metric("Cash just after moving at this pace", money(current["cash_after"]))
    st.caption("Estimates use whole months and fixed savings. A spending reduction is assumed to continue after moving. "
               "Only eligible cash pays move-in costs, and the cushion uses accessible cash left afterward.")
