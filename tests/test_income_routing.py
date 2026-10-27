"""Regression tests for flexible financial accounts and routed paychecks."""

from decimal import Decimal

import pytest

from moneylab.blocks import (
    ACCOUNT_TYPES, default_blocks, profile_from_json, profile_to_json,
    project_blocks, serialize_blocks, validate_blocks,
)
from moneylab.insights import scenario_impacts
from moneylab.blocks import modify_expense

D = Decimal


def paycheck(routes=None, amount="1000"):
    entry = {"id": "pay", "kind": "income", "name": "Net salary",
             "monthly_amount": amount}
    if routes is not None:
        entry["routes"] = routes
    return entry


def route(target, value, mode="fixed"):
    return {"destination_id": target, "mode": mode, "value": value}


def savings(ident="savings", subtype="savings", balance="0", monthly="0"):
    return {"id": ident, "kind": "account", "name": subtype,
            "account_type": subtype, "balance": balance,
            "annual_rate": "0", "monthly_contribution": monthly}


@pytest.mark.parametrize("account_type", sorted(ACCOUNT_TYPES))
def test_all_extended_account_types_are_projectable(account_type):
    items = [savings(subtype=account_type)]
    result = project_blocks(items, 1)
    assert result["summary"]["ending_assets"] == D("0.00")
    assert serialize_blocks(items)[0]["account_type"] == account_type


def test_fixed_and_percentage_direct_deposits_are_counted_once():
    items = [
        paycheck([route("invest", "25", "percent"),
                  route("checking", "100")]),
        {"id": "checking", "kind": "cash", "name": "Checking", "balance": "0"},
        savings("invest", "roth_ira"),
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": 400},
    ]
    result = project_blocks(items, 2)
    summary = result["summary"]
    row = result["monthly_records"][1]
    assert summary["monthly_income"] == D("1000.00")
    assert summary["first_month_direct_to_assets"] == D("250.00")
    assert summary["first_month_direct_to_cash"] == D("100.00")
    assert summary["first_month_transfers"] == D("250.00")
    assert row["direct_deposits"] == {"invest": D("250.00"),
                                      "checking": D("100.00")}
    assert row["cash_position"] == D("350.00")
    assert row["other_assets"] == D("250.00")
    assert row["net_position"] == D("600.00")
    assert result["monthly_records"][2]["net_position"] == D("1200.00")
    assert summary["unallocated_monthly_buffer"] == D("350.00")


def test_route_to_checking_does_not_reduce_spendable_cash():
    items = [
        paycheck([route("checking", "100", "percent")]),
        {"id": "checking", "kind": "cash", "name": "Checking", "balance": "0"},
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": 300},
    ]
    outcome = project_blocks(items, 1)
    assert outcome["summary"]["ending_cash_savings"] == D("700.00")
    assert outcome["summary"]["first_month_transfers"] == D("0.00")


def test_direct_deposits_and_recurring_contributions_both_transfer_once():
    items = [
        paycheck([route("hysa", "200")]),
        savings("hysa", "hysa", monthly="100"),
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": 400},
    ]
    result = project_blocks(items, 1)
    row = result["monthly_records"][1]
    assert row["asset_contributions"] == D("300.00")
    assert row["cash_position"] == D("300.00")
    assert row["other_assets"] == D("300.00")
    assert row["net_position"] == D("600.00")


def test_direct_deposit_may_leave_cash_shortfall_but_not_invent_money():
    items = [
        paycheck([route("hysa", "800")]),
        savings("hysa", "hysa"),
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": 400},
    ]
    result = project_blocks(items, 1)
    assert result["summary"]["ending_unfunded_shortfall"] == D("200.00")
    assert result["summary"]["unallocated_monthly_buffer"] == D("0.00")
    assert result["summary"]["ending_assets"] == D("800.00")
    assert result["summary"]["ending_net_position"] == D("600.00")


def test_fractional_percentages_are_decimal_exact_and_round_at_cents():
    items = [paycheck([route("hysa", "33.333", "percent")]),
             savings("hysa", "hysa")]
    result = project_blocks(items, 1)
    assert result["summary"]["first_month_direct_to_assets"] == D("333.33")
    assert result["summary"]["ending_cash_savings"] == D("666.67")


def test_multiple_incomes_route_to_same_account():
    items = [
        paycheck([route("hysa", 100)], "1000"),
        {"id": "side", "kind": "income", "name": "Side job",
         "monthly_amount": "200", "routes": [route("hysa", 50)]},
        savings("hysa", "hysa"),
    ]
    result = project_blocks(items, 1)
    assert result["summary"]["ending_assets"] == D("150.00")
    assert result["summary"]["ending_cash_savings"] == D("1050.00")


@pytest.mark.parametrize("bad_routes", [
    [route("missing", 5)],
    [route("expense", 5)],
    [route("savings", 101, "percent")],
    [route("savings", -1)],
    [route("savings", 800), route("checking", 400)],
    [route("savings", 10), route("savings", 10)],
    [{"destination_id": "savings", "value": 10, "mode": "unknown"}],
    [{"destination_id": "savings", "value": 10}],
])
def test_bad_routes_rejected(bad_routes):
    items = [
        paycheck(bad_routes),
        {"id": "checking", "kind": "cash", "name": "Checking", "balance": 0},
        savings(),
        {"id": "expense", "kind": "expense", "name": "Rent", "monthly_amount": 100},
    ]
    with pytest.raises(ValueError):
        validate_blocks(items)


def test_json_roundtrip_preserves_routes_and_precision():
    items = [paycheck([route("savings", "12.345", "percent")]), savings()]
    data = profile_to_json(items)
    restored = profile_from_json(data)
    assert restored == serialize_blocks(items)
    assert restored[0]["routes"][0]["value"] == "12.345"


def test_scenario_alerts_describe_actual_changed_fields():
    initial = default_blocks()
    baseline = project_blocks(initial, 24)
    changed = project_blocks(modify_expense(initial, "rent", 1000), 24)
    alerts = scenario_impacts(baseline, changed, initial)
    titles = [alert["title"] for alert in alerts]
    assert "Monthly spending flexibility changed" in titles
    assert "Projected checking / cash" in titles
    assert "Projected modeled net position" in titles
    assert any(title.startswith("Goal: ") for title in titles)
    assert any(alert["level"] == "warning" for alert in alerts)
    assert any(alert["change"] is not None for alert in alerts)


def test_scenario_alerts_do_not_claim_unaffected_goal_changed():
    blocks = default_blocks()
    original = project_blocks(blocks, 12)
    mild = project_blocks(modify_expense(blocks, "rent", 10), 12)
    alerts = scenario_impacts(original, mild, blocks)
    assert not any(alert["title"].startswith("Goal:") for alert in alerts)


def test_scenario_alerts_unchanged_plan_is_neutral():
    blocks = default_blocks()
    a = project_blocks(blocks, 12)
    b = project_blocks(modify_expense(blocks, "rent", 0), 12)
    notices = scenario_impacts(a, b, blocks)
    assert len(notices) == 1
    assert notices[0]["level"] == "info"
    assert notices[0]["title"] == "No change in modeled outcomes"
