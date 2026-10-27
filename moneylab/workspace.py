"""Portable MoneyLab workspace snapshots with saved what-if scenarios.

Schema 2 preserves the full validated set of blocks and up to 20 named
single-expense simulations. Schema 1 profile imports remain compatible.
Saved scenarios do not mutate the underlying profile.
"""

import json
from decimal import Decimal

from moneylab.blocks import modify_expense, serialize_blocks, profile_from_json
from moneylab.engine import validate_money

MAX_SCENARIOS = 20


def validated_scenarios(blocks, scenarios):
    if not isinstance(scenarios, list) or len(scenarios) > MAX_SCENARIOS:
        raise ValueError("Saved scenarios must be a list of no more than 20.")
    ids = {item["id"]: item for item in serialize_blocks(blocks)}
    result, used = [], set()
    for record in scenarios:
        if not isinstance(record, dict) or set(record) != {"name", "expense_id", "monthly_change"}:
            raise ValueError("Each scenario needs name, expense_id and monthly_change.")
        name, ident = record["name"], record["expense_id"]
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            raise ValueError("Scenario name must contain 1–60 characters.")
        name = name.strip()
        if name in used:
            raise ValueError("Scenario names must be unique.")
        used.add(name)
        if not isinstance(ident, str) or ids.get(ident, {}).get("kind") != "expense":
            raise ValueError("Saved scenarios must reference an existing expense block.")
        try:
            delta = Decimal(str(record["monthly_change"]))
        except (ValueError, ArithmeticError):
            raise ValueError("Invalid monthly scenario change.") from None
        if not delta.is_finite():
            raise ValueError("Monthly scenario change must be finite.")
        # Validate resulting amount without changing the original blocks.
        modify_expense(blocks, ident, delta)
        result.append({
            "name": name, "expense_id": ident,
            "monthly_change": str(delta.quantize(Decimal("0.01"))),
        })
    return result


def workspace_to_json(blocks, scenarios):
    blocks = serialize_blocks(blocks)
    saved = validated_scenarios(blocks, scenarios)
    return json.dumps({
        "schema_version": 2, "blocks": blocks, "scenarios": saved,
    }, ensure_ascii=False, indent=2)


def workspace_from_json(text):
    if not isinstance(text, str) or len(text) > 200_000:
        raise ValueError("Workspace file is too large.")
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        raise ValueError("File is not valid JSON.") from None
    if not isinstance(payload, dict):
        raise ValueError("Workspace must be an object.")
    if payload.get("schema_version") == 1:
        return profile_from_json(text), []
    if set(payload) != {"schema_version", "blocks", "scenarios"} or payload["schema_version"] != 2:
        raise ValueError("Unsupported workspace version or fields.")
    blocks = serialize_blocks(payload["blocks"])
    return blocks, validated_scenarios(blocks, payload["scenarios"])
