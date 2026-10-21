"""Regression tests for comparing savings and accelerated debt repayment."""

from decimal import Decimal

import pytest

from moneylab.engine import project_finances
from moneylab.strategies import compare_financial_strategies


def run_compare(**changes):
    options = {
        "current_savings": 0,
        "monthly_income": 1000,
        "monthly_living_expenses": 600,
        "outstanding_loan_balance": 1000,
        "annual_loan_interest_rate": 12,
        "required_monthly_loan_payment": 100,
        "months": 2,
        "extra_monthly_loan_payment": 100,
    }
    options.update(changes)
    return compare_financial_strategies(**options)


def test_comparison_is_based_on_identical_financial_profile():
    r = run_compare()
    baseline = r["saving"]["monthly_records"]
    accelerated = r["accelerated"]["monthly_records"]
    for b, a in zip(baseline, accelerated):
        assert b["month"] == a["month"]
        assert b["income"] == a["income"]
        assert b["living_expenses"] == a["living_expenses"]


def test_two_month_extra_payments_save_interest():
    r = run_compare()
    b = r["saving"]["monthly_records"]
    a = r["accelerated"]["monthly_records"]
    assert b[1]["loan_balance"] == Decimal("910.00")
    assert b[2]["loan_balance"] == Decimal("819.10")
    assert a[1]["loan_balance"] == Decimal("810.00")
    assert a[2]["loan_balance"] == Decimal("618.10")
    assert a[1]["regular_loan_payment"] == Decimal("100.00")
    assert a[1]["extra_loan_payment"] == Decimal("100.00")
    assert a[1]["loan_payment"] == Decimal("200.00")
    assert a[2]["extra_loan_payment"] == Decimal("100.00")
    assert r["comparison"]["interest_avoided"] == Decimal("1.00")
    assert r["comparison"]["ending_net_position_gain"] == Decimal("1.00")
    assert r["comparison"]["ending_savings_difference"] == Decimal("-200.00")
    assert r["comparison"]["ending_debt_reduction"] == Decimal("201.00")
    assert r["comparison"]["actual_total_extra_payments"] == Decimal("200.00")


def test_zero_extra_is_identical_to_existing_baseline():
    r = run_compare(extra_monthly_loan_payment=0)
    assert r["saving"] == r["accelerated"]
    assert r["comparison"]["interest_avoided"] == Decimal("0.00")
    assert r["comparison"]["ending_net_position_gain"] == Decimal("0.00")
    assert r["saving"] == project_finances(
        current_savings=0, monthly_income=1000,
        monthly_living_expenses=600, outstanding_loan_balance=1000,
        annual_loan_interest_rate=12, required_monthly_loan_payment=100,
        months=2,
    )


def test_zero_interest_changes_allocation_but_not_net_position():
    r = run_compare(annual_loan_interest_rate=0)
    assert r["comparison"]["interest_avoided"] == Decimal("0.00")
    assert r["comparison"]["ending_net_position_gain"] == Decimal("0.00")
    assert r["comparison"]["ending_debt_reduction"] == Decimal("200.00")


def test_requested_extra_is_capped_by_available_monthly_surplus():
    r = run_compare(
        monthly_income=300, monthly_living_expenses=190,
        annual_loan_interest_rate=0, months=1,
        extra_monthly_loan_payment=400,
    )
    month = r["accelerated"]["monthly_records"][1]
    assert month["regular_loan_payment"] == Decimal("100.00")
    assert month["extra_loan_payment"] == Decimal("10.00")
    assert month["loan_payment"] == Decimal("110.00")
    assert month["net_cash_flow"] == Decimal("0.00")
    assert month["loan_balance"] == Decimal("890.00")


def test_shortfalls_prevent_voluntary_extra_payments():
    r = run_compare(
        monthly_income=100, monthly_living_expenses=150,
        required_monthly_loan_payment=10,
    )
    assert all(
        row["extra_loan_payment"] == Decimal("0.00")
        for row in r["accelerated"]["monthly_records"]
    )
    assert r["saving"] == r["accelerated"]


def test_earlier_unfunded_shortfall_takes_priority_over_extra():
    # First month loan payoff causes a shortfall; after payoff, future
    # monthly surpluses go toward that shortfall rather than extra payments.
    r = run_compare(
        current_savings=0, monthly_income=100,
        monthly_living_expenses=90,
        outstanding_loan_balance=50,
        annual_loan_interest_rate=0,
        required_monthly_loan_payment=50,
        extra_monthly_loan_payment=100,
        months=6,
    )
    assert r["accelerated"]["monthly_records"][1]["unfunded_shortfall"] == Decimal("40.00")
    assert r["accelerated"]["summary"]["ending_unfunded_shortfall"] == Decimal("0.00")
    assert r["comparison"]["actual_total_extra_payments"] == Decimal("0.00")


def test_no_required_payment_extra_still_pays_interest_first():
    r = run_compare(
        outstanding_loan_balance=100,
        annual_loan_interest_rate=12,
        required_monthly_loan_payment=0,
        extra_monthly_loan_payment=100,
        months=1,
    )
    m = r["accelerated"]["monthly_records"][1]
    assert m["interest_charged"] == Decimal("1.00")
    assert m["extra_loan_payment"] == Decimal("100.00")
    assert m["principal_paid"] == Decimal("99.00")
    assert m["loan_balance"] == Decimal("1.00")


def test_extra_payment_cannot_overpay_final_amount_due():
    r = run_compare(
        outstanding_loan_balance=50,
        annual_loan_interest_rate=12,
        required_monthly_loan_payment=20,
        extra_monthly_loan_payment=1000,
        months=2,
    )
    m1 = r["accelerated"]["monthly_records"][1]
    m2 = r["accelerated"]["monthly_records"][2]
    assert m1["loan_payment"] == Decimal("50.50")
    assert m1["regular_loan_payment"] == Decimal("20.00")
    assert m1["extra_loan_payment"] == Decimal("30.50")
    assert m1["loan_balance"] == Decimal("0.00")
    assert m2["loan_payment"] == Decimal("0.00")
    assert r["comparison"]["accelerated_payoff_month"] == 1


def test_accounting_invariants_for_both_strategies():
    r = run_compare(
        current_savings=300, monthly_income=2000, monthly_living_expenses=600,
        outstanding_loan_balance=16000, annual_loan_interest_rate="5.295",
        required_monthly_loan_payment=250, extra_monthly_loan_payment=1000,
        months=120,
    )
    for projection in (r["saving"], r["accelerated"]):
        records = projection["monthly_records"]
        assert len(records) == 121
        for previous, row in zip(records, records[1:]):
            assert row["regular_loan_payment"] + row["extra_loan_payment"] == row["loan_payment"]
            assert row["savings"] - row["unfunded_shortfall"] == row["cash_position"]
            assert row["net_cash_flow"] == row["income"] - row["living_expenses"] - row["loan_payment"]
            assert row["loan_balance"] == previous["loan_balance"] + row["interest_charged"] - row["loan_payment"]
            assert row["cash_position"] == previous["cash_position"] + row["net_cash_flow"]
            assert row["extra_loan_payment"] <= Decimal("1000.00")
            assert row["extra_loan_payment"] >= Decimal("0.00")
    assert r["comparison"]["interest_avoided"] > Decimal("0.00")
    assert r["comparison"]["ending_net_position_gain"] >= Decimal("0.00")


@pytest.mark.parametrize("value", [-1, "NaN", "Infinity", "invalid", True, None])
def test_invalid_extra_payment_rejected(value):
    with pytest.raises(ValueError):
        run_compare(extra_monthly_loan_payment=value)
