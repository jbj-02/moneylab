"""MoneyLab Decision Check: explainable tradeoffs, not financial advice.

Scenarios run exclusively through the existing validated Decimal financial engine.
Nothing here mutates the original profile. One-time costs come out of recorded
checking/cash only; no borrowing, sale of investments or savings transfers is
invented. Monthly forecasts do not model intra-month bill/paycheck timing.
"""
from decimal import Decimal, ROUND_CEILING

from moneylab.blocks import MAX_BLOCKS, project_blocks, validate_blocks
from moneylab.cadence import monthly_equivalent
from moneylab.checkin import build_checkin

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def amount(value, label="Cost"):
    """Strict finite positive cent amount for proposed financial decisions."""
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a monetary amount.")
    try:
        candidate = Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        raise ValueError(f"{label} must be a monetary amount.") from None
    if not candidate.is_finite() or not ZERO < candidate <= Decimal("1000000000"):
        raise ValueError(f"{label} must be greater than zero and at most $1 billion.")
    if candidate != candidate.quantize(CENT):
        raise ValueError(f"{label} must have no more than two decimal places.")
    return candidate


def _new_expense(blocks, recurring_monthly):
    if len(blocks) >= MAX_BLOCKS:
        raise ValueError("The profile is at its block limit.")
    used = {item["id"] for item in blocks}
    ident = "decision_cost"
    index = 1
    while ident in used:
        ident = f"decision_cost_{index}"
        index += 1
    return [*blocks, {
        "id": ident, "kind": "expense",
        "name": "Decision Check: hypothetical commitment",
        "monthly_amount": str(recurring_monthly),
    }]


def _cash_purchase(blocks, price):
    """Deduct a one-time amount from cash blocks; refuse unsupported funding."""
    available = sum((b["balance"] for b in blocks if b["kind"] == "cash"), ZERO)
    if price > available:
        return None, available
    remaining = price
    updated = []
    for item in blocks:
        entry = dict(item)
        if entry["kind"] == "cash" and remaining > ZERO:
            portion = min(entry["balance"], remaining)
            entry["balance"] -= portion
            remaining -= portion
        updated.append(entry)
    return updated, available


def decision_check(blocks, *, cost, cost_type, months=24, frequency="monthly",
                   reviewed=False):
    """Project a new cost while preserving the baseline and goals.

    A one-time cost assumes payment immediately from *recorded checking only*.
    Recurring costs start now and repeat at monthly-average cadence. A monthly
    projected comparison is not a daily cash availability guarantee.
    """
    records = validate_blocks(blocks)
    proposed = amount(cost)
    baseline = project_blocks(records, months)
    base_check = build_checkin(records, baseline, reviewed=reviewed)
    if cost_type not in ("one_time", "recurring"):
        raise ValueError("Choose one-time or recurring cost.")
    monthly = monthly_equivalent(proposed, frequency) if cost_type == "recurring" else ZERO
    initial_cash = sum((item["balance"] for item in records if item["kind"] == "cash"), ZERO)
    if cost_type == "one_time":
        altered, recorded_cash = _cash_purchase(records, proposed)
        if altered is None:
            return {
                "comparable": False, "reason": (
                    "Recorded checking/cash cannot cover this one-time purchase. "
                    "MoneyLab won't assume borrowing, withdrawing from a savings "
                    "account, or an outside payment source."
                ),
                "cost": proposed, "monthly_equivalent": ZERO,
                "available_checking": recorded_cash, "reviewed": reviewed,
                "baseline_checkin": base_check, "baseline": baseline,
            }
    else:
        altered = _new_expense(records, monthly)
    alternative = project_blocks(altered, months)
    after_check = build_checkin(altered, alternative, reviewed=reviewed)
    before, after = baseline["summary"], alternative["summary"]
    new_unfunded = max(
        (row["unfunded_shortfall"] for row in alternative["monthly_records"][1:]),
        default=ZERO,
    )
    baseline_unfunded = max(
        (row["unfunded_shortfall"] for row in baseline["monthly_records"][1:]),
        default=ZERO,
    )
    baseline_goals = {goal["id"]: goal for goal in baseline["goals"]}
    changed_goals = []
    for item in alternative["goals"]:
        prior = baseline_goals[item["id"]]
        if item["projected_at_deadline"] != prior["projected_at_deadline"] or (
            item["on_track"] != prior["on_track"]
        ):
            changed_goals.append({
                "name": item["name"],
                "before": prior["projected_at_deadline"],
                "after": item["projected_at_deadline"],
                "previous_on_track": prior["on_track"],
                "on_track": item["on_track"],
            })
    cautions = []
    if base_check["missing"]:
        cautions.append("Missing core financial blocks: " + "; ".join(base_check["missing"]))
    if not reviewed:
        cautions.append("The current profile has not been manually reviewed.")
    if cost_type == "one_time":
        cautions.append(
            "One-time cost is deducted from current checking/cash. The projection "
            "does not model an exact purchase date or transfers from other accounts."
        )
    else:
        cautions.append(
            "Recurring cost is modeled as a constant monthly average. "
            "Yearly bills still occur as actual yearly payments."
        )
    if new_unfunded > baseline_unfunded:
        cautions.append("This decision increases an unfunded modeled cash shortfall.")
    if any(g["on_track"] is False for g in alternative["goals"]):
        cautions.append("One or more goals still miss their targets under this scenario.")
    if any(g["on_track"] is None for g in alternative["goals"]):
        cautions.append("Some goal deadlines are beyond the chosen projection horizon.")
    if cost_type == "recurring" and (
        after["monthly_income"] < after["monthly_expenses"] + after["first_month_loan_payments"]
    ):
        cautions.append("New recurring obligations exceed modeled take-home income.")
    return {
        "comparable": True, "cost": proposed, "cost_type": cost_type,
        "monthly_equivalent": monthly, "available_checking": initial_cash,
        "remaining_checking_now": initial_cash - proposed if cost_type == "one_time" else initial_cash,
        "reviewed": reviewed, "baseline": baseline, "alternative": alternative,
        "baseline_checkin": base_check, "alternative_checkin": after_check,
        "monthly_buffer_before": before["unallocated_monthly_buffer"],
        "monthly_buffer_after": after["unallocated_monthly_buffer"],
        "monthly_buffer_change": (
            after["unallocated_monthly_buffer"] - before["unallocated_monthly_buffer"]
        ),
        "ending_cash_change": after["ending_cash_savings"] - before["ending_cash_savings"],
        "ending_net_change": after["ending_net_position"] - before["ending_net_position"],
        "new_unfunded_shortfall": new_unfunded,
        "baseline_unfunded_shortfall": baseline_unfunded,
        "goals_affected": changed_goals,
        "cautions": cautions,
        "needs_attention": bool(
            new_unfunded > baseline_unfunded
            or (cost_type == "recurring" and after["monthly_income"] <
                after["monthly_expenses"] + after["first_month_loan_payments"])
            or any(x["on_track"] is False and x["previous_on_track"] is True
                   for x in changed_goals)
        ),
        "preliminary": (not reviewed or bool(base_check["missing"])),
    }


