"""One-click financial block templates for beginner-friendly onboarding."""

from moneylab.blocks import serialize_blocks


PRESET_CATALOG = {

    "hourly": {"kind": "income", "name": "Hourly wages (estimated monthly net)", "monthly_amount": "2000"},
    "freelance": {"kind": "income", "name": "Freelance / gig income (net)", "monthly_amount": "400"},
    "insurance": {"kind": "expense", "name": "Insurance", "monthly_amount": "100"},
    "transport": {"kind": "expense", "name": "Transportation", "monthly_amount": "120"},
    "shopping": {"kind": "expense", "name": "Shopping", "monthly_amount": "150"},
    "credit": {"kind": "loan", "name": "Credit card (fixed-rate simplified)",
               "balance": "1000", "annual_rate": "19", "monthly_payment": "75"},
    "mortgage": {"kind": "loan", "name": "Mortgage (simplified)",
                 "balance": "100000", "annual_rate": "6", "monthly_payment": "800"},
    "savings": {"kind": "account", "name": "Regular savings", "account_type": "savings",
                "balance": "0", "annual_rate": "0", "monthly_contribution": "0"},
    "money_market": {"kind": "account", "name": "Money market account",
                     "account_type": "money_market", "balance": "0",
                     "annual_rate": "0", "monthly_contribution": "0"},
    "cd": {"kind": "account", "name": "Certificate of deposit (simplified)",
           "account_type": "cd", "balance": "0", "annual_rate": "0",
           "monthly_contribution": "0"},
    "traditional_ira": {"kind": "account", "name": "Traditional IRA",
                        "account_type": "traditional_ira", "balance": "0",
                        "annual_rate": "0", "monthly_contribution": "0"},
    "traditional_401k": {"kind": "account", "name": "Traditional 401(k)",
                         "account_type": "traditional_401k", "balance": "0",
                         "annual_rate": "0", "monthly_contribution": "0"},
    "roth_401k": {"kind": "account", "name": "Roth 401(k)",
                  "account_type": "roth_401k", "balance": "0",
                  "annual_rate": "0", "monthly_contribution": "0"},
    "403b": {"kind": "account", "name": "403(b)", "account_type": "403b",
             "balance": "0", "annual_rate": "0", "monthly_contribution": "0"},
    "brokerage": {"kind": "account", "name": "Brokerage investments",
                   "account_type": "brokerage", "balance": "0",
                   "annual_rate": "0", "monthly_contribution": "0"},
    "hsa": {"kind": "account", "name": "Health savings account (HSA)",
             "account_type": "hsa", "balance": "0", "annual_rate": "0",
             "monthly_contribution": "0"},
    "529": {"kind": "account", "name": "529 college savings", "account_type": "529",
             "balance": "0", "annual_rate": "0", "monthly_contribution": "0"},
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
