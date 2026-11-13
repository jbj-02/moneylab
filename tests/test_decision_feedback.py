from copy import deepcopy
from decimal import Decimal

from moneylab.blocks import default_blocks
from moneylab.decision_feedback import goal_gap_changes, purchase_feedback


def test_purchase_distinguishes_existing_goal_gap_from_new_cash_impact():
    profile = default_blocks()
    original = deepcopy(profile)
    result = purchase_feedback(profile, 200, 2100)
    comparison = result["comparison"]
    assert result["after"] == 2000
    assert result["limit"] == 100
    assert result["wait_month"] == 1
    assert ("Summer travel fund", 18, Decimal("350"), Decimal("350")) in list(
        goal_gap_changes(comparison["baseline"], comparison["alternative"])
    )
    assert profile == original


def test_purchase_short_on_checking_does_not_use_dedicated_savings():
    result = purchase_feedback(default_blocks(), 2300, 2100)
    assert result["after"] == -100
    assert result["comparison"] is None


def test_purchase_warns_when_it_causes_a_future_unpaid_cost():
    profile = [
        {"id": "cash", "kind": "cash", "name": "Checking", "balance": "300"},
        {"id": "pay", "kind": "income", "name": "Pay", "monthly_amount": "100"},
        {"id": "bills", "kind": "expense", "name": "Bills", "monthly_amount": "250"},
    ]
    result = purchase_feedback(profile, 200, 0)
    assert result["after"] == 100
    assert result["future_shortfall"] == 1
