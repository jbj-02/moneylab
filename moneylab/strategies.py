"""Fair, side-by-side financial strategy comparisons for MoneyLab."""

from moneylab.engine import project_finances, validate_money


def compare_financial_strategies(
    current_savings,
    monthly_income,
    monthly_living_expenses,
    outstanding_loan_balance,
    annual_loan_interest_rate,
    required_monthly_loan_payment,
    months,
    extra_monthly_loan_payment,
):
    """Compare saving all surplus vs. allocating surplus to extra loan payments.

    Both strategies share *identical* income, expenses, loan terms and horizon.
    Extra payments are capped by surplus after the contractual payment, any
    earlier unfunded shortfall, and remaining loan balance. No cash savings
    are drawn down to fund an extra payment.
    """
    extra_request = validate_money(
        extra_monthly_loan_payment, "Extra monthly loan payment"
    )
    inputs = {
        "current_savings": current_savings,
        "monthly_income": monthly_income,
        "monthly_living_expenses": monthly_living_expenses,
        "outstanding_loan_balance": outstanding_loan_balance,
        "annual_loan_interest_rate": annual_loan_interest_rate,
        "required_monthly_loan_payment": required_monthly_loan_payment,
        "months": months,
    }

    saving = project_finances(**inputs)
    accelerating = project_finances(
        **inputs, extra_monthly_loan_payment=extra_request
    )
    base = saving["summary"]
    accelerated = accelerating["summary"]

    return {
        "saving": saving,
        "accelerated": accelerating,
        "comparison": {
            "requested_extra_monthly_payment": extra_request,
            "actual_total_extra_payments": accelerated["total_extra_loan_payments"],
            "interest_avoided": (
                base["total_interest_charged"]
                - accelerated["total_interest_charged"]
            ),
            "ending_debt_reduction": (
                base["ending_loan_balance"] - accelerated["ending_loan_balance"]
            ),
            "ending_savings_difference": (
                accelerated["ending_savings"] - base["ending_savings"]
            ),
            "ending_net_position_gain": (
                accelerated["ending_net_position"] - base["ending_net_position"]
            ),
            "saving_payoff_month": base["loan_payoff_month"],
            "accelerated_payoff_month": accelerated["loan_payoff_month"],
        },
    }
