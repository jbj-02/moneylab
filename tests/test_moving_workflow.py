"""Traceability, profile handoff, and workspace portability regressions."""
import json
from copy import deepcopy
from decimal import Decimal as D

import pytest

from moneylab.blocks import default_blocks, project_blocks
from moneylab.moving import compare_moving
from moneylab.moving_profile import (
    housing_candidates, suggest_housing_id, profile_to_moving,
    review_profile_changes, apply_reviewed_profile_changes,
)
from moneylab.workspace import (
    workspace_to_json, workspace_from_json_full, validated_decision_drafts,
)
from moneylab.workspace_session import (
    capture_decision_drafts, restore_decision_drafts,
)

SAMPLE = {
    "income": 3600, "current_housing": 400, "other_living": 850,
    "minimum_debt": 150, "checking": 4500, "savings": 3000,
    "rent": 1400, "utilities": 110, "internet": 50,
    "renters_insurance": 20, "transport_change": 45,
    "groceries_change": 100, "other_change": 0,
    "security_deposit": 1400, "moving_cost": 600,
    "furniture": 400, "other_upfront": 0,
}


def total(rows):
    return sum((item["amount"] for item in rows), D(0))


def test_visible_move_breakdown_exactly_reconciles_all_headlines():
    goal = {
        "id": "trip", "kind": "goal", "name": "Earmarked travel",
        "balance": "600", "annual_rate": 0,
        "monthly_contribution": "100", "target": "1500",
        "target_months": 12,
    }
    report = compare_moving(SAMPLE, existing_goals=[goal],
                            reviewed=True, source="fictional")
    details = report["details"]
    assert total(details["current"]) == report["current_monthly"] == D("1400")
    assert total(details["proposed"]) == report["proposed_monthly"] == D("2725")
    assert total(details["upfront"]) == report["upfront"] == D("2400")
    assert total(details["balances"]) == report["current_liquid"] == D("7500")
    assert details["checking"] == D("4500")
    assert details["savings"] == D("3000")
    assert details["earmarked_goals"] == D("600")
    assert details["planned_goal_contributions"] == D("100")
    assert report["available_for_upfront"] == D("4500")
    assert report["remaining_liquid"] == D("5100")
    assert details["upfront_from_checking"] == D("2400")
    assert details["upfront_from_savings"] == D(0)
    assert all(x["status"] in ("fictional", "confirmed_zero")
               for x in details["upfront"])


def test_missing_and_entered_zero_are_not_equivalent():
    incomplete = {"income": 3000, "current_housing": 0, "rent": 1200,
                  "checking": 0}
    report = compare_moving(incomplete, source="entered")
    d = report["details"]
    assert next(x for x in d["current"]
                if x["field"] == "current_housing")["status"] == "confirmed_zero"
    assert next(x for x in d["current"]
                if x["field"] == "other_living")["status"] == "missing"
    assert next(x for x in d["balances"]
                if x["field"] == "savings")["status"] == "missing"
    assert "other_living" in report["missing"]
    assert report["fundable"]


def test_reuse_profile_maps_current_only_and_excludes_goals():
    blocks = default_blocks()
    before = deepcopy(blocks)
    rent = suggest_housing_id(blocks)
    assert rent == "rent"
    mapped = profile_to_moving(blocks, rent)
    v = mapped["values"]
    assert v["income"] == "3800.00"
    assert v["current_housing"] == "1350.00"
    assert v["other_living"] == "650.00"
    assert v["minimum_debt"] == "470.00"
    assert v["checking"] == "2200.00"
    assert v["savings"] == "1200.00"
    assert v["rent"] is None
    assert v["security_deposit"] is None
    assert "roth" not in mapped["eligible_savings_ids"]
    assert "vacation" not in mapped["eligible_savings_ids"]
    assert blocks == before
    unknown = profile_to_moving(blocks, None)
    assert unknown["values"]["current_housing"] is None


def test_debt_expense_double_count_is_avoided_when_loans_already_recorded():
    blocks = [
        {"id": "cash", "kind": "cash", "name": "Checking", "balance": 0},
        {"id": "pay", "kind": "income", "name": "Take-home", "monthly_amount": 3000},
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": 1200},
        {"id": "food", "kind": "expense", "name": "Food", "monthly_amount": 200},
        {"id": "loanexpense", "kind": "expense", "name": "Loan payment", "monthly_amount": 150},
        {"id": "loan", "kind": "loan", "name": "Student loan", "balance": 5000,
         "annual_rate": 5, "monthly_payment": 150},
    ]
    mapped = profile_to_moving(blocks, "rent")
    assert mapped["values"]["other_living"] == "200.00"
    assert mapped["values"]["minimum_debt"] == "150.00"
    assert any("double counting" in note for note in mapped["notes"])


def test_opt_in_profile_import_adds_current_not_hypothetical():
    original = []
    plan = review_profile_changes(original, SAMPLE)
    assert not any(p["field"] == "rent" for p in plan)
    assert any(p["field"] == "current_housing" for p in plan)
    original_copy = deepcopy(original)
    # Approval is explicit and must be performed for each item.
    actions = {p["field"]: "apply" for p in plan if p["action"] != "conflict"}
    count = iter(range(10))
    updated = apply_reviewed_profile_changes(
        original, plan, actions,
        id_factory=lambda: f"new_{next(count)}",
    )
    assert original == original_copy
    assert len(updated) == len(actions)
    assert any(b["name"] == "Current housing" for b in updated)
    assert not any(b["name"] == "Proposed rent" for b in updated)
    repeated_plan = review_profile_changes(updated, SAMPLE)
    assert all(item["action"] == "update" for item in repeated_plan
               if item["field"] in ("income", "current_housing", "checking"))
    with pytest.raises(ValueError, match="at least one"):
        apply_reviewed_profile_changes(updated, repeated_plan, {})


