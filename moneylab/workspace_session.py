"""Capture and restore only explicitly entered decision assumptions in a workspace.

Streamlit state is not durable storage. Restoring a decision fills form inputs
but intentionally does not restore a cached "current" result: the user must
recalculate with the now-restored profile and goals.
"""
from moneylab.moving import FIELDS
from moneylab.workspace import validated_decision_drafts

MODES = {
    "Try fictional example": "fictional",
    "Enter my own numbers": "entered",
    "Use My Money figures": "profile",
}


def capture_decision_drafts(state):
    source = MODES.get(state.get("move_start_mode"), "entered")
    snapshot = state.get("move_inputs_at_run")
    if snapshot is None:
        snapshot = {
            f: state.get(f"move_{f}") for f in FIELDS
            if f"move_{f}" in state
        }
    if not snapshot:
        return []
    raw = {
        "kind": "moving", "source": source,
        "values": {f: snapshot.get(f) for f in FIELDS},
        "allow_savings": bool(state.get("move_use_savings", False)),
        "include_goals": bool(state.get("move_include_goals", False)),
        "reviewed": bool(state.get("move_confirm", False)),
        "variation": state.get("move_variant_inputs"),
    }
    return validated_decision_drafts([raw])


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
    if not checked:
        return
    draft = checked[0]
    # A profile-based draft is a historical snapshot, not an automatically
    # refreshed mapping; present it as editable personal numbers.
    state["move_start_mode"] = (
        "Try fictional example" if draft["source"] == "fictional"
        else "Enter my own numbers"
    )
    for field, amount in draft["values"].items():
        if amount is not None:
            state[f"move_{field}"] = float(amount)
    state["move_confirm"] = draft["reviewed"]
    state["move_use_savings"] = draft["allow_savings"]
    state["move_include_goals"] = draft["include_goals"]
    state["move_variant_inputs"] = draft["variation"]
    state["ml_restored_moving"] = True