def emergency_readiness(blocks, *, target_months=3, build_months=12,
                        reviewed=False, horizon=24):
    """Compare *recorded liquid funds* against a user-selected months target.

    This is an arithmetic gap, not an endorsed reserve level or a modeled
    future savings plan. It does not include earmarked goals or retirement.
    """
    if isinstance(target_months, bool) or not isinstance(target_months, int) or not 1 <= target_months <= 24:
        raise ValueError("Reserve target must be between 1 and 24 months.")
    if isinstance(build_months, bool) or not isinstance(build_months, int) or not 1 <= build_months <= 120:
        raise ValueError("Savings timeline must be between 1 and 120 months.")
    entries = validate_blocks(blocks)
    result = project_blocks(entries, horizon)
    checkin = build_checkin(entries, result, reviewed=reviewed)
    if checkin["coverage_months"] is None:
        return {"evaluable": False, "reason": (
            "Add a checking/cash balance and recorded monthly expenses or loan "
            "payments before comparing emergency savings."
        ), "checkin": checkin}
    outflows = checkin["recorded_monthly_outflow"]
    funds = checkin["accessible_starting_funds"]
    target = outflows * Decimal(target_months)
    gap = max(target - funds, ZERO)
    monthly_needed = (gap / Decimal(build_months)).quantize(
        CENT, rounding=ROUND_CEILING,
    )
    buffer = result["summary"]["unallocated_monthly_buffer"]
    return {
        "evaluable": True, "checkin": checkin,
        "recorded_monthly_outflow": outflows,
        "eligible_starting_funds": funds,
        "coverage_months": checkin["coverage_months"],
        "target_months": target_months, "target_funds": target,
        "gap": gap, "build_months": build_months,
        "average_additional_monthly_amount": monthly_needed,
        "first_month_unallocated_buffer": buffer,
        "within_first_month_buffer": monthly_needed <= buffer,
        "preliminary": (not reviewed or bool(checkin["missing"])),
    }


