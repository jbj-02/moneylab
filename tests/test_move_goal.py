from decimal import Decimal

from moneylab.move_goal import move_goal_timing
from moneylab.moving import compare_moving


def test_spending_cut_advances_move_by_two_months_without_drawing_on_protected_cash():
    report = compare_moving({
        "income": 3500, "current_housing": 1200, "other_living": 1200,
        "checking": 1200, "savings": 3000, "rent": 1600,
        "security_deposit": 2400,
    })
    plan = {"monthly_savings": Decimal("200"), "cushion": Decimal("2000"),
            "deadline": 4}

    baseline = move_goal_timing(report, **plan)
    improved = move_goal_timing(report, **plan, spending_cut=Decimal("100"))

    assert baseline["months"] == 6
    assert baseline["deadline_gap"] == Decimal("400")
    assert improved["months"] == 4
    assert improved["cash_after"] == Decimal("3000")
    assert improved["monthly_after"] == baseline["monthly_after"] + Decimal("100")


def test_cut_closes_existing_budget_deficit_before_funding_move():
    report = compare_moving({
        "income": 1500, "current_housing": 1000, "other_living": 600,
        "checking": 0, "rent": 1200, "security_deposit": 300,
    })
    result = move_goal_timing(report, monthly_savings=Decimal("0"),
                              cushion=Decimal("0"), deadline=3,
                              spending_cut=Decimal("150"))
    assert result["monthly_savings"] == Decimal("50")
    assert result["months"] == 6
    assert result["monthly_after"] == Decimal("-150")
