"""Moving Out Lab: transparent inputs, comparison, editable alternatives and opt-in profile sync.

Existing profile values are NEVER confused with proposed living costs. A report
is a snapshot; changing source or inputs invalidates the prior result. Money
calculations are delegated to moving.py's Decimal model.
"""
from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st

from moneylab.moving import FIELDS, LABELS, compare_moving, comparison_csv
from moneylab.moving_profile import (
    housing_candidates, suggest_housing_id, profile_to_moving,
    review_profile_changes, apply_reviewed_profile_changes,
)
from moneylab.ui_app import dollars

EXAMPLE = {
    "income": 3600, "current_housing": 400, "other_living": 850,
    "minimum_debt": 150, "checking": 4500, "savings": 3000,
    "rent": 1400, "utilities": 110, "internet": 50,
    "renters_insurance": 20, "transport_change": 45,
    "groceries_change": 100, "other_change": 0,
    "security_deposit": 1400, "moving_cost": 600,
    "furniture": 400, "other_upfront": 0,
}


def money(value):
    """Remove unnecessary decimal zeros while retaining exact cents."""
    number = Decimal(str(value))
    return f"${number:,.0f}" if number == number.to_integral_value() else f"${number:,.2f}"


def _source():
    return st.session_state.get("move_start_mode", "Try fictional example")


def _reset_result():
    for key in (
        "move_result", "move_inputs_at_run", "move_run_options",
        "move_profile_at_run",
        "move_variant_result", "move_variant_inputs", "move_variation_kind", "move_profile_review",
    ):
        st.session_state.pop(key, None)
    st.session_state.move_editing = True


def _switch_mode():
    for field in FIELDS:
        st.session_state.pop(f"move_{field}", None)
    for key in ("move_confirm", "move_include_goals", "move_use_savings",
                "move_housing_choice"):
        st.session_state.pop(key, None)
    _reset_result()


def _preset(field):
    value = st.session_state.get(f"move_{field}")
    if value is not None:
        return value
    if _source() == "Try fictional example":
        return EXAMPLE[field]
    return None


def _money(field, title=None, *, required=False, signed=False, help_text=None):
    value = _preset(field)
    return st.number_input(
        title or LABELS[field].capitalize(),
        min_value=-100000000.0 if signed else 0.0,
        max_value=100000000.0,
        value=float(value) if value is not None else None,
        step=25.0, format="%.2f",
        placeholder="Required" if required else "Unknown (leave blank)",
        key=f"move_{field}", help=help_text,
    )


def _section_summary(fields):
    pieces = []
    for field, title in fields:
        value = _preset(field)
        if value is not None:
            suffix = "/mo" if field not in (
                "checking", "savings", "security_deposit", "moving_cost",
                "furniture", "other_upfront"
            ) else ""
            pieces.append(f"{title}: {money(value)}{suffix}")
    return " · ".join(pieces) if pieces else "not entered"


def _profile_loader():
    profile = st.session_state.get("ml_blocks", [])
    if not profile or _source() != "Use My Money figures":
        return
    choices = housing_candidates(profile)
    options = [None, *[e["id"] for e in choices]]
    default = suggest_housing_id(profile)
    if st.session_state.get("move_housing_choice") not in options:
        st.session_state.move_housing_choice = default
    selected = st.selectbox(
        "Which recorded expense represents your current housing?",
        options, format_func=lambda key: (
            "I'll enter the current housing amount manually" if key is None
            else next(item["name"] for item in choices if item["id"] == key)
        ), key="move_housing_choice",
    )
    st.caption(
        "Only existing recorded income, expenses, loan minimums, checking "
        "and eligible savings are suggested. Goal, retirement and investing "
        "balances are excluded. Review each amount before comparing."
    )
    if st.button("Use My Money figures", key="move_load_profile", type="primary"):
        try:
            proposal = profile_to_moving(profile, selected)
            for field in FIELDS:
                st.session_state.pop(f"move_{field}", None)
                amount = proposal["values"].get(field)
                if amount is not None:
                    st.session_state[f"move_{field}"] = float(amount)
            st.session_state.move_profile_notes = proposal["notes"]
            _reset_result()
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if st.session_state.get("move_profile_notes"):
        with st.expander("What we reused from My Money", expanded=False):
            for note in st.session_state.move_profile_notes:
                st.write(f"• {note}")


