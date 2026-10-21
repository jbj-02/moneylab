"""Projection integration and accounting tests."""
from decimal import Decimal

import pytest

from moneylab.engine import project_finances


def project(**overrides):
    inputs = {
        "current_savings": 500,
        "monthly_income": 2000,
        "monthly_living_expenses": 1000,
        "outstanding_loan_balance": 1000,
        "annual_loan_interest_rate": 12,
        "required_monthly_loan_payment": 100,
        "months": 2,
    }
    inputs.update(overrides)
    return project_finances(**inputs)


def test_month_zero_is_initial_financial_position():
    result = project()
    first = result["monthly_records"][0]
    assert first["month"] == 0
    assert first["savings"] == Decimal("500.00")
    assert first["loan_balance"] == Decimal("1000.00")
    assert first["net_position"] == Decimal("-500.00")
    assert first["loan_payment"] == Decimal("0.00")
    assert first["interest_charged"] == Decimal("0.00")
    assert first["net_cash_flow"] == Decimal("0.00")


def test_two_month_projection_tracks_interest_and_savings():
    r = project()
    rows = r["monthly_records"]
    assert len(rows) == 3
    assert rows[1]["interest_charged"] == Decimal("10.00")
    assert rows[1]["loan_payment"] == Decimal("100.00")
    assert rows[1]["savings"] == Decimal("1400.00")
    assert rows[1]["loan_balance"] == Decimal("910.00")
    assert rows[1]["net_position"] == Decimal("490.00")
    assert rows[2]["interest_charged"] == Decimal("9.10")
    assert rows[2]["loan_balance"] == Decimal("819.10")
    assert rows[2]["savings"] == Decimal("2300.00")
    assert r["summary"]["ending_net_position"] == Decimal("1480.90")
    assert r["summary"]["total_interest_charged"] == Decimal("19.10")
    assert r["summary"]["total_loan_payments"] == Decimal("200.00")
    assert r["summary"]["loan_payoff_month"] is None


def test_early_payoff_uses_actual_payment_then_zero():
    r = project(
        current_savings=100,
        outstanding_loan_balance=50,
        required_monthly_loan_payment=500,
    )
    first_month, second_month = r["monthly_records"][1:]
    assert first_month["interest_charged"] == Decimal("0.50")
    assert first_month["loan_payment"] == Decimal("50.50")
    assert first_month["savings"] == Decimal("1049.50")
    assert second_month["loan_payment"] == Decimal("0.00")
    assert second_month["interest_charged"] == Decimal("0.00")
    assert second_month["savings"] == Decimal("2049.50")
    assert r["summary"]["loan_payoff_month"] == 1
    assert r["summary"]["ending_loan_balance"] == Decimal("0.00")


def test_zero_interest_payoff_in_second_month():
    r = project(outstanding_loan_balance=1000, annual_loan_interest_rate=0,
                required_monthly_loan_payment=600, months=3)
    rows = r["monthly_records"]
    assert [x["loan_payment"] for x in rows[1:]] == [
        Decimal("600.00"), Decimal("400.00"), Decimal("0.00")
    ]
    assert [x["loan_balance"] for x in rows[1:]] == [
        Decimal("400.00"), Decimal("0.00"), Decimal("0.00")
    ]
    assert r["summary"]["loan_payoff_month"] == 2
    assert r["summary"]["total_interest_charged"] == Decimal("0.00")


def test_no_initial_debt_has_payoff_month_zero():
    r = project(outstanding_loan_balance=0, months=3)
    assert r["summary"]["loan_payoff_month"] == 0
    assert all(row["loan_payment"] == 0 for row in r["monthly_records"])
    assert r["summary"]["ending_savings"] == Decimal("3500.00")


