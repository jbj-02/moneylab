"""Conservative bridges between the personal profile and a moving decision.

There is no implicit "current rent" in the core profile. A housing expense
must be selected or confidently identified. Mapping never transfers a
hypothetical proposed apartment into the current financial profile.
The reverse flow is a review-only plan with explicit add/update/skip choices.
"""
from decimal import Decimal
from uuid import uuid4

from moneylab.blocks import serialize_blocks, validate_blocks
from moneylab.moving import FIELDS, _decimal

ZERO = Decimal("0.00")
HOUSING = ("rent", "mortgage", "housing", "room and board", "room & board")
SAVINGS_TYPES = ("savings", "hysa")


def housing_candidates(blocks):
    entries = validate_blocks(blocks)
    return [item for item in entries if item["kind"] == "expense"
            and any(token in item["name"].lower() for token in HOUSING)]


def suggest_housing_id(blocks):
    matches = housing_candidates(blocks)
    return matches[0]["id"] if len(matches) == 1 else None


def profile_to_moving(blocks, housing_id=None):
    """Only known, consistently represented values are transferred.

    Unknown fields are None (NOT confirmed zero). Loans appear as minimum
    payments, while their balances do not become spendable cash. Savings
    includes only standard/high-yield savings accounts, excluding goals,
    retirement, brokerage, CDs and earmarked assets.
    """
    entries = validate_blocks(blocks)
    expenses = [b for b in entries if b["kind"] == "expense"]
    if housing_id is not None and not any(e["id"] == housing_id for e in expenses):
        raise ValueError("Select an existing housing expense.")
    incomes = [b for b in entries if b["kind"] == "income"]
    cash = [b for b in entries if b["kind"] == "cash"]
    savings = [
        b for b in entries
        if b["kind"] == "hysa" or
        (b["kind"] == "account" and b.get("account_type") in SAVINGS_TYPES)
    ]
    loans = [b for b in entries if b["kind"] == "loan"]
    selected = next((b for b in expenses if b["id"] == housing_id), None)
    other = [b for b in expenses if b["id"] != housing_id]
    def total(items, key):
        return str(sum((x[key] for x in items), ZERO)) if items else None
    fields = {key: None for key in FIELDS}
    fields.update({
        "income": total(incomes, "monthly_amount"),
        "current_housing": str(selected["monthly_amount"]) if selected else None,
        "other_living": total(other, "monthly_amount"),
        "minimum_debt": total(loans, "monthly_payment"),
        "checking": total(cash, "balance"),
        "savings": total(savings, "balance"),
    })
    notes = []
    if len(expenses) > 1:
        notes.append(
            "Other living costs include every recorded expense except the "
            "selected housing expense. Check that loan payments are not also "
            "represented as regular expenses."
        )
    if housing_id is None and expenses:
        notes.append(
            "A current housing expense was not selected. Enter a confirmed "
            "amount (including $0 if you pay nothing) in the decision."
        )
    if not loans:
        notes.append("No separate loan payments were identified; debt remains unknown.")
    if not cash:
        notes.append("No checking/cash block was identified.")
    if not savings:
        notes.append("No eligible unearmarked savings account was identified.")
    if any(b["kind"] in ("goal", "roth_ira") or
           (b["kind"] == "account" and b["account_type"] not in SAVINGS_TYPES)
           for b in entries):
        notes.append(
            "Goal, retirement, investment and other restricted balances "
            "are excluded from available move-out savings."
        )
    if any(b["kind"] == "hysa" and b["monthly_contribution"] > ZERO
           for b in entries):
        notes.append(
            "Savings balances are imported, but existing account savings "
            "contributions are not copied as new spending. Monthly margin "
            "is before transfers."
        )
    return {"values": fields, "notes": notes,
            "housing_id": housing_id, "eligible_savings_ids": [b["id"] for b in savings]}


