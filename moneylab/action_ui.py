"""Understand → compare → choose → check progress, using pure planning services."""
from datetime import date
from decimal import Decimal
import json

import pandas as pd
import streamlit as st

from moneylab.action_plan import (
    DEFAULT_PREFERENCE, FOCUSES, action_breakdown, build_action_plan,
    goal_options, stress_test, validate_preference,
)
from moneylab.blocks import project_blocks
from moneylab.design import eyebrow, hero
from moneylab.planning import goal_alternative, preview, signature
from moneylab.progress import add_months, progress_preview, remaining_months
from moneylab.ui_app import dollars


def _helpers():
    from moneylab import plan_ui
    return plan_ui


def model_date(metadata):
    record = metadata.get("accepted_plan")
    return date.fromisoformat(record["last_as_of"]) if record else date.today()


def action_context(blocks, metadata, reviewed, months=24):
    return build_action_plan(blocks, reviewed=reviewed, months=months,
                             preference=metadata.get("action_preference", DEFAULT_PREFERENCE),
                             missing=metadata.get("unknown", []))


def render_priorities(blocks, metadata):
    h = _helpers()
    preference = metadata.get("action_preference", DEFAULT_PREFERENCE)
    goals = [g for g in blocks if g["kind"] == "goal"]
    with st.popover("Your priorities"):
        st.markdown("**What matters most right now?**")
        focus = st.radio("Action priority", list(FOCUSES), index=list(FOCUSES).index(preference["focus"]),
                         format_func=FOCUSES.get, key="action_focus")
        goal_id = None
        floor = preference["cash_floor"]
        if focus in ("goals", "cash") and goals:
            ids = [None, *[g["id"] for g in goals]]
            goal_id = st.selectbox("Which goal should come first?", ids,
                                   index=ids.index(preference["goal_id"]) if preference["goal_id"] in ids else 0,
                                   format_func=lambda v: "Use deadline order" if v is None else next(g["name"] for g in goals if g["id"] == v),
                                   key="action_priority_goal")
        if focus == "cash":
            floor = st.number_input("Checking/cash cushion I'd like to keep ($)", min_value=0.0,
                                     value=float(preference["cash_floor"]), format="%.2f", key="action_cash_floor")
        h._caption("Cash shortfalls and growing debt remain first. This changes suggestions, not your recorded finances.")
        if st.button("Save priority", key="action_save_priority"):
            chosen = validate_preference({"focus": focus, "goal_id": goal_id, "cash_floor": floor})
            st.session_state.ml_plan_metadata = {**metadata, "action_preference": chosen}
            st.rerun()


def _open_action(action):
    st.session_state.ml_selected_action = {k: action.get(k) for k in ("id", "kind", "goal_id", "loan_id")}
    st.switch_page("pages/10_Action_Plan.py")


def funding_text(analysis):
    h = _helpers()
    f = analysis["funding"]
    h.prose(f"**Month 1 funding:** {dollars(f['income'])} take-home − {dollars(f['expenses'])} living costs "
            f"− {dollars(f['debt_payments'])} debt payments − {dollars(f['saving'])} funded savings "
            f"= **{dollars(f['remainder_before'])} left** in the current plan.")
    if analysis["goal"]:
        if f["goal_change"] < 0:
            h.prose(f"The proposed goal contribution falls by **{dollars(-f['goal_change'])}/month**. "
                    "The simulation shows how the released room affects other commitments and cash.")
        elif f["goal_increase"] or f["released"]:
            h.prose(f"The proposed goal contribution increases by **{dollars(f['goal_increase'])}/month**. "
                    f"Recorded spending falls by **{dollars(f['released'])}/month**.")
        else:
            h.prose("The monthly goal contribution and recorded spending stay as entered.")
        if f["released"]:
            h.prose(f"The proposed allocation directs **{dollars(f['from_released'])} of that reduction** toward this goal; "
                    f"{dollars(f['released_left'])} is not assigned to it. Other modeled commitments may use that money before it stays in cash.")
        if f["from_remainder"]:
            h.prose(f"A further **{dollars(f['from_remainder'])}/month** needs existing monthly room. "
                    "The simulation below checks whether that crowds out another commitment.")
        if f["fully_funded_months"] < f["months"]:
            st.warning(f"The full requested contribution is funded in {f['fully_funded_months']} of {f['months']} months. "
                       "Use the simulated goal outcome, rather than assuming every requested transfer happens.")
        h.prose(f"First-month goal transfer actually funded: **{dollars(f['first_month_funded'])}**. "
                f"First-month cash remainder with this option: **{dollars(f['remainder_after'])}**.")
    else:
        h.prose(f"First-month cash remainder with the option: **{dollars(f['remainder_after'])}**.")


