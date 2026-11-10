"""Presentation-independent planning and explicitly approved alternatives.

All outcomes come from project_blocks, including contribution searches. A goal
is a separate pot of money, never a second label on an existing account.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
import json

from moneylab.blocks import MAX_AMOUNT, project_blocks, serialize_blocks
from moneylab.engine import CENT, ZERO, calculate_monthly_loan_payment


def signature(blocks):
    canonical = json.dumps(serialize_blocks(blocks), sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode()).hexdigest()


def _set(blocks, ident, field, value):
    result = serialize_blocks(blocks)
    item = next((b for b in result if b["id"] == ident), None)
    if item is None:
        raise ValueError("That financial entry no longer exists.")
    item[field] = str(value)
    return serialize_blocks(result)


def goal_outlook(blocks, goal_id, *, result=None):
    """Find the smallest cent contribution that reaches a goal in this model.

    Searches include other accounts, income routing, debt payoff and shortfall
    recovery. An unreachable goal has no fabricated required contribution.
    """
    items = serialize_blocks(blocks)
    goal = next((b for b in items if b["id"] == goal_id and b["kind"] == "goal"), None)
    if goal is None:
        raise ValueError("Choose an existing savings goal.")
    deadline = goal["target_months"]
    horizon = max(deadline, min(120, deadline + 36))
    baseline = result if result and result["summary"]["months"] >= horizon else project_blocks(items, horizon)
    target = Decimal(goal["target"])

    def reached(projection):
        return projection["monthly_records"][deadline]["balances"][goal_id] >= target

    starting = Decimal(goal["balance"])
    planned = Decimal(goal["monthly_contribution"])
    at_deadline = baseline["monthly_records"][deadline]["balances"][goal_id]
    completion = next((r["month"] for r in baseline["monthly_records"]
                       if r["balances"][goal_id] >= target), None)
    # More than target dollars a month cannot improve feasibility: the engine
    # caps transfers at actual available money, including competing accounts.
    ceiling = target
    maximum = project_blocks(_set(items, goal_id, "monthly_contribution", ceiling), deadline)
    required = None
    if reached(maximum):
        lo, hi = 0, int((ceiling / CENT).to_integral_value(rounding=ROUND_CEILING))
        while lo < hi:
            mid = (lo + hi) // 2
            candidate = project_blocks(_set(items, goal_id, "monthly_contribution", mid * CENT), deadline)
            if reached(candidate):
                hi = mid
            else:
                lo = mid + 1
        required = lo * CENT
    return {
        "id": goal_id, "name": goal["name"], "target": target,
        "starting": starting, "planned": planned, "deadline": deadline,
        "projected": at_deadline, "gap": max(target - at_deadline, ZERO),
        "completion_month": completion, "searched_months": horizon,
        "required": required,
        "extra": max(required - planned, ZERO) if required is not None else None,
        "best_possible": maximum["monthly_records"][deadline]["balances"][goal_id],
        "on_track": at_deadline >= target,
    }


def preview(blocks, alternative, *, title, months=24):
    """Create a detached comparison bound to the profile that was reviewed."""
    before, after = serialize_blocks(blocks), serialize_blocks(alternative)
    deadlines = [b["target_months"] for b in before + after if b["kind"] == "goal"]
    horizon = max([months, *deadlines])
    return {
        "source_signature": signature(before), "candidate_signature": signature(after),
        "source_blocks": before, "blocks": after, "title": title,
        "baseline": project_blocks(before, horizon),
        "alternative": project_blocks(after, horizon),
    }


def apply_preview(blocks, comparison):
    """Reject stale previews; approval never reapplies or partially merges one."""
    if signature(blocks) != comparison["source_signature"]:
        raise ValueError("Your figures changed. Compare this alternative again before applying it.")
    if comparison.get("allow_apply", True) is not True:
        raise ValueError("A stress scenario cannot be applied to your plan.")
    if signature(comparison["blocks"]) != comparison.get("candidate_signature"):
        raise ValueError("The proposed changes changed. Compare this alternative again before applying it.")
    return serialize_blocks(deepcopy(comparison["blocks"]))


def goal_alternative(blocks, goal_id, monthly, *, expense_id=None, reduction=0, months=24,
                     target=None, deadline=None):
    """User-selected transfers/reductions, evaluated through the real engine."""
    from moneylab.blocks import modify_expense
    from moneylab.engine import validate_money
    value = validate_money(monthly, "Monthly goal saving")
    if value > MAX_AMOUNT:
        raise ValueError("Monthly saving is too large.")
    items = serialize_blocks(blocks)
    if not any(b["id"] == goal_id and b["kind"] == "goal" for b in items):
        raise ValueError("Choose an existing savings goal.")
    if expense_id is not None:
        cut = validate_money(reduction, "Expense reduction")
        items = modify_expense(items, expense_id, -cut)
    after = _set(items, goal_id, "monthly_contribution", value)
    goal = next(b for b in after if b["id"] == goal_id)
    if target is not None:
        goal["target"] = str(validate_money(target, "Goal target"))
    if deadline is not None:
        goal["target_months"] = deadline
    after = serialize_blocks(after)
    comparison = preview(blocks, after, title="A different savings pace", months=months)
    comparison["focus_goal_id"] = goal_id
    return comparison


def plan_actions(blocks, *, reviewed=False, months=24):
    """Rank problems before opportunities. Suggestions never spend invented cash.

    Competing goal suggestions are alternatives, not a combined allocation.
    Each must be simulated again after a different change is applied.
    """
    items = serialize_blocks(blocks)
    horizon = max([months, *[b["target_months"] for b in items if b["kind"] == "goal"]])
    baseline = project_blocks(items, horizon)
    rows, summary = baseline["monthly_records"], baseline["summary"]
    actions = []
    if not reviewed:
        actions.append({"kind": "review", "title": "Complete your financial picture",
                        "detail": "Confirm income, everyday spending, debts and balances before acting on these estimates."})
    shortfall = next((r for r in rows[1:] if r["unfunded_shortfall"] > ZERO), None)
    if shortfall:
        actions.append({"kind": "shortfall", "title": f"Cash runs short in month {shortfall['month']}",
                        "detail": f"The model has ${shortfall['unfunded_shortfall']:,.2f} of unfunded costs then. "
                                  "Test a change to a recorded expense; savings transfers already stop when cash is unavailable."})
    for loan in (b for b in items if b["kind"] == "loan"):
        interest = calculate_monthly_loan_payment(loan["balance"], loan["annual_rate"], loan["monthly_payment"])["monthly_interest"]
        if interest > Decimal(loan["monthly_payment"]):
            actions.append({"kind": "debt", "loan_id": loan["id"], "title": f"{loan['name']} is growing",
                            "detail": f"First-month interest is ${interest:,.2f}; the recorded payment is "
                                      f"${Decimal(loan['monthly_payment']):,.2f}. Check your actual loan terms before changing payments."})
    outlooks = {goal["id"]: goal_outlook(items, goal["id"], result=baseline) for goal in baseline["goals"]}
    for goal in baseline["goals"]:
        outlook = outlooks[goal["id"]]
        if outlook["on_track"]:
            continue
        if outlook["required"] is not None:
            detail = (f"At the current pace, {outlook['name']} is ${outlook['gap']:,.2f} short in month {outlook['deadline']}. "
                      f"Try ${outlook['required']:,.2f}/month (${outlook['extra']:,.2f} more). "
                      "The model can fund this alternative from recorded monthly money.")
        else:
            detail = (f"{outlook['name']} is ${outlook['gap']:,.2f} short in month {outlook['deadline']}. "
                      f"Even directing available monthly money here reaches only ${outlook['best_possible']:,.2f}. "
                      "Compare a later deadline or a reduction to an expense you recorded.")
        actions.append({"kind": "goal", "title": f"Close the gap for {outlook['name']}",
                        "detail": detail, "goal_id": goal["id"], "outlook": outlook})
    if not actions:
        actions.append({"kind": "maintain", "title": "Your recorded plan fits together",
                        "detail": "The modeled costs fit your income and the assessed goals reach their targets. "
                                  "Update your balances regularly and compare a decision before committing."})
    return {"actions": actions, "projection": baseline, "summary": summary, "goals": outlooks}