def _input_form():
    with st.form("move_alpha_form", border=False):
        st.markdown("### 1. Where you are today")
        a, b = st.columns(2, gap="medium")
        with a:
            _money("income", "Monthly take-home pay ($)", required=True)
            _money(
                "current_housing", "Your current housing cost ($/month)",
                required=True, help_text="Enter 0 if you pay no current rent.",
            )
        with b:
            _money(
                "other_living", "Other regular expenses ($/month)",
                help_text="Groceries, phone, transportation, insurance and "
                          "other monthly costs, excluding any loan payments below.",
            )
            _money(
                "checking", "Checking / cash available today ($)",
                help_text="Checking/cash only; other savings belong below.",
            )
        extra = _section_summary(
            (("minimum_debt", "Debt"), ("savings", "Savings"))
        )
        with st.expander(f"Debt & savings · {extra}"):
            a, b = st.columns(2)
            with a:
                _money("minimum_debt", "Minimum debt payments ($/month)")
            with b:
                _money(
                    "savings", "Accessible, unearmarked savings ($)",
                    help_text="Exclude amounts already earmarked for goals "
                              "and retirement or investment accounts.",
                )
            st.checkbox(
                "Allow savings to cover upfront moving costs",
                key="move_use_savings", value=False,
            )

        st.markdown("### 2. The proposed move")
        a, b = st.columns(2, gap="medium")
        with a:
            _money("rent", "Your share of new rent ($/month)", required=True)
            _money("security_deposit", "Security deposit & fees ($)")
        with b:
            _money("moving_cost", "Moving costs ($)")
            st.caption("Include known monthly costs below for a more reliable comparison.")

        costs = _section_summary((
            ("utilities", "Utilities"), ("internet", "Internet"),
            ("renters_insurance", "Insurance"),
            ("transport_change", "Transport change"),
            ("groceries_change", "Groceries change"),
            ("other_change", "Other change"),
        ))
        with st.expander(f"Monthly bills & lifestyle changes · {costs}"):
            a, b = st.columns(2)
            with a:
                _money("utilities", "Utilities ($/month)")
                _money("internet", "Internet ($/month)")
                _money("renters_insurance", "Renter's insurance ($/month)")
            with b:
                _money(
                    "transport_change", "Change in transport ($/month)",
                    signed=True,
                    help_text="Use a negative number if your costs decrease.",
                )
                _money(
                    "groceries_change", "Change in groceries ($/month)",
                    signed=True,
                )
                _money(
                    "other_change", "Other living-cost change ($/month)",
                    signed=True,
                )

        upfront = _section_summary((
            ("furniture", "Furniture"), ("other_upfront", "Other upfront")
        ))
        with st.expander(f"Other upfront costs · {upfront}"):
            a, b = st.columns(2)
            with a:
                _money("furniture", "Furniture & supplies ($)")
            with b:
                _money("other_upfront", "Other one-time costs ($)")

        goals = [
            g for g in st.session_state.get("ml_blocks", [])
            if isinstance(g, dict) and g.get("kind") == "goal"
        ]
        if goals:
            st.checkbox(
                f"Include my {len(goals)} existing savings goal(s)",
                key="move_include_goals", value=False,
            )
        st.checkbox(
            "I've reviewed the costs I know (optional)",
            key="move_confirm", value=False,
        )
        return st.form_submit_button(
            "Compare stay vs move", type="primary",
            use_container_width=True,
        )


def _read_inputs():
    return {field: st.session_state.get(f"move_{field}") for field in FIELDS}


def _run_options():
    return {
        "reviewed": bool(st.session_state.get("move_confirm", False)),
        "use_savings_for_upfront": bool(st.session_state.get("move_use_savings", False)),
        "include_goals": bool(st.session_state.get("move_include_goals", False)),
        "source": ("fictional" if _source() == "Try fictional example" else
                   "profile" if _source() == "Use My Money figures"
                   else "entered"),
    }


def _calculate(inputs, options):
    goals = [
        g for g in st.session_state.get("ml_blocks", [])
        if isinstance(g, dict) and g.get("kind") == "goal"
    ] if options["include_goals"] else None
    return compare_moving(
        inputs, existing_goals=goals,
        reviewed=options["reviewed"],
        use_savings_for_upfront=options["use_savings_for_upfront"],
        source=options["source"],
    )


