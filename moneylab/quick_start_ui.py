"""MoneyLab Quick Start: guided wizard or opt-in AI, with explicit review."""

import os
from copy import deepcopy

import streamlit as st

from moneylab.ai_setup import MAX_INPUT_CHARS, suggest_financial_blocks
from moneylab.blocks import ACCOUNT_TYPES, BLOCK_KINDS
from moneylab.cadence import FREQUENCIES, monthly_equivalent
from moneylab.onboarding import approve_drafts, guided_drafts

STEPS = ("Income", "Everyday spending", "Savings and debt", "Your goal")


def amount(label, key):
    return st.number_input(
        label, min_value=0.0, max_value=1000000000.0, value=0.0,
        step=25.0, format="%.2f", key=key,
    )


def cadence(label, key, preferred):
    options = list(FREQUENCIES)
    return st.selectbox(
        label, options, index=options.index(preferred),
        format_func=lambda key: FREQUENCIES[key][0], key=key,
    )


def secret(name):
    try:
        return st.secrets.get(name)
    except (FileNotFoundError, KeyError, OSError):
        return None


def ai_configuration():
    switch = secret("MONEYLAB_ENABLE_AI_SETUP")
    if switch is None:
        switch = os.environ.get("MONEYLAB_ENABLE_AI_SETUP", "")
    key = secret("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    return str(switch).lower() in ("true", "yes", "1") and bool(key), key


def guided_answers():
    s = st.session_state
    return {
        "income": s.get("qs_income", 0),
        "income_frequency": s.get("qs_income_frequency", "biweekly"),
        "rent": s.get("qs_rent", 0),
        "rent_frequency": s.get("qs_rent_frequency", "monthly"),
        "groceries": s.get("qs_groceries", 0),
        "groceries_frequency": s.get("qs_groceries_frequency", "weekly"),
        "other": s.get("qs_other", 0),
        "other_frequency": s.get("qs_other_frequency", "monthly"),
        "checking": s.get("qs_checking", 0),
        "savings": s.get("qs_savings", 0),
        "debt": s.get("qs_debt", 0),
        "debt_rate": s.get("qs_debt_rate") if s.get("qs_know_debt") else None,
        "debt_payment": s.get("qs_debt_payment") if s.get("qs_know_debt") else None,
        "include_goal": s.get("qs_include_goal", False),
        "goal_name": s.get("qs_goal_name", "Emergency fund"),
        "goal_target": s.get("qs_goal_target", 0),
        "goal_months": s.get("qs_goal_months", 12),
        "goal_balance": s.get("qs_goal_balance", 0),
        "goal_contribution": s.get("qs_goal_contribution", 0),
    }


def guided_step():
    step = st.session_state.setdefault("qs_step", 0)
    st.markdown(f"### Step {step + 1} of 4 · {STEPS[step]}")
    st.progress((step + 1) / 4)
    if step == 0:
        st.write("What's your take-home pay after taxes? Skip if you're unsure.")
        amount("Take-home pay each pay period ($)", "qs_income")
        cadence("How often are you paid?", "qs_income_frequency", "biweekly")
    elif step == 1:
        st.write("Start with a few costs. You can add more later.")
        a, b = st.columns(2)
        with a:
            amount("Rent or housing ($)", "qs_rent")
            cadence("Rent frequency", "qs_rent_frequency", "monthly")
            amount("Other living expenses ($)", "qs_other")
            cadence("Other expenses frequency", "qs_other_frequency", "monthly")
        with b:
            amount("Groceries ($)", "qs_groceries")
            cadence("Groceries frequency", "qs_groceries_frequency", "weekly")
        st.caption("Insurance, utilities, annual bills and other costs can be added later.")
    elif step == 2:
        st.write("Only enter numbers you know.")
        a, b = st.columns(2)
        with a:
            amount("Checking/cash balance ($)", "qs_checking")
            amount("Savings balance ($)", "qs_savings")
        with b:
            debt = amount("Loan balance ($)", "qs_debt")
            if debt > 0:
                if st.checkbox(
                    "I know this loan's rate and payment",
                    key="qs_know_debt",
                ):
                    st.number_input(
                        "Annual interest rate (%)",
                        min_value=0.0, max_value=100.0,
                        value=0.0, step=0.5, key="qs_debt_rate",
                    )
                    amount("Monthly loan payment ($)", "qs_debt_payment")
                else:
                    st.info("We will ask you to verify the missing loan details.")
    else:
        st.write("Optional: save for an emergency fund, travel, or something important.")
        if st.checkbox("I have a savings goal", key="qs_include_goal"):
            st.text_input(
                "Goal name", value="Emergency fund", max_chars=60,
                key="qs_goal_name",
            )
            amount("Goal target ($)", "qs_goal_target")
            st.number_input(
                "Months until goal", min_value=1, max_value=600,
                value=12, step=1, key="qs_goal_months",
            )
            a, b = st.columns(2)
            with a:
                amount("Already saved toward it ($)", "qs_goal_balance")
            with b:
                amount("Monthly contribution ($)", "qs_goal_contribution")

    back, forward = st.columns(2)
    if back.button("Back", disabled=step == 0, use_container_width=True):
        st.session_state.qs_step = step - 1
        st.rerun()
    if step < 3:
        if forward.button("Continue", type="primary", use_container_width=True):
            st.session_state.qs_step = step + 1
            st.rerun()
    elif forward.button("Review my profile", type="primary", use_container_width=True):
        try:
            drafts = guided_drafts(guided_answers())
            if drafts:
                st.session_state.qs_drafts = drafts
                st.rerun()
            st.info("Add at least one amount, or choose My Money to add a block.")
        except ValueError as exc:
            st.error(str(exc))


def ai_entry():
    active, api_key = ai_configuration()
    st.markdown("### Describe your financial situation")
    st.write(
        "Example: My net paycheck is $1,800 biweekly, rent is $1,200 monthly, "
        "groceries are $90 a week, and I have $500 in checking."
    )
    if not active:
        st.info(
            "AI setup is not enabled by the app owner. "
            "Guided setup is fully available without AI."
        )
        return
    st.warning(
        "AI setup is optional. **Your submitted description will be sent "
        "to OpenAI** for financial block extraction. The guided setup "
        "never sends financial information to OpenAI."
    )
    st.caption(
        "Do not share bank credentials, account numbers, Social Security numbers, "
        "addresses or other identifying details."
    )
    description = st.text_area(
        "Describe income, expenses, balances or goals",
        key="qs_ai_text", max_chars=MAX_INPUT_CHARS, height=140,
    )
    consent = st.checkbox(
        "I agree to send this description to OpenAI for setup",
        key="qs_ai_consent",
    )
    used = st.session_state.get("qs_ai_attempts", 0)
    st.caption(f"AI requests remaining this session: {max(0, 3 - used)}")
    if st.button(
        "Suggest my building blocks", type="primary", key="qs_ai_submit",
        disabled=not (consent and 20 <= len(description.strip()) <= MAX_INPUT_CHARS
                      and used < 3),
    ):
        st.session_state.qs_ai_attempts = used + 1
        try:
            with st.spinner("Extracting the amounts you provided"):
                drafts = suggest_financial_blocks(description, api_key)
            if not drafts:
                st.info("No supported values found. Try guided setup instead.")
            else:
                st.session_state.qs_drafts = drafts
                st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def review_drafts():
    drafts = st.session_state.qs_drafts
    st.markdown("### Review these building blocks")
    st.write(
        f"{len(drafts)} suggestions found. Correct any values and exclude "
        "anything that does not apply. **Nothing is saved until you approve.**"
    )
    edited, selected = [], []
    for index, saved in enumerate(drafts):
        item = deepcopy(saved)
        with st.container(border=True):
            include = st.checkbox(
                f"Include {saved['name']}", value=True,
                key=f"qs_include_{index}",
            )
            selected.append(include)
            if not include:
                edited.append(item)
                continue
            st.caption(BLOCK_KINDS[item["kind"]])
            item["name"] = st.text_input(
                "Name", value=item["name"], max_chars=60,
                key=f"qs_name_{index}",
            )
            kind = item["kind"]
            if kind in ("income", "expense"):
                a, b = st.columns(2)
                with a:
                    item["amount"] = str(st.number_input(
                        "Amount per period ($)", value=float(item["amount"]),
                        min_value=0.0, max_value=1000000000.0, step=25.0,
                        format="%.2f", key=f"qs_review_amount_{index}",
                    ))
                with b:
                    item["frequency"] = st.selectbox(
                        "Frequency", list(FREQUENCIES),
                        index=list(FREQUENCIES).index(item["frequency"]),
                        format_func=lambda f: FREQUENCIES[f][0],
                        key=f"qs_review_frequency_{index}",
                    )
                st.caption(
                    "Monthly equivalent: "
                    f"{monthly_equivalent(item['amount'], item['frequency']):,.2f} USD"
                )
            else:
                fields = (
                    ("balance",) if kind == "cash" else
                    ("balance", "annual_rate", "monthly_payment") if kind == "loan" else
                    ("balance", "target", "target_months", "monthly_contribution")
                    if kind == "goal" else
                    ("balance", "annual_rate", "monthly_contribution")
                )
                for field in fields:
                    if field == "target_months":
                        item[field] = st.number_input(
                            "Months until target", min_value=1, max_value=600,
                            value=int(item[field]), step=1,
                            key=f"qs_review_{index}_{field}",
                        )
                        continue
                    descriptions = {
                        "balance": "Current balance ($)",
                        "annual_rate": "Illustrative annual rate (%)",
                        "monthly_payment": "Required monthly payment ($)",
                        "monthly_contribution": "Planned monthly contribution ($)",
                        "target": "Goal target ($)",
                    }
                    item[field] = str(st.number_input(
                        descriptions[field],
                        value=float(item.get(field, 0)), min_value=0.0,
                        max_value=100.0 if field == "annual_rate" else 1000000000.0,
                        step=1.0, format="%.2f",
                        key=f"qs_review_{index}_{field}",
                    ))
                if kind == "account":
                    item["account_type"] = st.selectbox(
                        "Account type", list(ACCOUNT_TYPES),
                        index=list(ACCOUNT_TYPES).index(item["account_type"]),
                        format_func=lambda x: ACCOUNT_TYPES[x],
                        key=f"qs_review_{index}_subtype",
                    )
                if kind in ("account", "hysa", "roth_ira", "goal"):
                    st.caption("Default growth is 0% unless you enter an illustrative assumption.")
            if item["missing"]:
                st.warning(
                    "Unknown or unconfirmed: " + ", ".join(item["missing"])
                    + ". Displayed values are placeholders, not verified figures."
                )
                if st.checkbox(
                    "I have verified and updated these missing details",
                    key=f"qs_verified_{index}",
                ):
                    item["missing"] = []
            edited.append(item)

    st.caption(
        "The selected blocks will be added to your existing financial profile, "
        "not replace it. If any selected item is invalid, nothing is added."
    )
    if st.button(
        "Add selected blocks to my profile", type="primary",
        use_container_width=True, key="qs_confirm",
    ):
        from moneylab.ui_app import context
        existing, *_ = context()
        try:
            updated = approve_drafts(existing, edited, selected)
            st.session_state.ml_blocks = updated
            st.session_state.qs_drafts = None
            st.session_state.qs_step = 0
            st.session_state.pop("qs_ai_text", None)
            st.switch_page("pages/1_My_Money.py")
        except ValueError as exc:
            st.error(f"No blocks were added: {exc}")
    if st.button("Discard suggestions", key="qs_discard"):
        st.session_state.qs_drafts = None
        st.session_state.pop("qs_ai_text", None)
        st.rerun()


def render_quick_start():
    st.title("MoneyLab Quick Start")
    st.caption("Start with a few answers. Add several blocks at once.")
    st.write(
        "Choose guided questions or optional AI suggestions. "
        "You can edit and approve everything before updating your profile."
    )
    if st.session_state.get("qs_drafts") is not None:
        review_drafts()
        return
    path = st.radio(
        "Choose your setup method",
        ["Guided setup · no AI", "AI-assisted setup"],
        horizontal=True, key="qs_method",
    )
    if path.startswith("Guided"):
        guided_step()
    else:
        ai_entry()
    st.divider()
    if st.button("I'd rather build blocks individually", key="qs_manual"):
        st.switch_page("pages/1_My_Money.py")
    st.caption(
        "No bank connection or login is required. Session-only data must "
        "be exported from Settings & data to keep a copy."
    )
