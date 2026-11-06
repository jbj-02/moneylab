"""Portable, validated, explicitly entered MoneyLab decision snapshots.

No cached results are exported. Restored drafts populate inputs but require
the user to recompute; no profile or live balance is silently overwritten.
"""
from moneylab.moving import FIELDS
from moneylab.workspace import validated_decision_drafts

MODES = {
    "Try fictional example": "fictional",
    "Enter my own numbers": "entered",
    "Use My Money figures": "profile",
}


def capture_decision_drafts(state):
    collected = []
    moving = (
        state.get("move_inputs_at_run")
        if not state.get("move_editing", True) else None
    )
    if moving is None:
        moving = {field: state.get(f"move_{field}") for field in FIELDS
                  if f"move_{field}" in state}
    if moving:
        collected.append({
            "kind": "moving",
            "source": MODES.get(state.get("move_start_mode"), "entered"),
            "values": {field: moving.get(field) for field in FIELDS},
            "allow_savings": bool(state.get("move_use_savings", False)),
            "include_goals": bool(state.get("move_include_goals", False)),
            "reviewed": bool(state.get("move_confirm", False)),
            "variation": state.get("move_variant_inputs"),
        })

    has_guest = (
        state.get("dc_guest_compared", False)
        or state.get("dc_guest_cost") is not None
    )
    has_profile_cost = state.get("dc_profile_compared", False)
    if has_guest or has_profile_cost:
        use_profile = (
            bool(state.get("ml_blocks"))
            and state.get("dc_profile_source") != "Enter a temporary snapshot"
            and has_profile_cost
        )
        if use_profile:
            values = {"cost": state.get("dc_cost_value")}
            kind = (
                "recurring" if state.get("dc_cost_kind")
                == "Recurring commitment" else "one_time"
            )
            frequency = state.get("dc_cost_frequency", "monthly")
        else:
            values = {
                "cost": state.get("dc_guest_cost"),
                "income": state.get("dc_guest_income"),
                "spending": state.get("dc_guest_spending"),
                "checking": state.get("dc_guest_checking"),
                "savings": state.get("dc_guest_savings"),
            }
            kind = state.get("dc_guest_cost_kind", "one_time")
            frequency = state.get("dc_guest_frequency", "monthly")
        collected.append({
            "kind": "cost",
            "source": "profile" if use_profile else "entered",
            "values": values, "cost_type": kind,
            "frequency": frequency,
        })
    return validated_decision_drafts(collected)


def restore_decision_drafts(state, drafts):
    checked = validated_decision_drafts(drafts)
    for field in FIELDS:
        state.pop(f"move_{field}", None)
    for field in (
        "move_result", "move_inputs_at_run", "move_run_options",
        "move_variant_result", "move_variant_inputs", "move_variation_kind",
        "move_profile_review", "move_profile_notes",
    ):
        state.pop(field, None)
    state["move_editing"] = True
    state["move_confirm"] = False
    state["move_use_savings"] = False
    state["move_include_goals"] = False
    state["ml_restored_moving"] = False
    state["ml_restored_cost"] = False

    moving = next((item for item in checked if item["kind"] == "moving"), None)
    if moving is not None:
        state["move_start_mode"] = (
            "Try fictional example" if moving["source"] == "fictional"
            else "Enter my own numbers"
        )
        for field, amount in moving["values"].items():
            if amount is not None:
                state[f"move_{field}"] = float(amount)
        state["move_confirm"] = moving["reviewed"]
        state["move_use_savings"] = moving["allow_savings"]
        state["move_include_goals"] = moving["include_goals"]
        state["move_variant_inputs"] = moving["variation"]
        state["ml_restored_moving"] = True

    cost = next((item for item in checked if item["kind"] == "cost"), None)
    for key in (
        "dc_guest_cost", "dc_guest_income", "dc_guest_spending",
        "dc_guest_checking", "dc_guest_savings", "dc_cost_value",
    ):
        state.pop(key, None)
    state["dc_guest_compared"] = False
    state["dc_profile_compared"] = False
    if cost is not None:
        state["dc_decision_type"] = "💳 Can I take on a cost?"
        if cost["source"] == "profile":
            state["dc_profile_source"] = "Use My Money figures"
            state["dc_cost_value"] = float(cost["values"].get("cost") or 0)
            state["dc_cost_kind"] = (
                "Recurring commitment" if cost["cost_type"] == "recurring"
                else "One-time purchase"
            )
            state["dc_cost_frequency"] = cost["frequency"]
        else:
            state["dc_profile_source"] = "Enter a temporary snapshot"
            for field, key in (
                ("cost", "dc_guest_cost"),
                ("income", "dc_guest_income"),
                ("spending", "dc_guest_spending"),
                ("checking", "dc_guest_checking"),
                ("savings", "dc_guest_savings"),
            ):
                amount = cost["values"].get(field)
                if amount is not None:
                    state[key] = float(amount)
            state["dc_guest_cost_kind"] = cost["cost_type"]
            state["dc_guest_frequency"] = cost["frequency"]
        state["ml_restored_cost"] = True
