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


def validate_annual_interest_rate(value):
    """Validate an annual nominal interest rate expressed as a percentage.

    For example, 6.5 represents a 6.5% annual rate, not 0.065.
    Rates retain their supplied precision; only dollar amounts round to cents.
    """
    if isinstance(value, bool):
        raise ValueError("Annual interest rate must be a valid number.")

    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError("Annual interest rate must be a valid number.") from None

    if not rate.is_finite() or rate < 0:
        raise ValueError("Annual interest rate must be finite and nonnegative.")
    return rate


def calculate_monthly_loan_payment(
    starting_balance, annual_interest_rate, scheduled_payment
):
    """Calculate one month of loan interest, payment, and remaining balance.

    Model assumptions:
    - The annual interest rate is a nominal percentage (e.g., 6.5 for 6.5%).
    - Interest accrues monthly on the opening balance at annual_rate / 12.
    - Interest is rounded to cents using ROUND_HALF_UP.
    - Payments cover interest before principal and never exceed the amount due.
    - If the payment is less than interest, unpaid interest is added to the
      balance immediately (monthly capitalization). Actual loan terms vary.
    - The scheduled payment is assumed to be made even if cash flow is negative;
      the cash-flow model separately tracks whether that is affordable.

    All monetary outputs are Decimal values; status fields are bools.
    """
    balance = validate_money(starting_balance, "Starting loan balance")
    rate = validate_annual_interest_rate(annual_interest_rate)
    scheduled = validate_money(scheduled_payment, "Scheduled loan payment")

    monthly_interest = (balance * rate / Decimal("1200")).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    amount_due = balance + monthly_interest
    actual_payment = min(scheduled, amount_due)
    interest_paid = min(actual_payment, monthly_interest)
    unpaid_interest = monthly_interest - interest_paid
    principal_paid = actual_payment - interest_paid
    ending_balance = amount_due - actual_payment

    return {
        "starting_balance": balance,
        "annual_interest_rate": rate,
        "scheduled_payment": scheduled,
        "monthly_interest": monthly_interest,
        "actual_payment": actual_payment,
        "interest_paid": interest_paid,
        "unpaid_interest": unpaid_interest,
        "principal_paid": principal_paid,
        "ending_balance": ending_balance,
        "paid_off": ending_balance == ZERO,
        "negative_amortization": ending_balance > balance,
        "principal_not_decreasing": balance > ZERO and ending_balance >= balance,
    }


def project_finances(
    current_savings,
    monthly_income,
    monthly_living_expenses,
    outstanding_loan_balance,
    annual_loan_interest_rate,
    required_monthly_loan_payment,
    months,
):
    """Project fixed monthly cash flow and a single loan over 1 to 600 months.

    Returns a dictionary with ``monthly_records`` (including month 0) and a
    ``summary``. Currency values are Decimal so the UI can format them later.

    Assumptions: income, living expenses and loan terms remain constant; cash
    has no interest, and the entire monthly cash surplus stays as savings.
    No voluntary extra loan payments are made. Scheduled debt payments happen
    even when cash is inadequate, so any shortage is *unfunded*, not assumed
    to be an actual bank overdraft or a new interest-bearing loan.

    Signed cash position carries shortages forward. Positive cash position is
    savings; negative cash position creates a separate unfunded shortfall. A
    future surplus first offsets that shortfall before increasing savings.
    Net position is savings - loan balance - unfunded shortfall: it is NOT a
    complete net-worth estimate because other assets and debts are excluded.

    The underlying loan function capitalizes unpaid interest monthly; actual
    loan contracts may use other interest-capitalization rules.
    """
    if isinstance(months, bool) or not isinstance(months, int):
        raise ValueError("Months must be a whole number from 1 to 600.")
    if not 1 <= months <= 600:
        raise ValueError("Months must be a whole number from 1 to 600.")

    cash_position = validate_money(current_savings, "Current savings")
    income = validate_money(monthly_income, "Monthly income")
    expenses = validate_money(monthly_living_expenses, "Monthly living expenses")
    loan_balance = validate_money(outstanding_loan_balance, "Outstanding loan balance")
    rate = validate_annual_interest_rate(annual_loan_interest_rate)
    payment = validate_money(required_monthly_loan_payment, "Required monthly loan payment")

    initial_savings = cash_position
    initial_debt = loan_balance
    total_interest = ZERO
    total_payments = ZERO
    payoff_month = 0 if loan_balance == ZERO else None

    def snapshot(month, flow, loan):
        savings = max(cash_position, ZERO)
        shortfall = max(-cash_position, ZERO)
        return {
            "month": month,
            "savings": savings,
            "unfunded_shortfall": shortfall,
            "cash_position": cash_position,
            "loan_balance": loan_balance,
            "net_position": savings - shortfall - loan_balance,
            "income": flow["income"],
            "living_expenses": flow["living_expenses"],
            "loan_payment": loan["actual_payment"],
            "net_cash_flow": flow["net_cash_flow"],
            "interest_charged": loan["monthly_interest"],
            "interest_paid_this_month": loan["interest_paid"],
            "unpaid_interest_this_month": loan["unpaid_interest"],
            "principal_paid": loan["principal_paid"],
            "negative_amortization": loan["negative_amortization"],
            "cumulative_interest_charged": total_interest,
            "cumulative_loan_payments": total_payments,
        }

    zero_flow = calculate_monthly_cash_flow(ZERO, ZERO, ZERO)
    zero_loan = calculate_monthly_loan_payment(loan_balance, ZERO, ZERO)
    records = [snapshot(0, zero_flow, zero_loan)]

    for month in range(1, months + 1):
        loan = calculate_monthly_loan_payment(loan_balance, rate, payment)
        flow = calculate_monthly_cash_flow(income, expenses, loan["actual_payment"])

        cash_position += flow["net_cash_flow"]
        loan_balance = loan["ending_balance"]
        total_interest += loan["monthly_interest"]
        total_payments += loan["actual_payment"]
        if loan_balance == ZERO and payoff_month is None:
            payoff_month = month

        records.append(snapshot(month, flow, loan))

    ending_savings = max(cash_position, ZERO)
    ending_shortfall = max(-cash_position, ZERO)
    return {
        "monthly_records": records,
        "summary": {
            "projection_months": months,
            "starting_savings": initial_savings,
            "starting_loan_balance": initial_debt,
            "starting_net_position": initial_savings - initial_debt,
            "ending_savings": ending_savings,
            "ending_unfunded_shortfall": ending_shortfall,
            "ending_cash_position": cash_position,
            "ending_loan_balance": loan_balance,
            "ending_net_position": ending_savings - ending_shortfall - loan_balance,
            "total_interest_charged": total_interest,
            "total_loan_payments": total_payments,
            "loan_payoff_month": payoff_month,
        },
    }