def _breakdown_table(rows):
    source = st.session_state.move_result["details"]["source"]
    entries = []
    for item in rows:
        status = item["status"]
        if status == "missing":
            value, evidence = "Not entered", "Unknown"
        else:
            value = money(item["amount"])
            evidence = (
                "Fictional example" if source == "fictional" else
                "Confirmed zero" if status == "confirmed_zero" else
                "From My Money" if status == "profile" else "User-entered"
            )
        entries.append({
            "Included item": item["label"].capitalize(),
            "Amount": value, "Source": evidence,
        })
    st.dataframe(pd.DataFrame(entries), hide_index=True,
                 use_container_width=True)


def _cash_chart(report):
    rows = []
    for month in (6, 12, 24):
        values = report["timeframes"][month]
        for scenario, key in (
            ("Stay", "stay_liquid"), ("Move", "move_liquid")
        ):
            rows.append({
                "Month": month, "Scenario": scenario,
                "USD": float(values[key]),
            })
    data = pd.DataFrame(rows).sort_values(["Month", "Scenario"])
    chart = (
        alt.Chart(data).mark_bar()
        .encode(
            x=alt.X("Month:O", title="Months from today",
                    sort=[6, 12, 24]),
            xOffset=alt.XOffset("Scenario:N", sort=["Stay", "Move"]),
            y=alt.Y("USD:Q", title="Modeled liquid funds",
                    axis=alt.Axis(format="$,.0f")),
            color=alt.Color(
                "Scenario:N", sort=["Stay", "Move"],
                scale=alt.Scale(
                    domain=["Stay", "Move"],
                    range=["#2D79AA", "#E39339"],
                ),
                legend=alt.Legend(orient="bottom"),
            ),
            tooltip=[
                alt.Tooltip("Month:O", title="Month"),
                alt.Tooltip("Scenario:N", title="Scenario"),
                alt.Tooltip("USD:Q", title="Modeled liquid funds",
                            format="$,.2f"),
            ],
        )
        .properties(height=245)
    )
    st.altair_chart(chart, use_container_width=True)
    with st.expander("Exact 6-, 12- and 24-month estimates"):
        st.dataframe(pd.DataFrame([
            {
                "Period": f"{month} months",
                "Stay": money(report["timeframes"][month]["stay_liquid"]),
                "Move": money(report["timeframes"][month]["move_liquid"]),
                "Difference": money(report["timeframes"][month]["liquid_change"]),
            }
            for month in (6, 12, 24)
        ]), hide_index=True, use_container_width=True)


