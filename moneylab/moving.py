"""Move-versus-stay comparisons for MoneyLab alpha.

Pure Decimal calculations using project_blocks; never mutate a user profile.
Income, monthly costs, and move-upfront cash are manually provided inputs.
Optional pre-existing goals are imported *only* for scenario effects; no prior
income, debts, accounts, or routes are implicitly mixed into this estimate.
"""
from decimal import Decimal
from io import StringIO
import csv

from moneylab.blocks import project_blocks, validate_blocks

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
MAX_VALUE = Decimal("100000000.00")

MONTHLY = (
    "current_housing", "other_living", "minimum_debt",
    "rent", "utilities", "internet", "renters_insurance",
    "transport_change", "groceries_change", "other_change",
)
UPFRONT = ("security_deposit", "moving_cost", "furniture", "other_upfront")
BALANCES = ("checking", "savings")
FIELDS = ("income", *MONTHLY, *UPFRONT, *BALANCES)
REQUIRED = ("income", "current_housing", "rent")
SIGNED = ("transport_change", "groceries_change", "other_change")
LABELS = {
    "income": "monthly take-home income",
    "current_housing": "current monthly housing costs",
    "other_living": "other monthly living expenses",
    "minimum_debt": "minimum monthly debt payments",
    "rent": "proposed rent",
    "utilities": "utilities",
    "internet": "internet",
    "renters_insurance": "renter's insurance",
    "transport_change": "change in transportation spending",
    "groceries_change": "change in grocery spending",
    "other_change": "change in other living spending",
    "security_deposit": "security deposit",
    "moving_cost": "moving costs",
    "furniture": "furniture",
    "other_upfront": "other upfront charges",
    "checking": "available checking/cash",
    "savings": "available savings",
}
HORIZONS = (6, 12, 24)


def _decimal(value, field, *, signed=False):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{LABELS[field]} must be a number.")
    try:
        number = Decimal(str(value))
    except (ValueError, ArithmeticError, TypeError):
        raise ValueError(f"{LABELS[field]} must be a number.") from None
    if not number.is_finite() or abs(number) > MAX_VALUE:
        raise ValueError(f"{LABELS[field]} exceeds the supported range.")
    if number != number.quantize(CENT):
        raise ValueError(f"{LABELS[field]} must use at most two decimal places.")
    if number < ZERO and not signed:
        raise ValueError(f"{LABELS[field]} cannot be negative.")
    return number


def _projections(inputs, months, goal_blocks):
    """Generate independently validated current and proposed profiles."""
    v = inputs
    present_costs = v["current_housing"] + v["other_living"] + v["minimum_debt"]
    moving_costs = (
        v["rent"] + v["utilities"] + v["internet"] + v["renters_insurance"]
        + v["other_living"] + v["minimum_debt"]
        + v["transport_change"] + v["groceries_change"] + v["other_change"]
    )
    if moving_costs < ZERO:
        raise ValueError("Proposed monthly expenses cannot be negative.")
    if (v["other_living"] + v["transport_change"] +
            v["groceries_change"] + v["other_change"] < ZERO):
        raise ValueError(
            "Changes to transport, groceries and other spending cannot "
            "reduce your combined everyday expenses below zero."
        )
    upfront = sum((v[k] for k in UPFRONT), ZERO)
    checking, savings = v["checking"], v["savings"]
    use_savings = v["use_savings_for_upfront"]
    available = checking + (savings if use_savings else ZERO)
    shortfall = max(upfront - available, ZERO)
    # A net cash gap cannot be interpreted as financing. The baseline remains
    # calculable but the post-move projection is unavailable.
    goals = list(goal_blocks)
    reserved = {g["id"] for g in goals}
    def unique(base):
        key, counter = f"moving_{base}", 1
        while key in reserved:
            key = f"moving_{base}_{counter}"
            counter += 1
        reserved.add(key)
        return key
    salary_id, cash_id, savings_id, cost_id = (
        unique("income"), unique("checking"), unique("savings"), unique("cost")
    )
    base = [
        {"id": salary_id, "kind": "income", "name": "Take-home pay",
         "monthly_amount": str(v["income"])},
        {"id": cash_id, "kind": "cash", "name": "Checking / available cash",
         "balance": str(checking)},
        {"id": savings_id, "kind": "hysa", "name": "Available savings",
         "balance": str(savings), "annual_rate": "0",
         "monthly_contribution": "0"},
        {"id": cost_id, "kind": "expense", "name": "Current recorded expenses",
         "monthly_amount": str(present_costs)},
        *goals,
    ]
    before = project_blocks(base, months)
    if shortfall > ZERO:
        return {
            "fundable": False, "funding_gap": shortfall,
            "upfront": upfront, "upfront_eligible_funds": available,
            "current_monthly": present_costs, "proposed_monthly": moving_costs,
            "baseline": before,
        }
    # Model the upfront move separately from recurring commitments. Savings
    # are touched only with explicit consent and only when checking runs out.
    checking_after = max(checking - upfront, ZERO)
    savings_after = savings - max(upfront - checking, ZERO) if use_savings else savings
    candidate = []
    for entry in base:
        clone = dict(entry)
        if clone["id"] == cash_id:
            clone["balance"] = str(checking_after)
        elif clone["id"] == savings_id:
            clone["balance"] = str(savings_after)
        elif clone["id"] == cost_id:
            clone["monthly_amount"] = str(moving_costs)
            clone["name"] = "Proposed recorded expenses"
        candidate.append(clone)
    after = project_blocks(candidate, months)
    return {
        "fundable": True, "funding_gap": ZERO, "upfront": upfront,
        "upfront_eligible_funds": available,
        "current_monthly": present_costs, "proposed_monthly": moving_costs,
        "baseline": before, "proposed": after,
        "checking_after_move": checking_after,
        "savings_after_move": savings_after,
    }


