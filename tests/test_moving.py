"""Alpha regression tests: multi-cost comparisons, incomplete inputs and safety."""
from copy import deepcopy
from decimal import Decimal as D
import csv
from io import StringIO

import pytest

from moneylab.moving import FIELDS, compare_moving, comparison_csv

EXAMPLE = {
    "income": 3600, "current_housing": 400,
    "other_living": 850, "minimum_debt": 150,
    "checking": 4500, "savings": 3000,
    "rent": 1400, "utilities": 110, "internet": 50,
    "renters_insurance": 20, "transport_change": 45,
    "groceries_change": 100, "other_change": 0,
    "security_deposit": 1400, "moving_cost": 600,
    "furniture": 400, "other_upfront": 0,
}


def evaluate(**changes):
    values = {**EXAMPLE, **changes}
    return compare_moving(values, reviewed=True)


def test_full_sample_exact_current_and_proposed_costs():
    r = evaluate()
    assert r["fundable"]
    assert r["current_monthly"] == D("1400")
    assert r["proposed_monthly"] == D("2725")
    assert r["monthly_change"] == D("1325")
    assert r["monthly_margin_before"] == D("2200")
    assert r["monthly_margin_after"] == D("875")
    assert r["upfront"] == D("2400")
    assert r["current_liquid"] == D("7500")
    assert r["remaining_liquid"] == D("5100")
    assert r["funding_gap"] == D("0")
    assert r["missing"] == []


def test_six_twelve_and_twenty_four_month_impact():
    r = evaluate()
    for horizon in (6, 12, 24):
        assert r["timeframes"][horizon]["liquid_change"] == (
            -D("2400") - D("1325") * horizon
        )
    assert len(r["timeframes"]) == 3


def test_proposed_scenario_does_not_mutate_financial_profile_or_input():
    source = deepcopy(EXAMPLE)
    goals = [{
        "id": "goal1", "kind": "goal", "name": "Travel",
        "balance": "100", "annual_rate": "0",
        "monthly_contribution": "40", "target": "800", "target_months": 18,
    }]
    before = deepcopy(goals)
    compare_moving(source, existing_goals=goals, reviewed=True)
    assert source == EXAMPLE
    assert goals == before


def test_cash_first_and_savings_requires_opt_in():
    data = {**EXAMPLE, "checking": 1000, "savings": 5000}
    no = compare_moving(data, reviewed=True)
    assert not no["fundable"]
    assert no["funding_gap"] == D("1400")
    assert no["proposed"] is None
    yes = compare_moving(
        data, reviewed=True, use_savings_for_upfront=True
    )
    assert yes["fundable"]
    assert yes["remaining_liquid"] == D("3600")
    assert yes["timeframes"][6]["liquid_change"] == -D("10350")


def test_zero_upfront_zero_balances_are_valid_but_not_spendable():
    r = evaluate(
        checking=0, savings=0, security_deposit=0, moving_cost=0, furniture=0
    )
    assert r["fundable"]
    assert r["remaining_liquid"] == D("0")
    assert r["timeframes"][24]["liquid_change"] == -D("31800")


def test_negative_monthly_remainder_is_signed_not_clamped():
    r = evaluate(income=2200)
    assert r["monthly_margin_after"] == D("-525")
    assert r["fundable"]
    assert any("exceed" in warning for warning in r["warnings"])


def test_incomplete_optional_costs_are_explicitly_unknown():
    values = {"income": 3000, "current_housing": 0, "rent": 1100}
    r = compare_moving(values, reviewed=False)
    assert r["fundable"]
    assert "utilities" in r["missing"]
    assert "other_living" in r["missing"]
    assert "checking" in r["missing"]
    assert any("modeled at zero" in w for w in r["warnings"])
    assert any("provisional" in w for w in r["warnings"])
    assert r["monthly_margin_before"] == D("3000")


def test_goal_can_lose_affordability_after_move_without_creating_financing():
    vals = {**EXAMPLE,
            "income": 3000, "current_housing": 500,
            "other_living": 1800, "minimum_debt": 0,
            "rent": 1300, "utilities": 100, "internet": 0,
            "renters_insurance": 0, "transport_change": 0,
            "groceries_change": 0, "other_change": 0,
            "checking": 2000, "savings": 0,
            "security_deposit": 0, "moving_cost": 0,
            "furniture": 0, "other_upfront": 0}
    goals = [{
        "id": "target", "kind": "goal", "name": "First car",
        "balance": 0, "annual_rate": 0,
        "monthly_contribution": 200, "target": 1200,
        "target_months": 6,
    }]
    r = compare_moving(vals, existing_goals=goals, reviewed=True)
    assert len(r["goals_affected"]) == 1
    g = r["goals_affected"][0]
    assert g["previous_on_track"]
    assert not g["on_track"]
    assert any("fall behind" in w for w in r["warnings"])


def test_existing_goals_without_profile_income_are_still_allowed():
    r = compare_moving(EXAMPLE, existing_goals=[{
        "id": "moving_income", "kind": "goal", "name": "Collision",
        "balance": 100, "annual_rate": 0, "monthly_contribution": 0,
        "target": 100, "target_months": 12,
    }])
    assert r["fundable"]
    assert r["goals_included"] == 1


@pytest.mark.parametrize("change", [
    {"income": "NaN"}, {"income": "Infinity"}, {"income": "-200"},
    {"rent": -1}, {"utilities": -2}, {"checking": "-0.01"},
    {"moving_cost": "1000000000"}, {"furniture": True},
    {"rent": "0"}, {"rent": "1.001"}, {"income": None},
    {"transport_change": "-5000"},
])
def test_invalid_or_excessive_input_rejected(change):
    with pytest.raises(ValueError):
        evaluate(**change)


def test_declines_unrecognized_fields_and_non_goal_blocks():
    with pytest.raises(ValueError):
        compare_moving({**EXAMPLE, "bank_password": "not allowed"})
    with pytest.raises(ValueError):
        compare_moving(EXAMPLE, existing_goals=[{
            "id": "pay", "kind": "income", "name": "Pay",
            "monthly_amount": 2000,
        }])


def test_csv_has_comparison_not_private_names_or_unauthorized_urls():
    result = evaluate()
    data = comparison_csv(result)
    rows = list(csv.reader(StringIO(data)))
    assert rows[0] == ["MoneyLab Moving Decision Alpha", "stay", "move", "change"]
    assert len(rows) >= 7
    assert "https" not in data and "account number" not in data
    with pytest.raises(ValueError):
        comparison_csv(evaluate(checking=0, savings=0))


def test_zero_monthly_rent_now_is_supported():
    r = evaluate(current_housing=0)
    assert r["fundable"]
    assert r["current_monthly"] == D("1000")
