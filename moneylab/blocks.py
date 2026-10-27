"""Validated modular financial profiles and deterministic monthly projections.

Profiles are JSON-friendly. Historical income/cash/HYSA/Roth IRA/goal blocks
remain supported; flexible account blocks use a reusable account subtype.
Income routes are optional direct-deposit allocations to existing accounts.
All calculations are in Decimal cents and do not connect to financial services.
"""

import json
import re
from decimal import Decimal, ROUND_HALF_UP

from moneylab.engine import (
    CENT, ZERO, calculate_monthly_loan_payment, validate_annual_interest_rate,
    validate_money,
)
from moneylab.cadence import FREQUENCIES, monthly_equivalent, validate_schedule_date

ACCOUNT_TYPES = {
    "savings": "Traditional savings",
    "hysa": "High-yield savings",
    "money_market": "Money market",
    "cd": "Certificate of deposit (simplified)",
    "roth_ira": "Roth IRA",
    "traditional_ira": "Traditional IRA",
    "traditional_401k": "Traditional 401(k)",
    "roth_401k": "Roth 401(k)",
    "403b": "403(b)",
    "brokerage": "Taxable brokerage",
    "hsa": "Health savings account",
    "529": "529 education savings",
}
BLOCK_KINDS = {
    "income": "Income",
    "expense": "Expense",
    "loan": "Loan / debt",
    "cash": "Checking / cash",
    "hysa": "High-yield savings (legacy)",
    "roth_ira": "Roth IRA (legacy)",
    "goal": "Dedicated savings goal",
    "account": "Savings / retirement / investment account",
}
ASSET_KINDS = ("hysa", "roth_ira", "goal", "account")
MAX_BLOCKS = 50
MAX_AMOUNT = Decimal("1000000000000.00")


def default_blocks():
    """Optional fictional demonstration; real new users start with no blocks."""
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


def _routing_amount(route, income):
    """Convert a validated route to a monthly amount, rounded once to cents."""
    if route["mode"] == "percent":
        return (income * route["value"] / Decimal("100")).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
    return route["value"]


