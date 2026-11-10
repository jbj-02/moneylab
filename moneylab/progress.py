"""Dated selected-plan records and read-only progress until explicit approval."""
import calendar
from copy import deepcopy
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
import re

from moneylab.blocks import project_blocks, serialize_blocks
from moneylab.engine import ZERO, validate_money
from moneylab.planning import apply_preview, preview


def add_months(start, months):
    index = start.year * 12 + start.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(start.day, calendar.monthrange(year, month + 1)[1]))


def whole_months(start, end):
    if end < start:
        raise ValueError("A check-in cannot be before the selected plan's start date.")
    months = (end.year - start.year) * 12 + end.month - start.month
    return months - (add_months(start, months) > end)


def validate_tracking(record):
    if record is None:
        return None
    if not isinstance(record, dict) or not {"started_on", "last_as_of", "blocks"}.issubset(record) or set(record) - {"started_on", "last_as_of", "blocks", "due_dates"}:
        raise ValueError("Unsupported selected-plan record.")
    try:
        start = date.fromisoformat(record["started_on"])
        last = date.fromisoformat(record["last_as_of"])
    except (TypeError, ValueError):
        raise ValueError("Selected-plan dates must be real calendar dates.") from None
    if last < start or whole_months(start, last) > 600:
        raise ValueError("Selected-plan dates are outside the supported horizon.")
    try:
        blocks = serialize_blocks(record["blocks"])
    except (TypeError, KeyError, ArithmeticError):
        raise ValueError("Selected-plan financial details are invalid.") from None
    dates = record.get("due_dates", {g["id"]: add_months(start, g["target_months"]).isoformat() for g in blocks if g["kind"] == "goal"})
    if not isinstance(dates, dict) or len(dates) > 50:
        raise ValueError("Unsupported goal deadlines in selected plan.")
    normalized = {}
    for ident, raw in dates.items():
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ident):
            raise ValueError("Unsupported selected goal ID.")
        try:
            normalized[ident] = date.fromisoformat(raw).isoformat()
        except (TypeError, ValueError):
            raise ValueError("Selected goal deadlines must be real dates.") from None
    return {"started_on": start.isoformat(), "last_as_of": last.isoformat(), "blocks": blocks, "due_dates": normalized}


def select_plan(blocks, started_on):
    return validate_tracking({"started_on": started_on.isoformat(), "last_as_of": started_on.isoformat(),
                              "blocks": serialize_blocks(blocks)})


def tracking_signature(record):
    return sha256(json.dumps(validate_tracking(record), sort_keys=True).encode()).hexdigest()


def remaining_months(as_of, due):
    """Whole future model steps on or before the actual calendar deadline."""
    return 0 if as_of >= due else whole_months(as_of, due)


def progress_preview(blocks, record, goal_id, balance, as_of):
    record = validate_tracking(record)
    if record is None:
        raise ValueError("Choose a plan before comparing progress.")
    start, last = date.fromisoformat(record["started_on"]), date.fromisoformat(record["last_as_of"])
    if as_of < last:
        raise ValueError("Use a check-in date on or after your last accepted check-in.")
    elapsed = whole_months(start, as_of)
    if elapsed > 600:
        raise ValueError("Progress comparisons support up to 600 months.")
    baseline_goal = next((g for g in record["blocks"] if g["id"] == goal_id and g["kind"] == "goal"), None)
    reference = serialize_blocks(blocks)
    candidate = serialize_blocks(blocks)
    current_goal = next((g for g in candidate if g["id"] == goal_id and g["kind"] == "goal"), None)
    if baseline_goal is None or current_goal is None:
        raise ValueError("This goal is no longer in both the selected plan and current profile.")
    value = validate_money(balance, "Recorded goal balance")
    expected = project_blocks(record["blocks"], max(1, elapsed))["monthly_records"][elapsed]["balances"][goal_id]
    current_goal["balance"] = str(value)
    overdue, partial = [], []
    due_dates = {}
    for goal in (g for g in candidate if g["kind"] == "goal"):
        saved_date = record["due_dates"].get(goal["id"])
        due = date.fromisoformat(saved_date) if saved_date else add_months(last, goal["target_months"])
        # Respect an explicitly edited relative deadline. Otherwise retain the
        # original date, so frequent mid-month check-ins cannot move it.
        if saved_date and goal["target_months"] != max(1, remaining_months(last, due)):
            due = add_months(last, goal["target_months"])
        due_dates[goal["id"]] = due.isoformat()
        remaining = remaining_months(as_of, due)
        if as_of >= due and Decimal(goal["balance"]) < Decimal(goal["target"]):
            overdue.append(goal["name"])
        elif remaining == 0 and Decimal(goal["balance"]) < Decimal(goal["target"]):
            partial.append(goal["name"])
        # The engine requires at least one future month; overdue remains explicit.
        goal["target_months"] = max(remaining, 1)
        next(g for g in reference if g["id"] == goal["id"])["target_months"] = goal["target_months"]
    comparison = preview(blocks, candidate, title=f"Progress check-in for {current_goal['name']}")
    # Both displayed outlooks start at the check-in date and use the same
    # remaining deadlines. The source signature still protects the real profile.
    comparison["comparison_source_blocks"] = reference
    comparison["baseline"] = project_blocks(reference, comparison["alternative"]["summary"]["months"])
    comparison["tracking_signature"] = tracking_signature(record)
    comparison["tracking_update"] = {**deepcopy(record), "last_as_of": as_of.isoformat(), "due_dates": due_dates}
    comparison["progress"] = {
        "goal_id": goal_id, "expected": expected, "recorded": value,
        "difference": value - expected, "behind": max(expected - value, ZERO),
        "elapsed_months": elapsed, "as_of": as_of.isoformat(), "overdue": overdue, "partial_deadlines": partial,
    }
    return comparison


def accept_comparison(blocks, comparison, metadata, *, on_date):
    """Atomically validate both profile and selected schedule before committing."""
    if comparison.get("tracking_signature") and comparison["tracking_signature"] != tracking_signature(metadata.get("accepted_plan")):
        raise ValueError("Your selected plan changed. Compare progress again before approving it.")
    updated = apply_preview(blocks, comparison)
    record = (validate_tracking(comparison["tracking_update"]) if comparison.get("tracking_update")
              else select_plan(updated, on_date))
    return updated, {**deepcopy(metadata), "accepted_plan": record}
