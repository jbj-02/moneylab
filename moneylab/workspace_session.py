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
        moving = dict(state.get("move_draft_values", {}))
        moving.update({field: state.get(f"move_{field}") for field in FIELDS
                       if f"move_{field}" in state})
    if moving:
        collected.append({
            "kind": "moving",
            "source": MODES.get(state.get("move_start_mode", state.get("move_draft_source")), "entered"),
            "values": {field: moving.get(field) for field in FIELDS},
            "allow_savings": bool(state.get("move_use_savings", state.get("move_draft_options", {}).get("move_use_savings", False))),
            "include_goals": bool(state.get("move_include_goals", state.get("move_draft_options", {}).get("move_include_goals", False))),
            "reviewed": bool(state.get("move_confirm", state.get("move_draft_options", {}).get("move_confirm", False))),
            "variation": state.get("move_variant_inputs"),
        })

    guest = {**state.get("dc_guest_draft", {}),
             **{key: state[key] for key in state if key.startswith("dc_guest_")}}
    has_guest = (
        state.get("dc_guest_compared", False)
        or guest.get("dc_guest_cost") is not None
    )
    profile_draft = state.get("ml_profile_cost_draft")
    has_profile_cost = state.get("dc_profile_compared", False) or bool(profile_draft)
    if has_guest or has_profile_cost:
        use_profile = (
            bool(state.get("ml_blocks"))
            and (profile_draft or state.get("dc_profile_source") != "Enter a temporary snapshot")
            and has_profile_cost
        )
        if use_profile:
            if profile_draft:
                values = {"cost": profile_draft["cost"]}
                kind, frequency = profile_draft["cost_type"], profile_draft["frequency"]
            else:
                values = {"cost": state.get("dc_cost_value")}
                kind = (
                    "recurring" if state.get("dc_cost_kind")
                    == "Recurring commitment" else "one_time"
                )
                frequency = state.get("dc_cost_frequency", "monthly")
        else:
            values = {
                "cost": guest.get("dc_guest_cost"),
                "income": guest.get("dc_guest_income"),
                "spending": guest.get("dc_guest_spending"),
                "checking": guest.get("dc_guest_checking"),
                "savings": guest.get("dc_guest_savings"),
            }
            kind = guest.get("dc_guest_cost_kind", "one_time")
            frequency = guest.get("dc_guest_frequency", "monthly")
        collected.append({
            "kind": "cost",
            "source": "profile" if use_profile else "entered",
            "values": values, "cost_type": kind,
            "frequency": frequency,
        })
    return validated_decision_drafts(collected)


def restore_decision_drafts(state, drafts):
    checked = validated_decision_drafts(drafts)
    state.pop("ml_profile_cost_draft", None)
    for field in FIELDS:
        state.pop(f"move_{field}", None)
    for field in (
        "move_result", "move_inputs_at_run", "move_run_options",
        "move_variant_result", "move_variant_inputs", "move_variation_kind",
        "move_profile_review", "move_profile_notes",
    ):
        state.pop(field, None)
    state["move_draft_source"] = "Try fictional example"
    state["move_draft_values"] = {}
    state["move_draft_options"] = {}
    state["move_step"] = 0
    state["dc_guest_draft"] = {}
    state["dc_guest_step"] = 0
    state["dc_guest_show_result"] = False
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
        state["move_draft_source"] = state["move_start_mode"]
        for field, amount in moving["values"].items():
            if amount is not None:
                state[f"move_{field}"] = float(amount)
        state["move_draft_values"] = {field: (float(amount) if amount is not None else None)
                                      for field, amount in moving["values"].items()}
        state["move_confirm"] = moving["reviewed"]
        state["move_use_savings"] = moving["allow_savings"]
        state["move_include_goals"] = moving["include_goals"]
        state["move_variant_inputs"] = moving["variation"]
        state["move_draft_options"] = {"move_confirm": moving["reviewed"],
                                       "move_use_savings": moving["allow_savings"],
                                       "move_include_goals": moving["include_goals"]}
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
            state["ml_profile_cost_draft"] = {
                "cost": str(cost["values"].get("cost") or 0),
                "cost_type": cost["cost_type"], "frequency": cost["frequency"],
            }
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
