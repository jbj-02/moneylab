"""Shared temporary scenario operations for MoneyLab.

A scenario is a validated, immutable transformation of existing financial
blocks. It supports a new recurring expense, an adjusted recorded income or
expense, and an immediate cash outflow with explicitly allowed liquid sources.
These operations are used by both Decision Check and Moving Out. They never
write session state, save profile changes, assume financing, or modify inputs.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from moneylab.blocks import MAX_BLOCKS, validate_blocks, project_blocks

CENT = Decimal("0.01")
MAX_SCENARIO_AMOUNT = Decimal("100000000.00")


def _money(value):
    if isinstance(value, bool):
        raise ValueError("Scenario amounts must be numbers.")
    try:
        number = Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError):
        raise ValueError("Scenario amount must be a number.") from None
    if not number.is_finite() or number < 0 or number > MAX_SCENARIO_AMOUNT:
        raise ValueError("Scenario amount is outside the supported range.")
    if number != number.quantize(CENT):
        raise ValueError("Scenario amounts must have at most two decimals.")
    return number


def apply_scenario_changes(blocks, changes):
    """Return entirely new, validated blocks with bounded, explicit changes.

    Supported operations:
      * set_monthly: block_id (income or expense), amount
      * add_monthly_expense: amount, optional name
      * one_time_cash: amount, allow_hysa (explicit True only)
    """
    original = validate_blocks(blocks)
    if not isinstance(changes, list) or not 1 <= len(changes) <= 16:
        raise ValueError("Supply 1–16 supported scenario changes.")
    scenario = deepcopy(original)
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("Scenario changes must be structured objects.")
        operation = change.get("operation")
        if operation == "set_monthly":
            if set(change) != {"operation", "block_id", "amount"}:
                raise ValueError("Invalid fields for monthly change.")
            key = change["block_id"]
            target = next((entry for entry in scenario if entry["id"] == key), None)
            if target is None or target["kind"] not in ("income", "expense"):
                raise ValueError("Monthly changes require an existing income or expense block.")
            target["monthly_amount"] = _money(change["amount"])
            # A changed monthly average no longer describes the old
            # weekly/biweekly schedule; drop stale period metadata.
            target.pop("frequency", None)
            target.pop("period_amount", None)
            target.pop("next_date", None)
        elif operation == "add_monthly_expense":
            if set(change) - {"operation", "amount", "name"} or "amount" not in change:
                raise ValueError("Unexpected expense-scenario fields.")
            if len(scenario) >= MAX_BLOCKS:
                raise ValueError("Your profile is already at the block limit.")
            title = change.get("name", "Hypothetical expense")
            if not isinstance(title, str) or not 1 <= len(title.strip()) <= 60:
                raise ValueError("Give the hypothetical expense a short name.")
            names = {entry["id"] for entry in scenario}
            key = "scenario_extra_cost"
            i = 1
            while key in names:
                key = f"scenario_extra_cost_{i}"
                i += 1
            scenario.append({
                "id": key, "kind": "expense", "name": title.strip(),
                "monthly_amount": _money(change["amount"]),
            })
        elif operation == "one_time_cash":
            if set(change) - {"operation", "amount", "allow_hysa"} or "amount" not in change:
                raise ValueError("Unexpected cash-scenario fields.")
            if change.get("allow_hysa", False) not in (True, False):
                raise ValueError("Savings permission must be a boolean.")
            if "allow_hysa" in change and not isinstance(change["allow_hysa"], bool):
                raise ValueError("Savings permission must be a boolean.")
            spend = _money(change["amount"])
            include_savings = change.get("allow_hysa", False) is True
            liquid = sum((item["balance"] for item in scenario if
                         item["kind"] == "cash" or
                         (include_savings and item["kind"] == "hysa")), Decimal(0))
            if spend > liquid:
                raise ValueError(
                    "An upfront scenario cannot assume borrowing or an "
                    "unapproved withdrawal from savings."
                )
            remaining = spend
            # Checking/cash always pays first. Explicitly permitted HYSAs
            # are second; retirement, goals and brokerage remain untouched.
            for eligible_kind in ("cash", "hysa") if include_savings else ("cash",):
                for item in scenario:
                    if item["kind"] != eligible_kind or remaining == 0:
                        continue
                    taken = min(item["balance"], remaining)
                    item["balance"] -= taken
                    remaining -= taken
        else:
            raise ValueError(f"Unsupported scenario operation: {operation!r}.")
    return validate_blocks(scenario)


def compare_scenario_changes(blocks, changes, months=24):
    """Evaluate baseline and alternative through the same financial engine."""
    original = validate_blocks(blocks)
    alternative = apply_scenario_changes(original, changes)
    return {
        "baseline": project_blocks(original, months),
        "alternative": project_blocks(alternative, months),
    }