def _variation(report):
    st.markdown("#### What could you try next?")
    b1, b2, b3 = st.columns(3)
    if b1.button("Try lower rent", key="move_lower_rent",
                 use_container_width=True):
        st.session_state.move_variation_kind = "rent"
        st.session_state.pop("move_variant_result", None)
    if b2.button("Compare a roommate", key="move_roommate",
                 use_container_width=True):
        st.session_state.move_variation_kind = "roommate"
        st.session_state.pop("move_variant_result", None)
    if b3.button("Reduce upfront costs", key="move_lower_upfront",
                 use_container_width=True):
        st.session_state.move_variation_kind = "upfront"
        st.session_state.pop("move_variant_result", None)
    b4, b5 = st.columns(2)
    if b4.button("Delay and save first", key="move_delay",
                 use_container_width=True):
        st.session_state.move_variation_kind = "delay"
        st.session_state.pop("move_variant_result", None)
    if b5.button("Review missing expenses", key="move_missing",
                 use_container_width=True):
        st.session_state.move_editing = True
        st.rerun()

    kind = st.session_state.get("move_variation_kind")
    if not kind:
        return
    original = st.session_state.get("move_inputs_at_run", {})
    if not original:
        return
    with st.container(border=True):
        st.markdown("**Test another option without changing your first comparison**")
        if kind == "delay":
            with st.form("move_delay_plan"):
                months = st.number_input("Months to wait", 1, 36, 6)
                savings_per_month = st.number_input(
                    "Additional cash you could put aside monthly ($)",
                    min_value=0.0, max_value=100000.0,
                    value=100.0, format="%.2f",
                )
                submitted = st.form_submit_button("Estimate additional cash")
            if submitted:
                added = Decimal(str(months)) * Decimal(str(savings_per_month))
                st.info(
                    f"Saving {money(savings_per_month)} per month for "
                    f"{months} months adds **{money(added)}** in this "
                    "simplified illustration. This is not a dated forecast: "
                    "the amount may not be achievable after your other costs "
                    "and planned savings contributions."
                )
            return
        changed = dict(original)
        with st.form("move_variation_form"):
            if kind in ("rent", "roommate"):
                old = float(original.get("rent") or 0)
                suggested = old * (0.9 if kind == "rent" else 0.5)
                st.caption(
                    "The initial value below is only an editable example. "
                    "Enter your actual expected rent or roommate share."
                )
                changed["rent"] = st.number_input(
                    "Alternative monthly rent ($)", min_value=0.01,
                    max_value=100000000.0,
                    value=round(suggested, 2), format="%.2f",
                    key=f"move_variant_{kind}_rent",
                )
            else:
                for field in ("security_deposit", "moving_cost", "furniture",
                              "other_upfront"):
                    changed[field] = st.number_input(
                        LABELS[field].capitalize() + " ($)",
                        min_value=0.0, max_value=100000000.0,
                        value=float(original.get(field) or 0),
                        format="%.2f", key=f"move_variant_{field}",
                    )
            submitted = st.form_submit_button(
                "Compare this variation", type="primary",
            )
        if submitted:
            try:
                altered = _calculate(changed, st.session_state["move_run_options"])
                st.session_state.move_variant_result = altered
                st.session_state.move_variant_inputs = dict(changed)
            except ValueError as exc:
                st.session_state.pop("move_variant_result", None)
                st.error(str(exc))
        variant = st.session_state.get("move_variant_result")
        if variant:
            st.markdown("**Original move vs. this alternative**")
            a, b = st.columns(2)
            a.metric("Original moving monthly remainder",
                     money(report["monthly_margin_after"]))
            b.metric("Alternative monthly remainder",
                     money(variant["monthly_margin_after"]),
                     delta=money(
                         variant["monthly_margin_after"] -
                         report["monthly_margin_after"]
                     ))
            st.write(
                f"Upfront costs: originally {money(report['upfront'])}; "
                f"alternative {money(variant['upfront'])}."
            )
            if not variant["fundable"]:
                st.warning(
                    f"The alternative has an upfront funding gap of "
                    f"{money(variant['funding_gap'])}. No borrowing is assumed."
                )
            st.caption(
                "Your first comparison remains unchanged. Edit the alternative "
                "and compare again, or edit the original assumptions."
            )


def _profile_review(report):
    if report["details"]["source"] == "fictional":
        st.caption(
            "Fictional sample amounts cannot be added as your personal finances. "
            "Switch to your own figures before updating My Money."
        )
        return
    if st.button(
        "Review and add these figures to My Money", key="move_review_profile"
    ):
        st.session_state.move_profile_review = True
    if not st.session_state.get("move_profile_review"):
        return
    with st.container(border=True):
        st.markdown("#### Review changes to My Money")
        st.write(
            "Only your **current** income, housing, spending and balances "
            "are eligible. Proposed rent and moving costs are **never** "
            "automatically saved as your real expenses."
        )
        plan = review_profile_changes(
            st.session_state.get("ml_blocks", []),
            st.session_state["move_inputs_at_run"],
        )
        actions = {}
        for item in plan:
            st.write(
                f"**{item['label']}** — {money(item['value'])} · "
                f"{item['reason']}"
            )
            if item["action"] == "conflict":
                st.caption("Needs manual reconciliation in My Money; not imported.")
                actions[item["field"]] = "skip"
            else:
                approved = st.checkbox(
                    f"Approve {item['action']}: {item['label']}",
                    value=False, key=f"move_approve_{item['field']}",
                )
                actions[item["field"]] = "apply" if approved else "skip"
        if st.button(
            "Apply approved changes to My Money", type="primary",
            disabled=not any(x == "apply" for x in actions.values()),
            key="move_apply_profile",
        ):
            try:
                st.session_state.ml_blocks = apply_reviewed_profile_changes(
                    st.session_state.get("ml_blocks", []), plan, actions,
                )
                st.session_state.move_profile_review = False
                st.success("Approved current figures added or updated in My Money.")
            except ValueError as exc:
                st.error(f"Nothing was changed: {exc}")


