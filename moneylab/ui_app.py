"""Streamlit presentation layer for MoneyLab.

The financial engine is independent of these pages. All state is session-only,
and every status/goal/what-if value comes from validated model results.
"""

from datetime import date
from decimal import Decimal
from io import StringIO
from uuid import uuid4
import csv

import pandas as pd
import streamlit as st

from moneylab.blocks import (
    ACCOUNT_TYPES, ASSET_KINDS, BLOCK_KINDS, default_blocks, modify_expense,
    profile_from_json, profile_to_json, project_blocks, serialize_blocks,
)
from moneylab.cadence import FREQUENCIES, monthly_equivalent, upcoming_events
from moneylab.checkin import build_checkin
from moneylab.insights import scenario_impacts
from moneylab.learning import LESSONS, check_answer, recommended_lesson_ids
from moneylab.presets import PRESET_CATALOG, preset_block
from moneylab.workspace import validated_scenarios, workspace_from_json, workspace_to_json

def dollars(value):
    """USD metric label."""
    return f"${value:,.2f}" if value >= 0 else f"-${abs(value):,.2f}"


def money_field(label, key, initial=0):
    return st.number_input(
        label, key=key, min_value=0.0, value=float(initial),
        step=25.0, format="%.2f",
    )


def fields_for(kind, prefix, initial=None, frequency=None):
    """Render fields for exactly one block type, ready for validation."""
    item = initial or {}
    data = {}
    if kind in ("income", "expense"):
        frequency = frequency or item.get("frequency", "monthly")
        source_amount = (
            item.get("period_amount", item.get("monthly_amount", 0))
            if item.get("frequency", "monthly") == frequency
            else 0
        )
        period_amount = money_field(
            f"Amount each {FREQUENCIES[frequency][0].lower()} period ($)",
            f"{prefix}_{frequency}_period_amount", source_amount,
        )
        data["monthly_amount"] = str(monthly_equivalent(period_amount, frequency))
        if frequency != "monthly":
            data["frequency"] = frequency
            data["period_amount"] = period_amount
        if st.checkbox(
            "Add a next payday / due date",
            key=f"{prefix}_track_date",
            value=bool(item.get("next_date")),
        ):
            event_date = st.date_input(
                "Next scheduled occurrence",
                value=date.fromisoformat(item.get("next_date", date.today().isoformat())),
                key=f"{prefix}_event_date",
            )
            data["next_date"] = event_date.isoformat()
        st.caption(
            "Projected monthly equivalent: "
            f"{dollars(monthly_equivalent(period_amount, frequency))}. "
            "Cash-flow projections use averages; dates do not yet change "
            "the month-by-month financial simulation."
        )
    if kind in ("loan", "cash", *ASSET_KINDS):
        data["balance"] = money_field(
            "Current balance ($)", f"{prefix}_balance",
            item.get("balance", 0),
        )
    if kind == "loan":
        data["annual_rate"] = st.number_input(
            "Annual loan interest (%)", key=f"{prefix}_annual_rate",
            min_value=0.0, max_value=100.0, step=0.1,
            value=float(item.get("annual_rate", 0)), format="%.3f",
        )
        data["monthly_payment"] = money_field(
            "Required monthly payment ($)", f"{prefix}_monthly_payment",
            item.get("monthly_payment", 0),
        )
    if kind in ASSET_KINDS:
        data["annual_rate"] = st.number_input(
            "Illustrative annual growth / yield (%)",
            key=f"{prefix}_annual_rate", min_value=0.0, max_value=100.0,
            step=0.1, value=float(item.get("annual_rate", 0)),
            format="%.3f",
            help="A scenario assumption, not a guaranteed return or a quoted rate.",
        )
        data["monthly_contribution"] = money_field(
            "Planned monthly contribution ($)", f"{prefix}_monthly_contribution",
            item.get("monthly_contribution", 0),
        )
    if kind == "account":
        options = list(ACCOUNT_TYPES)
        data["account_type"] = st.selectbox(
            "Account type", options=options,
            index=options.index(item.get("account_type", "savings")),
            format_func=lambda x: ACCOUNT_TYPES[x],
            key=f"{prefix}_account_type",
        )
    if kind == "goal":
        data["target"] = money_field(
            "Savings target ($)", f"{prefix}_target",
            item.get("target", 1000),
        )
        data["target_months"] = st.number_input(
            "Months until goal", key=f"{prefix}_target_months",
            min_value=1, max_value=600, step=1,
            value=int(item.get("target_months", 12)),
        )
    return data