def render_breakdown(detail):
    h = _helpers()
    h.prose(f"**Finding.** {detail['finding']}")
    h.prose(f"**Why it matters.** {detail['rank_reason']}")
    h.prose(f"**How the model gets there.** {detail['reason']}")
    h.prose(f"**Action to consider.** {detail['proposed_action']}")
    if detail["analysis"]:
        funding_text(detail["analysis"])
    else:
        h.prose("**Funding.** No funding change is assumed. Choose a recorded item to test before increasing a commitment.")
    h.prose(f"**Projected outcome.** {detail['outcome']}")
    if detail["analysis"]:
        st.markdown("**Tradeoffs across your plan**")
        for text in detail["analysis"]["tradeoffs"]:
            h.prose(text)
    st.markdown("**Assumptions and missing information**")
    for text in detail["assumptions"]:
        h.prose(text)


def render_next_actions(blocks, plan, metadata, reviewed):
    h = _helpers()
    first = plan["actions"][0]
    st.subheader("What should I do next?")
    render_priorities(blocks, metadata)
    hero(first["title"], first["finding"], label="YOUR NEXT STEP" if reviewed else "PRELIMINARY ACTION PLAN")
    detail = action_breakdown(blocks, first)
    h._caption(first["rank_reason"])
    a, b = st.columns(2)
    if a.button("View action & alternatives", type="primary", key="action_open_primary"):
        _open_action(first)
    if first["kind"] == "goal" and first["outlook"]["required"] is not None:
        if b.button("Preview this saving pace", key=f"plan_recommend_{first['goal_id']}"):
            h._remember(detail["comparison"])
    with st.expander("How MoneyLab worked this out"):
        render_breakdown(detail)
    if len(plan["actions"]) > 1:
        st.subheader("Also worth a look")
    for action in plan["actions"][1:3]:
        with st.container(border=True):
            h.prose(f"**{action['title']}**")
            h.prose(action["finding"])
            h._caption(action["rank_reason"])
            if st.button("Review this action", key=f"action_open_{action['id']}"):
                _open_action(action)
            # Keep the direct preview for a well-defined, engine-tested pace.
            if action["kind"] == "goal" and action["outlook"]["required"] is not None:
                if st.button("Preview this saving pace", key=f"plan_recommend_{action['goal_id']}"):
                    h._remember(goal_alternative(blocks, action["goal_id"], action["outlook"]["required"]))
    h._caption("Options are alternatives, not a combined budget. After you approve one, MoneyLab recalculates the others.")


def _option_summary(analysis, anchor):
    h = _helpers()
    goal, effects = analysis["goal"], analysis["effects"]
    if goal:
        if goal["completion_after"] is not None:
            timing = add_months(anchor, goal["completion_after"]).strftime("%b %d, %Y")
            h.prose(f"**Projected target date: around {timing}** ({goal['completion_after']} months from the plan date).")
        else:
            h.prose(f"Target not reached within the {effects['searched_months']}-month calculation horizon.")
        h.prose(f"At the proposed deadline, month {goal['deadline_after']}: **{dollars(goal['at_new_deadline'])}** "
                f"toward **{dollars(goal['target_after'])}** · {'target reached in this model' if goal['on_track'] else 'target falls short'}.")
    if effects["shortfall_month"]:
        st.warning(f"This option has an unfunded cash shortfall starting in month {effects['shortfall_month']}.")
    funding_text(analysis)
    with st.expander("What this changes for the rest of my plan", expanded=True):
        for text in analysis["tradeoffs"]:
            h.prose(text)


