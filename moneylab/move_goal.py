"""Month-end estimates for an upfront move and a user-selected cash cushion."""
from decimal import Decimal, ROUND_CEILING

ZERO = Decimal("0")


def move_goal_timing(report, *, monthly_savings, cushion, deadline,
                     spending_cut=ZERO):
    """Project a fixed savings transfer while staying, then a one-time move.

    Savings permission constrains what can pay the upfront bill. Separately,
    total accessible cash after the bill must meet the cushion.
    """
    upfront = report["upfront"]
    starting_cash = report["current_liquid"]
    gap = max(ZERO, upfront - report["available_for_upfront"],
              upfront + cushion - starting_cash)
    commitments = report["details"]["planned_goal_contributions"]
    room = report["monthly_margin_before"] - commitments
    saving_capacity = max(ZERO, room)
    if monthly_savings > saving_capacity:
        raise ValueError("Planned savings exceed the recorded monthly room before moving.")
    savings_rate = min(monthly_savings + spending_cut, max(ZERO, room + spending_cut))
    months = (
        0 if gap == ZERO else
        int((gap / savings_rate).to_integral_value(rounding=ROUND_CEILING))
        if savings_rate > ZERO else None
    )
    return {
        "months": months,
        "monthly_savings": savings_rate,
        "monthly_after": report["monthly_margin_after"] + spending_cut - commitments,
        "cash_after": (starting_cash + months * savings_rate - upfront
                       if months is not None else None),
        "deadline_gap": max(ZERO, gap - deadline * savings_rate),
        "required_monthly": (gap / deadline).quantize(Decimal("0.01"), rounding=ROUND_CEILING),
        "saving_capacity": max(ZERO, room + spending_cut),
    }