def review_profile_changes(blocks, values):
    """Describe *current* amounts that might be added/updated in My Money.

    An aggregated figure never overwrites one of several original blocks.
    Duplicate-like blocks are never added automatically when a matching kind
    exists. Debt is not imported as an expense if loan blocks already exist.
    """
    entries = validate_blocks(blocks)
    if not isinstance(values, dict) or set(values) - set(FIELDS):
        raise ValueError("Unexpected decision fields.")
    specs = (
        ("income", "income", "Take-home income", "monthly_amount"),
        ("current_housing", "expense", "Current housing", "monthly_amount"),
        ("other_living", "expense", "Other living expenses", "monthly_amount"),
        ("minimum_debt", "expense", "Minimum debt payments", "monthly_amount"),
        ("checking", "cash", "Checking / cash", "balance"),
        ("savings", "hysa", "Unrestricted savings", "balance"),
    )
    plans = []
    for field, kind, label, amount_key in specs:
        raw = values.get(field)
        if raw is None:
            continue
        value = _decimal(raw, field)
        if value == ZERO and field not in ("checking", "current_housing"):
            continue
        if field == "minimum_debt" and any(b["kind"] == "loan" for b in entries):
            plans.append({
                "field": field, "label": label, "value": str(value),
                "action": "conflict", "target_id": None,
                "reason": "Existing loan blocks may already include these payments.",
            })
            continue
        if field == "income":
            candidates = [b for b in entries if b["kind"] == "income"]
        elif field == "current_housing":
            candidates = housing_candidates(entries)
        elif field == "other_living":
            candidates = [b for b in entries if b["kind"] == "expense"
                          and b not in housing_candidates(entries)
                          and not any(t in b["name"].lower() for t in ("loan", "debt payment"))]
        elif field == "minimum_debt":
            candidates = [b for b in entries if b["kind"] == "expense"
                          and any(t in b["name"].lower() for t in ("loan", "debt payment"))]
        elif field == "checking":
            candidates = [b for b in entries if b["kind"] == "cash"]
        else:
            candidates = [b for b in entries if b["kind"] == "hysa" or
                          (b["kind"] == "account" and b.get("account_type") in SAVINGS_TYPES)]
        if len(candidates) > 1:
            action, target, reason = (
                "conflict", None, f"{len(candidates)} possible existing blocks; "
                "edit them individually in My Money."
            )
        elif len(candidates) == 1:
            action, target, reason = (
                "update", candidates[0]["id"],
                f"Would replace the amount in '{candidates[0]['name']}' only if approved."
            )
        else:
            # For other living expenses, a broad generic new block can
            # double-count finer expense categories. User reviews it.
            action, target, reason = ("add", None, "Would create a new recorded block.")
        plans.append({
            "field": field, "label": label, "value": str(value),
            "kind": kind, "amount_key": amount_key,
            "action": action, "target_id": target, "reason": reason,
        })
    return plans


def apply_reviewed_profile_changes(blocks, plan, decisions, *, id_factory=None):
    """Commit *only* user-approved reviewed items; preserve original blocks.

    Decisions is mapping field -> 'apply'|'skip'. Conflicts cannot be applied.
    The entire profile is validated atomically to avoid partially saved data.
    """
    before = serialize_blocks(blocks)
    expected = review_profile_changes(before, {
        item["field"]: item["value"] for item in plan if "field" in item
    })
    if plan != expected:
        raise ValueError("Profile update preview is stale; review it again.")
    if not isinstance(decisions, dict) or set(decisions) - {item["field"] for item in plan}:
        raise ValueError("Unexpected profile change selections.")
    make_id = id_factory or (lambda: uuid4().hex[:12])
    after = [dict(b) for b in before]
    count = 0
    for item in plan:
        action = decisions.get(item["field"], "skip")
        if action == "skip":
            continue
        if action != "apply" or item["action"] == "conflict":
            raise ValueError(f"Cannot safely apply '{item['label']}'.")
        if item["action"] == "update":
            current = next(b for b in after if b["id"] == item["target_id"])
            current[item["amount_key"]] = item["value"]
            if item["amount_key"] == "monthly_amount":
                current.pop("frequency", None)
                current.pop("period_amount", None)
                current.pop("next_date", None)
        else:
            block = {
                "id": make_id(), "name": item["label"], "kind": item["kind"],
                item["amount_key"]: item["value"],
            }
            if item["kind"] == "hysa":
                block.update({"annual_rate": "0", "monthly_contribution": "0"})
            after.append(block)
        count += 1
    if count == 0:
        raise ValueError("Choose at least one block to add or update.")
    return serialize_blocks(after)