def goal_next_step(blocks, goal_id, *, months=24, reviewed=False):
    """Search for the smallest *additional* monthly goal contribution within
    the first month's recorded unallocated buffer. This is a trial scenario,
    not a guaranteed schedule of deposits or recommended transfer order.
    """
    entries = validate_blocks(blocks)
    goal = next((item for item in entries
                 if item["kind"] == "goal" and item["id"] == goal_id), None)
    if goal is None:
        raise ValueError("Choose a savings goal in your profile.")
    horizon = max(months, goal["target_months"])
    baseline = project_blocks(entries, horizon)
    check = build_checkin(entries, baseline, reviewed=reviewed)
    existing = next(x for x in baseline["goals"] if x["id"] == goal_id)
    gap = existing["gap_at_deadline"]
    if existing["on_track"]:
        return {
            "on_track": True, "goal": goal, "goal_projection": existing,
            "additional_monthly": ZERO, "proposed_contribution": goal["monthly_contribution"],
            "feasible_with_buffer": True, "first_month_buffer": baseline["summary"]["unallocated_monthly_buffer"],
            "checkin": check, "forecast": baseline,
        }
    available = baseline["summary"]["unallocated_monthly_buffer"]
    if available <= ZERO:
        return {
            "on_track": False, "goal": goal, "goal_projection": existing,
            "gap": gap, "additional_monthly": None, "feasible_with_buffer": False,
            "first_month_buffer": available, "checkin": check,
        }
    limit = int(available / CENT)
    def simulate(extra_cents):
        revised = []
        for block in entries:
            if block["id"] == goal_id:
                updated = dict(block)
                updated["monthly_contribution"] += Decimal(extra_cents) * CENT
                revised.append(updated)
            else:
                revised.append(block)
        return project_blocks(revised, horizon)
    maximum = simulate(limit)
    if not next(x for x in maximum["goals"] if x["id"] == goal_id)["on_track"]:
        return {
            "on_track": False, "goal": goal, "goal_projection": existing,
            "gap": gap, "additional_monthly": None, "feasible_with_buffer": False,
            "first_month_buffer": available, "checkin": check,
        }
    low, high = 0, limit
    while low < high:
        mid = (low + high) // 2
        candidate = simulate(mid)
        status = next(x for x in candidate["goals"] if x["id"] == goal_id)["on_track"]
        if status:
            high = mid
        else:
            low = mid + 1
    increment = Decimal(low) * CENT
    forecast = simulate(low)
    return {
        "on_track": False, "goal": goal, "goal_projection": existing,
        "gap": gap, "additional_monthly": increment,
        "proposed_contribution": goal["monthly_contribution"] + increment,
        "feasible_with_buffer": True,
        "first_month_buffer": available, "checkin": check, "forecast": forecast,
    }


def next_best_step(blocks, *, months=24, reviewed=False,
                   reserve_target_months=3):
    """Choose one deterministic, prioritized action; never use a fake score."""
    entries = validate_blocks(blocks)
    if not entries:
        return {"id": "start", "title": "Start with your financial picture",
                "why": "A few income, expense and cash entries unlock useful comparisons.",
                "action": "quick_start"}
    projection = project_blocks(entries, months)
    check = build_checkin(entries, projection, reviewed=reviewed)
    if check["missing"]:
        return {"id": "complete", "title": "Fill in the most useful missing detail",
                "why": check["missing"][0], "action": "quick_start"}
    if not reviewed:
        return {"id": "review", "title": "Confirm your financial inputs",
                "why": "Your results are estimates until you review the amounts and missing bills.",
                "action": "review"}
    summary = projection["summary"]
    if (summary["monthly_income"] <
            summary["monthly_expenses"] + summary["first_month_loan_payments"]):
        return {"id": "deficit", "title": "Explore your monthly spending gap",
                "why": "Recorded recurring obligations exceed modeled monthly take-home pay.",
                "action": "decisions"}
    if any(row["unfunded_shortfall"] > ZERO for row in projection["monthly_records"][1:]):
        return {"id": "shortfall", "title": "Investigate a projected cash shortfall",
                "why": "At least one modeled month ends with an unfunded balance.",
                "action": "decisions"}
    if any(row["negative_amortization"] for row in projection["monthly_records"][1:]):
        return {"id": "debt", "title": "Review a growing loan balance",
                "why": "At least one scheduled loan payment does not cover modeled interest.",
                "action": "my_money"}
    if any(g["on_track"] is False for g in projection["goals"]):
        return {"id": "goal", "title": "Explore a way to reach your savings goal",
                "why": "At least one goal misses its modeled deadline with current contributions.",
                "action": "goals"}
    if any(g["on_track"] is None for g in projection["goals"]):
        return {"id": "horizon", "title": "Check your longer-term goal deadline",
                "why": "The current projection stops before at least one goal deadline.",
                "action": "goals"}
    if (check["coverage_months"] is not None and
            check["coverage_months"] < Decimal(reserve_target_months)):
        return {"id": "reserves", "title": "Explore your emergency savings",
                "why": f"Recorded liquid funds cover about {check['coverage_months']} months "
                       f"of listed outflows, below the example {reserve_target_months}-month target.",
                "action": "decisions"}
    return {"id": "explore", "title": "Test a decision before you commit",
            "why": "Your reviewed modeled plan has no flagged issues in the selected horizon. "
                   "See how a new cost would affect your goals and cash.",
            "action": "decisions"}
