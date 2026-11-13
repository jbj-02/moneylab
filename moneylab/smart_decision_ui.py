"""One natural-language decision entry shared by Home and Decisions.

The interpreter returns a temporary, unapproved draft. A separate review
screen confirms source values before routing to the existing simulations.
No parser output can save/change MoneyLab financial blocks. All calculations
still happen in the Decimal-based simulation modules.
"""
import streamlit as st

from moneylab.cadence import FREQUENCIES
from moneylab.decision_language import interpret_decision, label_for

_ROUTES = {
    "moving": "pages/7_Moving_Out_Alpha.py",
    "purchase": "pages/3_Explore.py",
    "recurring": "pages/3_Explore.py",
}
_MOVING_FIELDS = (
    "income", "current_housing", "rent", "other_living", "minimum_debt",
    "checking", "savings", "utilities", "internet", "renters_insurance",
    "security_deposit", "moving_cost", "furniture", "other_upfront",
    "transport_change", "groceries_change", "other_change",
)
_EXPENSE_FIELDS = ("cost", "income", "other_living", "checking", "savings")
_TITLES = {
    "moving": "Moving to a different home",
    "recurring": "Adding a recurring cost",
    "purchase": "Making a one-time purchase",
}


def _review_amount(field, draft, context, revision):
    raw = draft["values"].get(field)
    signed = field in ("transport_change", "groceries_change", "other_change")
    return st.number_input(
        label_for(field).capitalize() + " ($)",
        min_value=-100000000.0 if signed else 0.0,
        max_value=100000000.0, value=float(raw) if raw is not None else None,
        step=25.0, format="%.2f",
        placeholder="Not supplied" if raw is None else None,
        key=f"smart_{context}_{revision}_{field}",
        help="A blank value stays unknown. Zero means you explicitly confirmed no cost.",
    )


def _route(draft, selected, frequency):
    intent = draft["intent"]
    if intent == "moving":
        # Clear any older fictional/demo numbers before importing this draft.
        from moneylab.moving import FIELDS
        for field in FIELDS:
            st.session_state.pop(f"move_{field}", None)
        for field, value in selected.items():
            if field in FIELDS and value is not None:
                st.session_state[f"move_{field}"] = value
        st.session_state.move_draft_values = {field: selected.get(field) for field in FIELDS}
        st.session_state.move_draft_options = {}
        st.session_state.move_step = 0
        st.session_state.move_editing = True
        st.session_state.move_draft_source = "Enter my own numbers"
        st.session_state.move_start_mode = "Enter my own numbers"
        st.session_state.pop("move_result", None)
        st.session_state.move_confirm = False
    else:
        st.session_state.dc_guest_draft = {}
        st.session_state.dc_guest_show_result = False
        st.session_state.dc_guest_step = 0
        st.session_state.dc_decision_type = "💳 Can I take on a cost?"
        st.session_state.dc_question = "Can I buy this?" if intent == "purchase" else "Test another change"
        st.session_state.pop("dc_purchase_result", None)
        st.session_state.pop("dc_purchase_draft", None)
        st.session_state.dc_cost_kind = (
            "One-time purchase" if intent == "purchase"
            else "Recurring commitment"
        )
        if selected.get("cost") is not None:
            st.session_state.dc_cost_value = selected["cost"]
            st.session_state.dc_guest_cost = selected["cost"]
        if frequency:
            st.session_state.dc_cost_frequency = frequency
            st.session_state.dc_guest_frequency = frequency
        # These are provisional *guest* assumptions, not saved profile edits.
        for field, key in (
            ("income", "dc_guest_income"),
            ("other_living", "dc_guest_spending"),
            ("checking", "dc_guest_checking"),
            ("savings", "dc_guest_savings"),
        ):
            st.session_state[key] = selected.get(field)
        st.session_state.dc_guest_cost_kind = (
            "one_time" if intent == "purchase" else "recurring"
        )
    st.session_state.pop("smart_draft", None)
    st.session_state.pop("smart_origin", None)
    st.switch_page(_ROUTES[intent])


