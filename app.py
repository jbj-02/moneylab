"""MoneyLab's customizable financial-life dashboard.

This is a local-first prototype: profiles live in the current Streamlit
session unless explicitly exported as JSON. The original loan interface
remains available as a separate classic simulator page.
"""

import csv
from datetime import date
from io import StringIO
from uuid import uuid4

import pandas as pd
import streamlit as st

from moneylab.blocks import (
    ACCOUNT_TYPES, ASSET_KINDS, BLOCK_KINDS, default_blocks, modify_expense,
    profile_from_json, profile_to_json, project_blocks, serialize_blocks,
)

from moneylab.checkin import build_checkin
from moneylab.insights import scenario_impacts
from moneylab.learning import LESSONS, check_answer, recommended_lesson_ids
from moneylab.presets import PRESET_CATALOG, preset_block

st.set_page_config(page_title="MoneyLab | My Financial Life", page_icon="💰", layout="wide")


def dollars(value):
    """USD metric label."""
    return f"${value:,.2f}" if value >= 0 else f"-${abs(value):,.2f}"


def money_field(label, key, initial=0):
    return st.number_input(
        label, key=key, min_value=0.0, value=float(initial),
        step=25.0, format="%.2f",
    )


def fields_for(kind, prefix, initial=None):
    """Render fields for exactly one block type, ready for validation."""
    item = initial or {}
    data = {}
    if kind in ("income", "expense"):
        data["monthly_amount"] = money_field(
            "Monthly amount ($)", f"{prefix}_monthly_amount",
            item.get("monthly_amount", 0),
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


if "ml_blocks" not in st.session_state:
    st.session_state.ml_blocks = []

st.title("💰 MoneyLab")
st.caption("Your money, your possibilities · Personalized financial planning")
st.write(
    "Build your financial picture from the pieces that apply to you. "
    "See what's left to spend, how your money may change, and what different "
    "decisions could mean for your goals."
)

with st.sidebar:
    st.header("Your workspace")
    months = st.slider("Projection months", 1, 120, 24, key="ml_months")
    st.caption("Start with zero blocks. Your changes stay in this browser session unless you export a profile.")
    if st.button("Load optional example profile", use_container_width=True):
        st.session_state.ml_blocks = default_blocks()
        st.rerun()
    if st.button("Start with an empty profile", use_container_width=True):
        st.session_state.ml_blocks = []
        st.rerun()
    st.divider()
    st.page_link(
        "pages/2_Classic_Simulator.py",
        label="Classic loan simulator", icon="🧮",
    )
    st.caption("No bank connections or third-party finance APIs are used.")

try:
    blocks = serialize_blocks(st.session_state.ml_blocks)
    result = project_blocks(blocks, months)
except ValueError as exc:
    st.error(f"Your profile needs attention: {exc}")
    st.stop()

summary = result["summary"]
profile_signature = profile_to_json(blocks)
reviewed = st.session_state.get("ml_reviewed_signature") == profile_signature
checkin = build_checkin(blocks, result, reviewed=reviewed)
tabs = st.tabs([
    "My dashboard", "Build my profile", "What-if Lab",
    "Goals & insights", "Export / import", "My check-in", "Learn",
])

with tabs[0]:
    if not blocks:
        st.info(
            "Welcome to MoneyLab! Your workspace starts completely empty. "
            "Open **Build my profile**, add a paycheck or an account, "
            "then keep adding the blocks that apply to your life. "
            "You can also load an optional example in the sidebar."
        )
        st.markdown("**Suggested starting blocks:** Take-home salary · Checking · Rent · HYSA")
        st.caption("Projections and spending estimates will appear when you add financial blocks.")
        st.subheader("What brings you to MoneyLab?")
        starters = {
            "I just got my first paycheck": "takehome",
            "I'm preparing to move out": "rent",
            "I want to start saving": "hysa",
            "I want to learn about investing": "roth",
            "I'm managing student debt": "student",
            "I want to organize my finances": "checking",
        }
        situation = st.selectbox(
            "Choose a starting point",
            list(starters),
            key="ml_start_situation",
        )
        if st.button("Add my first suggested block", type="primary"):
            try:
                first = preset_block(starters[situation], uuid4().hex[:12])
                st.session_state.ml_blocks = serialize_blocks([first])
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        st.caption(
            "The suggested block contains fictional starting values. "
            "Edit them to match your circumstances before relying on projections."
        )
    else:
        st.subheader("Your MoneyLab Check-In")
        if checkin["status"] == "on_track":
            st.success(f"**{checkin['heading']}** — {checkin['explanation']}")
        elif checkin["status"] == "needs_attention":
            st.warning(f"**{checkin['heading']}** — {checkin['explanation']}")
        else:
            st.info(f"**{checkin['heading']}** — {checkin['explanation']}")
        st.caption(
            "Open the **My check-in** tab for specific next steps, "
            "coverage estimates, and a manual review confirmation."
        )
        st.subheader("At a glance")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Monthly take-home income", dollars(summary["monthly_income"]))
        c2.metric("Monthly bills & spending", dollars(summary["monthly_expenses"]))
        c3.metric("Required loan payments", dollars(summary["first_month_loan_payments"]))
        c4.metric("Planned savings transfers", dollars(summary["first_month_transfers"]))

        st.subheader("Your spending flexibility")
        a, b, c = st.columns(3)
        a.metric("Unallocated monthly buffer", dollars(summary["unallocated_monthly_buffer"]))
        b.metric("Estimated extra weekly spend", dollars(summary["estimated_extra_weekly_spend"]))
        c.metric("Projected net position", dollars(summary["ending_net_position"]))
        st.caption(
            "The weekly estimate is the unallocated first-month buffer × 12 ÷ 52. "
            "It is **additional** spending beyond your listed categories, not "
            "verified cash in your bank. It assumes no surprise expenses and "
            "is reduced to zero when an unfunded shortfall remains."
        )

        if summary["ending_unfunded_shortfall"] > 0:
            st.warning(
                "This plan produces an unfunded cash shortfall of "
                f"{dollars(summary['ending_unfunded_shortfall'])} at month {months}. "
                "Reduce spending or contributions, or increase income."
            )
        if any(row["negative_amortization"] for row in result["monthly_records"][1:]):
            st.warning(
                "At least one loan grows because its scheduled payment "
                "does not cover the month's interest."
            )
        if summary["first_month_transfers"] == 0 and any(
            x["kind"] in ASSET_KINDS and float(x["monthly_contribution"]) > 0
            for x in blocks
        ):
            st.info("Planned savings transfers are not affordable this month.")

        routed_deposits = result["monthly_records"][1]["direct_deposits"]
        if routed_deposits:
            st.subheader("Your monthly income destinations")
            account_names = {item["id"]: item["name"] for item in blocks}
            st.dataframe(
                pd.DataFrame([
                    {"Destination": account_names.get(ident, ident),
                     "Monthly routed deposit": float(amount)}
                    for ident, amount in routed_deposits.items()
                ]),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Monthly routed deposit": st.column_config.NumberColumn(
                        "Monthly routed deposit", format="$%.2f"
                    )
                },
            )
            st.caption(
                "Routing shows where you directed take-home pay. Any remainder "
                "stays in modeled cash. This prototype pools checking/cash for "
                "spending projections rather than tracking every checking "
                "account's transactions separately."
            )

        st.subheader("Projected financial position")
        st.line_chart(as_chart(result), height=330)
        st.caption(
            "Balances are illustrative. HYSA and Roth IRA yields are fixed "
            "assumptions, not promised returns. Net position includes modeled "
            "assets, debts, and any negative cash position."
        )

