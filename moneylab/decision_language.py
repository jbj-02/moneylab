"""Private, rules-based interpretation of everyday financial decision descriptions.

This deliberately shares amount/frequency recognition with Quick Start's Smart
Paste, but creates *temporary, unapproved scenario drafts* rather than profile
blocks. Unknown values stay unknown. Gross pay is never treated as take-home.
No external APIs, machine learning, or arbitrary evaluation are involved.
"""
import re
from decimal import Decimal

from moneylab.cadence import monthly_equivalent
from moneylab.free_setup import _money_values, _frequency

MAX_DESCRIPTION = 2200
MAX_VALUE = Decimal("100000000.00")
_CENT = Decimal("0.01")

_MOVE = re.compile(
    r"\b(?:mov(?:e|ing)\s+(?:out|in|to)|relocat(?:e|ing|ion)|"
    r"new apartment|rent(?:ing)?\s+(?:an?\s+)?(?:apartment|place)|"
    r"move\s+to\s+(?:another|a new)\s+city|live\s+(?:alone|with roommates))\b",
    re.I,
)
_PURCHASE = re.compile(
    r"\b(?:vacation|trip|holiday|one[- ]time purchase|buy(?:ing)?\b|"
    r"purchase|expensive item|new laptop)\b", re.I,
)
_RECURRING = re.compile(
    r"\b(?:subscription|membership|new recurring|monthly commitment|"
    r"monthly expense|additional monthly|gym membership|pay for a gym)\b", re.I,
)
_UNSUPPORTED = re.compile(
    r"\b(?:refinanc(?:e|ing)|retirement strategy|401k vs|mortgage approval|"
    r"rent vs buy a home|stock recommendations)\b", re.I,
)
_CLAUSES = re.compile(
    r"(?<!\d)[,;.!?\n](?!\d)|"
    r"\s+\b(?:and|but)\b(?=\s+(?:(?:i|my|we|the|our|a|an|have)\s+){0,3}"
    r"(?:make|earn|take|pay|spend|have|saved|got|rent|housing|"
    r"checking|savings|cash|utilities|internet|deposit|"
    r"groceries|grocery|moving|transport|insurance|furniture|"
    r"monthly|buy|purchase|cost|salary|loan|debt))",
    re.I,
)
_NET = re.compile(
    r"\b(?:net\s+(?:pay|income|salary|paycheck)|take[- ]home|"
    r"after[- ]tax(?:es)?|after\s+taxes)\b", re.I,
)
_GROSS = re.compile(
    r"\b(?:gross|before[- ]tax(?:es)?|before\s+taxes|pre[- ]tax)\b", re.I,
)
_INCOME = re.compile(
    r"\b(?:income|salary|paycheck|earn|earning|make|making|"
    r"paid|wages|take[- ]home)\b", re.I,
)
_NUM_WORD = re.compile(r"\b(?:free|zero|no)\s+(?:rent|housing)\b|\brent[- ]free\b", re.I)