def compare_moving(values, *, existing_goals=None, reviewed=False,
                   use_savings_for_upfront=False):
    """Compare stay and move using only explicit, validated assumptions.

    The first three inputs are required; absent optional costs remain
    flagged unknown, not silently considered verified zero. Savings are
    excluded from upfront funding unless the caller explicitly opts in.
    """
    if not isinstance(values, dict) or set(values) - set(FIELDS):
        raise ValueError("Unexpected moving comparison inputs.")
    if not isinstance(reviewed, bool) or not isinstance(use_savings_for_upfront, bool):
        raise ValueError("Confirmation flags must be explicit.")
    missing = [k for k in FIELDS if values.get(k) is None]
    for key in REQUIRED:
        if key in missing:
            raise ValueError(f"Enter {LABELS[key]} before comparing.")
    validated = {}
    for field in FIELDS:
        checked = _decimal(values.get(field), field, signed=field in SIGNED)
        validated[field] = checked if checked is not None else ZERO
    if validated["income"] == ZERO or validated["rent"] == ZERO:
        raise ValueError("Monthly take-home pay and proposed rent must be above zero.")
    if len(existing_goals or []) > 25:
        raise ValueError("Use no more than 25 existing goals in one scenario.")
    goals = validate_blocks(existing_goals or [])
    if any(g["kind"] != "goal" for g in goals):
        raise ValueError("Only existing savings goal blocks may be reused.")
    if len(goals) + 4 > 50:
        raise ValueError("Too many savings goals for this scenario.")
    horizon = max(24, *(goal["target_months"] for goal in goals))
    model = _projections(
        {**validated, "use_savings_for_upfront": use_savings_for_upfront},
        horizon, goals,
    )
    current_monthly = model["current_monthly"]
    new_monthly = model["proposed_monthly"]
    monthly_delta = new_monthly - current_monthly
    spending_margin_before = validated["income"] - current_monthly
    spending_margin_after = validated["income"] - new_monthly
    current_liquid = validated["checking"] + validated["savings"]
    upfront = model["upfront"]
    result = {
        "fundable": model["fundable"],
        "income": validated["income"],
        "current_monthly": current_monthly,
        "proposed_monthly": new_monthly,
        "monthly_change": monthly_delta,
        "monthly_margin_before": spending_margin_before,
        "monthly_margin_after": spending_margin_after,
        "upfront": upfront,
        "current_liquid": current_liquid,
        "remaining_liquid": (
            current_liquid - upfront if model["fundable"] else None
        ),
        "available_for_upfront": model["upfront_eligible_funds"],
        "funding_gap": model["funding_gap"],
        "missing": missing,
        "reviewed": reviewed,
        "goals_included": len(goals),
        "baseline": model["baseline"],
        "proposed": model.get("proposed"),
        "timeframes": {},
        "goals_affected": [],
    }
    warnings = []
    if missing:
        warnings.append(
            "Not entered: " + ", ".join(LABELS[k] for k in missing)
            + ". Blank fields are modeled at zero only for comparison, "
              "not treated as verified zero expenses."
        )
    if not reviewed:
        warnings.append(
            "Costs have not been confirmed as complete. Monthly flexibility "
            "is provisional and may be overstated."
        )
    if spending_margin_after < ZERO:
        warnings.append(
            "Proposed recurring expenses exceed entered take-home income."
        )
    if not model["fundable"]:
        warnings.append(
            "Upfront costs exceed eligible entered funds. This comparison "
            "does not assume a loan, overdraft, or unapproved savings transfer."
        )
    if model["fundable"] and result["remaining_liquid"] < new_monthly:
        warnings.append(
            "Remaining liquid funds would cover less than one month of "
            "the proposed recorded expenses."
        )
    if not use_savings_for_upfront and validated["savings"] > ZERO:
        warnings.append(
            "Savings balances were not used to pay upfront costs. "
            "You can explicitly allow their use and recalculate."
        )
    if model["fundable"]:
        before, after = model["baseline"], model["proposed"]
        b_goals = {g["id"]: g for g in before["goals"]}
        for goal in after["goals"]:
            old = b_goals[goal["id"]]
            if (old["projected_at_deadline"] != goal["projected_at_deadline"]
                    or old["on_track"] != goal["on_track"]):
                result["goals_affected"].append({
                    "id": goal["id"], "name": goal["name"],
                    "before": old["projected_at_deadline"],
                    "after": goal["projected_at_deadline"],
                    "target": goal["target"],
                    "deadline_months": goal["target_months"],
                    "previous_on_track": old["on_track"],
                    "on_track": goal["on_track"],
                })
        if any(g["previous_on_track"] and not g["on_track"]
               for g in result["goals_affected"]):
            warnings.append(
                "One or more existing savings goals would fall behind "
                "under the proposed assumptions."
            )
        for month in HORIZONS:
            old_row = before["monthly_records"][month]
            new_row = after["monthly_records"][month]
            # Exclude goal balances from liquid funds and report separately.
            old_liquid = old_row["cash_position"] + validated["savings"]
            new_liquid = new_row["cash_position"] + model["savings_after_move"]
            result["timeframes"][month] = {
                "stay_liquid": old_liquid,
                "move_liquid": new_liquid,
                "liquid_change": new_liquid - old_liquid,
                "stay_cash": old_row["cash_position"],
                "move_cash": new_row["cash_position"],
                "stay_net_position": old_row["net_position"],
                "move_net_position": new_row["net_position"],
                "new_unfunded_shortfall": new_row["unfunded_shortfall"],
            }
    result["warnings"] = warnings
    return result


