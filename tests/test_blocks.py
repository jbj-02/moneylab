"""Tests for personalized financial blocks, projections, and saved profiles."""
from decimal import Decimal

import pytest

from moneylab.blocks import (
    default_blocks, modify_expense, profile_from_json, profile_to_json,
    project_blocks, serialize_blocks, validate_blocks,
)

D = Decimal


def test_starter_profile_contains_relevant_blocks():
    kinds = {block["kind"] for block in default_blocks()}
    assert kinds == {"income", "expense", "loan", "cash", "hysa", "roth_ira", "goal"}
    assert len(validate_blocks(default_blocks())) == 10


def test_default_profile_budget_and_accounting():
    r = project_blocks(default_blocks(), 1)
    s = r["summary"]
    assert s["monthly_income"] == D("3800.00")
    assert s["monthly_expenses"] == D("2000.00")
    assert s["first_month_loan_payments"] == D("470.00")
    assert s["first_month_transfers"] == D("425.00")
    assert s["unallocated_monthly_buffer"] == D("905.00")
    assert s["estimated_extra_weekly_spend"] == D("208.85")
    assert r["monthly_records"][0]["net_position"] == D("-22000.00")
    first = r["monthly_records"][1]
    assert first["cash_position"] == D("3105.00")
    assert first["loan_balance"] == D("26146.38")
    assert first["other_assets"] == D("2731.83")
    assert first["net_position"] == D("-20309.55")
    assert s["total_interest"] == D("116.38")


def test_month_zero_and_one_reconcile_transactions():
    rows = project_blocks(default_blocks(), 24)["monthly_records"]
    assert len(rows) == 25
    assert rows[0]["income"] == D("0.00")
    for previous, current in zip(rows, rows[1:]):
        assert current["cash_position"] == previous["cash_position"] + current["net_cash_flow"]
        assert current["net_position"] == (
            current["cash_position"] + current["other_assets"] - current["loan_balance"]
        )
        assert current["cash_position"] == current["cash_savings"] - current["unfunded_shortfall"]
        assert current["net_cash_flow"] == (
            current["income"] - current["living_expenses"] - current["loan_payments"]
            - current["asset_contributions"]
        )


def test_extra_expense_scenario_is_copy_and_raises_cost():
    original = default_blocks()
    adjusted = modify_expense(original, "rent", 200)
    assert original[1]["monthly_amount"] == "1350"
    assert adjusted[1]["monthly_amount"] == "1550.00"
    base = project_blocks(original, 12)["summary"]
    new = project_blocks(adjusted, 12)["summary"]
    assert base["unallocated_monthly_buffer"] - new["unallocated_monthly_buffer"] == D("200.00")
    assert base["ending_net_position"] - new["ending_net_position"] == D("2400.00")


def test_add_custom_expense_and_loan():
    blocks = [
        {"id": "salary", "kind": "income", "name": "Paycheck", "monthly_amount": 2000},
        {"id": "rent", "kind": "expense", "name": "Apartment", "monthly_amount": 900},
        {"id": "car", "kind": "loan", "name": "Car note", "balance": 500,
         "annual_rate": 0, "monthly_payment": 300},
        {"id": "cash", "kind": "cash", "name": "Checking", "balance": 50},
    ]
    result = project_blocks(blocks, 3)
    assert [row["loan_payments"] for row in result["monthly_records"][1:]] == [
        D("300.00"), D("200.00"), D("0.00")
    ]
    assert result["summary"]["ending_debt"] == D("0.00")
    assert result["summary"]["ending_cash_savings"] == D("2850.00")


def test_multiple_loans_and_increasing_balances_warning():
    blocks = [
        {"id": "one", "kind": "loan", "name": "Loan A", "balance": 1000,
         "annual_rate": 12, "monthly_payment": 5},
        {"id": "two", "kind": "loan", "name": "Loan B", "balance": 500,
         "annual_rate": 0, "monthly_payment": 50},
    ]
    r = project_blocks(blocks, 2)
    assert r["monthly_records"][1]["loan_balance"] == D("1455.00")
    assert r["monthly_records"][1]["negative_amortization"] is True
    assert r["summary"]["ending_unfunded_shortfall"] == D("110.00")


def test_transfers_never_draw_down_starting_savings():
    blocks = [
        {"id": "cash", "kind": "cash", "name": "Bank", "balance": 10000},
        {"id": "hysa", "kind": "hysa", "name": "Savings", "balance": 200,
         "annual_rate": 0, "monthly_contribution": 600},
    ]
    s = project_blocks(blocks, 1)
    assert s["summary"]["first_month_transfers"] == D("0.00")
    assert s["summary"]["ending_cash_savings"] == D("10000.00")
    assert s["summary"]["ending_assets"] == D("200.00")


