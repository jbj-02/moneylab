"""Plan-first consumer workflows. Calculations live in planning, never widgets."""
from decimal import Decimal
from datetime import date
import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

from moneylab.blocks import profile_to_json, serialize_blocks
from moneylab.cadence import FREQUENCIES, monthly_equivalent
from moneylab.design import eyebrow, goal_summary, hero
from moneylab.plan_setup import EXPENSES, PRIORITIES, build_profile
from moneylab.planning import apply_preview, goal_outlook, preview, signature
from moneylab.progress import accept_comparison, add_months, tracking_signature
from moneylab.plan_session import DEFAULT_METADATA, delete_local, load_example, restore, snapshot, sync_local
from moneylab.profile_store import plan_from_json
from moneylab.ui_app import add_block_dialog, as_csv, block_amount, context as financial_context, dollars, edit_block_dialog


def context():
    # Keep continuity at the page boundary as well as in the navigation shell.
    sync_local()
    if _metadata().get("is_example"):
        st.info("Fictional example plan. Replace these figures in My Finances before using it for yourself.")
    return financial_context()


def prose(text):
    st.markdown(text.replace("$", r"\$"))


def _caption(text):
    st.caption(text.replace("$", r"\$"))


def _metadata():
    return st.session_state.get("ml_plan_metadata", DEFAULT_METADATA)


def _reviewed(blocks):
    return (st.session_state.get("ml_reviewed_signature") == profile_to_json(blocks)
            and not _metadata()["unknown"])


def _review(blocks):
    unknown = _metadata()["unknown"]
    if unknown:
        names = {**EXPENSES, "income": "take-home income", "checking": "checking balance", "savings": "savings balance", "debts": "debts"}
        st.info("Not yet confirmed: " + ", ".join(names[k] for k in unknown) + ". Estimates only include recorded figures.")
    confirmed = st.checkbox("My entries include all income, regular spending, balances and debts (including any $0 amounts)",
                            key="plan_review_confirmation")
    if st.button("Confirm my figures", disabled=not confirmed, key="plan_confirm_figures"):
        st.session_state.ml_plan_metadata = {**_metadata(), "unknown": [], "is_example": False}
        st.session_state.ml_reviewed_signature = profile_to_json(blocks)
        st.rerun()


