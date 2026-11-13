"""Facts for the decision summary, derived from existing projections."""
from decimal import Decimal

from moneylab.blocks import project_blocks
from moneylab.engine import ZERO, validate_money
from moneylab.planning import preview
from moneylab.scenario_changes import apply_scenario_changes


def goal_gap_changes(before, after):
    """Compare each goal at the same deadline and distinguish existing gaps."""
    baseline = {goal["id"]: goal for goal in before["goals"]}
    for goal in after["goals"]:
        prior = baseline.get(goal["id"])
        if prior is None or prior["target_months"] != goal["target_months"]:
            continue
        yield (
            goal["name"], goal["target_months"],
            max(ZERO, prior["target"] - prior["projected_at_deadline"]),
            max(ZERO, goal["target"] - goal["projected_at_deadline"]),
        )


def purchase_feedback(blocks, price, floor=None, *, months=24):
    """Evaluate an immediate purchase using checking only."""
    price = validate_money(price, "Purchase price")
    blocks = list(blocks)
    if price <= ZERO:
        raise ValueError("Enter a purchase price above zero.")
    floor = validate_money(floor, "Checking cushion") if floor is not None else None
    checking = sum((Decimal(b["balance"]) for b in blocks if b["kind"] == "cash"), ZERO)
    facts = {
        "price": price, "checking": checking, "floor": floor,
        "after": checking - price,
        "limit": max(ZERO, checking - (floor or ZERO)),
        "comparison": None, "wait_month": None, "future_shortfall": None,
    }
    if price <= checking:
        candidate = apply_scenario_changes(blocks, [{"operation": "one_time_cash", "amount": price}])
        comparison = preview(blocks, candidate, title="One-time purchase", months=months)
        facts["comparison"] = comparison
        before = comparison["baseline"]
        prior = comparison["baseline"]["monthly_records"]
        proposed = comparison["alternative"]["monthly_records"]
        facts["future_shortfall"] = next((
            row["month"] for old, row in zip(prior[1:], proposed[1:])
            if row["unfunded_shortfall"] > old["unfunded_shortfall"]
        ), None)
    else:
        before = project_blocks(blocks, months)
    if floor is not None and facts["after"] < floor:
        for row in before["monthly_records"][1:]:
            if row["unfunded_shortfall"] > ZERO:
                break
            if row["cash_position"] >= price + floor:
                facts["wait_month"] = row["month"]
                break
    return facts
