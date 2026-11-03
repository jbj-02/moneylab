"""Decision interpretation must never invent net pay, frequencies, or balances."""
from decimal import Decimal as D

import pytest

from moneylab.decision_language import interpret_decision
from moneylab.scenario_changes import (
    apply_scenario_changes, compare_scenario_changes,
)


def test_moving_parses_net_income_rent_savings_and_upfront_costs():
    draft = interpret_decision(
        "I want to move out. My take-home pay is $3,500 monthly, "
        "new rent is $1,500/month, I have $8,000 saved, "
        "and security deposit is $1,500."
    )
    assert draft["intent"] == "moving"
    assert draft["values"]["income"] == "3500.00"
    assert draft["values"]["rent"] == "1500"
    assert draft["values"]["savings"] == "8000"
    assert draft["values"]["security_deposit"] == "1500"
    assert "current_housing" in draft["missing"]


def test_gross_salary_not_assumed_to_be_takehome_pay():
    draft = interpret_decision(
        "I want to move out and rent an apartment for $1,800 monthly. "
        "I make $60,000 per year before taxes and I have $8,000 saved."
    )
    assert draft["intent"] == "moving"
    assert draft["values"]["rent"] == "1800"
    assert draft["values"]["savings"] == "8000"
    assert "income" in draft["missing"]
    assert draft["gross_income"] is not None
    assert draft["gross_income"]["amount"] == "60000"


def test_biweekly_takehome_is_normalized_with_existing_cadence_math():
    draft = interpret_decision(
        "I want to move out. I take home $1,800 every two weeks, "
        "the apartment rent is $1,200 per month."
    )
    assert draft["intent"] == "moving"
    assert draft["values"]["income"] == "3900.00"
    assert draft["values"]["rent"] == "1200"


def test_purchase_and_recurring_costs_are_distinct():
    purchase = interpret_decision("Can I buy a $3,000 vacation this summer?")
    assert purchase["intent"] == "purchase"
    assert purchase["values"]["cost"] == "3000"
    recurring = interpret_decision(
        "I'd like a gym membership that costs $45 per month."
    )
    assert recurring["intent"] == "recurring"
    assert recurring["values"]["cost"] == "45"
    assert recurring["values"]["frequency"] == "monthly"


def test_recurring_without_frequency_keeps_frequency_missing():
    draft = interpret_decision("Can I add a gym membership that costs $45?")
    assert draft["intent"] == "recurring"
    assert "frequency" in draft["missing"]
    assert draft["values"]["cost"] == "45"


def test_unspecified_income_not_assumed_after_tax():
    draft = interpret_decision(
        "I'd like a new gym membership for $60 per month, "
        "and my salary is $60,000 annually."
    )
    assert draft["intent"] == "recurring"
    assert draft["values"]["cost"] == "60"
    assert "income" not in draft["values"]
    assert draft["gross_income"] is not None


def test_unsupported_and_multi_intent_are_detected_not_guessed():
    assert interpret_decision(
        "Can I refinance my student loans for a lower interest rate?"
    )["intent"] == "unsupported"
    assert interpret_decision(
        "I want to move out and buy a car for $6,000 at the same time."
    )["intent"] == "ambiguous"


@pytest.mark.parametrize("unsafe", ["", "hi", "x" * 2500, None, 5])
def test_invalid_descriptions_fail_closed(unsafe):
    with pytest.raises(ValueError):
        interpret_decision(unsafe)


def test_unrecognized_cost_does_not_create_fake_values():
    draft = interpret_decision(
        "I want to move out and my electricity is uncertain."
    )
    assert draft["intent"] == "moving"
    assert "utilities" not in draft["values"]
    assert "income" in draft["missing"]


def sample():
    return [
        {"id": "net", "kind": "income", "name": "Take-home", "monthly_amount": "3000"},
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": "1000"},
        {"id": "cash", "kind": "cash", "name": "Checking", "balance": "2500"},
        {"id": "save", "kind": "hysa", "name": "Emergency savings",
         "balance": "1000", "annual_rate": "0",
         "monthly_contribution": "0"},
    ]


def test_shared_engine_applies_multiple_changes_and_keeps_baseline_unchanged():
    baseline = sample()
    edits = [
        {"operation": "set_monthly", "block_id": "net", "amount": "3600"},
        {"operation": "set_monthly", "block_id": "rent", "amount": "1600"},
        {"operation": "add_monthly_expense", "amount": "150", "name": "New utilities"},
        {"operation": "one_time_cash", "amount": "1800", "allow_hysa": False},
    ]
    report = compare_scenario_changes(baseline, edits, 12)
    assert report["baseline"]["summary"]["monthly_income"] == D("3000")
    assert report["alternative"]["summary"]["monthly_income"] == D("3600")
    assert report["baseline"]["summary"]["monthly_expenses"] == D("1000")
    assert report["alternative"]["summary"]["monthly_expenses"] == D("1750")
    assert report["alternative"]["monthly_records"][0]["cash_position"] == D("700")
    assert baseline[2]["balance"] == "2500"
    assert baseline[1]["monthly_amount"] == "1000"


def test_upfront_cost_does_not_implicitly_consume_savings():
    data = sample()
    with pytest.raises(ValueError, match="borrowing"):
        apply_scenario_changes(data, [
            {"operation": "one_time_cash", "amount": "3000"},
        ])
    changed = apply_scenario_changes(data, [
        {"operation": "one_time_cash", "amount": "3000", "allow_hysa": True},
    ])
    assert changed[2]["balance"] == D("0")
    assert changed[3]["balance"] == D("500")
    assert data[2]["balance"] == "2500"


@pytest.mark.parametrize("changes", [
    [{"operation": "erase_profile"}],
    [{"operation": "set_monthly", "block_id": "missing", "amount": 10}],
    [{"operation": "add_monthly_expense", "amount": -2}],
    [{"operation": "add_monthly_expense", "amount": "NaN"}],
    [{"operation": "one_time_cash", "amount": 100, "allow_hysa": "yes"}],
    [{"operation": "set_monthly", "block_id": "cash", "amount": 100}],
])
def test_malformed_scenario_changes_are_rejected(changes):
    with pytest.raises(ValueError):
        apply_scenario_changes(sample(), changes)


def test_no_input_changes_and_no_arbitrary_extra_fields():
    with pytest.raises(ValueError):
        apply_scenario_changes(sample(), [])
    with pytest.raises(ValueError):
        apply_scenario_changes(sample(), [{
            "operation": "add_monthly_expense",
            "amount": 100,
            "api_key": "bad",
        }])
