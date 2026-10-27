"""Explainable, conservative financial check-ins for manual-first MoneyLab.

A check-in is not a financial health score or a verification of bank data.
'On track' only describes modeled results when the user has explicitly
reviewed enough inputs. The engine never invents account data.
"""

from decimal import Decimal, ROUND_HALF_UP

from moneylab.blocks import validate_blocks

ZERO = Decimal("0.00")
MONTH = Decimal("0.1")
LIQUID_ACCOUNT_TYPES = {"savings", "hysa", "money_market"}


def build_checkin(blocks, projection, reviewed=False):
    """Summarize recorded obligations, accessible reserves and modeled risks.

    Reviewed is an explicit, user-controlled confirmation that income, regular
    expenses and available account balances have been entered. It does *not*
    mean MoneyLab can confirm completeness, accuracy, or live transactions.
    """
    items = validate_blocks(blocks)
    summary = projection["summary"]
    rows = projection["monthly_records"]
    kinds = {entry["kind"] for entry in items}
    has_income = "income" in kinds
    has_expenses = "expense" in kinds
    has_cash = "cash" in kinds
    missing = []
    if not has_income:
        missing.append("Add your monthly take-home income.")
    if not has_expenses:
        missing.append("Add regular living expenses, including bills and everyday spending.")
    if not has_cash:
        missing.append("Add a checking/cash account balance to assess accessible reserves.")

    liquid_savings = sum(
        (item["balance"] for item in items
         if item["kind"] == "hysa" or
         (item["kind"] == "account" and
          item["account_type"] in LIQUID_ACCOUNT_TYPES)),
        ZERO,
    )
    starting_liquid = rows[0]["cash_savings"] + liquid_savings
    recorded_outflow = (
        summary["monthly_expenses"] + summary["first_month_loan_payments"]
    )
    coverage = None
    if recorded_outflow > ZERO and has_cash:
        coverage = (starting_liquid / recorded_outflow).quantize(
            MONTH, rounding=ROUND_HALF_UP
        )

    current_deficit = (
        summary["monthly_income"] < recorded_outflow
        if has_income and has_expenses else False
    )
    projected_shortfall = any(
        row["unfunded_shortfall"] > ZERO for row in rows[1:]
    )
    growing_loan = any(row["negative_amortization"] for row in rows[1:])
    missed_goals = [
        goal["name"] for goal in projection["goals"]
        if goal["on_track"] is False
    ]
    unassessed_goals = [
        goal["name"] for goal in projection["goals"]
        if goal["on_track"] is None
    ]

    attention = []
    if current_deficit:
        attention.append(
            "Recorded monthly living costs and required loan payments "
            "exceed modeled take-home income."
        )
    if projected_shortfall:
        attention.append(
            "The projection shows an unfunded cash shortfall in at least one month."
        )
    if growing_loan:
        attention.append(
            "At least one scheduled loan payment does not cover modeled monthly interest."
        )
    if missed_goals:
        attention.append(
            "Some savings goals miss their targets under current assumptions: "
            + ", ".join(missed_goals) + "."
        )

    actions = list(missing)
    if not reviewed and not missing:
        actions.append(
            "Confirm that your key income, spending, debts and balances "
            "have been entered and recently reviewed."
        )
    if unassessed_goals:
        actions.append(
            "Extend the projection horizon to check these goal deadlines: "
            + ", ".join(unassessed_goals) + "."
        )
    if attention:
        actions.append(
            "Test adjustments in the What-if Lab before changing your real-world plan."
        )
    if not projection["goals"] and not missing:
        actions.append(
            "Consider adding a specific savings goal to measure progress."
        )

    if attention:
        status = "needs_attention"
        heading = "Your plan has something worth checking"
        explanation = (
            "MoneyLab found a possible issue in the figures you entered. "
            "This is a planning alert, not a judgment of your financial health."
        )
    elif missing or not reviewed or unassessed_goals:
        status = "not_enough_information"
        heading = "Let's complete your financial picture"
        explanation = (
            "MoneyLab needs more reviewed information before describing "
            "your plan as on track. No live account data is available."
        )
    else:
        status = "on_track"
        heading = "Your modeled plan is on track"
        explanation = (
            "Based on the figures you reviewed, recorded costs fit within "
            "take-home income, no unfunded cash shortfalls appear in this "
            "projection, and assessed savings goals meet their deadlines. "
            "Actual results may differ."
        )

    return {
        "status": status,
        "heading": heading,
        "explanation": explanation,
        "reviewed": bool(reviewed),
        "missing": missing,
        "attention": attention,
        "actions": actions,
        "coverage_months": coverage,
        "accessible_starting_funds": starting_liquid,
        "recorded_monthly_outflow": recorded_outflow,
        "unassessed_goals": unassessed_goals,
        "missed_goals": missed_goals,
        "spending_buffer": summary["unallocated_monthly_buffer"],
        "estimated_weekly_extra": summary["estimated_extra_weekly_spend"],
    }
