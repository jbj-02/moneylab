"""Financial Quick Start: draft-only setup and strict batch validation.

Drafts are never silently inserted into the user's financial profile.
Unknown monetary amounts stay marked as missing until explicitly reviewed.
Only the existing MoneyLab Decimal validation engine may approve the blocks.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from moneylab.blocks import ACCOUNT_TYPES, BLOCK_KINDS, MAX_BLOCKS, serialize_blocks
from moneylab.cadence import FREQUENCIES, monthly_equivalent

DRAFT_MAX = 12
REVIEW_FIELDS = {
    "income": ("amount",),
    "expense": ("amount",),
    "cash": ("balance",),
    "loan": ("balance", "annual_rate", "monthly_payment"),
    "hysa": ("balance",),
    "roth_ira": ("balance",),
    "account": ("balance", "account_type"),
    "goal": ("target", "target_months"),
}


def _decimal(value, field):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} needs a number.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field} needs a number.") from None
    if not number.is_finite() or number < 0:
        raise ValueError(f"{field} must be a nonnegative finite number.")
    if number > Decimal("1000000000000"):
        raise ValueError(f"{field} is too large.")
    return number


def parse_drafts(items):
    """Turn untrusted structured AI suggestions into editable, unsigned drafts.

    Entries with incomplete information remain incomplete. Their missing fields
    are NOT assumed to be zeros: the review UI must obtain user confirmation.
    No arbitrary fields or third-party instructions are retained.
    """
    if not isinstance(items, list) or len(items) > DRAFT_MAX:
        raise ValueError(f"Please suggest at most {DRAFT_MAX} items.")
    drafts = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each suggestion must be a structured item.")
        kind = item.get("kind")
        if kind not in BLOCK_KINDS:
            raise ValueError("An unsupported financial block was proposed.")
        name = item.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            raise ValueError("Each proposed block needs a short name.")
        draft = {"kind": kind, "name": name.strip(), "missing": []}
        fields = REVIEW_FIELDS[kind]
        if kind in ("income", "expense"):
            supplied_frequency = item.get("frequency")
            freq = supplied_frequency or "monthly"
            if freq not in FREQUENCIES:
                raise ValueError("Unsupported pay or expense frequency.")
            draft["frequency"] = freq
            if supplied_frequency is None:
                draft["missing"].append("frequency")
            value = _decimal(item.get("amount"), "Amount")
            if value is None:
                draft["missing"].append("amount")
            draft["amount"] = str(value if value is not None else Decimal("0"))
        else:
            for field in fields:
                if field == "account_type":
                    subtype = item.get("account_type")
                    if subtype not in ACCOUNT_TYPES:
                        draft["missing"].append(field)
                        subtype = "savings"
                    draft[field] = subtype
                elif field == "target_months":
                    raw = item.get(field)
                    if isinstance(raw, bool) or not isinstance(raw, int) or not 1 <= raw <= 600:
                        draft["missing"].append(field)
                        raw = 12
                    draft[field] = raw
                else:
                    value = _decimal(item.get(field), field)
                    if value is None:
                        draft["missing"].append(field)
                    draft[field] = str(value if value is not None else Decimal("0"))
            if kind in ("hysa", "roth_ira", "account", "goal"):
                growth = _decimal(item.get("annual_rate"), "Annual illustrative rate")
                # 0 growth is a transparent default assumption, not a rate quote.
                draft["annual_rate"] = str(growth if growth is not None else Decimal("0"))
                contribution = _decimal(item.get("monthly_contribution"), "Monthly contribution")
                draft["monthly_contribution"] = str(
                    contribution if contribution is not None else Decimal("0")
                )
            if kind == "goal":
                balance = _decimal(item.get("balance"), "Current goal savings")
                draft["balance"] = str(balance if balance is not None else Decimal("0"))
        drafts.append(draft)
    return drafts


def guided_drafts(data):
    """Create a few explicit blocks from answers, skipping unanswered sections."""
    if not isinstance(data, dict):
        raise ValueError("Setup answers must be structured.")
    raw = []
    takehome = _decimal(data.get("income"), "Income")
    if takehome is not None and takehome > 0:
        raw.append({
            "kind": "income", "name": "Take-home pay", "amount": str(takehome),
            "frequency": data.get("income_frequency", "monthly"),
        })
    for key, label, default_frequency in (
        ("rent", "Rent / housing", "monthly"),
        ("groceries", "Groceries", "weekly"),
        ("other", "Other living expenses", "monthly"),
    ):
        money = _decimal(data.get(key), label)
        if money is not None and money > 0:
            raw.append({
                "kind": "expense", "name": label, "amount": str(money),
                "frequency": data.get(f"{key}_frequency", default_frequency),
            })
    checking = _decimal(data.get("checking"), "Checking")
    if checking is not None and checking > 0:
        raw.append({"kind": "cash", "name": "Checking / cash", "balance": str(checking)})
    savings = _decimal(data.get("savings"), "Savings")
    if savings is not None and savings > 0:
        raw.append({"kind": "hysa", "name": "Savings account", "balance": str(savings)})
    debt = _decimal(data.get("debt"), "Loan balance")
    if debt is not None and debt > 0:
        raw.append({
            "kind": "loan", "name": "Loan / debt", "balance": str(debt),
            "annual_rate": data.get("debt_rate"),
            "monthly_payment": data.get("debt_payment"),
        })
    if data.get("include_goal"):
        goal_target = _decimal(data.get("goal_target"), "Savings goal target")
        if goal_target is not None and goal_target > 0:
            raw.append({
                "kind": "goal",
                "name": str(data.get("goal_name") or "Savings goal")[:60],
                "target": str(goal_target),
                "target_months": data.get("goal_months", 12),
                "balance": data.get("goal_balance", 0),
                "monthly_contribution": data.get("goal_contribution", 0),
            })
    return parse_drafts(raw)


def make_block(draft, block_id):
    """Build a validated MoneyLab block from one fully reviewed draft."""
    if not isinstance(draft, dict):
        raise ValueError("Draft must be a dictionary.")
    if draft.get("missing"):
        raise ValueError(
            "Review these unknown fields before adding this block: "
            + ", ".join(draft["missing"])
        )
    kind = draft.get("kind")
    if kind not in REVIEW_FIELDS:
        raise ValueError("Unknown block kind.")
    name = draft.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
        raise ValueError("Give each block a name (1–60 characters).")
    item = {"id": block_id, "kind": kind, "name": name.strip()}
    if kind in ("income", "expense"):
        freq = draft.get("frequency", "monthly")
        value = _decimal(draft.get("amount"), "Amount")
        if value is None:
            raise ValueError("Enter an amount for the income or expense.")
        item["monthly_amount"] = str(monthly_equivalent(value, freq))
        if freq != "monthly":
            item["frequency"] = freq
            item["period_amount"] = str(value)
    elif kind == "cash":
        item["balance"] = str(_decimal(draft.get("balance"), "Balance"))
    elif kind == "loan":
        for key in ("balance", "annual_rate", "monthly_payment"):
            item[key] = str(_decimal(draft.get(key), key))
    else:
        item["balance"] = str(_decimal(draft.get("balance", 0), "Balance"))
        item["annual_rate"] = str(_decimal(draft.get("annual_rate", 0), "Rate"))
        item["monthly_contribution"] = str(
            _decimal(draft.get("monthly_contribution", 0), "Monthly contribution")
        )
        if kind == "account":
            item["account_type"] = draft.get("account_type")
        if kind == "goal":
            item["target"] = str(_decimal(draft.get("target"), "Goal target"))
            item["target_months"] = draft.get("target_months")
    return serialize_blocks([item])[0]


def approve_drafts(existing_blocks, drafts, selected=None, id_factory=None):
    """Atomic merge; no mutation of original profile if one block is invalid."""
    before = serialize_blocks(existing_blocks)
    if not isinstance(drafts, list) or len(drafts) > DRAFT_MAX:
        raise ValueError("Too many suggested blocks.")
    if selected is None:
        selected = [True] * len(drafts)
    if not isinstance(selected, list) or len(selected) != len(drafts):
        raise ValueError("Select which blocks to add.")
    if id_factory is None:
        id_factory = lambda: uuid4().hex[:12]
    additions = [
        make_block(deepcopy(draft), id_factory())
        for draft, keep in zip(drafts, selected)
        if keep is True
    ]
    if not additions:
        raise ValueError("Choose at least one block to add.")
    if len(before) + len(additions) > MAX_BLOCKS:
        raise ValueError(f"Your profile supports up to {MAX_BLOCKS} blocks.")
    return serialize_blocks(before + additions)