def comparison_csv(report):
    """Portable summary only; no PII, narration, filenames or bank identifiers."""
    if not isinstance(report, dict) or not report.get("fundable"):
        raise ValueError("A valid, funded comparison is required to export.")
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(("MoneyLab Moving Decision Alpha", "stay", "move", "change"))
    for key, title in (
        ("current_monthly", "Recorded monthly expenses"),
        ("monthly_margin_before", "Monthly margin before optional savings"),
    ):
        if key == "current_monthly":
            old, new = report["current_monthly"], report["proposed_monthly"]
        else:
            old, new = report["monthly_margin_before"], report["monthly_margin_after"]
        writer.writerow((title, str(old), str(new), str(new - old)))
    writer.writerow(("Liquid funds immediately after move",
                     str(report["current_liquid"]), str(report["remaining_liquid"]),
                     str(-report["upfront"])))
    for month, values in sorted(report["timeframes"].items()):
        writer.writerow((f"Modeled liquid funds at month {month}",
                         str(values["stay_liquid"]), str(values["move_liquid"]),
                         str(values["liquid_change"])))
    writer.writerow(("Upfront move costs", "", str(report["upfront"]), ""))
    writer.writerow(("Calculation note", "Monthly averages, not a daily cash ledger", "", ""))
    writer.writerow(("Completeness note", "Manually supplied assumptions; review missing costs", "", ""))
    return buffer.getvalue()