def _custom_goal(blocks, goal, outlook, draft):
    h = _helpers()
    ident = goal["id"]
    expenses = [b for b in blocks if b["kind"] == "expense"]
    expense_ids = [None, *[b["id"] for b in expenses]]
    expense_id = st.selectbox("Optional: choose a recorded expense to reduce", expense_ids,
                               index=expense_ids.index(draft.get("expense_id")) if draft.get("expense_id") in expense_ids else 0,
                               format_func=lambda v: "Keep spending as entered" if v is None else next(b["name"] for b in expenses if b["id"] == v),
                               key=f"action_expense_{ident}")
    reduction = 0
    if expense_id:
        expense = next(b for b in expenses if b["id"] == expense_id)
        same_expense = draft.get("expense_id") == expense_id
        saved_cut = min(float(draft.get("reduction", 0)), float(expense["monthly_amount"])) if same_expense else 0.0
        reduction = st.number_input("Reduce this expense each month by ($)", min_value=0.0,
                                    max_value=float(expense["monthly_amount"]), value=saved_cut, step=10.0,
                                    format="%.2f", key=f"action_cut_{ident}_{expense_id}")
        saved_redirect = min(float(draft.get("redirect", reduction)), reduction) if same_expense and reduction == draft.get("reduction") else reduction
        redirect = st.number_input("Of that reduction, put toward this goal ($)", min_value=0.0,
                                   max_value=reduction, value=saved_redirect, step=10.0, format="%.2f",
                                   key=f"action_redirect_{ident}_{expense_id}_{reduction}")
        monthly = Decimal(goal["monthly_contribution"]) + Decimal(str(redirect))
        h.prose(f"Proposed goal saving: **{dollars(monthly)}/month**. The remaining **{dollars(Decimal(str(reduction)) - Decimal(str(redirect)))}** "
                "is not assigned to this goal; the engine shows how other commitments and cash use it.")
    else:
        monthly = st.number_input("Try saving each month ($)", min_value=0.0,
                                   value=float(draft.get("monthly", outlook["required"] if outlook["required"] is not None else outlook["planned"])),
                                   step=25.0, format="%.2f", key=f"action_monthly_{ident}")
    a, b = st.columns(2)
    target = a.number_input("Try a savings target ($)", min_value=0.01, value=float(draft.get("target", goal["target"])),
                            step=100.0, format="%.2f", key=f"action_target_{ident}")
    deadline = b.number_input("Try a deadline (months from plan date)", min_value=1, max_value=600,
                              value=draft.get("deadline", goal["target_months"]), key=f"action_deadline_{ident}")
    draft.update(expense_id=expense_id, reduction=reduction, redirect=redirect if expense_id else 0,
                 monthly=str(monthly), target=target, deadline=deadline)
    h._caption("Choose changes you could realistically make. MoneyLab does not assume any expense is optional.")
    if st.button("Inspect my adjustment", type="primary", key=f"action_custom_compare_{ident}"):
        try:
            candidate = goal_alternative(blocks, ident, monthly, expense_id=expense_id, reduction=reduction,
                                         target=target, deadline=deadline)
            candidate["title"] = f"Your adjustment for {goal['name']}"
            h._remember(candidate, origin="pages/10_Action_Plan.py")
        except ValueError as exc:
            st.error(str(exc))


def render_action_details():
    h = _helpers()
    blocks, _, _, months, *_ = h.context()
    metadata = h._metadata()
    plan = action_context(blocks, metadata, h._reviewed(blocks), months)
    selected = st.session_state.get("ml_selected_action", {})
    action = next((a for a in plan["actions"] if a["id"] == selected.get("id")), None)
    if action is None and selected.get("goal_id") in plan["goals"]:
        outlook = plan["goals"][selected["goal_id"]]
        action = {"id": f"goal:{outlook['id']}", "kind": "goal", "goal_id": outlook["id"],
                  "title": f"Review {outlook['name']}", "detail": "Compare a saving pace, date or target using your recorded finances.",
                  "finding": f"Your current plan projects {dollars(outlook['projected'])} by month {outlook['deadline']}.",
                  "outlook": outlook, "rank_reason": "You selected this goal to explore.",
                  "assumptions": ["Figures repeat monthly at entered rates; future results may differ."]}
    if action is None:
        st.info("That action no longer applies to your current figures. Review the recalculated plan.")
        st.page_link("pages/0_Home.py", label="Return to My Plan")
        return
    eyebrow("UNDERSTAND YOUR OPTIONS")
    st.title("What should I do?")
    st.subheader(action["title"])
    h.prose(action["finding"])
    h._caption(action["rank_reason"])
    anchor = model_date(metadata)
    h._caption(f"Projection starts from the recorded plan date: {anchor:%b %d, %Y}.")
    detail = action_breakdown(blocks, action)
    with st.expander("Why this action, and how it is calculated"):
        render_breakdown(detail)
    if not h._reviewed(blocks):
        st.info("Preliminary comparison. Complete and confirm the missing figures in My Finances before approving a change.")
        st.page_link("pages/1_My_Money.py", label="Complete my figures")
    if action["kind"] == "goal":
        goal_id = action["goal_id"]
        options = goal_options(blocks, goal_id)
        keys = [o["key"] for o in options] + ["custom"]
        labels = {o["key"]: o["title"] for o in options} | {"custom": "Try my own adjustment or expense reduction"}
        drafts = st.session_state.setdefault("ml_action_drafts", {})
        if drafts.get(goal_id, {}).get("source_signature") != signature(blocks):
            drafts[goal_id] = {"source_signature": signature(blocks)}
        draft = drafts[goal_id]
        default = keys.index(draft["option"]) if draft.get("option") in keys else keys.index("deadline") if "deadline" in keys else 0
        selected_key = st.radio("Ways to reach this goal", keys, index=default, format_func=labels.get,
                                key=f"action_option_{goal_id}")
        draft["option"] = selected_key
        goal = next(g for g in blocks if g["id"] == goal_id)
        if selected_key == "custom":
            _custom_goal(blocks, goal, action["outlook"], draft)
        else:
            option = next(o for o in options if o["key"] == selected_key)
            _option_summary(option["analysis"], anchor)
            if selected_key == "target":
                st.info("This changes the size of the goal, not how much money you have. Check that a smaller target still serves your purpose.")
            if st.button("Inspect this option", type="primary", key="action_inspect_option"):
                h._remember(option["comparison"], origin="pages/10_Action_Plan.py")
        with st.expander("See the options side by side"):
            rows = []
            for option in options:
                g = option["analysis"]["goal"]
                rows.append({"Option": option["title"], "Saving / month": dollars(option["analysis"]["funding"]["requested"]),
                             "Target": dollars(g["target_after"]), "Deadline (month)": g["deadline_after"],
                             "Target reached": "Yes" if g["on_track"] else "No",
                             "Finish (month)": str(g["completion_after"]) if g["completion_after"] is not None else "Outside horizon"})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    elif detail["comparison"]:
        _option_summary(detail["analysis"], anchor)
        if st.button("Inspect this option", type="primary", key="action_inspect_option"):
            h._remember(detail["comparison"], origin="pages/10_Action_Plan.py")
    else:
        h.prose(detail["proposed_action"])
        h.prose(detail["outcome"])
        st.page_link("pages/3_Explore.py", label="Choose a recorded change to compare")
    st.page_link("pages/0_Home.py", label="Back to My Plan")


