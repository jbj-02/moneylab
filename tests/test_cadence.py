"""Verify period normalization, optional schedules, and old profile behavior."""

from datetime import date
from decimal import Decimal

import pytest

from moneylab.blocks import default_blocks, modify_expense, project_blocks, serialize_blocks
from moneylab.cadence import (
    monthly_equivalent, upcoming_events, validate_schedule_date,
)

D = Decimal


@pytest.mark.parametrize("frequency,amount,expected", [
    ("weekly", "100", "433.33"),
    ("biweekly", "100", "216.67"),
    ("monthly", "100", "100.00"),
    ("yearly", "1200", "100.00"),
    ("weekly", "90.75", "393.25"),
])
def test_normalized_monthly_equivalents(frequency, amount, expected):
    assert monthly_equivalent(amount, frequency) == D(expected)


@pytest.mark.parametrize("bad", ["daily", "semiweekly", None, 12])
def test_unsupported_cadence(bad):
    with pytest.raises(ValueError):
        monthly_equivalent(100, bad)


def income(amount, frequency, ident="pay"):
    return {
        "id": ident, "name": "Paycheck", "kind": "income",
        "monthly_amount": str(monthly_equivalent(amount, frequency)),
        "frequency": frequency, "period_amount": str(amount),
    }


def expense(amount, frequency, ident="rent"):
    return {
        "id": ident, "name": "Expense", "kind": "expense",
        "monthly_amount": str(monthly_equivalent(amount, frequency)),
        "frequency": frequency, "period_amount": str(amount),
    }


def test_combined_frequencies_and_exact_cash_flow():
    blocks = [
        income("1500", "biweekly"),
        expense("300", "weekly"),
        expense("1200", "yearly", ident="insurance"),
    ]
    summary = project_blocks(blocks, 1)["summary"]
    assert summary["monthly_income"] == D("3250.00")
    assert summary["monthly_expenses"] == D("1400.00")
    assert summary["unallocated_monthly_buffer"] == D("1850.00")


def test_legacy_blocks_keep_monthly_semantics_and_import():
    blocks = default_blocks()
    validated = serialize_blocks(blocks)
    assert "frequency" not in validated[0]
    assert project_blocks(blocks, 1)["summary"]["monthly_income"] == D("3800.00")


def test_whatif_adjusts_monthly_equivalent_without_changing_base_cadence():
    base = [expense("1200", "yearly")]
    temporary = modify_expense(base, "rent", 25)
    assert base[0]["frequency"] == "yearly"
    assert temporary[0]["monthly_amount"] == "125.00"
    assert "period_amount" not in temporary[0]
    assert project_blocks(temporary, 1)["summary"]["monthly_expenses"] == D("125.00")


@pytest.mark.parametrize("bad_profile", [
    [{"id":"income","kind":"income","name":"Pay","monthly_amount":"100",
      "frequency":"weekly","period_amount":"100"}],
    [{"id":"income","kind":"income","name":"Pay","monthly_amount":"100",
      "frequency":"weekly"}],
    [{"id":"income","kind":"income","name":"Pay","monthly_amount":"100",
      "period_amount":"100"}],
    [{"id":"income","kind":"income","name":"Pay","monthly_amount":"100",
      "next_date":"not-a-date"}],
    [{"id":"income","kind":"income","name":"Pay","monthly_amount":"100",
      "frequency":"daily","period_amount":"100"}],
])
def test_inconsistent_or_invalid_profile_rejected(bad_profile):
    with pytest.raises(ValueError):
        serialize_blocks(bad_profile)


def test_iso_date_validation():
    assert validate_schedule_date("2026-10-27") == "2026-10-27"
    assert validate_schedule_date(None) is None
    with pytest.raises(ValueError):
        validate_schedule_date("2026-02-31")


def test_biweekly_dates_include_every_fourteen_days():
    block = income("1000", "biweekly")
    block["next_date"] = "2026-10-05"
    events = upcoming_events(
        [block], from_date=date(2026, 10, 27), days=45,
    )
    assert [e["date"] for e in events] == [
        "2026-11-02", "2026-11-16", "2026-11-30",
    ]
    assert all(e["amount"] == D("1000.00") for e in events)


def test_month_end_schedule_clips_to_existing_dates():
    block = expense("600", "monthly")
    block["next_date"] = "2026-01-31"
    events = upcoming_events(
        [block], from_date=date(2026, 2, 1), days=60,
    )
    assert [e["date"] for e in events] == [
        "2026-02-28", "2026-03-31",
    ]


def test_yearly_event_does_not_become_a_monthly_bill():
    block = expense("1200", "yearly")
    block["next_date"] = "2026-12-20"
    events = upcoming_events(
        [block], from_date=date(2026, 12, 1), days=90,
    )
    assert len(events) == 1
    assert events[0]["date"] == "2026-12-20"
    assert events[0]["amount"] == D("1200.00")