def _review(context):
    draft = st.session_state.get("smart_draft")
    if not draft or st.session_state.get("smart_origin") != context:
        return
    intent = draft["intent"]
    version = st.session_state.get("smart_draft_version", 0)
    if intent not in _ROUTES:
        st.warning(
            "This description involves an unsupported or multiple decision types. "
            "Try describing one decision at a time, or select a decision below."
        )
        if st.button("Dismiss", key=f"smart_{context}_dismiss"):
            st.session_state.pop("smart_draft", None)
            st.rerun()
        return
    with st.container(border=True):
        st.markdown(f"#### Review: {_TITLES[intent]}")
        st.caption(
            "These are proposed inputs only. Review and edit them before "
            "opening the decision. Nothing has been saved to My Money."
        )
        if draft.get("gross_income"):
            details = draft["gross_income"]
            freq = details.get("frequency") or "an unspecified period"
            st.warning(
                f"Income of ${details['amount']} for {freq} was not "
                "identified as take-home pay. Enter **monthly after-tax "
                "income** below instead; MoneyLab will not estimate taxes."
            )
        for note in list(dict.fromkeys(draft["notes"]))[:5]:
            st.caption(f"Note: {note}")
        if draft["ignored"]:
            with st.expander(f"{len(draft['ignored'])} unrecognized details"):
                st.write(
                    "These phrases were not applied. Check whether any "
                    "important cost should be added in the scenario."
                )
                for ignored in draft["ignored"][:8]:
                    st.write(f"• {ignored}")

        fields = _MOVING_FIELDS if intent == "moving" else _EXPENSE_FIELDS
        # Keep review manageable: show the core required inputs and only
        # additional amounts the interpreter actually recognized.
        mandatory = ("rent", "income", "current_housing") if intent == "moving" else ("cost",)
        visible = [field for field in fields if field in mandatory or
                   field in draft["values"]]
        a, b = st.columns(2)
        confirmed = {}
        for index, field in enumerate(visible):
            with (a if index % 2 == 0 else b):
                confirmed[field] = _review_amount(field, draft, context, version)
        cadence = None
        if intent == "recurring":
            choices = ["Choose a frequency", *FREQUENCIES.keys()]
            value = draft["values"].get("frequency")
            cadence = st.selectbox(
                "How often will you pay this cost?",
                choices, index=choices.index(value) if value in choices else 0,
                format_func=lambda k: FREQUENCIES[k][0]
                if k in FREQUENCIES else k,
                key=f"smart_{context}_{version}_frequency",
            )
        if intent == "moving":
            missing = [label_for(x) for x in draft["missing"]]
            if missing:
                st.info(
                    "**Still to confirm:** " + ", ".join(missing)
                    + ". You can also enter missing details in the Moving Out Lab."
                )
        else:
            st.caption(
                "If you already have a MoneyLab profile, the decision tool "
                "uses your existing recorded finances as its baseline. "
                "It will not overwrite them with this description."
            )
        left, right = st.columns([3, 1])
        with left:
            if st.button(
                "Open my decision with these values", type="primary",
                key=f"smart_{context}_{version}_confirm",
                use_container_width=True,
            ):
                if intent in ("purchase", "recurring") and (
                    confirmed.get("cost") is None or confirmed["cost"] <= 0
                ):
                    st.warning("Enter a positive cost before opening the decision.")
                elif intent == "recurring" and cadence not in FREQUENCIES:
                    st.warning(
                        "Choose how often the cost recurs. It would be "
                        "unsafe to assume that it's monthly."
                    )
                else:
                    _route(draft, confirmed, cadence)
        with right:
            if st.button(
                "Discard", key=f"smart_{context}_{version}_cancel",
                use_container_width=True,
            ):
                st.session_state.pop("smart_draft", None)
                st.rerun()


def render_smart_decision_entry(context="home"):
    """Display one compact input and its review panel, without duplicates."""
    with st.container(border=True):
        st.markdown("#### Describe a money decision")
        st.caption(
            r"Try: “I want to move out. New rent would be \$1,500 per month; "
            r"I take home \$3,500 monthly.”"
        )
        description = st.text_area(
            "What are you thinking about doing?",
            max_chars=2200, height=85,
            placeholder="I'm thinking about...",
            key=f"smart_{context}_description",
        )
        st.caption(
            "Describe a move, a purchase, or a new regular expense. "
            "You’ll review the suggested figures before using them."
        )
        if st.button(
            "Understand my decision", key=f"smart_{context}_interpret",
            disabled=len(description.strip()) < 12,
        ):
            try:
                draft = interpret_decision(description)
                st.session_state.smart_draft = draft
                st.session_state.smart_origin = context
                st.session_state.smart_draft_version = (
                    st.session_state.get("smart_draft_version", 0) + 1
                )
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    _review(context)
