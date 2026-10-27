"""Quick Start protects user decisions and financial accounting."""
from copy import deepcopy
from decimal import Decimal

import pytest

from moneylab.blocks import default_blocks, project_blocks
from moneylab.onboarding import (
    DRAFT_MAX, approve_drafts, guided_drafts, make_block, parse_drafts,
)


def test_guided_setup_creates_several_frequency_aware_blocks():
    drafts = guided_drafts({
        "income": 1800, "income_frequency": "biweekly",
        "rent": 1200, "rent_frequency": "monthly",
        "groceries": 100, "groceries_frequency": "weekly",
        "checking": 550, "savings": 850,
        "include_goal": True, "goal_name": "Emergency fund",
        "goal_target": 3000, "goal_months": 12,
        "goal_contribution": 150,
    })
    assert [d["kind"] for d in drafts] == [
        "income", "expense", "expense", "cash", "hysa", "goal",
    ]
    assert all(not draft["missing"] for draft in drafts)
    merged = approve_drafts([], drafts, id_factory=iter(
        ["pay", "rent", "food", "checking", "savings", "emergency"]
    ).__next__)
    assert len(merged) == 6
    assert merged[0]["frequency"] == "biweekly"
    assert merged[0]["monthly_amount"] == "3900.00"
    assert merged[2]["frequency"] == "weekly"
    assert merged[2]["monthly_amount"] == "433.33"
    assert merged[3]["balance"] == "550.00"
    assert merged[-1]["target"] == "3000.00"
    result = project_blocks(merged, 12)
    assert result["summary"]["monthly_income"] == Decimal("3900.00")
    assert result["summary"]["monthly_expenses"] == Decimal("1633.33")


def test_unanswered_sections_are_skipped_not_invented():
    assert guided_drafts({}) == []
    drafts = guided_drafts({"rent": 1100})
    assert len(drafts) == 1
    assert drafts[0]["name"] == "Rent / housing"


def test_incomplete_student_loan_not_silently_added():
    drafts = guided_drafts({"debt": 12000})
    assert len(drafts) == 1
    assert set(drafts[0]["missing"]) == {"annual_rate", "monthly_payment"}
    with pytest.raises(ValueError, match="Review"):
        approve_drafts([], drafts)
    drafts[0]["missing"] = []
    drafts[0]["annual_rate"] = "4.5"
    drafts[0]["monthly_payment"] = "150"
    merged = approve_drafts([], drafts, id_factory=lambda: "loan")
    assert merged[0]["annual_rate"] == "4.5"


def test_ai_gross_only_income_cannot_be_committed_without_confirmation():
    drafts = parse_drafts([{
        "kind": "income", "name": "Salary", "amount": None, "frequency": None,
    }])
    assert drafts[0]["missing"] == ["frequency", "amount"]
    with pytest.raises(ValueError):
        approve_drafts([], drafts)


def test_unknown_frequency_requires_explicit_acknowledgment():
    drafts = parse_drafts([{"kind": "expense", "name": "Rent", "amount": 1200}])
    assert "frequency" in drafts[0]["missing"]
    with pytest.raises(ValueError):
        make_block(drafts[0], "rent")


def test_batch_merge_does_not_mutate_existing_blocks():
    original = default_blocks()
    before = deepcopy(original)
    candidates = guided_drafts({"rent": 1000})
    updated = approve_drafts(original, candidates, id_factory=lambda: "extra")
    assert original == before
    assert len(updated) == len(before) + 1
    assert updated[-1]["id"] == "extra"


def test_batch_approval_is_atomic_when_any_selected_item_is_bad():
    original = default_blocks()
    candidates = guided_drafts({"income": 1800, "rent": 1000})
    candidates[-1]["amount"] = "-100"
    before = deepcopy(original)
    with pytest.raises(ValueError):
        approve_drafts(original, candidates)
    assert original == before


def test_excluding_incomplete_items_allows_other_items():
    candidates = guided_drafts({"income": 2000, "debt": 10000})
    result = approve_drafts(
        [], candidates, [True, False], id_factory=lambda: "pay"
    )
    assert len(result) == 1
    assert result[0]["kind"] == "income"


def test_no_items_selected_and_bad_selection_rejected():
    draft = guided_drafts({"rent": 1200})
    with pytest.raises(ValueError):
        approve_drafts([], draft, [False])
    with pytest.raises(ValueError):
        approve_drafts([], draft, [])
    with pytest.raises(ValueError):
        approve_drafts([], draft, [1])


@pytest.mark.parametrize("bad", [
    [{"kind": "loan", "name": "Debt", "balance": "NaN"}],
    [{"kind": "cash", "name": "Checking", "balance": -1}],
    [{"kind": "expense", "name": "Rent", "amount": 100,
      "frequency": "daily"}],
    [{"kind": "alien", "name": "Something", "balance": 0}],
    [{"kind": "cash", "name": ""}],
    [123],
])
def test_untrusted_ai_suggestions_rejected(bad):
    with pytest.raises(ValueError):
        parse_drafts(bad)


def test_suggested_goal_requires_explicit_target():
    draft = parse_drafts([{
        "kind": "goal", "name": "Move", "target": None,
        "target_months": 12,
    }])
    assert "target" in draft[0]["missing"]
    with pytest.raises(ValueError):
        make_block(draft[0], "goal")


def test_account_type_must_be_confirmed_when_not_supplied():
    draft = parse_drafts([{
        "kind": "account", "name": "My Account", "balance": 100,
        "account_type": None,
    }])
    assert "account_type" in draft[0]["missing"]


def test_batch_limit():
    with pytest.raises(ValueError):
        parse_drafts([{"kind": "cash", "name": "A", "balance": 0}] * (DRAFT_MAX + 1))
