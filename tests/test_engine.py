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
