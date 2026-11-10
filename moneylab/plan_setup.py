"""One goal-first setup model. Blank answers remain explicit unknowns."""
from decimal import Decimal

from moneylab.blocks import serialize_blocks
from moneylab.engine import validate_money, validate_annual_interest_rate

EXPENSES = {
    "housing": "Rent / housing", "food": "Groceries & dining",
    "transport": "Transport", "bills": "Utilities, phone & subscriptions",
    "other": "Other regular spending",
}
PRIORITIES = ("Build an emergency fund", "Move out", "Save for something", "Understand my money")


def build_profile(answers):
    """Build a new profile atomically, without conflating unknown and zero.

    Savings allocated to a goal are deducted from the total savings balance.
    Setup never replaces or merges into an existing profile.
    """
    blocks, unknown = [], []

    def amount(field):
        raw = answers.get(field)
        if raw is None or raw == "":
            unknown.append(field)
            return None
        return validate_money(raw, field)

    income = amount("income")
    if income is not None:
        blocks.append({"id": "setup_income", "kind": "income", "name": "Take-home pay", "monthly_amount": str(income)})
    for key, label in EXPENSES.items():
        value = amount(key)
        if value is not None:
            blocks.append({"id": f"setup_{key}", "kind": "expense", "name": label, "monthly_amount": str(value)})
    checking, savings = amount("checking"), amount("savings")
    if checking is not None:
        blocks.append({"id": "setup_checking", "kind": "cash", "name": "Checking / cash", "balance": str(checking)})
    priority = answers.get("priority", PRIORITIES[0])
    if priority not in PRIORITIES:
        raise ValueError("Choose a financial priority.")
    allocated = Decimal(0)
    if priority != "Understand my money":
        target = amount("target")
        saved = amount("goal_saved")
        pace = amount("goal_monthly")
        duration = answers.get("goal_months")
        if target is None or target <= 0 or saved is None or pace is None:
            raise ValueError("Enter a goal target, money already set aside and monthly saving, including $0 where appropriate.")
        if savings is None and saved > 0:
            raise ValueError("Enter total savings so money already set aside is not counted twice.")
        if savings is not None and saved > savings:
            raise ValueError("Money set aside for this goal cannot exceed your total savings.")
        allocated = saved
        blocks.append({"id": "setup_goal", "kind": "goal",
                       "name": answers.get("goal_name") or {PRIORITIES[0]: "Emergency fund", PRIORITIES[1]: "Move-out fund"}.get(priority, "My savings goal"),
                       "balance": str(saved), "annual_rate": "0", "monthly_contribution": str(pace),
                       "target": str(target), "target_months": duration})
    if savings is not None:
        blocks.append({"id": "setup_savings", "kind": "hysa", "name": "Other savings",
                       "balance": str(savings - allocated), "annual_rate": "0", "monthly_contribution": "0"})
    debt_status = answers.get("debt_status", "I'll add this later")
    if debt_status == "I have debt":
        debt = {key: amount(key) for key in ("debt_balance", "debt_payment")}
        debt["debt_rate"] = (validate_annual_interest_rate(answers["debt_rate"])
                             if answers.get("debt_rate") is not None else None)
        if any(v is None for v in debt.values()):
            raise ValueError("Enter the debt balance, interest rate and monthly payment, or choose to add debt later.")
        blocks.append({"id": "setup_debt", "kind": "loan", "name": "Loan / debt",
                       "balance": str(debt["debt_balance"]), "annual_rate": str(debt["debt_rate"]),
                       "monthly_payment": str(debt["debt_payment"])})
    elif debt_status != "I have no debt":
        unknown.append("debts")
    return serialize_blocks(blocks), {"priority": priority, "unknown": unknown, "is_example": False}