def as_chart(projection):
    return pd.DataFrame(
        {
            "Month": entry["month"],
            "Checking / cash": float(entry["cash_savings"]),
            "Other assets": float(entry["other_assets"]),
            "Loan balances": float(entry["loan_balance"]),
            "Modeled net position": float(entry["net_position"]),
        }
        for entry in projection["monthly_records"]
    ).set_index("Month")


def as_csv(projection):
    fields = (
        "month", "income", "living_expenses", "loan_payments",
        "asset_contributions", "asset_yield", "net_cash_flow",
        "cash_savings", "unfunded_shortfall", "other_assets",
        "loan_balance", "net_position",
    )
    result = StringIO()
    writer = csv.DictWriter(result, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in projection["monthly_records"]:
        writer.writerow({field: str(row[field]) for field in fields})
    return result.getvalue()



def context():
    """Calculate a fresh view on each page rerun; never cache session finances."""
    if "ml_blocks" not in st.session_state:
        st.session_state.ml_blocks = []
    if "ml_saved_scenarios" not in st.session_state:
        st.session_state.ml_saved_scenarios = []
    months = st.session_state.get("ml_months", 24)
    try:
        blocks = serialize_blocks(st.session_state.ml_blocks)
        result = project_blocks(blocks, months)
    except ValueError as exc:
        st.error(f"Your financial profile needs attention: {exc}")
        st.stop()
    summary = result["summary"]
    try:
        saved_scenarios = validated_scenarios(
            blocks, st.session_state.ml_saved_scenarios
        )
    except ValueError:
        saved_scenarios = []
        st.session_state.ml_saved_scenarios = []
        st.warning("Saved scenarios with outdated financial inputs were cleared.")
    signature = profile_to_json(blocks)
    reviewed = st.session_state.get("ml_reviewed_signature") == signature
    checkin = build_checkin(blocks, result, reviewed=reviewed)
    return blocks, result, summary, months, saved_scenarios, checkin, signature


def show_checkin_status(checkin):
    message = f"**{checkin['heading']}** — {checkin['explanation']}"
    if checkin["status"] == "needs_attention":
        st.warning(message)
    elif checkin["status"] == "on_track":
        st.success(message)
    else:
        st.info(message)


def add_from_preset(name, blocks):
    """Starter values are editable immediately, rather than auto-saved."""
    seed = PRESET_CATALOG[name]
    edit_block_form("add", seed=seed, preferred_kind=seed["kind"],
                    form_identity=f"preset_{name}")


@st.dialog("Build your financial profile", width="large")
def add_block_dialog(preferred_kind=None, preset=None):
    st.caption("Create one building block. Everything is editable later.")
    if preset:
        seed = PRESET_CATALOG[preset]
        preferred_kind = seed["kind"]
        st.write(f"Starting with **{seed['name']}**. Replace the example amounts.")
    else:
        seed = None
    edit_block_form("add", seed=seed, preferred_kind=preferred_kind,
                    form_identity=f"add_{preset or preferred_kind or 'custom'}")


@st.dialog("Edit financial block", width="large")
def edit_block_dialog(block_id):
    blocks, *_ = context()
    selected = next((item for item in blocks if item["id"] == block_id), None)
    if selected is None:
        st.error("This block was removed. Refresh your workspace.")
        return
    edit_block_form("edit", seed=selected, preferred_kind=selected["kind"],
                    form_identity=f"edit_{block_id}")


def edit_block_form(action, *, seed=None, preferred_kind=None, form_identity="edit"):
    blocks, *_ = context()
    if action == "add" and preferred_kind is None:
        kind = st.selectbox(
            "What are you adding?", list(BLOCK_KINDS),
            format_func=lambda item: BLOCK_KINDS[item],
            key=f"{form_identity}_kind",
        )
    else:
        kind = preferred_kind
        st.caption(BLOCK_KINDS[kind])
    source = seed or {}
    frequency = None
    if kind in ("income", "expense"):
        frequency = st.selectbox(
            "How often does this happen?", list(FREQUENCIES),
            index=list(FREQUENCIES).index(source.get("frequency", "monthly")),
            format_func=lambda item: FREQUENCIES[item][0],
            key=f"{form_identity}_frequency",
        )
    with st.form(f"{form_identity}_form"):
        name = st.text_input(
            "Name", value=source.get("name", ""),
            placeholder="e.g. Paycheck, apartment rent, emergency fund",
        )
        fields = fields_for(kind, form_identity, source, frequency=frequency)
        submitted = st.form_submit_button(
            "Save changes" if action == "edit" else "Add to my money",
            type="primary", use_container_width=True,
        )
    if submitted:
        data = {
            "id": source["id"] if action == "edit" else uuid4().hex[:12],
            "kind": kind, "name": name, **fields,
        }
        if action == "edit" and kind == "income" and "routes" in source:
            data["routes"] = source["routes"]
        revised = [
            data if item["id"] == data["id"] else item for item in blocks
        ] if action == "edit" else [*blocks, data]
        try:
            st.session_state.ml_blocks = serialize_blocks(revised)
            st.rerun()
        except ValueError as exc:
            st.error(f"Please check these values: {exc}")


def remove_block(block_id):
    blocks, *_ = context()
    remaining = [item for item in blocks if item["id"] != block_id]
    for item in remaining:
        if item["kind"] == "income" and "routes" in item:
            item["routes"] = [
                r for r in item["routes"] if r["destination_id"] != block_id
            ]
    st.session_state.ml_blocks = serialize_blocks(remaining)
    st.rerun()


def shift_block(block_id, direction):
    blocks, *_ = context()
    pos = next(i for i, item in enumerate(blocks) if item["id"] == block_id)
    target = pos + direction
    if 0 <= target < len(blocks):
        blocks[pos], blocks[target] = blocks[target], blocks[pos]
        st.session_state.ml_blocks = blocks
        st.rerun()


def block_amount(block):
    kind = block["kind"]
    if kind in ("income", "expense"):
        frequency = block.get("frequency", "monthly")
        return (
            dollars(Decimal(block.get("period_amount", block["monthly_amount"]))),
            f"{FREQUENCIES[frequency][0]} · "
            f"{dollars(Decimal(block['monthly_amount']))}/month average",
        )
    if kind == "loan":
        return dollars(Decimal(block["balance"])), (
            f"Owed · {dollars(Decimal(block['monthly_payment']))}/month"
        )
    if kind == "goal":
        return dollars(Decimal(block["balance"])), (
            f"Saved toward {dollars(Decimal(block['target']))} · "
            f"Month {block['target_months']} target"
        )
    label = ACCOUNT_TYPES.get(block.get("account_type"), BLOCK_KINDS[kind])
    return dollars(Decimal(block["balance"])), label


def block_card(block, index, total):
    amount, detail = block_amount(block)
    with st.container(border=True):
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        with c1:
            st.markdown(f"**{block['name']}**")
            st.markdown(f"### {amount}")
            st.caption(detail)
        with c2:
            if st.button("Edit", key=f"edit_card_{block['id']}",
                         use_container_width=True):
                edit_block_dialog(block["id"])
        with st.popover("More options", use_container_width=False):
            l, r = st.columns(2)
            if l.button("Move up", key=f"up_{block['id']}", disabled=index == 0):
                shift_block(block["id"], -1)
            if r.button("Move down", key=f"down_{block['id']}",
                        disabled=index == total - 1):
                shift_block(block["id"], 1)
            confirm = st.checkbox(
                f"Confirm removal of {block['name']}",
                key=f"confirm_delete_{block['id']}",
            )
            if st.button("Remove block", key=f"remove_{block['id']}",
                         disabled=not confirm):
                remove_block(block["id"])


def render_home():
    blocks, result, summary, months, _, checkin, _ = context()
    st.title("Your financial home")
    st.caption("Understand your money. Enjoy your life.")

    if not blocks:
        st.markdown(
            "### Your money journey starts here"
        )
        st.write(
            "You don't need to know everything about personal finance to "
            "get started. Choose a situation, add one building block, and "
            "learn as you go."
        )
        situations = {
            "I just got paid": "takehome",
            "I'm thinking of moving": "rent",
            "I want to start saving": "hysa",
            "I have student loans": "student",
            "I want to start investing": "roth",
            "I want to organize my finances": "checking",
        }
        choice = st.selectbox(
            "What brings you here?", list(situations),
            key="ml_first_situation",
        )
        if st.button("Start with this", type="primary"):
            add_block_dialog(preset=situations[choice])
        st.caption(
            "Suggested examples are fictional and fully editable. "
            "Your information is not automatically saved to an account."
        )
        return

    st.markdown("#### Your check-in")
    show_checkin_status(checkin)
    if checkin["attention"]:
        st.write(f"**Most important thing to review:** {checkin['attention'][0]}")
    elif checkin["missing"]:
        st.write(f"**Next step:** {checkin['missing'][0]}")
    elif not checkin["reviewed"]:
        st.write("**Next step:** Review your figures to see what the model can tell you.")
    else:
        st.write("**Next step:** Keep your plan current as your life changes.")

    a, b, c = st.columns(3)
    a.metric("Monthly take-home", dollars(summary["monthly_income"]))
    committed = summary["monthly_expenses"] + summary["first_month_loan_payments"]
    b.metric("Recorded monthly obligations", dollars(committed))
    c.metric(
        "Additional monthly flexibility",
        dollars(summary["unallocated_monthly_buffer"])
        if checkin["status"] == "on_track" else "Review needed",
    )
    st.caption(
        "Figures reflect manual entries. Spending flexibility is an estimate "
        "after recorded costs and affordable planned transfers, not verified bank money."
    )

    st.markdown("#### Your next step")
    if st.button("Review or update my finances", key="home_review", type="primary"):
        st.session_state.ml_expand_review = True
    if st.button("Add another building block", key="home_add_block"):
        add_block_dialog()
    if result["goals"]:
        st.markdown("#### Your goals")
        for goal in result["goals"][:3]:
            with st.container(border=True):
                st.markdown(f"**{goal['name']}**")
                starting = goal["starting_balance"]
                progress = min(float(starting / goal["target"]), 1.0)
                st.progress(max(0.0, progress))
                st.caption(
                    f"{dollars(starting)} saved / {dollars(goal['target'])} target. "
                    "Open Goals to view the projected timeline."
                )

    with st.expander(
        "Update your finances and upcoming dates",
        expanded=st.session_state.get("ml_expand_review", False),
    ):
        render_quick_review(blocks, result, summary, checkin)

    with st.expander("Explore your detailed financial projection"):
        st.line_chart(as_chart(result), height=320)
        st.caption(
            "Projection assumes your recorded monthly averages and hypothetical "
            "account rates stay constant. Timing of individual bills is not modeled."
        )
        if any(row["negative_amortization"] for row in result["monthly_records"][1:]):
            st.warning("One or more loans grows because payments do not cover interest.")


def render_quick_review(blocks, result, summary, checkin):
    st.markdown("#### Update a balance or recurring expense")
    options = [item for item in blocks if item["kind"] in ("cash", "expense")]
    if options:
        selected = st.selectbox(
            "Choose what changed", [item["id"] for item in options],
            format_func=lambda k: next(i["name"] for i in options if i["id"] == k),
            key="ml_quick_update_select",
        )
        block = next(i for i in options if i["id"] == selected)
        old_value = (
            block["balance"] if block["kind"] == "cash"
            else block.get("period_amount", block["monthly_amount"])
        )
        frequency = block.get("frequency", "monthly")
        with st.form(f"quick_update_{selected}"):
            amount = st.number_input(
                "New balance ($)" if block["kind"] == "cash" else
                f"New {FREQUENCIES[frequency][0].lower()} expense ($)",
                value=float(old_value), min_value=0.0, step=10.0, format="%.2f",
            )
            submitted = st.form_submit_button("Save this update")
        if submitted:
            revised = []
            for item in blocks:
                if item["id"] != selected:
                    revised.append(item)
                    continue
                updated = dict(item)
                if item["kind"] == "cash":
                    updated["balance"] = amount
                else:
                    updated["monthly_amount"] = str(
                        monthly_equivalent(amount, frequency)
                    )
                    if "frequency" in updated:
                        updated["period_amount"] = amount
                revised.append(updated)
            try:
                st.session_state.ml_blocks = serialize_blocks(revised)
                st.session_state.ml_last_manual_update = date.today().isoformat()
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    else:
        st.caption("Add a checking account or expense to enable quick updates.")

    st.markdown("#### Confirm your financial picture")
    if checkin["missing"]:
        for note in checkin["missing"]:
            st.write(f"• {note}")
    if st.button("I've reviewed my entered financial information",
                 key="ml_review_home"):
        st.session_state.ml_reviewed_signature = profile_to_json(blocks)
        st.rerun()
    st.caption(
        "You are confirming your entries, not verifying transactions or account balances. "
        "Changes to blocks require another review."
    )

    dates = upcoming_events(blocks, from_date=date.today(), days=45)
    st.markdown("#### Upcoming dates you've entered")
    if dates:
        st.dataframe(pd.DataFrame([
            {"Date": item["date"],
             "Type": "Payday" if item["kind"] == "income" else "Bill",
             "Description": item["name"], "Amount ($)": float(item["amount"])}
            for item in dates
        ]), hide_index=True, use_container_width=True)
    else:
        st.caption(
            "Add a due date to an income or expense block to display upcoming events."
        )
    st.caption(
        "These are reminders of entered dates, not a dated account-balance forecast."
    )

def render_my_money():
    blocks, result, summary, months, _, checkin, _ = context()
    st.title("My Money")
    st.caption("Build a picture of your finances, one block at a time.")
    top, other = st.columns([3, 1], vertical_alignment="center")
    with top:
        st.write(f"**{len(blocks)} building blocks** in your profile")
    with other:
        if st.button("＋ Add a block", type="primary", use_container_width=True):
            add_block_dialog()

    if not blocks:
        st.info(
            "Nothing here yet. Choose **Add a block** to start with an income, "
            "expense, account, debt or savings goal."
        )
    else:
        groups = {
            "Income": ("income",),
            "Everyday spending": ("expense",),
            "Accounts & savings": ("cash", "hysa", "roth_ira", "account"),
            "Loans & debt": ("loan",),
            "Savings goals": ("goal",),
        }
        all_ids = [b["id"] for b in blocks]
        for group_name, kinds in groups.items():
            members = [b for b in blocks if b["kind"] in kinds]
            if not members:
                continue
            st.markdown(f"#### {group_name}")
            for block in members:
                block_card(block, all_ids.index(block["id"]), len(blocks))

    st.markdown("#### Add something common")
    shortcuts = [
        ("Paycheck", "takehome"),
        ("Rent", "rent"),
        ("Checking", "checking"),
        ("HYSA", "hysa"),
        ("Emergency goal", "emergency"),
        ("Student loan", "student"),
    ]
    columns = st.columns(3)
    for index, (label, preset) in enumerate(shortcuts):
        with columns[index % 3]:
            if st.button(f"＋ {label}", key=f"shortcut_{preset}",
                         use_container_width=True):
                add_block_dialog(preset=preset)

    incomes = [b for b in blocks if b["kind"] == "income"]
    destinations = [
        b for b in blocks if b["kind"] == "cash" or b["kind"] in ASSET_KINDS
    ]
    if incomes and destinations:
        with st.expander("Advanced · Route take-home income into accounts"):
            st.subheader("Where does each paycheck go?")
            st.caption(
                "Route take-home income to named accounts by dollars or percent. "
                "The unallocated remainder stays in modeled checking/cash. "
                "Routes to savings accounts are direct deposits, not new income "
                "or additional expenses. Enter **net** income here—pretax employer "
                "retirement withholding is not modeled."
            )
            income_sources = [item for item in blocks if item["kind"] == "income"]
            destinations = [item for item in blocks
                            if item["kind"] == "cash" or item["kind"] in ASSET_KINDS]
            if income_sources and destinations:
                income_id = st.selectbox(
                    "Choose an income source",
                    options=[item["id"] for item in income_sources],
                    format_func=lambda ident: next(
                        item["name"] for item in income_sources if item["id"] == ident
                    ),
                    key="ml_route_income",
                )
                income_block = next(item for item in income_sources if item["id"] == income_id)
                current_routes = income_block.get("routes", [])
                if current_routes:
                    for route in current_routes:
                        target = next(item["name"] for item in destinations
                                      if item["id"] == route["destination_id"])
                        suffix = "%" if route["mode"] == "percent" else " dollars"
                        st.write(f"• {target}: {route['value']}{suffix} of monthly pay")
                else:
                    st.info("No allocations yet. All take-home pay currently flows to modeled cash.")

                with st.form("ml_route_editor"):
                    dest = st.selectbox(
                        "Destination account", [item["id"] for item in destinations],
                        format_func=lambda ident: next(
                            item["name"] for item in destinations if item["id"] == ident
                        ),
                    )
                    mode = st.radio(
                        "Allocation method", ["fixed", "percent"],
                        format_func=lambda name: "Dollars ($)" if name == "fixed" else "Percent (%)",
                        horizontal=True,
                    )
                    amount = st.number_input(
                        "Monthly allocation amount",
                        min_value=0.0,
                        max_value=100.0 if mode == "percent" else 100000000.0,
                        value=10.0 if mode == "percent" else 100.0,
                        step=1.0 if mode == "percent" else 25.0,
                        format="%.2f",
                    )
                    save_route = st.form_submit_button("Add / update income route")
                if save_route:
                    updated = []
                    for item in blocks:
                        if item["id"] == income_id:
                            new_routes = [
                                route for route in item.get("routes", [])
                                if route["destination_id"] != dest
                            ]
                            new_routes.append({
                                "destination_id": dest, "mode": mode, "value": amount,
                            })
                            updated.append({**item, "routes": new_routes})
                        else:
                            updated.append(item)
                    try:
                        st.session_state.ml_blocks = serialize_blocks(updated)
                        st.rerun()
                    except ValueError as exc:
                        st.error(f"Cannot allocate income: {exc}")

                if current_routes:
                    remove_route_id = st.selectbox(
                        "Remove an existing income route",
                        options=[route["destination_id"] for route in current_routes],
                        format_func=lambda ident: next(
                            item["name"] for item in destinations if item["id"] == ident
                        ),
                        key="ml_remove_route_id",
                    )
                    if st.button("Remove income route"):
                        revised = [
                            {**item, "routes": [
                                route for route in item.get("routes", [])
                                if route["destination_id"] != remove_route_id
                            ]} if item["id"] == income_id else item
                            for item in blocks
                        ]
                        st.session_state.ml_blocks = serialize_blocks(revised)
                        st.rerun()
            else:
                st.info("Add an income block and a checking/savings/investment block to enable routing.")


    elif incomes:
        st.caption("Add a checking or savings account to enable paycheck routing.")

def render_goals():
    blocks, result, summary, months, _, _, _ = context()
    st.title("Your goals")
    st.caption("Turn something you want into a plan you can follow.")
    if st.button("＋ Add a savings goal", type="primary"):
        add_block_dialog(preferred_kind="goal")

    goal_blocks = [item for item in blocks if item["kind"] == "goal"]
    if not goal_blocks:
        st.info(
            "No savings goals yet. Start with an emergency fund, moving costs, "
            "a vacation, or a goal of your own."
        )
        if st.button("Start an emergency fund", key="goal_start_emergency"):
            add_block_dialog(preset="emergency")
        return

    projection_horizon = max([months] + [item["target_months"] for item in goal_blocks])
    deadline_projection = project_blocks(blocks, projection_horizon)
    forecasts = {goal["id"]: goal for goal in deadline_projection["goals"]}
    for goal in goal_blocks:
        saved = Decimal(goal["balance"])
        target = Decimal(goal["target"])
        outcome = forecasts[goal["id"]]
        with st.container(border=True):
            name, action = st.columns([4, 1], vertical_alignment="center")
            with name:
                st.markdown(f"### {goal['name']}")
                st.caption(f"Target: {dollars(target)} · In {goal['target_months']} months")
            with action:
                if st.button("Edit goal", key=f"goal_edit_{goal['id']}"):
                    edit_block_dialog(goal["id"])
            st.progress(min(1.0, max(0.0, float(saved / target))))
            st.caption(
                f"{dollars(saved)} saved now · {dollars(Decimal(goal['monthly_contribution']))} "
                "planned per month"
            )
            projected = outcome["projected_at_deadline"]
            if projected is None:
                st.info("The selected horizon does not reach this goal's deadline.")
            elif outcome["on_track"]:
                st.success(
                    f"On track in this scenario: {dollars(projected)} "
                    "projected at the deadline."
                )
            else:
                st.warning(
                    f"Projected {dollars(projected)} at the deadline — "
                    f"{dollars(outcome['gap_at_deadline'])} below your target."
                )
                if goal["target_months"] > 0:
                    required = (
                        max(target - saved, Decimal("0.00"))
                        / Decimal(goal["target_months"])
                    ).quantize(Decimal("0.01"))
                    st.caption(
                        f"For orientation only: without growth, the difference "
                        f"between the target and current balance averages "
                        f"about {dollars(required)} per month. "
                        "Available income may limit contributions."
                    )
    with st.expander("How MoneyLab projects goals"):
        st.write(
            "Each goal block represents a separately earmarked account. "
            "The model projects planned transfers only from affordable monthly "
            "surplus; hypothetical growth is not guaranteed. "
            "The goal screen projects through each entered deadline, "
            "even when your dashboard chart uses a shorter horizon."
        )

def render_explore():
    blocks, result, summary, months, saved_scenarios, _, _ = context()
    st.title("Explore a decision")
    st.caption("See what changes before you make a real-world commitment.")
    expenses = [item for item in blocks if item["kind"] == "expense"]
    if not expenses:
        st.info("Add a recurring expense under My Money to start exploring decisions.")
        return
    st.markdown("### Try a different monthly expense")
    ident = st.selectbox(
        "Which expense might change?",
        options=[item["id"] for item in expenses],
        format_func=lambda key: next(b["name"] for b in expenses if b["id"] == key),
        key="explore_expense_id",
    )
    chosen = next(x for x in expenses if x["id"] == ident)
    delta = st.number_input(
        "How much more or less would it cost per month? ($)",
        min_value=-float(Decimal(chosen["monthly_amount"])),
        max_value=10000.0,
        value=100.0, step=25.0, format="%.2f",
        key="explore_monthly_change",
    )
    try:
        changed = modify_expense(blocks, ident, delta)
        alternative = project_blocks(changed, months)
        impacts = scenario_impacts(result, alternative, blocks)
    except ValueError as exc:
        st.error(f"Unable to calculate that scenario: {exc}")
        return
    st.markdown("### What would be different?")
    a, b, c = st.columns(3)
    a.metric(
        "Monthly flexibility",
        dollars(alternative["summary"]["unallocated_monthly_buffer"]),
        delta=dollars(
            alternative["summary"]["unallocated_monthly_buffer"]
            - summary["unallocated_monthly_buffer"]
        ),
        delta_color="normal",
    )
    b.metric(
        "Cash after projection",
        dollars(alternative["summary"]["ending_cash_savings"]),
        delta=dollars(
            alternative["summary"]["ending_cash_savings"]
            - summary["ending_cash_savings"]
        ),
    )
    c.metric(
        f"Net position at month {months}",
        dollars(alternative["summary"]["ending_net_position"]),
        delta=dollars(
            alternative["summary"]["ending_net_position"]
            - summary["ending_net_position"]
        ),
    )
    st.caption(
        "All figures compare this one expense change with your baseline. "
        "Other assumptions remain unchanged."
    )

    st.markdown("#### The most important effects")
    for notice in impacts[:3]:
        message = f"**{notice['title']}** — {notice['detail']}"
        if notice["level"] == "warning":
            st.warning(message)
        elif notice["level"] == "positive":
            st.success(message)
        else:
            st.info(message)
    if len(impacts) > 3:
        with st.expander(f"See all {len(impacts)} calculated effects"):
            for notice in impacts[3:]:
                st.write(f"**{notice['title']}** — {notice['detail']}")
    with st.expander("Compare full projections"):
        st.line_chart(pd.DataFrame({
            "Month": [r["month"] for r in result["monthly_records"]],
            "Current plan": [float(r["net_position"]) for r in result["monthly_records"]],
            "What-if plan": [float(r["net_position"]) for r in alternative["monthly_records"]],
        }).set_index("Month"), height=330)

    st.markdown("#### Save this decision")
    saved_name = st.text_input(
        "Name this scenario", value=f"{chosen['name']} change",
        max_chars=60,
        key="explore_scenario_name",
    )
    if st.button("Save scenario", key="explore_save_scenario"):
        item = {
            "name": saved_name, "expense_id": ident,
            "monthly_change": str(Decimal(str(delta))),
        }
        revised = [s for s in saved_scenarios if s["name"] != saved_name] + [item]
        try:
            st.session_state.ml_saved_scenarios = validated_scenarios(blocks, revised)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    with st.expander(f"Saved scenarios ({len(saved_scenarios)})"):
        if not saved_scenarios:
            st.caption("You haven't saved a comparison yet.")
        else:
            selected = st.selectbox(
                "Saved decision",
                options=[s["name"] for s in saved_scenarios],
                key="explore_pick_saved",
            )
            entry = next(s for s in saved_scenarios if s["name"] == selected)
            try:
                saved_projection = project_blocks(modify_expense(
                    blocks, entry["expense_id"], entry["monthly_change"],
                ), months)
                difference = (
                    saved_projection["summary"]["ending_net_position"]
                    - summary["ending_net_position"]
                )
                st.metric("Modeled net-position change", dollars(difference))
                st.caption(
                    f"Monthly adjustment: {dollars(Decimal(entry['monthly_change']))}"
                )
            except ValueError as exc:
                st.warning(f"Saved scenario unavailable: {exc}")
            if st.button("Delete this saved scenario"):
                st.session_state.ml_saved_scenarios = [
                    s for s in saved_scenarios if s["name"] != selected
                ]
                st.rerun()
    st.caption(
        "What-if projections are educational estimates. Save a workspace in "
        "Settings & data to keep your named scenarios outside this session."
    )

def render_learn():
    blocks, result, summary, months, _, _, _ = context()
    st.subheader("Learn by doing")
    st.write(
        "Short, practical lessons when they matter to your financial life. "
        "Each topic includes one question to check your understanding."
    )
    recommendations = recommended_lesson_ids(blocks)
    topics = recommendations + [
        topic for topic in LESSONS if topic not in recommendations
    ]
    st.caption(
        "Suggested topics are based only on your currently entered building blocks. "
        "Lessons are educational and do not provide individualized investment advice."
    )
    if "ml_completed_lessons" not in st.session_state:
        st.session_state.ml_completed_lessons = []
    st.metric(
        "Lessons completed this session",
        f"{len(st.session_state.ml_completed_lessons)} / {len(LESSONS)}",
    )
    topic = st.selectbox(
        "Choose a 1-minute lesson",
        options=topics,
        format_func=lambda name: LESSONS[name]["title"],
        key="ml_lesson",
    )
    lesson = LESSONS[topic]
    st.markdown(f"#### {lesson['title']}")
    st.write(lesson["summary"])
    st.write(lesson["explanation"])
    st.markdown("**Quick self-check**")
    st.write(lesson["question"])
    with st.form(f"ml_lesson_quiz_{topic}"):
        selected_answer = st.radio(
            "Your answer",
            options=list(range(len(lesson["options"]))),
            format_func=lambda index: lesson["options"][index],
            index=None,
        )
        submitted = st.form_submit_button("Check my answer")
    if submitted:
        if selected_answer is None:
            st.info("Choose an answer first.")
        else:
            feedback = check_answer(topic, selected_answer)
            if feedback["correct"]:
                if topic not in st.session_state.ml_completed_lessons:
                    st.session_state.ml_completed_lessons = (
                        st.session_state.ml_completed_lessons + [topic]
                    )
                st.success(feedback["explanation"])
            else:
                st.info(feedback["explanation"])
    st.caption(
        "Learning progress is held only in this Streamlit browser session. "
        "It is not connected to an account, grade, or bank."
    )

def render_settings():
    blocks, result, summary, months, saved_scenarios, checkin, profile_signature = context()
    st.title("Settings & data")
    st.subheader("Keep your profile portable")
    st.write(
        "Download your blocks as JSON for later use or upload a previously "
        "exported MoneyLab profile. No account is required and data is not "
        "automatically saved between browser sessions."
    )
    st.download_button(
        "Download my workspace + saved scenarios (JSON)",
        data=workspace_to_json(blocks, saved_scenarios),
        file_name="moneylab_workspace.json",
        mime="application/json",
        use_container_width=True,
    )
    st.caption(
        "Version 2 workspace files include your blocks and named scenarios. "
        "Older profile-only JSON files are still supported for import."
    )
    st.download_button(
        "Download projection (CSV)",
        data=as_csv(result),
        file_name="moneylab_modular_projection.csv",
        mime="text/csv",
        use_container_width=True,
    )
    uploaded = st.file_uploader(
        "Import a MoneyLab profile (.json)", type=["json"],
        help="Only import files you trust. Files must match MoneyLab's supported profile format.",
    )
    if st.button("Load selected profile", disabled=uploaded is None):
        try:
            text = uploaded.getvalue().decode("utf-8")
            restored, restored_scenarios = workspace_from_json(text)
            st.session_state.ml_blocks = restored
            st.session_state.ml_saved_scenarios = restored_scenarios
            st.rerun()
        except (UnicodeDecodeError, ValueError) as exc:
            st.error(f"Could not load profile: {exc}")
    with st.expander("Calculation assumptions and data handling"):
        st.markdown(
            """
            - Money figures are in USD and calculated with Decimal cents.
            - Take-home income and recorded living expenses are assumed constant.
            - Required loan payments are modeled separately and stop after payoff.
              Unpaid monthly loan interest is added to the balance.
            - Optional take-home income routes direct-deposit funds into existing
              accounts; they are never extra income or additional expenses.
              The remaining net pay flows to modeled cash.
            - Other account contributions occur only from affordable monthly
              surplus; transfers are not double-counted as expenses.
            - Every non-cash account uses a fixed hypothetical yield or return;
              investment values may fluctuate in reality. CDs may restrict
              deposits/withdrawals; no lock-up terms are simulated.
            - Retirement/HSA/529 contribution limits, eligibility, pretax payroll
              deductions, taxes and employer matches are not modeled.
            - A negative cash position represents an unfunded shortfall, not
              actual borrowed money.
            - No bank connections, Plaid integration, or automatic transaction
              synchronization exist in this version.
            - Profile data lives in the current Streamlit browser session; it is
              not stored in an account database. Export the profile to save it.
            - Educational scenario model, not financial advice.
            """
        )