def validate_blocks(blocks):
    """Return normalized entries and validate all cross-block route references.

    An income block can optionally contain a list of routes. Fixed amounts and
    percentages may be mixed. The remainder stays in modeled checking/cash.
    Route destinations must be named cash or asset blocks, never expenses/debts.
    """
    if not isinstance(blocks, list) or len(blocks) > MAX_BLOCKS:
        raise ValueError(f"Use a list of no more than {MAX_BLOCKS} financial blocks.")
    fields = {
        "income": {"monthly_amount"},
        "expense": {"monthly_amount"},
        "loan": {"balance", "annual_rate", "monthly_payment"},
        "cash": {"balance"},
        "hysa": {"balance", "annual_rate", "monthly_contribution"},
        "roth_ira": {"balance", "annual_rate", "monthly_contribution"},
        "goal": {"balance", "annual_rate", "monthly_contribution", "target", "target_months"},
        "account": {"balance", "annual_rate", "monthly_contribution", "account_type"},
    }
    result, seen = [], set()
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
        required = {"id", "kind", "name"} | fields[kind]
        extra = {"frequency", "period_amount", "next_date"} if kind in ("income", "expense") else set()
        allowed = required | extra | ({"routes"} if kind == "income" else set())
        if not required.issubset(raw) or set(raw) - allowed:
            raise ValueError(f"{name}: unexpected or missing fields for {kind}.")
        item = {"id": block_id, "kind": kind, "name": name.strip()}
        for key in fields[kind] - {"annual_rate", "target_months", "account_type"}:
            item[key] = _money(raw[key], f"{name}: {key}")
        if kind in ("income", "expense"):
            frequency = raw.get("frequency", "monthly")
            if frequency not in FREQUENCIES:
                raise ValueError(f"{name}: unsupported income/expense frequency.")
            if ("frequency" in raw) != ("period_amount" in raw):
                raise ValueError(f"{name}: frequency and period_amount must be supplied together.")
            if "frequency" in raw:
                per_period = _money(raw["period_amount"], f"{name}: period_amount")
                expected = monthly_equivalent(per_period, frequency)
                if item["monthly_amount"] != expected:
                    raise ValueError(f"{name}: monthly amount does not match the period amount.")
                item["frequency"] = frequency
                item["period_amount"] = per_period
            if "next_date" in raw:
                item["next_date"] = validate_schedule_date(raw["next_date"])
                if item["next_date"] is None:
                    raise ValueError(f"{name}: next_date must be a real date when supplied.")
        if "annual_rate" in fields[kind]:
            item["annual_rate"] = _rate(raw["annual_rate"], f"{name}: annual_rate")
        if kind == "account":
            account_type = raw["account_type"]
            if not isinstance(account_type, str) or account_type not in ACCOUNT_TYPES:
                raise ValueError(f"{name}: unsupported account type.")
            item["account_type"] = account_type
        if kind == "goal":
            duration = raw["target_months"]
            if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 600:
                raise ValueError(f"{name}: target_months must be 1–600.")
            item["target_months"] = duration
            if item["target"] == ZERO:
                raise ValueError(f"{name}: target must be greater than zero.")
        if kind == "income" and "routes" in raw:
            routes = raw["routes"]
            if not isinstance(routes, list) or len(routes) > MAX_BLOCKS:
                raise ValueError(f"{name}: routes must be a list of at most {MAX_BLOCKS}.")
            normalized, targets = [], set()
            for route in routes:
                if not isinstance(route, dict) or set(route) != {"destination_id", "mode", "value"}:
                    raise ValueError(f"{name}: each route needs destination_id, mode and value.")
                target = route["destination_id"]
                mode = route["mode"]
                if not isinstance(target, str) or not target:
                    raise ValueError(f"{name}: route destination ID is required.")
                if target in targets:
                    raise ValueError(f"{name}: duplicate destination route.")
                targets.add(target)
                if mode not in ("fixed", "percent"):
                    raise ValueError(f"{name}: route mode must be fixed or percent.")
                value = _money(route["value"], f"{name}: route value") if mode == "fixed" else _rate(
                    route["value"], f"{name}: route percentage"
                )
                normalized.append({"destination_id": target, "mode": mode, "value": value})
            item["routes"] = normalized
        result.append(item)

    destinations = {b["id"]: b["kind"] for b in result}
    for item in result:
        if item["kind"] != "income":
            continue
        allocated = ZERO
        for route in item.get("routes", []):
            target = route["destination_id"]
            if destinations.get(target) not in ("cash", *ASSET_KINDS):
                raise ValueError(
                    f"{item['name']}: income route must point to an existing cash or account block."
                )
            allocated += _routing_amount(route, item["monthly_amount"])
        if allocated > item["monthly_amount"]:
            raise ValueError(
                f"{item['name']}: routed deposits exceed monthly take-home income."
            )
    return result


def serialize_blocks(blocks):
    """Serialize a validated profile preserving exact monetary/route values."""
    def serial(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, list):
            return [serial(x) for x in value]
        if isinstance(value, dict):
            return {k: serial(v) for k, v in value.items()}
        return value

    return serial(validate_blocks(blocks))


def profile_to_json(blocks):
    return json.dumps(
        {"schema_version": 1, "blocks": serialize_blocks(blocks)},
        indent=2, ensure_ascii=False,
    )


def profile_from_json(text):
    if not isinstance(text, str) or len(text) > 100_000:
        raise ValueError("The imported profile is too large.")
    try:
        document = json.loads(text)
    except (ValueError, TypeError):
        raise ValueError("The file is not valid JSON.") from None
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "blocks"}
        or document["schema_version"] != 1
    ):
        raise ValueError("Unsupported MoneyLab profile format.")
    return serialize_blocks(document["blocks"])


def modify_expense(blocks, block_id, monthly_change):
    """Create a what-if profile without mutating the saved scenario."""
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
            # The What-if Lab models a monthly-average change. Keep the saved
            # block intact, but express the temporary scenario in monthly terms.
            item.pop("frequency", None)
            item.pop("period_amount", None)
            found = True
    if not found:
        raise ValueError("Expense block not found.")
    return items