# More-specific patterns must precede generic housing and living expenses.
_FIELDS = (
    ("minimum_debt", r"\b(?:minimum\s+(?:loan|debt)\s+payment|"
     r"student\s+loan\s+payment|debt\s+payments?|loan\s+payments?)\b"),
    ("security_deposit", r"\b(?:security\s+deposit|move[- ]in\s+deposit)\b"),
    ("moving_cost", r"\b(?:moving\s+(?:costs?|expenses?|fees?)|movers?|moving\s+truck)\b"),
    ("furniture", r"\b(?:furniture|furnishings)\b"),
    ("renters_insurance", r"\b(?:renters?'?\s+insurance)\b"),
    ("utilities", r"\b(?:utilities|utility\s+bills?|electricity|heating\s+bill)\b"),
    ("internet", r"\b(?:internet|wi[- ]?fi\s+bill)\b"),
    ("checking", r"\b(?:checking|cash\s+(?:available|balance|on\s+hand)|in\s+cash)\b"),
    ("savings", r"\b(?:savings?|saved|in\s+(?:my|the)\s+bank)\b"),
    ("current_housing", r"\b(?:current(?:ly)?\s+(?:rent|housing|pay(?:ing)?\s+(?:for\s+)?housing)|"
     r"rent\s+(?:now|currently)|housing\s+(?:now|currently))\b"),
    ("rent", r"\b(?:rent|apartment|new\s+place|housing)\b"),
    ("other_living", r"\b(?:other\s+(?:living\s+)?expenses?|"
     r"living\s+expenses?|monthly\s+(?:expenses|bills)|"
     r"regular\s+(?:expenses|bills))\b"),
    ("transport_change", r"\b(?:transport(?:ation)?|commut(?:e|ing)|gas\s+costs?)\b"),
    ("groceries_change", r"\b(?:groceries|grocery\s+costs?)\b"),
    ("other_change", r"\b(?:other\s+(?:cost|spending)\s+change)\b"),
    ("other_upfront", r"\b(?:upfront\s+fees?|one[- ]time\s+(?:fees?|costs?))\b"),
)
_COMPILED = [(name, re.compile(pattern, re.I)) for name, pattern in _FIELDS]
_CHANGE = re.compile(
    r"\b(?:additional|extra|increase|decrease|more|less|higher|lower|"
    r"change|difference|save)\b", re.I,
)
_DECREASE = re.compile(r"\b(?:decrease|less|lower|save)\b", re.I)

_REQUIRED = {
    "moving": ("income", "current_housing", "rent"),
    "recurring": ("cost", "frequency"),
    "purchase": ("cost",),
}
_LABELS = {
    "income": "monthly take-home income", "current_housing": "current housing costs",
    "rent": "proposed monthly rent", "cost": "proposed cost",
    "frequency": "how often the new cost occurs",
    "checking": "available checking/cash",
}


def _classify(description):
    move = bool(_MOVE.search(description))
    purchase = bool(_PURCHASE.search(description))
    recurring = bool(_RECURRING.search(description))
    if _UNSUPPORTED.search(description):
        return "unsupported"
    # Rent and deposits in a moving description aren't a second purchase.
    if move:
        distinct_purchase = bool(re.search(
            r"\b(?:buy(?:ing)?\s+(?:a|an|the)|purchase\s+(?:a|an|the)|"
            r"vacation|holiday|trip)\b", description, re.I
        ))
        if distinct_purchase:
            return "ambiguous"
        return "moving"
    if purchase and recurring:
        return "ambiguous"
    if recurring:
        return "recurring"
    if purchase:
        return "purchase"
    # Standalone cost descriptions may express recurrence explicitly.
    if re.search(r"\b(?:add|start|sign\s+up\s+for)\b.*"
                 r"\b(?:per\s+month|monthly|per\s+week|weekly)\b",
                 description, re.I | re.S):
        return "recurring"
    return "unsupported"


def _field(clause, intent):
    if _INCOME.search(clause) or _NET.search(clause):
        # Don't mix salary and living costs in one ambiguous clause.
        if re.search(r"\b(?:loan|rent|housing|expenses)\b", clause, re.I):
            return None
        return "income"
    if intent == "moving":
        for key, pattern in _COMPILED:
            if pattern.search(clause):
                return key
    if re.search(r"\b(?:checking|cash\s+(?:available|balance|on\s+hand))\b", clause, re.I):
        return "checking"
    if re.search(r"\b(?:savings?|saved)\b", clause, re.I):
        return "savings"
    if re.search(r"\b(?:living\s+expenses?|monthly\s+expenses?|"
                 r"regular\s+(?:expenses|bills)|spending\s+each\s+month)\b",
                 clause, re.I):
        return "other_living"
    return "cost"


def _validate_value(value):
    if not value.is_finite() or value < 0 or value > MAX_VALUE:
        raise ValueError("One amount is outside supported financial limits.")
    if value != value.quantize(_CENT):
        raise ValueError("Use no more than two decimal places for dollar amounts.")
    return str(value)


