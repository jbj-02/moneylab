"""Tests for conservative, explainable MoneyLab financial check-ins."""

from decimal import Decimal

from moneylab.blocks import project_blocks
from moneylab.checkin import build_checkin

D = Decimal


def income(amount=2000):
    return {"id": "salary", "kind": "income", "name": "Take-home salary",
            "monthly_amount": amount}


def expense(amount=1000):
    return {"id": "rent", "kind": "expense", "name": "Rent",
            "monthly_amount": amount}


def cash(amount=4000):
    return {"id": "cash", "kind": "cash", "name": "Checking",
            "balance": amount}


def check(blocks, *, reviewed=False, months=12):
    return build_checkin(blocks, project_blocks(blocks, months),
                         reviewed=reviewed)


def test_empty_profile_is_not_misleadingly_on_track():
    status = check([], reviewed=True)
    assert status["status"] == "not_enough_information"
    assert len(status["missing"]) == 3
    assert status["coverage_months"] is None
    assert status["spending_buffer"] == D("0.00")


def test_missing_information_and_unreviewed_profiles_are_not_on_track():
    blocks = [income(), expense(), cash()]
    unreviewed = check(blocks)
    assert unreviewed["status"] == "not_enough_information"
    assert unreviewed["missing"] == []
    assert any("Confirm" in action for action in unreviewed["actions"])
    reviewed = check(blocks, reviewed=True)
    assert reviewed["status"] == "on_track"
    assert reviewed["reviewed"] is True


def test_insufficient_regular_income_triggers_attention_without_shortfall():
    blocks = [income(900), expense(1000), cash(50000)]
    report = check(blocks, reviewed=True, months=2)
    assert report["status"] == "needs_attention"
    assert any("exceed" in issue for issue in report["attention"])
    assert report["coverage_months"] == D("50.0")


def test_monthly_shortfall_is_flagged_even_without_loan():
    blocks = [income(400), expense(800), cash(100)]
    report = check(blocks, reviewed=True)
    assert report["status"] == "needs_attention"
    assert any("unfunded" in issue for issue in report["attention"])


def test_failed_goal_is_flagged():
    blocks = [income(), expense(), cash(),
              {"id": "goal", "kind": "goal", "name": "Vacation",
               "balance": 0, "monthly_contribution": 10,
               "annual_rate": 0, "target": 1000, "target_months": 6}]
    report = check(blocks, reviewed=True)
    assert report["status"] == "needs_attention"
    assert report["missed_goals"] == ["Vacation"]
    assert any("Vacation" in item for item in report["attention"])


def test_goals_beyond_horizon_are_not_declared_on_track():
    blocks = [income(), expense(), cash(),
              {"id": "goal", "kind": "goal", "name": "Move out",
               "balance": 0, "monthly_contribution": 50,
               "annual_rate": 0, "target": 1500, "target_months": 36}]
    report = check(blocks, reviewed=True, months=12)
    assert report["status"] == "not_enough_information"
    assert report["unassessed_goals"] == ["Move out"]
    assert any("Extend" in action for action in report["actions"])


def test_only_liquid_savings_count_toward_spending_coverage():
    blocks = [
        income(), expense(), cash(1000),
        {"id": "hysa", "kind": "hysa", "name": "HYSA",
         "balance": 600, "annual_rate": 0, "monthly_contribution": 0},
        {"id": "savings", "kind": "account", "name": "Savings",
         "account_type": "savings", "balance": 400,
         "annual_rate": 0, "monthly_contribution": 0},
        {"id": "roth", "kind": "roth_ira", "name": "Retirement",
         "balance": 100000, "annual_rate": 0, "monthly_contribution": 0},
        {"id": "cd", "kind": "account", "name": "CD",
         "account_type": "cd", "balance": 100000,
         "annual_rate": 0, "monthly_contribution": 0},
        {"id": "goal", "kind": "goal", "name": "Travel",
         "balance": 500, "annual_rate": 0, "monthly_contribution": 0,
         "target": 500, "target_months": 4},
    ]
    report = check(blocks, reviewed=True)
    assert report["accessible_starting_funds"] == D("2000.00")
    assert report["coverage_months"] == D("2.0")
    assert report["status"] == "on_track"


def test_loan_growth_is_reported():
    blocks = [
        income(), expense(), cash(),
        {"id": "loan", "kind": "loan", "name": "Education loan",
         "balance": 1000, "annual_rate": 12,
         "monthly_payment": 5},
    ]
    report = check(blocks, reviewed=True)
    assert report["status"] == "needs_attention"
    assert any("loan payment" in msg for msg in report["attention"])
