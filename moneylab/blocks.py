"""Composable financial blocks for MoneyLab's personalized planning workspace.

All balances and calculations use Decimal with explicit cent rounding.
This module never connects to banking services or stores personal information.
"""

import copy
import json
import re
from decimal import Decimal, ROUND_HALF_UP

from moneylab.engine import (
    CENT, ZERO, calculate_monthly_loan_payment, validate_annual_interest_rate,
    validate_money,
)

BLOCK_KINDS = {
    "income": "Income",
    "expense": "Expense",
    "loan": "Loan / car payment",
    "cash": "Checking / cash",
    "hysa": "High-yield savings",
    "roth_ira": "Roth IRA (illustrative)",
    "goal": "Dedicated savings goal",
}
ASSET_KINDS = ("hysa", "roth_ira", "goal")
MAX_BLOCKS = 50
MAX_AMOUNT = Decimal("1000000000000.00")


def default_blocks():
    """Fictional starter profile; no real user details."""
    return [
        {"id": "pay", "kind": "income", "name": "Take-home salary", "monthly_amount": "3800"},
        {"id": "rent", "kind": "expense", "name": "Rent", "monthly_amount": "1350"},
        {"id": "food", "kind": "expense", "name": "Groceries", "monthly_amount": "350"},
        {"id": "fun", "kind": "expense", "name": "Dining & entertainment", "monthly_amount": "300"},
        {"id": "car", "kind": "loan", "name": "Car loan", "balance": "8500", "annual_rate": "6.9", "monthly_payment": "280"},
        {"id": "student", "kind": "loan", "name": "Student loan", "balance": "18000", "annual_rate": "4.5", "monthly_payment": "190"},
        {"id": "checking", "kind": "cash", "name": "Checking account", "balance": "2200"},
        {"id": "hysa", "kind": "hysa", "name": "Emergency fund HYSA", "balance": "1200", "annual_rate": "3.5", "monthly_contribution": "250"},
        {"id": "roth", "kind": "roth_ira", "name": "Roth IRA", "balance": "800", "annual_rate": "5", "monthly_contribution": "100"},
        {"id": "vacation", "kind": "goal", "name": "Summer travel fund", "balance": "300", "annual_rate": "0", "monthly_contribution": "75", "target": "2000", "target_months": 18},
    ]


def _money(value, label):
    amount = validate_money(value, label)
    if amount > MAX_AMOUNT:
        raise ValueError(f"{label} must be at most one trillion dollars.")
    return amount


def _rate(value, label):
    rate = validate_annual_interest_rate(value)
    if rate > Decimal("100"):
        raise ValueError(f"{label} must be between 0 and 100%.")
    return rate