with tabs[1]:
    st.subheader("Your financial building blocks")
    st.write(
        "Start from zero. Add only the accounts, bills, income sources, loans "
        "and goals that belong in your life. Edit or remove anything at any time."
    )
    st.markdown("#### Quick-add a common financial block")
    preset = st.selectbox(
        "Choose a ready-to-edit example",
        options=list(PRESET_CATALOG),
        format_func=lambda code: PRESET_CATALOG[code]["name"],
        key="ml_preset",
    )
    if st.button("Add this building block", key="ml_add_preset", type="primary"):
        new_block = preset_block(preset, uuid4().hex[:12])
        try:
            st.session_state.ml_blocks = serialize_blocks(blocks + [new_block])
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.caption("Templates start with fictional values. Edit each amount to fit your own life.")

    if not blocks:
        st.info("Your profile is empty. Add your first block below.")
    else:
        for block in blocks:
            left, right = st.columns([3, 2])
            with left:
                st.markdown(
                    f"**{block['name']}**  ·  {BLOCK_KINDS[block['kind']]}"
                )
            with right:
                if block["kind"] in ("income", "expense"):
                    st.caption(dollars(float(block["monthly_amount"])) + " / month")
                elif block["kind"] == "loan":
                    st.caption(
                        f"{dollars(float(block['balance']))} owed · "
                        f"{dollars(float(block['monthly_payment']))}/mo"
                    )
                else:
                    st.caption(dollars(float(block["balance"])) + " balance")

    st.divider()
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### Add a building block")
        new_kind = st.selectbox(
            "Type", options=list(BLOCK_KINDS),
            format_func=lambda kind: BLOCK_KINDS[kind], key="ml_new_kind",
        )
        with st.form("new_financial_block", clear_on_submit=False):
            name = st.text_input("Give this block a name", value="", key="ml_new_name",
                                 placeholder="e.g. Apartment rent")
            new_fields = fields_for(new_kind, "ml_add_" + new_kind)
            add = st.form_submit_button("Add block", use_container_width=True)
        with st.expander("Why would I add this kind of block?"):
            topic = recommended_lesson_ids([{"kind": new_kind}])[0]
            st.markdown(f"**{LESSONS[topic]['title']}**")
            st.write(LESSONS[topic]["summary"])
            st.caption("Explore the Learn tab for a short interactive explanation.")
        if add:
            candidate = {"id": uuid4().hex[:12], "kind": new_kind, "name": name, **new_fields}
            try:
                st.session_state.ml_blocks = serialize_blocks(blocks + [candidate])
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    with right:
        st.markdown("#### Edit or remove a block")
        if blocks:
            selected_id = st.selectbox(
                "Choose a block", options=[item["id"] for item in blocks],
                format_func=lambda key: next(
                    x["name"] for x in blocks if x["id"] == key
                ),
                key="ml_selected_block",
            )
            selected = next(x for x in blocks if x["id"] == selected_id)
            with st.form(f"edit_{selected_id}"):
                edit_name = st.text_input("Name", value=selected["name"])
                changes = fields_for(
                    selected["kind"], "ml_edit_" + selected_id, selected
                )
                save = st.form_submit_button("Save changes", use_container_width=True)
            if save:
                replacement = {
                    "id": selected_id, "kind": selected["kind"],
                    "name": edit_name, **changes,
                }
                if selected["kind"] == "income" and "routes" in selected:
                    replacement["routes"] = selected["routes"]
                try:
                    updated = [
                        replacement if item["id"] == selected_id else item
                        for item in blocks
                    ]
                    st.session_state.ml_blocks = serialize_blocks(updated)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            idx = next(i for i, item in enumerate(blocks) if item["id"] == selected_id)
            up_col, down_col = st.columns(2)
            with up_col:
                if st.button("Move up", disabled=idx == 0,
                             key="ml_move_up", use_container_width=True):
                    reordered = list(blocks)
                    reordered[idx - 1], reordered[idx] = reordered[idx], reordered[idx - 1]
                    st.session_state.ml_blocks = reordered
                    st.rerun()
            with down_col:
                if st.button("Move down", disabled=idx == len(blocks) - 1,
                             key="ml_move_down", use_container_width=True):
                    reordered = list(blocks)
                    reordered[idx + 1], reordered[idx] = reordered[idx], reordered[idx + 1]
                    st.session_state.ml_blocks = reordered
                    st.rerun()
            if st.button("Remove selected block", key="ml_remove_block",
                         use_container_width=True):
                remaining = [item for item in blocks if item["id"] != selected_id]
                for item in remaining:
                    if item["kind"] == "income" and "routes" in item:
                        item["routes"] = [
                            route for route in item["routes"]
                            if route["destination_id"] != selected_id
                        ]
                st.session_state.ml_blocks = serialize_blocks(remaining)
                st.rerun()
        else:
            st.caption("Add a block first, then choose it to edit or remove.")

    st.divider()
    st.subheader("Income routing: Where does each paycheck go?")
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