def test_insufficient_interest_payment_grows_debt():
    r = project(current_savings=0, monthly_income=0, monthly_living_expenses=0,
                required_monthly_loan_payment=5)
    assert r["monthly_records"][1]["loan_balance"] == Decimal("1005.00")
    assert r["monthly_records"][2]["loan_balance"] == Decimal("1010.05")
    assert r["monthly_records"][2]["cumulative_interest_charged"] == Decimal("20.05")
    assert r["summary"]["ending_unfunded_shortfall"] == Decimal("10.00")
    assert r["summary"]["ending_savings"] == Decimal("0.00")
    assert r["summary"]["ending_net_position"] == Decimal("-1020.05")
    assert r["monthly_records"][1]["negative_amortization"] is True


def test_unfunded_shortfall_is_carried_forward_and_offset_first():
    r = project(current_savings=0, monthly_income=100, monthly_living_expenses=90,
                outstanding_loan_balance=50, annual_loan_interest_rate=0,
                required_monthly_loan_payment=50, months=6)
    assert r["monthly_records"][1]["cash_position"] == Decimal("-40.00")
    assert r["monthly_records"][1]["unfunded_shortfall"] == Decimal("40.00")
    assert r["monthly_records"][1]["savings"] == Decimal("0.00")
    assert r["monthly_records"][4]["unfunded_shortfall"] == Decimal("10.00")
    assert r["monthly_records"][5]["savings"] == Decimal("0.00")
    assert r["monthly_records"][6]["savings"] == Decimal("10.00")
    assert r["summary"]["ending_unfunded_shortfall"] == Decimal("0.00")
    assert r["summary"]["loan_payoff_month"] == 1


def test_no_automatic_extra_loan_payments():
    r = project(monthly_income=10000, months=1)
    assert r["monthly_records"][1]["loan_payment"] == Decimal("100.00")
    assert r["monthly_records"][1]["loan_balance"] == Decimal("910.00")


def test_cash_and_loan_accounting_identities_each_month():
    r = project(current_savings=50, monthly_income=120,
                monthly_living_expenses=200, months=36)
    rows = r["monthly_records"]
    for previous, current in zip(rows, rows[1:]):
        assert current["cash_position"] == previous["cash_position"] + current["net_cash_flow"]
        assert current["cash_position"] == current["savings"] - current["unfunded_shortfall"]
        assert current["net_position"] == (
            current["savings"] - current["unfunded_shortfall"] - current["loan_balance"]
        )
        assert current["loan_balance"] == (
            previous["loan_balance"] + current["interest_charged"] - current["loan_payment"]
        )
        assert current["net_cash_flow"] == (
            current["income"] - current["living_expenses"] - current["loan_payment"]
        )
        assert current["cumulative_loan_payments"] >= previous["cumulative_loan_payments"]
        assert current["cumulative_interest_charged"] >= previous["cumulative_interest_charged"]


def test_600_month_horizon_and_cash_balance_no_interest():
    r = project(current_savings=0, monthly_income=100, monthly_living_expenses=50,
                outstanding_loan_balance=0, months=600)
    assert len(r["monthly_records"]) == 601
    assert r["summary"]["ending_savings"] == Decimal("30000.00")
    assert r["summary"]["ending_net_position"] == Decimal("30000.00")


def test_zero_scheduled_payment_not_falsely_reported_as_payoff():
    r = project(required_monthly_loan_payment=0, months=12)
    assert r["summary"]["loan_payoff_month"] is None
    assert r["summary"]["ending_loan_balance"] > Decimal("1000.00")


@pytest.mark.parametrize("months", [0, -1, 601, 1.5, 12.0, True, "12", None])
def test_invalid_projection_horizon(months):
    with pytest.raises(ValueError, match="Months must"):
        project(months=months)


@pytest.mark.parametrize("overrides", [
    {"current_savings": -1},
    {"monthly_income": -1},
    {"monthly_living_expenses": -1},
    {"outstanding_loan_balance": -1},
    {"annual_loan_interest_rate": -1},
    {"required_monthly_loan_payment": -1},
    {"monthly_income": "NaN"},
    {"annual_loan_interest_rate": "Infinity"},
])
def test_invalid_projection_financial_inputs(overrides):
    with pytest.raises(ValueError):
        project(**overrides)