def test_profile_update_requires_explicit_approval_and_no_multi_block_overwrite():
    blocks = default_blocks()
    before = deepcopy(blocks)
    plan = review_profile_changes(blocks, SAMPLE)
    assert next(p for p in plan if p["field"] == "other_living")["action"] == "conflict"
    assert next(p for p in plan if p["field"] == "minimum_debt")["action"] == "conflict"
    with pytest.raises(ValueError):
        apply_reviewed_profile_changes(blocks, plan, {"other_living": "apply"})
    assert blocks == before


def test_workspace_version_three_contains_editable_moving_inputs_not_cached_results():
    snapshot = [{
        "kind": "moving", "source": "entered",
        "values": {"income": "3000", "current_housing": "0", "rent": "1200",
                   "savings": None},
        "reviewed": False, "allow_savings": False,
        "include_goals": False, "variation": {"rent": "1000"},
    }]
    text = workspace_to_json([], [], snapshot)
    payload = json.loads(text)
    assert payload["schema_version"] == 3
    assert "decision_drafts" in payload
    assert "results" not in payload
    assert workspace_from_json_full(text) == (
        [], [], validated_decision_drafts(snapshot)
    )
    assert workspace_from_json_full(workspace_to_json([], [])) == ([], [], [])
    assert "schema_version" in workspace_to_json([], [])


@pytest.mark.parametrize("bad", [
    [{"kind": "moving"}],
    [{"kind": "moving", "source": "entered", "values": {"password": "secret"},
      "allow_savings": False, "include_goals": False,
      "reviewed": False, "variation": None}],
    [{"kind": "moving", "source": "entered", "values": {"rent": "NaN"},
      "allow_savings": False, "include_goals": False,
      "reviewed": False, "variation": None}],
])
def test_invalid_moving_draft_rejected(bad):
    with pytest.raises(ValueError):
        validated_decision_drafts(bad)


def test_restoring_decision_removes_stale_results_and_keeps_missing():
    state = {
        "move_start_mode": "Enter my own numbers",
        "move_income": 3600.0,
        "move_rent": 1400.0,
        "move_checking": None,
        "move_result": {"fake": "stale"},
        "move_inputs_at_run": {"income": 3600, "rent": 1500},
        "move_use_savings": False,
    }
    drafts = capture_decision_drafts(state)
    target = {"move_result": {"old": 1}, "move_rent": 900}
    restore_decision_drafts(target, drafts)
    assert "move_result" not in target
    assert target["move_editing"] is True
    assert target["move_start_mode"] == "Enter my own numbers"
    assert target["move_income"] == 3600.0
    assert target["move_rent"] == 1400.0  # unsubmitted edit takes precedence over stale result
    assert "move_checking" not in target



def test_guest_recurring_cost_draft_roundtrip_with_no_profile():
    state = {
        "ml_blocks": [], "dc_guest_compared": True,
        "dc_guest_cost": 45.0, "dc_guest_income": 3000.0,
        "dc_guest_spending": 1000.0, "dc_guest_checking": 500.0,
        "dc_guest_cost_kind": "recurring", "dc_guest_frequency": "monthly",
    }
    drafts = capture_decision_drafts(state)
    assert len(drafts) == 1 and drafts[0]["kind"] == "cost"
    assert D(drafts[0]["values"]["cost"]) == D("45")
    data = workspace_to_json([], [], drafts)
    blocks, scenarios, restored = workspace_from_json_full(data)
    assert blocks == [] and scenarios == []
    target = {"dc_guest_cost": 900.0, "dc_guest_compared": True}
    restore_decision_drafts(target, restored)
    assert target["dc_guest_cost"] == 45.0
    assert target["dc_guest_income"] == 3000.0
    assert target["dc_guest_cost_kind"] == "recurring"
    assert not target["dc_guest_compared"]
    assert target["ml_restored_cost"]


def test_profile_cost_draft_does_not_duplicate_profile_blocks():
    blocks = default_blocks()
    state = {
        "ml_blocks": deepcopy(blocks), "dc_profile_compared": True,
        "dc_profile_source": "Use My Money figures",
        "dc_cost_value": 60.0, "dc_cost_kind": "Recurring commitment",
        "dc_cost_frequency": "weekly",
    }
    drafts = capture_decision_drafts(state)
    assert drafts[0]["source"] == "profile"
    loaded, _, decision = workspace_from_json_full(
        workspace_to_json(blocks, [], drafts)
    )
    target = {}
    restore_decision_drafts(target, decision)
    assert target["dc_cost_value"] == 60.0
    assert target["dc_cost_frequency"] == "weekly"
    assert target["dc_profile_source"] == "Use My Money figures"
    assert len(loaded) == len(blocks)


def test_malformed_saved_cost_amount_and_frequency_rejected():
    normal = {
        "kind": "cost", "source": "entered", "values": {"cost": "100"},
        "cost_type": "recurring", "frequency": "monthly",
    }
    for changes in (
        {"values": {"cost": "NaN"}},
        {"values": {"cost": "-1"}},
        {"frequency": "every_eon"},
        {"secret": "user-data"},
    ):
        with pytest.raises(ValueError):
            validated_decision_drafts([{**normal, **changes}])
