"""Automated tests for MoneyLab's single-month cash-flow calculations."""

from decimal import Decimal

import pytest

from moneylab.engine import calculate_monthly_cash_flow, validate_money


def test_positive_monthly_cash_flow():
    result = calculate_monthly_cash_flow(3000, 1800, 300)

    assert result["income"] == Decimal("3000.00")
    assert result["living_expenses"] == Decimal("1800.00")
    assert result["debt_payment"] == Decimal("300.00")
    assert result["total_outflow"] == Decimal("2100.00")
    assert result["net_cash_flow"] == Decimal("900.00")
    assert result["available_for_savings"] == Decimal("900.00")
    assert result["monthly_deficit"] == Decimal("0.00")


def test_negative_monthly_cash_flow():
    result = calculate_monthly_cash_flow(2000, 1900, 300)

    assert result["net_cash_flow"] == Decimal("-200.00")
    assert result["available_for_savings"] == Decimal("0.00")
    assert result["monthly_deficit"] == Decimal("200.00")


def test_zero_monthly_cash_flow():
    result = calculate_monthly_cash_flow(2500, 2200, 300)
    assert result["net_cash_flow"] == Decimal("0.00")
    assert result["monthly_deficit"] == Decimal("0.00")


def test_decimal_precision():
    result = calculate_monthly_cash_flow(4500.25, 2000.10, 299.99)
    assert result["net_cash_flow"] == Decimal("2200.16")


def test_zero_debt_payment():
    result = calculate_monthly_cash_flow(3000, 1800, 0)
    assert result["net_cash_flow"] == Decimal("1200.00")


def test_zero_inputs():
    result = calculate_monthly_cash_flow(0, 0, 0)
    assert result["net_cash_flow"] == Decimal("0.00")


def test_round_half_up_to_cents():
    assert validate_money("1.005", "Amount") == Decimal("1.01")
    assert validate_money("1.004", "Amount") == Decimal("1.00")


@pytest.mark.parametrize(
    "income, expenses, debt",
    [
        (-100, 1000, 100),
        (3000, -100, 200),
        (3000, 1000, -50),
        ("invalid", 1000, 200),
        ("NaN", 1000, 200),
        ("Infinity", 1000, 200),
        (True, 1000, 200),
        (3000, None, 200),
    ],
)
def test_invalid_inputs(income, expenses, debt):
    with pytest.raises(ValueError):
        calculate_monthly_cash_flow(income, expenses, debt)



from moneylab.engine import calculate_monthly_loan_payment


def test_loan_normal_payment():
    result = calculate_monthly_loan_payment(1000, 12, 100)
    assert result["monthly_interest"] == Decimal("10.00")
    assert result["interest_paid"] == Decimal("10.00")
    assert result["principal_paid"] == Decimal("90.00")
    assert result["actual_payment"] == Decimal("100.00")
    assert result["ending_balance"] == Decimal("910.00")
    assert result["paid_off"] is False
    assert result["negative_amortization"] is False


def test_loan_zero_interest():
    result = calculate_monthly_loan_payment(1000, 0, 150)
    assert result["monthly_interest"] == Decimal("0.00")
    assert result["principal_paid"] == Decimal("150.00")
    assert result["ending_balance"] == Decimal("850.00")


def test_loan_early_payoff_caps_actual_payment():
    result = calculate_monthly_loan_payment(50, 12, 500)
    assert result["monthly_interest"] == Decimal("0.50")
    assert result["actual_payment"] == Decimal("50.50")
    assert result["principal_paid"] == Decimal("50.00")
    assert result["ending_balance"] == Decimal("0.00")
    assert result["paid_off"] is True


def test_loan_insufficient_payment_capitalizes_unpaid_interest():
    result = calculate_monthly_loan_payment(1000, 12, 5)
    assert result["monthly_interest"] == Decimal("10.00")
    assert result["interest_paid"] == Decimal("5.00")
    assert result["unpaid_interest"] == Decimal("5.00")
    assert result["principal_paid"] == Decimal("0.00")
    assert result["ending_balance"] == Decimal("1005.00")
    assert result["negative_amortization"] is True
    assert result["principal_not_decreasing"] is True


def test_loan_interest_only_payment_does_not_reduce_balance():
    result = calculate_monthly_loan_payment(1000, 12, 10)
    assert result["ending_balance"] == Decimal("1000.00")
    assert result["unpaid_interest"] == Decimal("0.00")
    assert result["negative_amortization"] is False
    assert result["principal_not_decreasing"] is True


def test_loan_zero_balance_has_zero_actual_payment():
    result = calculate_monthly_loan_payment(0, 7, 250)
    assert result["monthly_interest"] == Decimal("0.00")
    assert result["actual_payment"] == Decimal("0.00")
    assert result["ending_balance"] == Decimal("0.00")
    assert result["paid_off"] is True


def test_loan_interest_rounds_to_cents():
    result = calculate_monthly_loan_payment(1000, 5, 100)
    assert result["monthly_interest"] == Decimal("4.17")
    assert result["principal_paid"] == Decimal("95.83")
    assert result["ending_balance"] == Decimal("904.17")


def test_loan_rate_keeps_subcent_percentage_precision():
    result = calculate_monthly_loan_payment(10000, "3.295", 200)
    assert result["annual_interest_rate"] == Decimal("3.295")
    assert result["monthly_interest"] == Decimal("27.46")
    assert result["ending_balance"] == Decimal("9827.46")


def test_loan_no_payment_with_interest_increases_balance():
    result = calculate_monthly_loan_payment(1000, 12, 0)
    assert result["monthly_interest"] == Decimal("10.00")
    assert result["unpaid_interest"] == Decimal("10.00")
    assert result["ending_balance"] == Decimal("1010.00")
    assert result["negative_amortization"] is True


def test_loan_zero_interest_and_zero_payment_unchanged():
    result = calculate_monthly_loan_payment(1000, 0, 0)
    assert result["ending_balance"] == Decimal("1000.00")
    assert result["principal_not_decreasing"] is True
    assert result["negative_amortization"] is False


def test_loan_cash_flow_uses_actual_payment_after_payoff():
    loan = calculate_monthly_loan_payment(50, 12, 500)
    cash = calculate_monthly_cash_flow(3000, 1800, loan["actual_payment"])
    assert cash["net_cash_flow"] == Decimal("1149.50")


def test_loan_accounting_identity():
    for balance, rate, payment in [
        (1000, 12, 100), (50, 12, 500), (1000, 12, 5), (1000, 0, 0)
    ]:
        r = calculate_monthly_loan_payment(balance, rate, payment)
        assert r["starting_balance"] + r["monthly_interest"] == (
            r["ending_balance"] + r["actual_payment"]
        )
        assert r["interest_paid"] + r["principal_paid"] == r["actual_payment"]
        assert r["interest_paid"] + r["unpaid_interest"] == r["monthly_interest"]


@pytest.mark.parametrize(
    "balance, rate, payment",
    [
        (-1, 5, 100), (1000, -0.1, 100), (1000, 5, -1),
        (1000, "NaN", 100), (1000, "Infinity", 100),
        (1000, True, 100), (1000, "invalid", 100),
    ],
)
def test_loan_invalid_inputs(balance, rate, payment):
    with pytest.raises(ValueError):
        calculate_monthly_loan_payment(balance, rate, payment)
