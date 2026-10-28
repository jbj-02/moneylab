"""Decision Check must show math without inventing spendable cash or advice."""
from copy import deepcopy
from decimal import Decimal as D

import pytest

from moneylab.blocks import default_blocks, project_blocks
from moneylab.decisions import (
    amount, decision_check, emergency_readiness,
    goal_next_step, next_best_step,
)


def basic():
    return [
        {"id": "income", "kind": "income", "name": "Net pay", "monthly_amount": "3000"},
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": "1000"},
        {"id": "checking", "kind": "cash", "name": "Checking", "balance": "2400"},
    ]


def goal():
    return {"id": "goal", "kind": "goal", "name": "Emergency move",
            "balance": "0", "annual_rate": "0",
            "monthly_contribution": "50", "target": "1200", "target_months": 12}


def test_recurring_weekly_expense_is_normalized_and_keeps_base_intact():
    blocks = basic()
    original = deepcopy(blocks)
    r = decision_check(blocks, cost=100, cost_type="recurring",
                       frequency="weekly", months=12, reviewed=True)
    assert r["comparable"] is True
    assert r["monthly_equivalent"] == D("433.33")
    assert r["monthly_buffer_before"] == D("2000.00")
    assert r["monthly_buffer_after"] == D("1566.67")
    assert r["monthly_buffer_change"] == D("-433.33")
    assert r["ending_net_change"] == D("-5199.96")
    assert r["goals_affected"] == []
    assert not r["preliminary"]
    assert blocks == original


def test_one_time_purchase_reduces_checking_only_without_repeating_cost():
    r = decision_check(basic(), cost=500, cost_type="one_time",
                       months=12, reviewed=True)
    assert r["remaining_checking_now"] == D("1900.00")
    assert r["monthly_buffer_change"] == D("0.00")
    assert r["ending_cash_change"] == D("-500.00")
    assert r["ending_net_change"] == D("-500.00")
    assert any("One-time" in note for note in r["cautions"])


def test_one_time_purchase_not_invented_from_savings_or_borrowing():
    blocks = basic()
    blocks[2]["balance"] = "200"
    blocks.append({"id": "hysa", "kind": "hysa", "name": "Savings",
                   "balance": "10000", "annual_rate": 0,
                   "monthly_contribution": 0})
    r = decision_check(blocks, cost=350, cost_type="one_time",
                       reviewed=True)
    assert r["comparable"] is False
    assert r["available_checking"] == D("200.00")
    assert "won't assume borrowing" in r["reason"]


def test_missing_income_or_unreviewed_are_preliminary_even_with_positive_cash():
    blocks = basic()
    r = decision_check(blocks, cost=200, cost_type="recurring",
                       reviewed=False)
    assert r["preliminary"]
    assert "not been manually reviewed" in " ".join(r["cautions"])
    missing = [b for b in blocks if b["kind"] != "income"]
    r = decision_check(missing, cost=200, cost_type="recurring",
                       reviewed=True)
    assert r["preliminary"]
    assert any("Missing core" in note for note in r["cautions"])


def test_large_new_commitment_flags_new_unfunded_shortfall():
    r = decision_check(basic(), cost=2800, cost_type="recurring",
                       months=6, reviewed=True)
    assert r["needs_attention"]
    assert r["new_unfunded_shortfall"] > D("0")


def test_goal_impact_is_derived_from_modeled_scenario_not_guessed():
    blocks = basic() + [goal()]
    base = project_blocks(blocks, 12)
    r = decision_check(blocks, cost=1980, cost_type="recurring",
                       months=12, reviewed=True)
    assert r["comparable"]
    assert r["goals_affected"]
    assert r["goals_affected"][0]["after"] < r["goals_affected"][0]["before"]
    assert r["goals_affected"][0]["previous_on_track"] == base["goals"][0]["on_track"]


@pytest.mark.parametrize("bad", ["NaN", "Infinity", -100, 0, True,
                                  "1.001", "not-a-number"])
def test_invalid_decision_cost_fails_closed(bad):
    with pytest.raises(ValueError):
        amount(bad)


def test_explicit_emergency_target_coverage_and_gap():
    r = emergency_readiness(
        basic(), target_months=3, build_months=12, reviewed=True,
    )
    assert r["evaluable"]
    assert r["eligible_starting_funds"] == D("2400.00")
    assert r["recorded_monthly_outflow"] == D("1000.00")
    assert r["coverage_months"] == D("2.4")
    assert r["target_funds"] == D("3000.00")
    assert r["gap"] == D("600.00")
    assert r["average_additional_monthly_amount"] == D("50.00")
    assert r["within_first_month_buffer"]


def test_emergency_liquid_funds_do_not_include_earmarked_retirement():
    blocks = basic()
    blocks.extend([
        {"id": "roth", "kind": "roth_ira", "name": "Roth", "balance": 20000,
         "annual_rate": 0, "monthly_contribution": 0},
        {"id": "goal", "kind": "goal", "name": "Vacation", "balance": 10000,
         "target": 10000, "target_months": 12,
         "annual_rate": 0, "monthly_contribution": 0},
    ])
    r = emergency_readiness(blocks, reviewed=True)
    assert r["eligible_starting_funds"] == D("2400.00")


def test_emergency_readiness_requires_cash_and_expenses():
    assert not emergency_readiness([], reviewed=True)["evaluable"]
    assert not emergency_readiness(
        [b for b in basic() if b["kind"] != "cash"],
        reviewed=True,
    )["evaluable"]


def test_goal_coaching_finds_exact_minimum_contribution():
    blocks = basic() + [goal()]
    before = deepcopy(blocks)
    r = goal_next_step(blocks, "goal", months=6, reviewed=True)
    assert not r["on_track"]
    assert r["feasible_with_buffer"]
    assert r["goal_projection"]["on_track"] is False
    assert r["additional_monthly"] == D("50.00")
    assert r["proposed_contribution"] == D("100.00")
    assert next(x for x in r["forecast"]["goals"] if x["id"] == "goal")["on_track"] is True
    assert blocks == before


def test_goal_coaching_reports_when_no_extra_capacity():
    blocks = [
        {"id": "pay", "kind": "income", "name": "Net", "monthly_amount": "1000"},
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": "1000"},
        {"id": "cash", "kind": "cash", "name": "Cash", "balance": "0"},
        goal(),
    ]
    r = goal_next_step(blocks, "goal", reviewed=True)
    assert r["additional_monthly"] is None
    assert not r["feasible_with_buffer"]


def test_next_best_step_is_prioritized():
    assert next_best_step([])["action"] == "quick_start"
    assert next_best_step(basic()[:-1], reviewed=True)["id"] == "complete"
    assert next_best_step(basic(), reviewed=False)["id"] == "review"
    deficit = basic()
    deficit[0]["monthly_amount"] = "500"
    assert next_best_step(deficit, reviewed=True)["id"] == "deficit"
    assert next_best_step(basic() + [goal()], months=12, reviewed=True)["id"] == "goal"
    assert next_best_step(basic(), reviewed=True, reserve_target_months=3)["id"] == "reserves"
    assert next_best_step(basic(), reviewed=True, reserve_target_months=2)["id"] == "explore"
