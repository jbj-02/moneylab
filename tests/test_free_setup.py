"""Free MoneyLab Smart Paste should be useful without API keys or invented values."""
from decimal import Decimal

import pytest

from moneylab.free_setup import suggest_blocks_from_text
from moneylab.onboarding import approve_drafts


def test_four_common_financial_items_from_plain_english():
    drafts, ignored = suggest_blocks_from_text(
        "My take-home pay is $1,800 biweekly, my rent is $1,200 monthly, "
        "groceries are $100 a week, and checking is $500."
    )
    assert [(d["kind"], d["name"]) for d in drafts] == [
        ("income", "Take-home income"),
        ("expense", "Rent / housing"),
        ("expense", "Groceries / food"),
        ("cash", "Checking / cash"),
    ]
    assert drafts[0]["amount"] == "1800"
    assert drafts[0]["frequency"] == "biweekly"
    assert drafts[2]["frequency"] == "weekly"
    assert drafts[3]["balance"] == "500"
    assert all(not d["missing"] for d in drafts)
    merged = approve_drafts(
        [], drafts, id_factory=iter(["inc", "rent", "food", "checking"]).__next__
    )
    assert merged[0]["monthly_amount"] == "3900.00"
    assert merged[2]["monthly_amount"] == "433.33"


def test_unknown_net_income_is_not_invented():
    drafts, _ = suggest_blocks_from_text(
        "I make $4,000 monthly before taxes, and my rent is $1,200 monthly."
    )
    assert drafts[0]["kind"] == "income"
    assert "amount" in drafts[0]["missing"]
    assert drafts[0]["amount"] == "0"
    with pytest.raises(ValueError):
        approve_drafts([], drafts)


def test_unknown_frequencies_and_student_loan_payment_are_flagged():
    drafts, ignored = suggest_blocks_from_text(
        "Rent is $1400, my student loan balance is $12,000."
    )
    assert drafts[0]["kind"] == "expense"
    assert "frequency" in drafts[0]["missing"]
    assert drafts[1]["kind"] == "loan"
    assert drafts[1]["balance"] == "12000"
    assert "monthly_payment" in drafts[1]["missing"]
    assert "annual_rate" in drafts[1]["missing"]


def test_explicit_loan_terms_are_recognized():
    drafts, _ = suggest_blocks_from_text(
        "I have a student loan balance of $12,000 at 5% interest "
        "with monthly payment $150."
    )
    assert len(drafts) == 1
    assert drafts[0]["annual_rate"] == "5"
    assert drafts[0]["monthly_payment"] == "150"
    assert drafts[0]["missing"] == []


def test_goal_without_deadline_requires_confirmation():
    drafts, _ = suggest_blocks_from_text(
        "I want to save $3,000 for an emergency fund."
    )
    assert drafts[0]["kind"] == "goal"
    assert drafts[0]["target"] == "3000"
    assert "target_months" in drafts[0]["missing"]


def test_irrelevant_clauses_cannot_create_phantom_blocks():
    drafts, ignored = suggest_blocks_from_text(
        "My take-home paycheck is $2,000 monthly. I love hiking."
    )
    assert len(drafts) == 1
    assert len(ignored) == 1
    assert "hiking" in ignored[0]


def test_k_notation_without_huge_multiplier_error():
    drafts, _ = suggest_blocks_from_text(
        "My savings account has $2.5k in it, and my rent is $1.2k monthly."
    )
    assert drafts[0]["balance"] == "2500.0"
    assert drafts[1]["amount"] == "1200.0"


def test_non_profile_values_and_negative_numbers_not_silently_added():
    with pytest.raises(ValueError):
        suggest_blocks_from_text("The weather is great and I don't know my finances.")
    with pytest.raises(ValueError):
        suggest_blocks_from_text("I have $12,000 in savings. " * 200)


def test_two_weeks_not_misidentified_as_income_amount():
    drafts, _ = suggest_blocks_from_text(
        "I get my net paycheck every 2 weeks, it is $1,800."
    )
    assert drafts[0]["amount"] == "1800"
    assert drafts[0]["frequency"] == "biweekly"