def interpret_decision(description):
    """Return a temporary interpretation; NEVER create/modify profile blocks.

    Only explicit, unambiguous figures are used. For every unrecognized
    essential value, the user is asked to supply it in the review or lab.
    """
    if not isinstance(description, str) or not 12 <= len(description.strip()) <= MAX_DESCRIPTION:
        raise ValueError("Describe your decision in 12–2,200 characters.")
    intent = _classify(description)
    result = {
        "intent": intent, "values": {}, "missing": [],
        "notes": [], "ignored": [], "gross_income": None,
        "provided": [],
    }
    if intent in ("unsupported", "ambiguous"):
        result["notes"].append(
            "Please choose one supported decision: moving, a new recurring "
            "expense, or a one-time purchase."
        )
        return result

    parts = [x.strip() for x in _CLAUSES.split(description) if x.strip()]
    for part in parts:
        matches = _money_values(part)
        if not matches:
            if intent == "moving" and _NUM_WORD.search(part):
                key = "current_housing" if re.search(
                    r"\b(?:currently|now|parents|at\s+home)\b", part, re.I
                ) else None
                if key:
                    result["values"][key] = "0"
                    result["provided"].append(key)
            continue
        # Multiple dollar figures in the same clause lack unambiguous labels.
        # Better to leave them out than silently assign the first one.
        if len(matches) != 1:
            result["ignored"].append(part[:110])
            continue
        value = matches[0][0]
        try:
            safe_value = _validate_value(value)
        except ValueError:
            result["ignored"].append(part[:110])
            continue
        key = _field(part, intent)
        if key in ("transport_change", "groceries_change", "other_change"):
            if not _CHANGE.search(part):
                result["ignored"].append(part[:110])
                continue
            if _DECREASE.search(part):
                safe_value = str(-Decimal(safe_value))
        if key == "income":
            if not _NET.search(part) or _GROSS.search(part):
                result["gross_income"] = {
                    "amount": safe_value, "frequency": _frequency(part),
                }
                result["notes"].append(
                    "Salary was not explicitly identified as take-home pay, "
                    "so it was not used as spendable income."
                )
                continue
            freq = _frequency(part)
            if freq is None:
                result["ignored"].append(part[:110])
                result["notes"].append(
                    "Take-home pay needs a frequency before it can be "
                    "converted to a monthly amount."
                )
                continue
            safe_value = str(monthly_equivalent(value, freq))
        elif key in ("rent", "current_housing", "other_living",
                     "minimum_debt", "utilities", "internet", "renters_insurance",
                     "transport_change", "groceries_change", "other_change"):
            freq = _frequency(part)
            if freq not in (None, "monthly"):
                safe_value = str(monthly_equivalent(Decimal(safe_value), freq))
            elif freq is None:
                result["notes"].append(
                    f"{key.replace('_', ' ').capitalize()} is interpreted as "
                    "a monthly cost. Confirm its frequency in the review."
                )
        elif key == "cost":
            # Purchase is by definition one-time, but a recurring cost
            # requires an explicit frequency or later user confirmation.
            if intent == "recurring":
                freq = _frequency(part)
                if freq:
                    result["values"]["frequency"] = freq
                    result["provided"].append("frequency")
        if key in result["values"]:
            result["ignored"].append(part[:110])
            result["notes"].append(
                f"Multiple values for {key.replace('_', ' ')} were found. "
                "Please confirm the amount in the scenario."
            )
            result["values"].pop(key, None)
            continue
        result["values"][key] = safe_value
        result["provided"].append(key)

    # There is no safe assumption that gross salary is net income or that
    # undocumented expenses are truly zero.
    result["missing"] = [
        name for name in _REQUIRED[intent] if name not in result["values"]
    ]
    if intent == "moving" and "other_living" not in result["values"]:
        result["notes"].append(
            "Other living expenses have not been entered and will be "
            "flagged as missing in Moving Out."
        )
    return result


def label_for(key):
    return _LABELS.get(key, key.replace("_", " ").capitalize())