def test_shortfalls_are_not_spendable_money():
    blocks = [
        {"id": "earn", "kind": "income", "name": "Income", "monthly_amount": 200},
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": 400},
        {"id": "hysa", "kind": "hysa", "name": "Savings", "balance": 10,
         "annual_rate": 0, "monthly_contribution": 100},
    ]
    s = project_blocks(blocks, 2)
    assert s["summary"]["ending_unfunded_shortfall"] == D("400.00")
    assert s["summary"]["unallocated_monthly_buffer"] == D("0.00")
    assert s["summary"]["first_month_transfers"] == D("0.00")


def test_previous_unfunded_shortfall_first():
    blocks = [
        {"id": "pay", "kind": "income", "name": "Salary", "monthly_amount": 100},
        {"id": "expense", "kind": "expense", "name": "Costs", "monthly_amount": 50},
        {"id": "debt", "kind": "loan", "name": "Debt", "balance": 70,
         "annual_rate": 0, "monthly_payment": 70},
        {"id": "hysa", "kind": "hysa", "name": "Savings", "balance": 0,
         "annual_rate": 0, "monthly_contribution": 50},
    ]
    r = project_blocks(blocks, 3)
    assert r["monthly_records"][1]["unfunded_shortfall"] == D("20.00")
    assert r["monthly_records"][2]["asset_contributions"] == D("30.00")
    assert r["monthly_records"][2]["cash_position"] == D("0.00")
    assert r["monthly_records"][3]["asset_contributions"] == D("50.00")


def test_goal_deadline_and_progress():
    goals = [
        {"id": "pay", "kind": "income", "name": "Income", "monthly_amount": 100},
        {"id": "vacation", "kind": "goal", "name": "Holiday", "balance": 100,
         "annual_rate": 0, "monthly_contribution": 50, "target": 200,
         "target_months": 2},
    ]
    r = project_blocks(goals, 2)
    assert r["goals"][0]["on_track"] is True
    assert r["goals"][0]["projected_at_deadline"] == D("200.00")
    late = project_blocks(goals, 1)["goals"][0]
    assert late["on_track"] is None


def test_profile_json_round_trip_preserves_precision():
    blocks = default_blocks()
    raw = profile_to_json(blocks)
    saved = profile_from_json(raw)
    assert saved == serialize_blocks(blocks)
    assert profile_to_json(saved) == raw


def test_empty_profile_is_valid_and_has_zero_finances():
    r = project_blocks([], 12)
    assert r["summary"]["ending_net_position"] == D("0.00")
    assert r["summary"]["unallocated_monthly_buffer"] == D("0.00")
    assert len(r["monthly_records"]) == 13


@pytest.mark.parametrize("bad", [
    "not json", "[]", '{"schema_version":2,"blocks":[]}',
    '{"schema_version":1,"blocks":{}}',
])
def test_bad_profile_file(bad):
    with pytest.raises(ValueError):
        profile_from_json(bad)


@pytest.mark.parametrize("blocks", [
    [{"id": "x", "kind": "potatoes", "name": "Not valid"}],
    [{"id": "!?", "kind": "income", "name": "Salary", "monthly_amount": 10}],
    [{"id": "x", "kind": "income", "name": " ", "monthly_amount": 10}],
    [{"id": "x", "kind": "income", "name": "Salary", "monthly_amount": -1}],
    [{"id": "x", "kind": "income", "name": "Salary", "monthly_amount": "NaN"}],
    [{"id": "x", "kind": "income", "name": "Salary", "monthly_amount": 20, "balance": 20}],
    [{"id": "x", "kind": "income", "name": "Salary", "monthly_amount": 10},
     {"id": "x", "kind": "expense", "name": "Rent", "monthly_amount": 10}],
    [{"id": "x", "kind": "hysa", "name": "High-yield", "balance": 10,
      "annual_rate": 101, "monthly_contribution": 10}],
    [{"id": "x", "kind": "goal", "name": "Savings goal", "balance": 10,
      "annual_rate": 0, "monthly_contribution": 10, "target": 0, "target_months": 12}],
    [{"id": "x", "kind": "goal", "name": "Savings goal", "balance": 10,
      "annual_rate": 0, "monthly_contribution": 10, "target": 100, "target_months": 0}],
])
def test_bad_blocks_rejected(blocks):
    with pytest.raises(ValueError):
        validate_blocks(blocks)


@pytest.mark.parametrize("horizon", [0, -2, 601, 2.0, "12", True])
def test_invalid_horizon_rejected(horizon):
    with pytest.raises(ValueError):
        project_blocks([], horizon)


def test_change_can_only_target_expense():
    with pytest.raises(ValueError):
        modify_expense(default_blocks(), "pay", 100)
    with pytest.raises(ValueError):
        modify_expense(default_blocks(), "missing", 100)
    with pytest.raises(ValueError):
        modify_expense(default_blocks(), "rent", -100000)