def _render_result(report):
    st.subheader("Your moving decision, side by side")
    delta, upfront = report["monthly_change"], report["upfront"]
    direction = "increase" if delta >= 0 else "decrease"
    st.markdown(
        f"**Moving would {direction} your recorded monthly costs by "
        f"{money(abs(delta))}. Your monthly remainder would be "
        f"{money(report['monthly_margin_after'])} before optional savings "
        f"contributions, with {money(upfront)} required upfront.**"
    )
    if report["missing"] or not report["reviewed"]:
        st.info(
            "Preliminary result: not every financial input is confirmed. "
            "Open the breakdown to see precisely which amounts are missing."
        )
    a, b, c = st.columns(3)
    a.metric("Monthly expense change", money(delta))
    b.metric("Upfront cash required", money(upfront))
    c.metric("Remainder before savings transfers",
             money(report["monthly_margin_after"]))
    if report["monthly_margin_after"] < 0:
        st.warning(
            "Your proposed recorded expenses exceed your take-home income. "
            "A negative remainder is a modeled shortfall, not available cash."
        )

    details = report["details"]
    with st.container(border=True):
        st.markdown("#### Included in this comparison")
        st.caption(
            "Missing values are not confirmed zero. A zero you entered is "
            "shown separately from an unknown cost."
        )
        st.markdown("**Monthly expenses — current arrangement**")
        _breakdown_table(details["current"])
        st.write(f"**Current recorded total: {money(report['current_monthly'])}/month**")
        st.markdown("**Monthly expenses — proposed move**")
        _breakdown_table(details["proposed"])
        st.write(f"**Proposed recorded total: {money(report['proposed_monthly'])}/month**")
        st.markdown("**One-time moving costs**")
        _breakdown_table(details["upfront"])
        st.write(f"**Upfront total: {money(upfront)}**")
        st.markdown("**Where the liquid-funds figure comes from**")
        _breakdown_table(details["balances"])
        st.write(
            f"Checking {money(details['checking'])} + unrestricted savings "
            f"{money(details['savings'])} = **{money(report['current_liquid'])}** "
            "in recorded liquid funds."
        )
        st.write(
            f"Eligible for upfront costs: checking "
            f"{money(details['checking_available_for_upfront'])} + explicitly "
            f"allowed savings {money(details['savings_allowed_for_upfront'])} "
            f"= **{money(report['available_for_upfront'])}**."
        )
        st.caption(
            f"Dedicated goal balances excluded: "
            f"{money(details['earmarked_goals'])}. "
            f"Planned monthly goal contributions: "
            f"{money(details['planned_goal_contributions'])}; these are "
            "modeled as transfers, not a second living expense."
        )
        if report["fundable"]:
            st.write(
                f"Upfront payments use {money(details['upfront_from_checking'])} "
                f"from checking and {money(details['upfront_from_savings'])} "
                "from savings."
            )

    st.markdown("#### Your monthly comparison")
    st.dataframe(pd.DataFrame([
        {"Measure": "Take-home pay",
         "Stay": money(report["income"]), "Move": money(report["income"])},
        {"Measure": "Recorded expenses",
         "Stay": money(report["current_monthly"]),
         "Move": money(report["proposed_monthly"])},
        {"Measure": "Remainder before savings contributions",
         "Stay": money(report["monthly_margin_before"]),
         "Move": money(report["monthly_margin_after"])},
    ]), hide_index=True, use_container_width=True)

    if not report["fundable"]:
        st.warning(
            f"Upfront costs exceed your eligible funds by "
            f"{money(report['funding_gap'])}. No loan or overdraft is assumed."
        )
    else:
        st.markdown("#### What happens to your cash?")
        a, b = st.columns(2)
        a.metric("Recorded liquid funds before move",
                 money(report["current_liquid"]))
        b.metric("Recorded liquid funds after upfront",
                 money(report["remaining_liquid"]), delta=money(-upfront))
        st.caption(
            "Liquid funds = entered checking plus savings identified as "
            "accessible. Check whether any savings are actually earmarked. "
            "This is not a verified bank balance; only explicitly permitted "
            "funds pay upfront costs."
        )
        st.markdown("#### Modeled cash over time")
        _cash_chart(report)
        st.caption(
            "Negative checking balances indicate unfunded cash shortfalls, "
            "not automatic loans. Charts include any modeled goal transfers."
        )
        if report["goals_included"]:
            st.markdown("#### Existing savings goals")
            if report["goals_affected"]:
                for goal in report["goals_affected"]:
                    st.write(
                        f"**{goal['name']}** at month {goal['deadline_months']}: "
                        f"{money(goal['before'])} if staying vs. "
                        f"{money(goal['after'])} after moving."
                    )
            else:
                st.caption("No change to assessed goal outcomes in this model.")
        st.download_button(
            "Export this comparison (CSV)",
            data=comparison_csv(report),
            file_name="moneylab-moving-comparison.csv",
            mime="text/csv", key="move_csv",
            use_container_width=True,
        )

    st.markdown("#### Next steps")
    a, b = st.columns(2)
    if a.button("Edit original assumptions", key="move_edit",
                use_container_width=True):
        st.session_state.move_editing = True
        st.session_state.pop("move_variant_result", None)
        st.rerun()
    if b.button("Explore another decision", key="move_other_decision",
                use_container_width=True):
        st.switch_page("pages/3_Explore.py")
    _variation(report)
    _profile_review(report)

    with st.expander(
        "Missing information and calculation details",
        expanded=bool(report["missing"]),
    ):
        if report["missing"]:
            st.write("**Not entered:** " + ", ".join(
                LABELS[k] for k in report["missing"]
            ))
        else:
            st.write("All listed categories have a value, but costs may be omitted.")
        st.write(
            "Consider upfront application fees, first/last month's rent, "
            "utilities, annual bills, transport, health costs and deposits."
        )
        st.write(
            "Monthly remainder is take-home income minus recorded recurring "
            "costs and debt minimums, before optional savings contributions. "
            "The underlying projections use constant monthly averages."
        )
        st.write(
            "Deposits reduce upfront funds without assumed refunds. If first "
            "month's rent was prepaid, review whether it is counted twice. "
            "There is no exact payday/bill timing or guaranteed investment growth."
        )
        for warning in report["warnings"]:
            st.write(f"• {warning}")
    st.page_link(
        "pages/6_Settings.py", label="Save or restore my workspace",
        icon="💾",
    )