with tabs[2]:
    st.subheader("What if you changed one expense?")
    expenses = [item for item in blocks if item["kind"] == "expense"]
    if not expenses:
        st.info("Add an expense block to try a scenario.")
    else:
        expense_id = st.selectbox(
            "Choose an expense to adjust", [x["id"] for x in expenses],
            format_func=lambda ident: next(x["name"] for x in expenses if x["id"] == ident),
        )
        chosen = next(x for x in expenses if x["id"] == expense_id)
        delta = st.number_input(
            "Change per month ($, negative means less spending)",
            min_value=-float(chosen["monthly_amount"]), max_value=10000.0,
            value=100.0, step=25.0, format="%.2f",
        )
        try:
            adjusted = modify_expense(blocks, expense_id, delta)
            scenario = project_blocks(adjusted, months)
            gap = scenario["summary"]["ending_net_position"] - summary["ending_net_position"]
            col1, col2, col3 = st.columns(3)
            col1.metric("Current monthly buffer", dollars(summary["unallocated_monthly_buffer"]))
            col2.metric("Scenario monthly buffer",
                        dollars(scenario["summary"]["unallocated_monthly_buffer"]))
            col3.metric("Net-position difference", dollars(gap))
            st.subheader("What this decision actually affects")
            st.caption(
                "Alerts below compare real model results with your current profile. "
                "Unchanged items are not described as affected."
            )
            for alert in scenario_impacts(result, scenario, blocks):
                message = f"**{alert['title']}** — {alert['detail']}"
                if alert["level"] == "warning":
                    st.warning(message)
                elif alert["level"] == "positive":
                    st.success(message)
                else:
                    st.info(message)
            st.line_chart(pd.DataFrame({
                "Month": [r["month"] for r in result["monthly_records"]],
                "Current plan": [float(r["net_position"]) for r in result["monthly_records"]],
                "What-if plan": [float(r["net_position"]) for r in scenario["monthly_records"]],
            }).set_index("Month"), height=300)
            st.caption(
                "This is a temporary comparison only; it does not alter "
                "your saved profile. Adjusting rent, dining, or subscriptions "
                "changes the outlook while keeping all other assumptions fixed."
            )
        except ValueError as exc:
            st.error(str(exc))