def project_blocks(blocks, months=24):
    """Project multiple loans, accounts and take-home direct-deposit routing.

    Routes allocate income to an existing account or cash block; any unrouted
    remainder is modeled as available cash even without a checking block.
    Savings/retirement allocations are internal transfers, not expenses.
    Recurring account contributions use the remaining monthly available
    cash only after expenses, contractual payments and any prior shortfall.

    This is a constant-rate planning model, NOT an investment/tax forecast.
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

    def snapshot(month, loan_paid, transfers, earned, negative_amortization, routes=None):
        loan_total = sum(loan_balances.values(), ZERO)
        asset_total = sum(assets.values(), ZERO)
        shortfall = max(-cash, ZERO)
        return {
            "month": month,
            "income": income if month else ZERO,
            "living_expenses": expenses if month else ZERO,
            "loan_payments": loan_paid,
            "asset_contributions": transfers,
            "asset_yield": earned,
            "direct_deposits": routes or {},
            "net_cash_flow": (income - expenses - loan_paid - transfers) if month else ZERO,
            "cash_position": cash,
            "cash_savings": max(cash, ZERO),
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
    first_month_direct_assets = ZERO
    first_month_cash_routes = ZERO

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

        routed = {}
        directed_assets = ZERO
        cash_routes = ZERO
        for block in items:
            if block["kind"] != "income":
                continue
            for route in block.get("routes", []):
                amount = _routing_amount(route, block["monthly_amount"])
                id_ = route["destination_id"]
                routed[id_] = routed.get(id_, ZERO) + amount
                if id_ in assets:
                    directed_assets += amount
                else:
                    cash_routes += amount

        # Direct deposits to assets leave less take-home income for expenses.
        free = income - expenses - paid - directed_assets
        available = min(max(free, ZERO), max(cash + free, ZERO))
        planned = ZERO
        earned = ZERO
        for id_, balance in assets.items():
            block = by_id[id_]
            growth = (balance * block["annual_rate"] / Decimal("1200")).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            contribution = min(block["monthly_contribution"], available)
            available -= contribution
            planned += contribution
            earned += growth
            assets[id_] = balance + growth + contribution + routed.get(id_, ZERO)
            if block["kind"] == "goal" and month == block["target_months"]:
                goal_progress[id_] = assets[id_]

        transferred = planned + directed_assets
        cash += free - planned
        total_transfers += transferred
        total_yield += earned
        if month == 1:
            first_month_unallocated = min(max(free - planned, ZERO), max(cash, ZERO))
            first_month_direct_assets = directed_assets
            first_month_cash_routes = cash_routes
        rows.append(snapshot(month, paid, transferred, earned, negative, routed))

    end = rows[-1]
    goals = []
    for block in items:
        if block["kind"] != "goal":
            continue
        balance = goal_progress.get(block["id"])
        goals.append({
            "id": block["id"],
            "name": block["name"],
            "target": block["target"],
            "target_months": block["target_months"],
            "starting_balance": block["balance"],
            "projected_at_deadline": balance,
            "on_track": balance >= block["target"] if balance is not None else None,
            "gap_at_deadline": max(block["target"] - balance, ZERO) if balance is not None else None,
        })

    return {
        "monthly_records": rows,
        "goals": goals,
        "summary": {
            "months": months,
            "starting_net_position": rows[0]["net_position"],
            "ending_net_position": end["net_position"],
            "ending_cash_savings": end["cash_savings"],
            "ending_unfunded_shortfall": end["unfunded_shortfall"],
            "ending_assets": end["other_assets"],
            "ending_debt": end["loan_balance"],
            "monthly_income": income,
            "monthly_expenses": expenses,
            "first_month_loan_payments": rows[1]["loan_payments"],
            "first_month_transfers": rows[1]["asset_contributions"],
            "first_month_direct_to_assets": first_month_direct_assets,
            "first_month_direct_to_cash": first_month_cash_routes,
            "unallocated_monthly_buffer": first_month_unallocated,
            "estimated_extra_weekly_spend": (
                first_month_unallocated * Decimal(12) / Decimal(52)
            ).quantize(CENT, rounding=ROUND_HALF_UP),
            "total_interest": total_interest,
            "total_asset_yield": total_yield,
            "total_asset_contributions": total_transfers,
        },
    }
