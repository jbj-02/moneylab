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


def validated_decision_drafts(drafts):
    """Validate transient decision assumptions for portable schema v3.

    No free-form descriptions, computed forecasts, or third-party responses
    are exported. A restored scenario must be re-run by the user.
    """
    from moneylab.moving import FIELDS, SIGNED, _decimal
    if not isinstance(drafts, list) or len(drafts) > 3:
        raise ValueError("A workspace may contain up to three decision drafts.")
    seen = set()
    output = []
    for draft in drafts:
        if not isinstance(draft, dict):
            raise ValueError("Unsupported decision draft fields.")
        kind, source = draft.get("kind"), draft.get("source")
        if kind == "cost":
            from moneylab.cadence import FREQUENCIES
            if (set(draft) != {
                "kind", "source", "values", "cost_type", "frequency"
            } or kind in seen or source not in ("entered", "profile")
                or draft["cost_type"] not in ("one_time", "recurring")
                or draft["frequency"] not in FREQUENCIES):
                raise ValueError("Unsupported saved cost decision.")
            values = draft["values"]
            allowed_cost = {"cost", "income", "spending", "checking", "savings"}
            if not isinstance(values, dict) or set(values) - allowed_cost:
                raise ValueError("Unsupported cost decision fields.")
            cleaned = {}
            for key, value in values.items():
                if value is None:
                    cleaned[key] = None
                    continue
                if isinstance(value, bool):
                    raise ValueError("Invalid cost scenario amount.")
                try:
                    number = Decimal(str(value))
                except (TypeError, ValueError, ArithmeticError):
                    raise ValueError("Invalid cost scenario amount.") from None
                if (not number.is_finite() or number < 0
                        or number > Decimal("100000000")
                        or number != number.quantize(Decimal("0.01"))):
                    raise ValueError("Invalid cost scenario amount.")
                cleaned[key] = str(number)
            seen.add(kind)
            output.append({
                "kind": kind, "source": source, "values": cleaned,
                "cost_type": draft["cost_type"],
                "frequency": draft["frequency"],
            })
            continue
        if set(draft) != {
            "kind", "source", "values", "allow_savings",
            "include_goals", "reviewed", "variation",
        }:
            raise ValueError("Unsupported decision draft fields.")
        if kind != "moving" or kind in seen or source not in (
            "entered", "fictional", "profile"
        ):
            raise ValueError("Unsupported or repeated decision draft.")
        seen.add(kind)
        if any(not isinstance(draft[key], bool)
               for key in ("allow_savings", "include_goals", "reviewed")):
            raise ValueError("Decision confirmation flags must be boolean.")
        def sanitize(data):
            if not isinstance(data, dict) or set(data) - set(FIELDS):
                raise ValueError("Unexpected decision amount or field.")
            return {
                key: None if val is None else str(
                    _decimal(val, key, signed=key in SIGNED)
                )
                for key, val in data.items()
            }
        raw = sanitize(draft["values"])
        variation = (
            sanitize(draft["variation"])
            if draft["variation"] is not None else None
        )
        output.append({
            "kind": kind, "source": source, "values": raw,
            "allow_savings": draft["allow_savings"],
            "include_goals": draft["include_goals"],
            "reviewed": draft["reviewed"], "variation": variation,
        })
    return output


def workspace_to_json(blocks, scenarios, decision_drafts=None):
    """Version 2 by default; version 3 explicitly includes decision drafts."""
    blocks = serialize_blocks(blocks)
    saved = validated_scenarios(blocks, scenarios)
    if decision_drafts is None:
        payload = {
            "schema_version": 2, "blocks": blocks, "scenarios": saved,
        }
    else:
        payload = {
            "schema_version": 3, "blocks": blocks, "scenarios": saved,
            "decision_drafts": validated_decision_drafts(decision_drafts),
        }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def workspace_from_json_full(text):
    """Return blocks, named scenarios, and optionally reviewed decision drafts."""
    if not isinstance(text, str) or len(text) > 200_000:
        raise ValueError("Workspace file exceeds the supported size limit.")
    try:
        payload = json.loads(text)
    except (ValueError, TypeError, RecursionError):
        raise ValueError("File is not valid JSON.") from None
    if not isinstance(payload, dict):
        raise ValueError("Workspace must be an object.")
    version = payload.get("schema_version")
    if version == 1:
        return profile_from_json(text), [], []
    expected = (
        {"schema_version", "blocks", "scenarios"}
        if version == 2 else
        {"schema_version", "blocks", "scenarios", "decision_drafts"}
    )
    if version not in (2, 3) or set(payload) != expected:
        raise ValueError(
            "Unsupported workspace version or unexpected fields. "
            "Use a MoneyLab JSON workspace export."
        )
    blocks = serialize_blocks(payload["blocks"])
    scenarios = validated_scenarios(blocks, payload["scenarios"])
    drafts = (validated_decision_drafts(payload["decision_drafts"])
              if version == 3 else [])
    return blocks, scenarios, drafts


def workspace_from_json(text):
    """Backward-compatible two-part import for older callers."""
    blocks, scenarios, _ = workspace_from_json_full(text)
    return blocks, scenarios
