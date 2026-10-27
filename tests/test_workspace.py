"""Portable what-if workspaces preserve profiles and validated scenarios."""

import json
from decimal import Decimal

import pytest

from moneylab.blocks import default_blocks, profile_to_json, project_blocks, modify_expense
from moneylab.workspace import (
    validated_scenarios, workspace_from_json, workspace_to_json,
)


def scenario(label="Rent adjustment", delta="150"):
    return {
        "name": label,
        "expense_id": "rent",
        "monthly_change": delta,
    }


def test_version_two_workspace_roundtrip_preserves_named_scenarios():
    blocks = default_blocks()
    original = [scenario(), scenario("Cheaper apartment", "-150")]
    data = workspace_to_json(blocks, original)
    restored, saved = workspace_from_json(data)
    assert len(restored) == len(blocks)
    assert len(saved) == 2
    assert saved[0]["monthly_change"] == "150.00"
    assert saved[1]["monthly_change"] == "-150.00"
    outcome = project_blocks(modify_expense(restored, "rent", 150), 12)
    base = project_blocks(restored, 12)
    assert base["summary"]["ending_net_position"] - outcome["summary"]["ending_net_position"] == Decimal("1800.00")


def test_existing_profile_only_json_remains_supported():
    restored, scenarios = workspace_from_json(profile_to_json(default_blocks()))
    assert len(restored) == 10
    assert scenarios == []


def test_empty_profile_and_scenarios_roundtrip():
    blocks, scenarios = workspace_from_json(workspace_to_json([], []))
    assert blocks == []
    assert scenarios == []


@pytest.mark.parametrize("bad", [
    "not-json", "{}", "[]",
    '{"schema_version":2,"blocks":[],"scenarios":{}}',
    '{"schema_version":99,"blocks":[],"scenarios":[]}',
])
def test_bad_workspace_rejected(bad):
    with pytest.raises(ValueError):
        workspace_from_json(bad)


@pytest.mark.parametrize("bad_scenarios", [
    [scenario("A", 1), scenario("A", 2)],
    [scenario("Missing") | {"expense_id": "unknown"}],
    [scenario("Wrong kind") | {"expense_id": "pay"}],
    [scenario("Unbounded", "-10000000")],
    [scenario("", 2)],
    [scenario("NaN", "NaN")],
    [scenario("extra", 2) | {"color": "red"}],
])
def test_invalid_scenarios_rejected(bad_scenarios):
    with pytest.raises(ValueError):
        validated_scenarios(default_blocks(), bad_scenarios)


def test_saved_scenarios_do_not_mutate_default_profile():
    blocks = default_blocks()
    original = json.dumps(blocks)
    _ = validated_scenarios(blocks, [scenario()])
    assert json.dumps(blocks) == original


def test_20_scenario_limit():
    good = [scenario(f"Plan {index}", index) for index in range(20)]
    assert len(validated_scenarios(default_blocks(), good)) == 20
    with pytest.raises(ValueError):
        validated_scenarios(default_blocks(), good + [scenario("21", 1)])