def render_stress_test(comparison):
    h = _helpers()
    with st.expander("What if things change?"):
        h.prose("Test the same assumption against your current plan and the chosen option. "
                "This is a temporary stress scenario; it does not change the option you can approve.")
        original = comparison["source_blocks"]
        kinds = ["One-time expense"]
        if any(b["kind"] == "income" for b in original): kinds.insert(0, "Lower income")
        if any(b["kind"] == "expense" for b in original): kinds.insert(0, "Higher recorded expense")
        kind = st.radio("Assumption to test", kinds, key="action_stress_kind")
        if kind == "One-time expense":
            amount = st.number_input("Unexpected one-time cost ($)", min_value=0.0, value=0.0, step=50.0, format="%.2f", key="action_stress_once")
            change = {"operation": "one_time_cash", "amount": str(amount)}
        else:
            options = [b for b in original if b["kind"] == ("income" if kind == "Lower income" else "expense")]
            ident = st.selectbox("Recorded item to stress-test", [b["id"] for b in options],
                                 format_func=lambda v: next(b["name"] for b in options if b["id"] == v), key=f"action_stress_item_{kind}")
            item = next(b for b in options if b["id"] == ident)
            counterpart = next(b for b in comparison["blocks"] if b["id"] == ident)
            # Apply an equal dollar shock to each plan's own recorded amount.
            amount = st.number_input("Monthly change to test ($)", min_value=0.0,
                                      max_value=min(float(item["monthly_amount"]), float(counterpart["monthly_amount"])) if kind == "Lower income" else 1e8,
                                      value=0.0, step=25.0, format="%.2f", key=f"action_stress_delta_{ident}")
            change = {"operation": "adjust_monthly", "block_id": ident,
                      "delta": str(Decimal(str(amount)) if kind == "Higher recorded expense" else -Decimal(str(amount)))}
        marker = json.dumps(change, sort_keys=True)
        if st.button("Run stress test", key="action_run_stress"):
            if amount <= 0:
                st.info("Enter a positive amount to test.")
            else:
                try:
                    st.session_state.ml_stress_result = stress_test(comparison, change)
                    st.session_state.ml_stress_marker = marker
                except ValueError as exc:
                    st.error(str(exc))
        result = st.session_state.get("ml_stress_result")
        if (result and st.session_state.get("ml_stress_marker") == marker and
                result["source_signature"] == comparison["source_signature"] and
                result["candidate_signature"] == comparison["candidate_signature"]):
            st.markdown("**Under your stress assumption**")
            for key, label in (("current", "Current plan under stress"), ("chosen", "Chosen option under stress")):
                outcome = result[key]
                if outcome["projection"] is None:
                    st.warning(f"{label}: checking/cash cannot cover this cost. The upfront gap is {dollars(outcome['upfront_gap'])}. No financing is assumed.")
                else:
                    p = outcome["projection"]
                    h.prose(f"**{label}:** first-month cash remainder {dollars(p['monthly_records'][1]['net_cash_flow'])}.")
                    for goal in p["goals"]:
                        h.prose(f"{goal['name']}: {dollars(goal['projected_at_deadline'])} at month {goal['target_months']} "
                                f"({'target reached' if goal['on_track'] else 'target falls short'}).")
                    gap = next((r for r in p["monthly_records"][1:] if r["unfunded_shortfall"] > 0), None)
                    if gap:
                        st.warning(f"{label}: unfunded cash starts in month {gap['month']}.")
            h._caption("The exact proposed edits and approval below still refer to the unstressed option.")