with tabs[3]:
    st.subheader("Savings goals")
    if not result["goals"]:
        st.info("Add a Dedicated savings goal block to track a target.")
    for goal in result["goals"]:
        st.markdown(f"**{goal['name']}** · Goal {dollars(goal['target'])} "
                    f"by month {goal['target_months']}")
        if goal["projected_at_deadline"] is None:
            st.caption("Extend the projection horizon to assess this goal's deadline.")
        else:
            progress = min(
                float(goal["projected_at_deadline"] / goal["target"]), 1.0
            )
            st.progress(progress)
            if goal["on_track"]:
                st.success(
                    f"Projected {dollars(goal['projected_at_deadline'])} "
                    "by the goal deadline — on track under current assumptions."
                )
            else:
                st.warning(
                    f"Projected {dollars(goal['projected_at_deadline'])} "
                    f"at the deadline; short by {dollars(goal['gap_at_deadline'])}."
                )

    st.subheader("Budget insights")
    committed = (
        summary["monthly_expenses"] + summary["first_month_loan_payments"]
        + summary["first_month_transfers"]
    )
    if summary["monthly_income"] == 0:
        st.info("Add an income block to estimate spending flexibility.")
    elif committed > summary["monthly_income"]:
        st.warning(
            "Your listed obligations and actual savings contributions exceed "
            "monthly income. Review the blocks for possible changes."
        )
    else:
        st.info(
            f"Based on your entries, {dollars(committed)} of "
            f"{dollars(summary['monthly_income'])} monthly income is allocated "
            "to recorded expenses, required loan payments and planned transfers."
        )
    st.caption(
        "Retirement, HSA and 529 growth assumptions are illustrative. "
        "The model does not implement tax rules, eligibility or contribution limits."
    )