def render():
    st.title("Moving Out Decision Lab")
    st.caption("Compare staying with a potential move, without needing a complete profile.")
    profile = st.session_state.get("ml_blocks", [])
    modes = ["Try fictional example", "Enter my own numbers"]
    if profile:
        modes.append("Use My Money figures")
    # A Smart Decisions draft may preselect manual mode, which remains valid.
    if st.session_state.get("move_start_mode") not in modes:
        st.session_state.move_start_mode = "Try fictional example"
    st.radio(
        "Where should we get the figures?",
        modes, key="move_start_mode",
        horizontal=True, on_change=_switch_mode,
    )
    if _source() == "Try fictional example":
        st.info(
            "Fictional example: includes $4,500 checking and $3,000 savings, "
            "plus debt payments and move-in costs in the expandable sections. "
            "These are not your personal finances."
        )
    elif _source() == "Use My Money figures":
        _profile_loader()
    else:
        st.caption(
            "Enter your own numbers. Unknown costs can stay blank; "
            "enter 0 only for confirmed zero expenses."
        )

    report = st.session_state.get("move_result")
    if report and st.session_state.get("move_inputs_at_run"):
        profile_source = st.session_state.get("move_run_options", {})
        profile_dependent = (
            profile_source.get("source") == "profile"
            or profile_source.get("include_goals")
        )
        changed_profile = (
            profile_dependent
            and st.session_state.get("move_profile_at_run") !=
            st.session_state.get("ml_blocks", [])
        )
        if (_read_inputs() != st.session_state["move_inputs_at_run"] or
                _run_options() != st.session_state.get("move_run_options")
                or changed_profile):
            _reset_result()
            st.warning(
                "Your financial assumptions or referenced profile changed. "
                "Review and recalculate to see updated results."
            )
            report = None
    if report and not st.session_state.get("move_editing", False):
        _render_result(report)
    else:
        submitted = _input_form()
        if submitted:
            inputs = _read_inputs()
            options = _run_options()
            try:
                st.session_state.move_result = _calculate(inputs, options)
                st.session_state.move_inputs_at_run = dict(inputs)
                st.session_state.move_run_options = dict(options)
                st.session_state.move_profile_at_run = [
                    dict(item) for item in st.session_state.get("ml_blocks", [])
                ]
                st.session_state.move_editing = False
                st.session_state.pop("move_variant_result", None)
                st.session_state.pop("move_variation_kind", None)
                st.rerun()
            except ValueError as exc:
                st.session_state.pop("move_result", None)
                st.error(f"Review your entries: {exc}")
        else:
            st.caption(
                "Nothing is saved to My Money until you explicitly approve it."
            )
    st.divider()
    st.page_link(
        "pages/8_Feedback.py",
        label="Share private alpha feedback",
        icon="💬",
    )
