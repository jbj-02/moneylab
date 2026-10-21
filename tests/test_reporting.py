"""Tests that downloadable CSVs reconcile with exact engine output."""

import csv
from decimal import Decimal
from io import StringIO

from moneylab.reporting import comparison_to_csv, projection_to_csv
from moneylab.strategies import compare_financial_strategies


def example_comparison():
    return compare_financial_strategies(
        current_savings=500, monthly_income=2000,
        monthly_living_expenses=1000, outstanding_loan_balance=1000,
        annual_loan_interest_rate=12, required_monthly_loan_payment=100,
        extra_monthly_loan_payment=200, months=2,
    )


def test_projection_export_contains_month_zero_and_exact_cents():
    result = example_comparison()
    content = projection_to_csv(result["saving"])
    rows = list(csv.DictReader(StringIO(content)))
    assert len(rows) == 3
    assert rows[0]["month"] == "0"
    assert rows[0]["savings"] == "500.00"
    assert rows[1]["interest_charged"] == "10.00"
    assert rows[1]["loan_balance"] == "910.00"
    assert rows[1]["extra_loan_payment"] == "0.00"
    assert Decimal(rows[-1]["net_position"]) == result["saving"]["summary"]["ending_net_position"]


def test_combined_export_has_both_named_strategies():
    result = example_comparison()
    rows = list(csv.DictReader(StringIO(comparison_to_csv(result))))
    assert len(rows) == 6
    assert [row["scenario"] for row in rows] == [
        "saving", "saving", "saving", "accelerated", "accelerated", "accelerated"
    ]
    assert rows[4]["extra_loan_payment"] == "200.00"
    assert Decimal(rows[-1]["loan_balance"]) == result["accelerated"]["summary"]["ending_loan_balance"]


def test_exports_preserve_negative_values_and_shortfalls():
    comparison = compare_financial_strategies(
        current_savings=0, monthly_income=50, monthly_living_expenses=100,
        outstanding_loan_balance=100, annual_loan_interest_rate=0,
        required_monthly_loan_payment=20, months=1,
        extra_monthly_loan_payment=50,
    )
    row = list(csv.DictReader(
        StringIO(projection_to_csv(comparison["saving"]))
    ))[1]
    assert row["savings"] == "0.00"
    assert row["unfunded_shortfall"] == "70.00"
    assert row["net_cash_flow"] == "-70.00"
    assert row["net_position"] == "-150.00"
