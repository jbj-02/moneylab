"""One-click financial block templates for beginner-friendly onboarding."""

from moneylab.blocks import serialize_blocks


PRESET_CATALOG = {
    "takehome": {"kind": "income", "name": "Take-home salary", "monthly_amount": "3000"},
    "sidejob": {"kind": "income", "name": "Side income", "monthly_amount": "250"},
    "rent": {"kind": "expense", "name": "Rent", "monthly_amount": "1200"},
    "groceries": {"kind": "expense", "name": "Groceries", "monthly_amount": "300"},
    "utilities": {"kind": "expense", "name": "Utilities & internet", "monthly_amount": "150"},
    "fun": {"kind": "expense", "name": "Fun & going out", "monthly_amount": "200"},
    "subscriptions": {"kind": "expense", "name": "Subscriptions", "monthly_amount": "40"},
    "student": {"kind": "loan", "name": "Student loan", "balance": "10000",
                "annual_rate": "5", "monthly_payment": "110"},
    "car": {"kind": "loan", "name": "Car payment", "balance": "8000",
            "annual_rate": "6", "monthly_payment": "250"},
    "checking": {"kind": "cash", "name": "Checking account", "balance": "500"},
    "hysa": {"kind": "hysa", "name": "High-yield savings", "balance": "500",
             "annual_rate": "3", "monthly_contribution": "100"},
    "roth": {"kind": "roth_ira", "name": "Roth IRA", "balance": "0",
             "annual_rate": "0", "monthly_contribution": "50"},
    "emergency": {"kind": "goal", "name": "Emergency fund", "balance": "0",
                  "annual_rate": "0", "monthly_contribution": "150",
                  "target": "5000", "target_months": 24},
    "trip": {"kind": "goal", "name": "Travel savings", "balance": "0",
             "annual_rate": "0", "monthly_contribution": "75",
             "target": "1800", "target_months": 18},
}


def preset_block(preset_id, block_id):
    """Make a validated independent copy with a unique caller-provided ID."""
    if preset_id not in PRESET_CATALOG:
        raise ValueError("Unknown financial block template.")
    raw = {"id": block_id, **PRESET_CATALOG[preset_id]}
    return serialize_blocks([raw])[0]
