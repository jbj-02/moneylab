"""Quick purchase input and a result that explains the decision."""
from decimal import Decimal

import streamlit as st

from moneylab.decision_feedback import goal_gap_changes, purchase_feedback
from moneylab.ui_app import dollars


def _prose(text):
    st.markdown(text.replace("$", r"\$"))


def render_purchase(blocks, months, metadata):
    from moneylab.plan_ui import _remember, _reviewed

    draft = st.session_state.get("dc_purchase_draft", {})
    recorded_cash = [block for block in blocks if block["kind"] == "cash"]
    quick = not recorded_cash
    preference = metadata.get("action_preference", {})
    default_floor = float(preference.get("cash_floor", 0)) if preference.get("focus") == "cash" else None
    old_cost = st.session_state.get("ml_profile_cost_draft", {})
    default_price = (float(old_cost["cost"]) if old_cost.get("cost_type") == "one_time"
                     else 200.0 if metadata.get("is_example") else None)
    if recorded_cash:
        total = sum(Decimal(b["balance"]) for b in recorded_cash)
        _prose(f"Using **{dollars(total)}** in recorded checking and cash.")
        st.page_link("pages/1_My_Money.py", label="Edit my figures")
    with st.form("dc_purchase", border=False):
        if "dc_cost_value" not in st.session_state:
            guest_price = st.session_state.get("dc_guest_draft", {}).get("dc_guest_cost")
            st.session_state.dc_cost_value = draft.get("price", default_price if default_price is not None else guest_price)
        price = st.number_input("Cost amount ($)", min_value=0.0, max_value=1e8,
                                step=25.0, format="%.2f", key="dc_cost_value",
                                help="Include taxes and fees.")
        checking = st.number_input(
            "Available checking and cash ($)", min_value=0.0, max_value=1e8,
            value=draft.get("checking", st.session_state.get("dc_guest_checking",
                st.session_state.get("dc_guest_draft", {}).get("dc_guest_checking"))), step=25.0, key="dc_purchase_checking",
            help="Exclude money already set aside for goals.",
        ) if quick else None
        floor = st.number_input("Minimum cash to keep ($)", min_value=0.0, max_value=1e8,
                                value=draft.get("floor", default_floor), step=25.0, format="%.2f",
                                key="dc_purchase_floor", placeholder="Optional")
        submitted = st.form_submit_button("Compare with my current plan", type="primary")
    if submitted:
        st.session_state.pop("ml_plan_preview", None)
        st.session_state.dc_purchase_draft = {"price": price, "checking": checking, "floor": floor}
        st.session_state.pop("dc_purchase_result", None)
        if price is None or (quick and checking is None):
            st.error("Enter the purchase price and available checking or cash.")
            return
        source = blocks if not quick else [
            {"id": "quick_cash", "kind": "cash", "name": "Checking and cash", "balance": str(checking)},
        ]
        try:
            facts = purchase_feedback(source, price, floor, months=months)
        except ValueError as exc:
            st.error(str(exc))
            return
        if quick or facts["comparison"] is None:
            st.session_state.dc_purchase_result = {"source": blocks, "facts": facts}
        if quick:
            st.session_state.dc_guest_draft = {"dc_guest_cost": price, "dc_guest_checking": checking,
                                               "dc_guest_cost_kind": "one_time", "dc_guest_frequency": "monthly"}
            st.session_state.dc_guest_compared = True
            st.session_state.dc_profile_source = "Enter a temporary snapshot"
            st.session_state.pop("ml_profile_cost_draft", None)
            st.session_state.dc_profile_compared = False
        else:
            st.session_state.ml_profile_cost_draft = {
                "cost": str(price), "cost_type": "one_time", "frequency": "monthly",
            }
            st.session_state.dc_profile_compared = True
            st.session_state.dc_profile_source = "Use My Money figures"
            if facts["comparison"] is not None:
                _remember(facts["comparison"], origin="pages/3_Explore.py", decision=facts)
    saved = st.session_state.get("dc_purchase_result")
    if not saved or saved["source"] != blocks:
        return
    facts = saved["facts"]
    render_purchase_answer(facts, preliminary=quick or not _reviewed(blocks), quick=quick)
    if quick:
        with st.expander("See the breakdown"):
            _prose(f"Entered cash {dollars(facts['checking'])} less price {dollars(facts['price'])}. "
                   "Add your finances to include bills and goals.")
            st.page_link("pages/5_Quick_Start.py", label="Add my finances")


def render_purchase_answer(facts, *, preliminary, quick=False):
    comparison = facts["comparison"]
    floor = facts["floor"]
    after = facts["after"]
    st.subheader("What this purchase changes")
    if comparison is None:
        _prose(f"**You’re {dollars(-after)} short of paying in cash today.** "
               f"The price is {dollars(facts['price'])} and you have {dollars(facts['checking'])} in checking and cash.")
    else:
        _prose(f"**Buying now leaves {dollars(after)} in checking and cash.**")
    if preliminary:
        st.caption("Cash-only estimate. Bills, income and goals are outside this estimate." if quick else
                   "Preliminary estimate. Unconfirmed balances or upcoming bills could change this result.")
    if floor is None and comparison is None and facts["checking"] > 0:
        _prose(f"**Next step:** Try a price below {dollars(facts['checking'])}, or wait until you have more cash. "
               "Set a cash cushion to see how much of that balance you want to keep.")
    elif floor is None and comparison is None:
        _prose("**Next step:** Wait until you have available cash and enter the minimum you want to keep.")
    elif floor is None:
        _prose("**Next step:** Enter the minimum cash you want to keep to see how much room this purchase leaves.")
    elif after < floor:
        _prose(f"Buying now would leave **{dollars(floor - after)} below your {dollars(floor)} cushion**.")
        if facts["limit"]:
            _prose(f"**Try a lower price.** You can spend up to {dollars(facts['limit'])} today "
                   "and keep your cushion, based on recorded cash.")
        else:
            _prose("**Wait to build your cash cushion.** There’s no room for this purchase above your cushion today.")
        if facts["wait_month"] and not quick and not preliminary:
            _prose(f"**Or revisit in {facts['wait_month']} month(s).** Projected cash would cover this price "
                   "and your cushion then, if your recorded plan holds.")
    elif facts["future_shortfall"]:
        _prose(f"**Try a lower price or wait.** This purchase adds to an unpaid cost in month "
               f"{facts['future_shortfall']} of the projection.")
    else:
        margin = after - floor
        takeaway = f"This keeps {dollars(margin)} above your cushion today." if margin else "This leaves exactly your chosen cushion today."
        _prose(f"**{takeaway}** Check upcoming bills before committing.")
    if (floor is None or after < floor) and facts["future_shortfall"]:
        _prose(f"The purchase also adds to an unpaid cost in month {facts['future_shortfall']}. Try a lower price or wait.")
    if comparison and not quick:
        changes = sorted(goal_gap_changes(comparison["baseline"], comparison["alternative"]),
                         key=lambda goal: (goal[2] == goal[3], goal[1]))
        visible = [goal for goal in changes if goal[2] or goal[3]][:2]
        for name, deadline, before, after_gap in visible:
            if after_gap == before and before:
                _prose(f"**{name}:** The {dollars(before)} gap at month {deadline} was already there. This purchase leaves it unchanged.")
            elif after_gap != before:
                _prose(f"**{name}:** The projected gap at month {deadline} changes from {dollars(before)} to {dollars(after_gap)}.")
