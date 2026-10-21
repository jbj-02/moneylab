"""Core financial calculations for MoneyLab, independent of the UI."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def validate_money(value, field_name):
    """Convert a nonnegative monetary input to a Decimal rounded to cents.

    A consistent cent-rounding policy prevents floating-point surprises in
    downstream cash-flow and loan calculations.
    """
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a valid number.")

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError(f"{field_name} must be a valid number.") from None

    if not amount.is_finite():
        raise ValueError(f"{field_name} must be a finite number.")
    if amount < 0:
        raise ValueError(f"{field_name} must be a nonnegative number.")

    try:
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError(f"{field_name} is too large.") from None


def calculate_monthly_cash_flow(
    monthly_income, monthly_living_expenses, monthly_debt_payment
):
    """Calculate a single month's cash flow using the *actual* debt payment.

    Living expenses exclude debt payments to avoid double-counting. A surplus
    is available for saving or optional extra payments, but is not allocated
    automatically. Negative cash flow is reported as a deficit.

    Returns a dictionary of monetary Decimal values.
    """
    income = validate_money(monthly_income, "Monthly income")
    living_expenses = validate_money(
        monthly_living_expenses, "Monthly living expenses"
    )
    debt_payment = validate_money(monthly_debt_payment, "Monthly debt payment")

    total_outflow = living_expenses + debt_payment
    net_cash_flow = income - total_outflow

    return {
        "income": income,
        "living_expenses": living_expenses,
        "debt_payment": debt_payment,
        "total_outflow": total_outflow,
        "net_cash_flow": net_cash_flow,
        "available_for_savings": max(net_cash_flow, ZERO),
        "monthly_deficit": max(-net_cash_flow, ZERO),
    }