with tabs[4]:
    st.subheader("Keep your profile portable")
    st.write(
        "Download your blocks as JSON for later use or upload a previously "
        "exported MoneyLab profile. No account is required and data is not "
        "automatically saved between browser sessions."
    )
    st.download_button(
        "Download my profile (JSON)",
        data=profile_to_json(blocks),
        file_name="moneylab_profile.json",
        mime="application/json",
        use_container_width=True,
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
            st.session_state.ml_blocks = profile_from_json(text)
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


with tabs[5]:
    st.subheader("Your MoneyLab Check-In")
    st.write(
        "A calmer way to review your financial plan: what's covered, "
        "what may need attention, and one manageable next step."
    )
    if checkin["status"] == "on_track":
        st.success(f"**{checkin['heading']}** — {checkin['explanation']}")
    elif checkin["status"] == "needs_attention":
        st.warning(f"**{checkin['heading']}** — {checkin['explanation']}")
    else:
        st.info(f"**{checkin['heading']}** — {checkin['explanation']}")

    st.markdown("#### How complete is your financial picture?")
    if not checkin["reviewed"]:
        st.caption(
            "The entries have **not** been confirmed as reviewed in this session. "
            "MoneyLab does not have current bank or transaction data."
        )
    else:
        st.caption(
            "You confirmed this set of inputs during this session. "
            "Any edited, added, or removed block requires another review."
        )
    for missing_item in checkin["missing"]:
        st.write(f"◯ {missing_item}")
    if not checkin["missing"]:
        st.write("✓ Income, expense, and checking/cash blocks are present.")
    if st.button(
        "I've reviewed my entered financial information",
        key="ml_mark_reviewed",
        use_container_width=True,
    ):
        st.session_state.ml_reviewed_signature = profile_signature
        st.rerun()
    st.caption(
        "This acknowledges your own review only; it does not verify "
        "accuracy, completeness, bank balances, or recent transactions."
    )

    st.divider()
    st.markdown("#### Everyday stability and emergency readiness")
    left, right = st.columns(2)
    left.metric(
        "Estimated extra weekly flexibility",
        dollars(checkin["estimated_weekly_extra"]),
    )
    if checkin["coverage_months"] is not None:
        right.metric(
            "Months of listed outflows covered",
            f"{checkin['coverage_months']:.1f}",
        )
    else:
        right.metric("Months of listed outflows covered", "Unknown")
    st.caption(
        "Coverage uses entered checking/cash plus traditional savings, HYSA "
        "and money-market balances, divided by listed monthly expenses "
        "and first-month required loan payments. Retirement, brokerage, "
        "CDs, HSA and earmarked goal accounts are excluded. The estimate "
        "depends on your inputs and does not account for bill timing."
    )
    if checkin["attention"]:
        st.markdown("#### What needs attention")
        for issue in checkin["attention"]:
            st.warning(issue)
    st.markdown("#### A useful next step")
    if checkin["actions"]:
        for action in checkin["actions"]:
            st.write(f"• {action}")
    else:
        st.write(
            "Your reviewed model has no flagged issues within this projection. "
            "Revisit the check-in when expenses, income or goals change."
        )
    st.caption(
        "This is an educational planning check-in, not a financial-health "
        "rating or a guarantee that future expenses are affordable."
    )

with tabs[6]:
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