def render_followthrough(blocks, goal, metadata):
    h = _helpers()
    record = metadata.get("accepted_plan")
    selected = next((g for g in record["blocks"] if g["id"] == goal["id"] and g["kind"] == "goal"), None) if record else None
    if selected is None:
        if st.button("Choose and track this plan", key=f"action_track_{goal['id']}"):
            comparison = preview(blocks, blocks, title=f"Choose the current plan for {goal['name']}")
            comparison["focus_goal_id"] = goal["id"]
            h._remember(comparison)
        return
    start = date.fromisoformat(record["started_on"])
    horizon = max([120, *[g["target_months"] for g in record["blocks"] if g["kind"] == "goal"]])
    projection = project_blocks(record["blocks"], horizon)
    from moneylab.action_plan import first_reached
    completion = first_reached(projection, selected)
    timing = (f"around {add_months(start, completion):%b %d, %Y}" if completion is not None
              else f"outside the {horizon}-month horizon")
    h.prose(f"**Your chosen plan:** {dollars(Decimal(selected['monthly_contribution']))}/month toward "
            f"{dollars(Decimal(selected['target']))}. Projected target date: **{timing}**. "
            f"Chosen deadline: around {add_months(start, selected['target_months']):%b %d, %Y}.")
    due = date.fromisoformat(record.get("due_dates", {}).get(goal["id"], add_months(start, selected["target_months"]).isoformat()))
    last = date.fromisoformat(record["last_as_of"])
    expected_remaining = max(1, remaining_months(last, due))
    if (Decimal(goal["monthly_contribution"]) != Decimal(selected["monthly_contribution"]) or
            Decimal(goal["target"]) != Decimal(selected["target"]) or goal["target_months"] != expected_remaining or
            due != add_months(start, selected["target_months"])):
        st.info("Your recorded pace, target or deadline now differs from this chosen schedule. Explore the goal options to select an updated plan.")
    if date.today() > add_months(start, selected["target_months"]) and Decimal(goal["balance"]) < Decimal(goal["target"]):
        st.warning("The chosen deadline has passed and the last recorded balance is below target. Check in with a current balance before choosing a recovery plan.")
    if last < due and remaining_months(last, due) == 0 and Decimal(goal["balance"]) < Decimal(goal["target"]):
        st.info("Less than one full month remains before the calendar deadline. The one-month projection cannot establish whether that earlier date can be met.")
    h._caption(st.session_state.get("ml_save_status", "Session only · download a backup") + ". Your selected schedule is included in workspace backups.")
    with st.expander(f"Check my progress for {goal['name']}"):
        h._caption("Compare a recorded balance with the schedule you chose. Other figures stay as recorded; update any that changed. "
                   "Only whole future months before each calendar deadline are available; partial months are not modeled. Checking in retains the calendar deadlines.")
        with st.form(f"action_checkin_{goal['id']}"):
            as_of = st.date_input("Balance recorded on", value=max(date.today(), last), min_value=last,
                                 key=f"action_checkin_date_{goal['id']}")
            balance = st.number_input("Recorded goal balance ($)", min_value=0.0, value=float(goal["balance"]),
                                       step=25.0, format="%.2f", key=f"action_checkin_balance_{goal['id']}")
            submit = st.form_submit_button("Compare my progress", type="primary")
        if submit:
            try:
                comparison = progress_preview(blocks, record, goal["id"], balance, as_of)
                comparison["focus_goal_id"] = goal["id"]
                h._remember(comparison)
            except ValueError as exc:
                st.error(str(exc))