def _chart(projection, alternative=None):
    records = []
    for label, result in [("Current plan", projection), ("Alternative", alternative)]:
        if result is None:
            continue
        for row in result["monthly_records"]:
            records.append({"Month": row["month"], "Plan": label,
                            "Cash & savings": float(row["cash_position"] + row["other_assets"])})
    chart = alt.Chart(pd.DataFrame(records)).mark_line(strokeWidth=3).encode(
        x=alt.X("Month:Q", axis=alt.Axis(tickMinStep=1, title="Months from the plan date")),
        y=alt.Y("Cash & savings:Q", axis=alt.Axis(format="$,.0f"), title="Modeled cash + savings / investments"),
        color=alt.Color("Plan:N", scale=alt.Scale(domain=["Current plan", "Alternative"], range=["#17665a", "#bb7728"]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["Plan:N", "Month:Q", alt.Tooltip("Cash & savings:Q", format="$,.2f")],
    ).properties(height=260).configure_view(stroke=None).configure_axis(gridColor="#e6ebe5", labelColor="#526462", titleColor="#526462")
    st.altair_chart(chart, width="stretch")
    _caption("Includes recorded savings and investments; negative cash represents unfunded costs. This is a monthly estimate, not a bank balance forecast.")


def _comparison(blocks):
    comparison = st.session_state.get("ml_plan_preview")
    if not comparison:
        return
    st.subheader("Current plan vs alternative")
    stale = None
    try:
        apply_preview(blocks, comparison)
        if comparison.get("tracking_signature") and comparison["tracking_signature"] != tracking_signature(_metadata().get("accepted_plan")):
            stale = "Your selected schedule changed. Compare progress again before approving it."
    except ValueError as exc:
        stale = str(exc)
    if stale:
        st.warning("Your figures changed. Compare again to see an up-to-date alternative." if comparison["source_signature"] != signature(blocks) else stale)
        if st.button("Discard alternative", key="plan_discard_stale"):
            st.session_state.ml_plan_preview = None
            st.rerun()
        return
    before, after = comparison["baseline"], comparison["alternative"]
    months = before["summary"]["months"]
    _caption(f"{comparison['title']} · {months}-month comparison · your current plan is unchanged")
    from moneylab.action_ui import model_date, funding_text, render_stress_test
    from moneylab.action_plan import explain_option
    anchor = date.fromisoformat(comparison["progress"]["as_of"]) if comparison.get("progress") else model_date(_metadata())
    _caption(f"These outlooks start at {anchor:%b %d, %Y}. Dates are estimates in whole months.")
    if comparison.get("progress"):
        progress = comparison["progress"]
        prose(f"**Progress against your chosen schedule:** expected {dollars(progress['expected'])}; recorded {dollars(progress['recorded'])} "
              f"after {progress['elapsed_months']} whole months.")
        if progress["behind"]:
            st.warning(f"Your recorded balance is {dollars(progress['behind'])} behind the selected schedule. Review the new saving pace below.")
            revised = goal_outlook(comparison["blocks"], progress["goal_id"])
            if revised["required"] is not None:
                prose(f"To reach the target in the remaining {revised['deadline']} months, the model needs "
                      f"**{dollars(revised['required'])}/month** ({dollars(revised['extra'])} more than the recorded pace). "
                      "After approving this balance update, review that recalculated action on My Plan.")
            else:
                prose("The remaining deadline cannot be funded from the recorded monthly money. "
                      "After recording this balance, compare a later date, smaller target or an expense reduction you choose.")
        else:
            st.success("Your recorded balance meets or exceeds the selected schedule at this check-in.")
        if progress["overdue"]:
            st.warning("The original deadline has passed for: " + ", ".join(progress["overdue"]) + ". The engine uses at least one future month for a recovery projection.")
        if progress.get("partial_deadlines"):
            st.warning("Less than one full month remains for: " + ", ".join(progress["partial_deadlines"]) +
                       ". The monthly model uses one future month and cannot establish whether the original partial-month deadline can be met.")
        _caption("The two outlooks compare the last recorded and proposed balances at the same check-in date. "
                 "Other balances and commitments stay as recorded; update them if they changed.")
    # Make the edits concrete before asking for approval.
    original = {b["id"]: b for b in serialize_blocks(blocks)}
    for item in comparison["blocks"]:
        old = original.get(item["id"])
        if old is None:
            prose(f"Add **{item['name']}**: {dollars(Decimal(item.get('monthly_amount', 0)))}/month")
        elif old != item:
            for key, label in (("monthly_amount", "monthly amount"), ("balance", "balance"), ("target", "savings target"),
                               ("monthly_contribution", "monthly saving"), ("monthly_payment", "monthly debt payment"),
                               ("target_months", "deadline in months")):
                if old.get(key) != item.get(key):
                    left = str(old[key]) if key == "target_months" else dollars(Decimal(old[key]))
                    right = str(item[key]) if key == "target_months" else dollars(Decimal(item[key]))
                    prose(f"**{item['name']}**, {label}: {left} → {right}")
    cashflow = after["monthly_records"][1]["net_cash_flow"]
    cashflow_change = cashflow - before["monthly_records"][1]["net_cash_flow"]
    st.metric("First-month remainder after bills, debt & saving", dollars(cashflow),
              delta=dollars(cashflow_change) if cashflow_change else None)
    a, b, c = st.columns(3)
    for col, field, label in ((a, "ending_cash_savings", "Cash at the end"),
                               (b, "ending_debt", "Debt at the end"),
                               (c, "total_interest", "Interest paid / accrued")):
        change = after["summary"][field] - before["summary"][field]
        col.metric(label, dollars(after["summary"][field]),
                   delta=dollars(change) if change else None,
                   delta_color="inverse" if field in ("ending_debt", "total_interest") else "normal")
    _chart(before, after)
    goals_before = {g["id"]: g for g in before["goals"]}
    for goal in after["goals"]:
        old = goals_before.get(goal["id"])
        if old:
            # Compare each plan at its OWN deadline, which is labeled explicitly.
            prose(f"**{goal['name']}**: {dollars(old['projected_at_deadline'])} at month {old['target_months']} → "
                     f"{dollars(goal['projected_at_deadline'])} at month {goal['target_months']} "
                     f"({'target reached' if goal['on_track'] else 'below target'}).")
    analysis = explain_option(comparison, comparison.get("focus_goal_id"))
    for goal in analysis["effects"]["goals"]:
        if goal["completion_after"] is not None:
            prose(f"**{goal['name']} projected target date:** around {add_months(anchor, goal['completion_after']):%b %d, %Y} "
                  f"({goal['completion_after']} months from this plan date).")
        else:
            prose(f"**{goal['name']}:** target not reached within {analysis['effects']['searched_months']} months.")
    with st.expander("Where the money comes from, and what gives"):
        funding_text(analysis)
        for text in analysis["tradeoffs"]:
            prose(text)
    preference = _metadata().get("action_preference", {})
    if preference.get("focus") == "cash" and analysis["effects"]["min_cash_after"] < Decimal(preference.get("cash_floor", "0")):
        st.warning("This option falls below the checking/cash cushion you selected. Review that tradeoff before approving it.")
    shortfall = next((r for r in after["monthly_records"][1:] if r["unfunded_shortfall"] > 0), None)
    if shortfall:
        st.warning(f"This alternative has unfunded costs starting in month {shortfall['month']}. "
                   f"The first gap is {dollars(shortfall['unfunded_shortfall'])}. No borrowing is assumed.")
    if any(r["negative_amortization"] for r in after["monthly_records"][1:]):
        st.warning("At least one loan grows because payments do not cover interest.")
    with st.expander("What this comparison assumes"):
        prose("Amounts repeat monthly from now. Interest uses the entered constant rates; income is after tax. "
                 "Savings transfers use available monthly money after recorded expenses and debt payments, in profile order. "
                 "A larger transfer to one goal can delay another. Inflation, unexpected costs and daily bill timing are excluded.")
        for unknown in _metadata().get("unknown", []):
            from moneylab.action_plan import MISSING_LABELS
            prose("Not yet confirmed: " + MISSING_LABELS.get(unknown, unknown) + ".")
    render_stress_test(comparison)
    reviewed = _reviewed(blocks)
    if not reviewed:
        st.info("Confirm your complete figures in My Finances before applying an alternative. You can still explore it here.")
    choosing_current = comparison["source_signature"] == comparison["candidate_signature"] and not comparison.get("progress")
    approved = st.checkbox("Use this plan as my selected schedule" if choosing_current else
                           "I want to replace my plan with these exact changes", key="plan_apply_confirm")
    a, b = st.columns(2)
    if a.button("Choose this plan" if choosing_current else "Apply these changes to my plan",
                 type="primary", disabled=not approved or not reviewed, key="plan_apply"):
        try:
            updated, metadata = accept_comparison(blocks, comparison, _metadata(), on_date=anchor)
            st.session_state.ml_blocks = updated
            st.session_state.ml_plan_metadata = metadata
            st.session_state.pop("ml_reviewed_signature", None)
            st.session_state.ml_plan_preview = None
            st.session_state.plan_applied = True
            st.switch_page("pages/0_Home.py")
        except ValueError as exc:
            st.error(str(exc))
    if b.button("Discard alternative", key="plan_discard"):
        st.session_state.ml_plan_preview = None
        st.rerun()


def _remember(comparison, *, origin="pages/0_Home.py"):
    st.session_state.ml_plan_preview = comparison
    st.session_state.ml_plan_preview_origin = origin
    st.session_state.pop("plan_apply_confirm", None)
    st.session_state.pop("ml_stress_result", None)
    st.switch_page("pages/9_Compare_Plan.py")


def _pending(blocks):
    comparison = st.session_state.get("ml_plan_preview")
    if comparison:
        if comparison["source_signature"] != signature(blocks):
            st.warning("Your figures changed. Compare again to see an up-to-date alternative.")
        st.page_link("pages/9_Compare_Plan.py", label="Review pending alternative")


def render_comparison():
    blocks, *_ = context()
    if not st.session_state.get("ml_plan_preview"):
        st.switch_page(st.session_state.get("ml_plan_preview_origin", "pages/0_Home.py"))
    eyebrow("A TRIAL RUN FOR YOUR MONEY")
    st.title("Compare your plan")
    _comparison(blocks)
    st.page_link(st.session_state.get("ml_plan_preview_origin", "pages/0_Home.py"), label="Keep exploring without applying")


def render_home():
    blocks, result, summary, months, _, _, _ = context()
    eyebrow("YOUR FINANCIAL PLAN")
    st.title("My Plan")
    if not blocks:
        hero("Make room for what comes next.", "Know where you stand, build a plan for a goal, and see what a big decision would change. Start with what you know; fill in the rest later.")
        a, b = st.columns([2, 1])
        with a:
            st.subheader("A plan you can actually use")
            prose("1. Choose what matters to you.\n2. Add your pay, spending and savings.\n3. Get a clear next step, backed by your numbers.")
            if st.button("Set up my finances", type="primary", key="ml_home_quick_start"):
                st.switch_page("pages/5_Quick_Start.py")
        with b:
            with st.container(border=True):
                st.markdown("**Just exploring?**")
                prose("See how the plan works with fictional figures, or check a move before setting everything up.")
                if st.button("Try a fictional plan", key="plan_example_home"):
                    load_example()
                    st.rerun()
                st.page_link("pages/7_Moving_Out_Alpha.py", label="Try a move-out decision")
        _smart_entry()
        return
    reviewed = _reviewed(blocks)
    from moneylab.action_ui import action_context, render_next_actions, render_followthrough
    plan = action_context(blocks, _metadata(), reviewed, months)
    from moneylab.action_ui import model_date
    _caption(f"Recorded plan date: {model_date(_metadata()):%b %d, %Y}. Update your balances with a progress check-in as time passes.")
    render_next_actions(blocks, plan, _metadata(), reviewed)
    _pending(blocks)
    if st.session_state.pop("plan_applied", False):
        st.success("Your approved changes are now in your plan. Review your updated figures when you are ready.")
    # Signed cash flow remains visible when the user is struggling; never mask it as $0.
    flow = result["monthly_records"][1]["net_cash_flow"]
    a, b, c = st.columns(3)
    a.metric("Monthly take-home", dollars(summary["monthly_income"]))
    b.metric("After bills, debt & saving", dollars(flow))
    c.metric("Cash available today", dollars(result["monthly_records"][0]["cash_savings"]))
    _caption("Recorded figures only. The monthly remainder includes transfers the model can fund; existing cash may temporarily cover a deficit.")
    if not reviewed:
        with st.expander("Complete or confirm your financial picture", expanded=True):
            _review(blocks)
            st.page_link("pages/1_My_Money.py", label="Edit my finances")
    goals = [g for g in blocks if g["kind"] == "goal"]
    st.subheader("What you're working toward")
    if not goals:
        prose("Give your savings a purpose. Add a target and a deadline to see a practical saving pace.")
        if st.button("Add a savings goal", key="plan_add_goal"):
            add_block_dialog(preferred_kind="goal")
    for goal in goals:
        outlook = plan["goals"][goal["id"]]
        with st.container(border=True):
            goal_summary(goal["name"], outlook["starting"], outlook["target"], on_track=outlook["on_track"])
            st.progress(float(min(outlook["starting"] / outlook["target"], 1)))
            _caption(f"{dollars(outlook['planned'])}/month planned · month {outlook['deadline']} target · {dollars(outlook['projected'])} projected then")
            if st.button("Explore ways to reach this goal", key=f"action_goal_open_{goal['id']}"):
                st.session_state.ml_selected_action = {"id": f"goal:{goal['id']}", "kind": "goal", "goal_id": goal["id"]}
                st.switch_page("pages/10_Action_Plan.py")
            render_followthrough(blocks, goal, _metadata())
    st.subheader("Where your plan could take you")
    _caption(f"{months} months from the recorded plan date, if your monthly pattern continues.")
    _chart(result)
    _smart_entry()


def _smart_entry():
    from moneylab.smart_decision_ui import render_smart_decision_entry
    with st.expander("Describe a decision in your own words", expanded=st.session_state.get("smart_origin") == "home"):
        render_smart_decision_entry("home")


def render_finances():
    blocks, _, summary, _, _, _, _ = context()
    eyebrow("THE FIGURES BEHIND YOUR PLAN")
    st.title("My Finances")
    prose("Update your numbers once. Your plan and decisions use the same financial picture.")
    from moneylab.action_ui import model_date
    _caption(f"Goal timelines are relative to the recorded plan date, {model_date(_metadata()):%b %d, %Y}. Use a progress check-in to advance that date.")
    if not blocks:
        if st.button("Set up my finances", type="primary"):
            st.switch_page("pages/5_Quick_Start.py")
        return
    st.metric("Monthly take-home minus bills & debt", dollars(summary["monthly_income"] - summary["monthly_expenses"] - summary["first_month_loan_payments"]))
    groups = (("Monthly money", ("income", "expense")),
              ("Balances & debt", ("cash", "loan", "hysa", "roth_ira", "account")),
              ("Goals", ("goal",)))
    tabs = st.tabs([g[0] for g in groups])
    for tab, (_, kinds) in zip(tabs, groups):
        with tab:
            for entry in (b for b in blocks if b["kind"] in kinds):
                with st.container(border=True):
                    a, b = st.columns([4, 1], vertical_alignment="center")
                    amount, detail = block_amount(entry)
                    a.markdown(f"**{entry['name']}** · {amount}".replace("$", r"\$"))
                    a.caption(detail)
                    if b.button("Edit", key=f"plan_edit_{entry['id']}", width="stretch"):
                        edit_block_dialog(entry["id"])
                    with st.popover("Remove this entry"):
                        approved = st.checkbox("Remove this figure from my plan", key=f"plan_remove_confirm_{entry['id']}")
                        if st.button("Remove entry", disabled=not approved, key=f"plan_remove_{entry['id']}"):
                            from moneylab.ui_app import remove_block
                            remove_block(entry["id"])
            cols = st.columns(min(len(kinds), 3))
            labels = {"income": "Income", "expense": "Expense", "cash": "Checking / cash",
                      "loan": "Debt", "hysa": "Savings", "goal": "Goal"}
            visible = [k for k in kinds if k in labels]
            for index, kind in enumerate(visible):
                if cols[index % len(cols)].button(f"Add {labels[kind].lower()}", key=f"plan_add_{kind}", width="stretch"):
                    add_block_dialog(preferred_kind=kind)
            if "goal" in kinds:
                _caption("Each goal is a separate savings pot. Move money out of another account before assigning it here, so it is counted once. "
                           "Available monthly money funds accounts and goals in their saved order.")
    with st.expander("Review completeness", expanded=not _reviewed(blocks)):
        _review(blocks)
    st.page_link("pages/6_Settings.py", label="Back up, restore or delete my data")


def render_setup():
    eyebrow("A LITTLE CLARITY GOES A LONG WAY")
    st.title("Build your financial plan")
    if st.session_state.get("ml_blocks"):
        st.info("You already have a plan. Edit its figures in My Finances; setup will never replace it.")
        st.page_link("pages/1_My_Money.py", label="Edit my finances")
        return
    draft = dict(st.session_state.get("plan_setup_draft", {}))
    step = st.session_state.get("plan_setup_step", 0)
    titles = ("What matters to you", "Your monthly picture", "Balances & review")
    st.progress((step + 1) / 3)
    _caption(f"Step {step + 1} of 3 · {titles[step]}")
    st.subheader(titles[step])
    _caption("Blank means unknown. Enter $0 when you know there is nothing to record. Your answers stay here when you go Back.")

    def field(label, key, parent=st, help=None):
        return parent.number_input(label, min_value=0.0, max_value=1e12,
                                   value=float(draft[key]) if draft.get(key) is not None else None,
                                   step=25.0, format="%.2f", key=f"setup_{key}", help=help)

    values = {}
    if step == 0:
        priority = st.radio("I want to…", PRIORITIES, index=PRIORITIES.index(draft.get("priority", PRIORITIES[0])), key="setup_priority")
        values["priority"] = priority
        with st.form("plan_setup_priority_form"):
            if priority != "Understand my money":
                values["goal_name"] = st.text_input("Give your goal a name", value=draft.get("goal_name", ""),
                                                   placeholder="Emergency fund, first apartment, a car…", max_chars=60)
                values["target"] = field("How much do you want to save? ($)", "target", help="For an emergency fund, choose a cushion that feels useful to you. You can change it later.")
                values["goal_months"] = st.number_input("In how many months?", min_value=1, max_value=600, value=draft.get("goal_months", 12))
            submitted = st.form_submit_button("Continue", type="primary")
        if submitted:
            if priority != "Understand my money" and (values["target"] is None or values["target"] <= 0):
                st.error("Enter a savings target greater than $0, or choose Understand my money to start without a goal.")
            else:
                st.session_state.plan_setup_draft = {**draft, **values}
                st.session_state.plan_setup_step = 1
                st.rerun()
    elif step == 1:
        with st.form("plan_setup_monthly_form"):
            values["income"] = field("Monthly take-home pay ($)", "income", help="Money you receive after tax and payroll deductions. Include regular income you expect to continue.")
            st.markdown("**Everyday spending, per month**")
            _caption("Include what you pay yourself. Keep debt payments separate below.")
            a, b = st.columns(2)
            for index, (key, label) in enumerate(EXPENSES.items()):
                values[key] = field(f"{label} ($)", key, a if index % 2 == 0 else b)
            left, right = st.columns(2)
            back = left.form_submit_button("Back")
            submitted = right.form_submit_button("Continue", type="primary")
        if back or submitted:
            st.session_state.plan_setup_draft = {**draft, **values}
            st.session_state.plan_setup_step = 0 if back else 2
            st.rerun()
    else:
        debt_statuses = ("I'll add this later", "I have no debt", "I have debt")
        status = st.radio("Loans or credit card balances?", debt_statuses,
                          index=debt_statuses.index(draft.get("debt_status", debt_statuses[0])), key="setup_debt_status")
        values["debt_status"] = status
        with st.form("plan_setup_balances_form"):
            a, b = st.columns(2)
            values["checking"] = field("Checking / cash today ($)", "checking", a)
            values["savings"] = field("Total savings today ($)", "savings", b, help="Include money set aside for your goal. Exclude checking, investments and retirement.")
            if draft.get("priority") != "Understand my money":
                st.markdown("**Your goal's savings pot**")
                values["goal_saved"] = field("Of your total savings, already set aside for this goal ($)", "goal_saved")
                values["goal_monthly"] = field("What do you currently plan to save each month? ($)", "goal_monthly", help="Enter $0 if you are not saving yet. MoneyLab will show the pace needed for your deadline.")
            if status == "I have debt":
                _caption("Start with one loan. Add any others in My Finances after setup.")
                values["debt_balance"] = field("Debt balance ($)", "debt_balance")
                values["debt_rate"] = st.number_input("Annual interest rate (%)", min_value=0.0, max_value=100.0,
                                                      value=draft.get("debt_rate"), step=0.1, key="setup_debt_rate")
                values["debt_payment"] = field("Monthly debt payment ($)", "debt_payment")
            _caption(f"Monthly take-home: {dollars(Decimal(str(draft['income'])))}" if draft.get("income") is not None else "Take-home income is still unknown.")
            _caption("We assume no savings interest in setup. Add interest rates and more accounts later if useful.")
            approved = st.checkbox("Use these figures to build my preliminary plan", key="plan_setup_approve")
            left, right = st.columns(2)
            back = left.form_submit_button("Back")
            submitted = right.form_submit_button("Build my plan", type="primary")
        if back:
            st.session_state.plan_setup_draft = {**draft, **values}
            st.session_state.plan_setup_step = 1
            st.rerun()
        elif submitted:
            st.session_state.plan_setup_draft = {**draft, **values}
            if not approved:
                st.error("Review your figures and check the box to build your plan.")
            else:
                try:
                    blocks, metadata = build_profile({**draft, **values})
                    if not blocks:
                        raise ValueError("Enter at least one financial figure to start your plan.")
                    st.session_state.ml_blocks = blocks
                    st.session_state.ml_plan_metadata = metadata
                    st.session_state.pop("ml_reviewed_signature", None)
                    st.switch_page("pages/0_Home.py")
                except ValueError as exc:
                    st.error(str(exc))


def render_decisions():
    blocks, _, _, months, _, _, _ = context()
    if not blocks:
        # A temporary snapshot is still useful for someone evaluating one cost.
        from moneylab.decision_ui import render_decision_page
        render_decision_page()
        return
    eyebrow("GIVE A DECISION A TRIAL RUN")
    st.title("Explore Decisions")
    prose("Use your current plan as the starting point. See the tradeoffs before changing it.")
    choices = ("One-time purchase", "Recurring commitment", "Change an expense", "Change income", "Pay down debt", "Moving out")
    saved_cost = st.session_state.get("ml_profile_cost_draft")
    default_kind = "Recurring commitment" if saved_cost and saved_cost["cost_type"] == "recurring" else "One-time purchase"
    kind = st.radio("What would you like to compare?", choices, index=choices.index(default_kind), horizontal=True, key="dc_cost_kind")
    if kind == "Moving out":
        prose("Compare staying with moving, including deposits, rent and the savings cushion you want to keep.")
        if st.button("Open move-out comparison", type="primary"):
            st.session_state.move_start_mode = "Use My Money figures"
            st.switch_page("pages/7_Moving_Out_Alpha.py")
        return
    amount = 0
    frequency = "monthly"
    selected = None
    if kind in ("Change an expense", "Change income", "Pay down debt"):
        match = {"Change an expense": "expense", "Change income": "income", "Pay down debt": "loan"}[kind]
        options = [b for b in blocks if b["kind"] == match]
        if not options:
            st.info("Add this type of financial entry in My Finances before comparing a change.")
            return
        selected_id = st.selectbox("Choose a recorded item", [b["id"] for b in options],
                                   format_func=lambda v: next(b["name"] for b in options if b["id"] == v))
        selected = next(b for b in options if b["id"] == selected_id)
        field_name = "monthly_payment" if match == "loan" else "monthly_amount"
        amount = st.number_input("Try a new monthly amount ($)", min_value=0.0,
                                 value=float(selected[field_name]), step=25.0, format="%.2f",
                                 key=f"plan_decision_amount_{selected_id}")
    else:
        amount = st.number_input("Cost amount ($)", min_value=0.0, max_value=1e8,
                                 value=None if "dc_cost_value" in st.session_state else float(saved_cost["cost"]) if saved_cost else 200.0,
                                 step=25.0, format="%.2f", key="dc_cost_value")
        if kind == "Recurring commitment":
            frequency = st.selectbox("How often is this cost paid?", list(FREQUENCIES),
                                     index=list(FREQUENCIES).index(saved_cost["frequency"] if saved_cost else "monthly"),
                                     format_func=lambda k: FREQUENCIES[k][0], key="dc_cost_frequency")
            _caption(f"Monthly average: {dollars(monthly_equivalent(amount, frequency))}.")
        _caption("Include taxes and extra costs you expect. A purchase uses recorded checking / cash only; no borrowing or goal withdrawals are assumed.")
    if not _reviewed(blocks):
        st.info("This is a preliminary comparison. Confirm complete figures in My Finances before applying changes.")
    if st.button("Compare with my current plan", type="primary", key="plan_compare_decision"):
        try:
            from moneylab.scenario_changes import apply_scenario_changes
            if kind == "Pay down debt":
                alternative = serialize_blocks(blocks)
                next(b for b in alternative if b["id"] == selected["id"])["monthly_payment"] = str(amount)
            elif kind in ("Change an expense", "Change income"):
                alternative = apply_scenario_changes(blocks, [{"operation": "set_monthly", "block_id": selected["id"], "amount": amount}])
            else:
                operation = "one_time_cash" if kind == "One-time purchase" else "add_monthly_expense"
                cost = monthly_equivalent(amount, frequency) if kind == "Recurring commitment" else amount
                alternative = apply_scenario_changes(blocks, [{"operation": operation, "amount": cost}])
            st.session_state.dc_profile_compared = kind in ("One-time purchase", "Recurring commitment")
            if st.session_state.dc_profile_compared:
                st.session_state.dc_profile_source = "Use My Money figures"
                st.session_state.ml_profile_cost_draft = {
                    "cost": str(amount), "cost_type": "recurring" if kind == "Recurring commitment" else "one_time",
                    "frequency": frequency,
                }
            else:
                st.session_state.pop("ml_profile_cost_draft", None)
            _remember(preview(blocks, alternative, title=kind, months=months), origin="pages/3_Explore.py")
            st.rerun()
        except ValueError as exc:
            st.error(f"Could not compare: {exc}")
    _pending(blocks)


def render_settings():
    blocks, result, *_ = context()
    eyebrow("YOUR DATA, YOUR CONTROL")
    st.title("Save or restore your workspace")
    if st.session_state.pop("plan_deleted", False):
        st.success("Your financial data has been deleted.")
    status = st.session_state.get("ml_save_status", "Session only · download a backup")
    st.info(status)
    if status == "Saved locally on this computer":
        prose("Your plan is saved in a private file on this computer. This is single-user local development storage, without account authentication or application-level encryption. Keep backups private.")
    else:
        prose("This deployment does not provide account-based saving. Your session may end when you close or reload the app. Download a backup to return to your plan.")
    st.subheader("Keep a copy")
    _caption("Includes entered figures, your action preference and selected schedule, missing-information markers, saved expense scenarios and supported decision drafts. Pending alternatives and calculated results are not saved.")
    st.download_button("Download workspace (JSON)", snapshot(), file_name="moneylab_workspace.json", mime="application/json", type="primary")
    st.download_button("Download financial projection (CSV)", as_csv(result), file_name="moneylab_projection.csv", mime="text/csv")
    st.subheader("Restore a copy")
    _caption("Supports workspace versions 1–5. A validated import replaces the current plan. Restored results must be recalculated and figures reviewed.")
    uploaded = st.file_uploader("Choose a MoneyLab workspace (.json)", type=["json"])
    replace = st.checkbox("I understand this replaces my current session's data", key="ml_restore_approval")
    if st.button("Restore selected workspace", disabled=uploaded is None or not replace, key="ml_restore_workspace"):
        try:
            raw = uploaded.getvalue()
            if len(raw) > 200_000:
                raise ValueError("Workspace exceeds the 200 KB limit.")
            text = raw.decode("utf-8")
            plan_from_json(text)  # Complete validation before touching state.
            restore(text)
            st.session_state.plan_restored = True
            st.rerun()
        except (ValueError, UnicodeDecodeError) as exc:
            st.error(f"Workspace not restored: {exc}")
    if st.session_state.pop("plan_restored", False):
        st.success("Workspace restored. Review your figures and recalculate any decision.")
    if st.session_state.get("ml_restored_moving"):
        st.page_link("pages/7_Moving_Out_Alpha.py", label="Open restored Moving Out decision")
    if st.session_state.get("ml_restored_cost"):
        st.page_link("pages/3_Explore.py", label="Open restored purchase or expense decision")
    with st.expander("Delete my financial data"):
        prose("Clears this session and deletes the locally saved plan if local saving is enabled. Copies you downloaded are separate.")
        confirmed = st.checkbox("Delete my plan and decision drafts", key="plan_delete_confirm")
        if st.button("Delete my data", disabled=not confirmed):
            try:
                delete_local()
                st.session_state.plan_deleted = True
                st.rerun()
            except (ValueError, OSError, sqlite3.Error) as exc:
                st.error(f"Data was not deleted: {exc}")
