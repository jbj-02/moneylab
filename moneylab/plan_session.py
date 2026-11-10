"""Streamlit state boundary, optional local continuity and honest save status."""
import streamlit as st
import sqlite3

from moneylab.profile_store import configured_local_store, plan_from_json, plan_to_json
from moneylab.workspace import validated_scenarios
from moneylab.workspace_session import capture_decision_drafts, restore_decision_drafts

DEFAULT_METADATA = {"priority": "Understand my money", "unknown": ["debts"], "is_example": False}


def load_example():
    from moneylab.blocks import default_blocks
    restore(plan_to_json(default_blocks(), [], [], {
        "priority": "Understand my money", "unknown": [], "is_example": True,
    }))
    st.session_state.ml_example_confirm = False


def restore(payload):
    blocks, scenarios, drafts, metadata = plan_from_json(payload)
    for key in list(st.session_state):
        if key.startswith(("setup_", "plan_goal_", "plan_setup_", "smart_", "edit_", "dc_", "move_")):
            st.session_state.pop(key, None)
    restore_decision_drafts(st.session_state, drafts)
    st.session_state.ml_blocks = blocks
    st.session_state.ml_saved_scenarios = scenarios
    st.session_state.ml_plan_metadata = metadata
    st.session_state.pop("ml_reviewed_signature", None)
    st.session_state.ml_plan_preview = None


def snapshot():
    blocks = st.session_state.get("ml_blocks", [])
    try:
        scenarios = validated_scenarios(blocks, st.session_state.get("ml_saved_scenarios", []))
    except ValueError:
        scenarios = []
    return plan_to_json(blocks, scenarios, capture_decision_drafts(st.session_state),
                        st.session_state.get("ml_plan_metadata", DEFAULT_METADATA))


def sync_local():
    """Called before and after rendering; never cache finances across users."""
    try:
        store = configured_local_store(st.get_option("server.address"))
        if store is None:
            st.session_state.ml_save_status = "Session only · download a backup"
            return
        if not st.session_state.get("ml_store_loaded"):
            payload, revision = store.load()
            if payload:
                restore(payload)
            st.session_state.ml_store_revision = revision
            st.session_state.ml_store_snapshot = snapshot()
            st.session_state.ml_store_loaded = True
        current = snapshot()
        if current != st.session_state.ml_store_snapshot:
            revision = store.save(current, st.session_state.ml_store_revision)
            st.session_state.ml_store_revision = revision
            st.session_state.ml_store_snapshot = current
        st.session_state.ml_save_status = "Saved locally on this computer"
        st.session_state.pop("ml_store_error", None)
    except (ValueError, OSError, sqlite3.Error):
        st.session_state.ml_save_status = "Not saved · download a backup"
        st.session_state.ml_store_error = True


def delete_local():
    store = configured_local_store(st.get_option("server.address"))
    if store:
        store.delete(st.session_state.ml_store_revision)
        st.session_state.ml_store_revision += 1
    # Clear every financial form/draft, including retired workflow state.
    retained = {key: st.session_state[key] for key in list(st.session_state)
                if key.startswith("ml_store_") or key == "ml_save_status"}
    for key in list(st.session_state):
        st.session_state.pop(key, None)
    st.session_state.update(retained)
    st.session_state.ml_blocks = []
    st.session_state.ml_saved_scenarios = []
    st.session_state.ml_plan_metadata = dict(DEFAULT_METADATA)
    if store:
        st.session_state.ml_store_snapshot = snapshot()