def validate_blocks(blocks):
    """Validate a JSON-friendly profile, returning normalized Decimal entries.

    Only documented fields are accepted. IDs must be unique; labels are
    plain text. The UI can serialize with `serialize_blocks`.
    """
    if not isinstance(blocks, list) or len(blocks) > MAX_BLOCKS:
        raise ValueError(f"Use a list of no more than {MAX_BLOCKS} financial blocks.")
    output, seen = [], set()
    fields = {
        "income": {"monthly_amount"},
        "expense": {"monthly_amount"},
        "loan": {"balance", "annual_rate", "monthly_payment"},
        "cash": {"balance"},
        "hysa": {"balance", "annual_rate", "monthly_contribution"},
        "roth_ira": {"balance", "annual_rate", "monthly_contribution"},
        "goal": {"balance", "annual_rate", "monthly_contribution", "target", "target_months"},
    }
    for index, raw in enumerate(blocks):
        if not isinstance(raw, dict):
            raise ValueError(f"Block {index + 1} must be a dictionary.")
        kind = raw.get("kind")
        if kind not in BLOCK_KINDS:
            raise ValueError(f"Unknown financial block type: {kind!r}.")
        block_id = raw.get("id")
        if not isinstance(block_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", block_id):
            raise ValueError("Block IDs must use 1–64 letters, numbers, - or _.")
        if block_id in seen:
            raise ValueError(f"Duplicate financial block ID: {block_id}.")
        seen.add(block_id)
        name = raw.get("name")
        if not isinstance(name, str) or not (1 <= len(name.strip()) <= 60):
            raise ValueError("Each block needs a name of 1–60 characters.")
        if set(raw) != ({"id", "kind", "name"} | fields[kind]):
            raise ValueError(f"{name}: unexpected or missing fields for {kind}.")
        item = {"id": block_id, "kind": kind, "name": name.strip()}
        for key in fields[kind] - {"annual_rate", "target_months"}:
            item[key] = _money(raw[key], f"{name}: {key}")
        if "annual_rate" in fields[kind]:
            item["annual_rate"] = _rate(raw["annual_rate"], f"{name}: annual_rate")
        if kind == "goal":
            duration = raw["target_months"]
            if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 600:
                raise ValueError(f"{name}: target_months must be 1–600.")
            item["target_months"] = duration
            if item["target"] == ZERO:
                raise ValueError(f"{name}: target must be greater than zero.")
        output.append(item)
    return output


def serialize_blocks(blocks):
    """Return a JSON-compatible validated list with exact decimal strings."""
    parsed = validate_blocks(blocks)
    return [
        {key: str(value) if isinstance(value, Decimal) else value
         for key, value in item.items()}
        for item in parsed
    ]


def profile_to_json(blocks):
    return json.dumps({"schema_version": 1, "blocks": serialize_blocks(blocks)},
                      indent=2, ensure_ascii=False)


def profile_from_json(text):
    if not isinstance(text, str) or len(text) > 100_000:
        raise ValueError("The imported profile is too large.")
    try:
        document = json.loads(text)
    except (ValueError, TypeError):
        raise ValueError("The file is not valid JSON.") from None
    if not isinstance(document, dict) or set(document) != {"schema_version", "blocks"} or document["schema_version"] != 1:
        raise ValueError("Unsupported MoneyLab profile format.")
    return serialize_blocks(document["blocks"])


def modify_expense(blocks, block_id, monthly_change):
    """Create a new what-if profile without mutating the saved scenario."""
    items = serialize_blocks(blocks)
    delta = Decimal(str(monthly_change))
    if not delta.is_finite():
        raise ValueError("Monthly change must be finite.")
    found = False
    for item in items:
        if item["id"] == block_id:
            if item["kind"] != "expense":
                raise ValueError("What-if adjustment must target an expense block.")
            item["monthly_amount"] = str(_money(
                Decimal(item["monthly_amount"]) + delta, "Adjusted expense"
            ))
            found = True
    if not found:
        raise ValueError("Expense block not found.")
    return items


def project_blocks(blocks, months=24):
    """Run a monthly cash/debt/asset simulation for a modular financial profile.

    Loans use the existing amortization engine. Asset monthly yields are
    illustrative deterministic assumptions, **not guaranteed investment returns**.
    Planned transfers into HYSA, Roth and goal accounts are only made from
    available *monthly* surplus, after outstanding unfunded shortfalls.
    Transfers move money from checking to assets and are not expenses.
    """
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= 600:
        raise ValueError("Projection months must be an integer from 1 to 600.")
    items = validate_blocks(blocks)
    by_id = {b["id"]: b for b in items}
    income = sum((b["monthly_amount"] for b in items if b["kind"] == "income"), ZERO)
    expenses = sum((b["monthly_amount"] for b in items if b["kind"] == "expense"), ZERO)
    cash = sum((b["balance"] for b in items if b["kind"] == "cash"), ZERO)
    loan_balances = {b["id"]: b["balance"] for b in items if b["kind"] == "loan"}
    assets = {b["id"]: b["balance"] for b in items if b["kind"] in ASSET_KINDS}
    total_interest = ZERO
    total_yield = ZERO
    total_transfers = ZERO
    goal_progress = {}
    rows = []

    def snapshot(month, loan_paid, transfers, earned, negative_amortization):
        loan_total = sum(loan_balances.values(), ZERO)
        asset_total = sum(assets.values(), ZERO)
        shortfall = max(-cash, ZERO)
        savings = max(cash, ZERO)
        return {
            "month": month,
            "income": income if month else ZERO,
            "living_expenses": expenses if month else ZERO,
            "loan_payments": loan_paid,
            "asset_contributions": transfers,
            "asset_yield": earned,
            "net_cash_flow": (income - expenses - loan_paid - transfers) if month else ZERO,
            "cash_position": cash,
            "cash_savings": savings,
            "unfunded_shortfall": shortfall,
            "other_assets": asset_total,
            "loan_balance": loan_total,
            "net_position": cash + asset_total - loan_total,
            "negative_amortization": negative_amortization,
            "balances": {**loan_balances, **assets},
            "cumulative_interest": total_interest,
            "cumulative_yield": total_yield,
            "cumulative_contributions": total_transfers,
        }

    rows.append(snapshot(0, ZERO, ZERO, ZERO, False))
    first_month_unallocated = ZERO
    for month in range(1, months + 1):
        paid = ZERO
        negative = False
        for id_, balance in loan_balances.items():
            block = by_id[id_]
            entry = calculate_monthly_loan_payment(
                balance, block["annual_rate"], block["monthly_payment"]
            )
            loan_balances[id_] = entry["ending_balance"]
            paid += entry["actual_payment"]
            total_interest += entry["monthly_interest"]
            negative = negative or entry["negative_amortization"]

        free = income - expenses - paid
        # Monthly available cash before planned transfers; starting savings do
        # not fund contributions and negative prior cash gets covered first.
        available = min(max(free, ZERO), max(cash + free, ZERO))
        transferred = ZERO
        earned = ZERO
        for id_, balance in assets.items():
            block = by_id[id_]
            asset_yield = (balance * block["annual_rate"] / Decimal("1200")).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            contribution = min(block["monthly_contribution"], available)
            available -= contribution
            transferred += contribution
            earned += asset_yield
            assets[id_] = balance + asset_yield + contribution
            if block["kind"] == "goal" and month == block["target_months"]:
                goal_progress[id_] = assets[id_]

        cash += free - transferred
        total_transfers += transferred
        total_yield += earned
        if month == 1:
            first_month_unallocated = max(free - transferred, ZERO)
        rows.append(snapshot(month, paid, transferred, earned, negative))

    start_net = rows[0]["net_position"]
    end = rows[-1]
    goals = []
    for block in items:
        if block["kind"] != "goal":
            continue
        at_deadline = goal_progress.get(block["id"])
        goals.append({
            "id": block["id"],
            "name": block["name"],
            "target": block["target"],
            "target_months": block["target_months"],
            "starting_balance": block["balance"],
            "projected_at_deadline": at_deadline,
            "on_track": at_deadline >= block["target"] if at_deadline is not None else None,
            "gap_at_deadline": max(block["target"] - at_deadline, ZERO) if at_deadline is not None else None,
        })
    return {
        "monthly_records": rows,
        "goals": goals,
        "summary": {
            "months": months,
            "starting_net_position": start_net,
            "ending_net_position": end["net_position"],
            "ending_cash_savings": end["cash_savings"],
            "ending_unfunded_shortfall": end["unfunded_shortfall"],
            "ending_assets": end["other_assets"],
            "ending_debt": end["loan_balance"],
            "monthly_income": income,
            "monthly_expenses": expenses,
            "first_month_loan_payments": rows[1]["loan_payments"],
            "first_month_transfers": rows[1]["asset_contributions"],
            "unallocated_monthly_buffer": first_month_unallocated,
            "estimated_extra_weekly_spend": (first_month_unallocated * Decimal(12) / Decimal(52)).quantize(CENT, rounding=ROUND_HALF_UP),
            "total_interest": total_interest,
            "total_asset_yield": total_yield,
            "total_asset_contributions": total_transfers,
        },
    }
