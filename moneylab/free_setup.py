"""Free, private text-to-financial-block suggestions for MoneyLab.

This is deliberately a small, explainable rules-based extractor, *not* an LLM.
It supports common financial categories and monetary amounts without making
network calls. Unrecognized statements are ignored and assumptions are flagged
for human review. No source text is placed inside saved financial blocks.
"""
import re
from decimal import Decimal

from moneylab.onboarding import DRAFT_MAX, parse_drafts

MAX_TEXT = 2200
_MONEY = r"(?:\$\s*)?(?P<amount>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?P<suffix>\s*[kK])?"
_MONEY_RE = re.compile(_MONEY)
_PERCENT = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)\s*%")
_SEGMENTS = re.compile(r"[,;](?!\d)|\n|(?<=[.!?])\s+(?=[A-Z])")
_SPLIT_CATEGORY = re.compile(
    r"\s+\band\b(?=\s+(?:(?:my|the|i\s+have|i\s+pay|i\s+make|i\s+earn)\s+)?"
    r"(?:rent|mortgage|housing|grocer|food|transport|gas|utility|utilities|insurance|"
    r"subscriptions?|checking|saving|hysa|emergency|car loan|student loan|"
    r"loan|debt|credit card|paycheck|income|salary|wages|job))",
    re.IGNORECASE,
)

_TAGS = (
    ("loan", re.compile(r"\b(?:student loans?|car loans?|personal loans?|mortgage|credit cards?|debt|loans?)\b", re.I)),
    ("goal", re.compile(r"\b(?:saving for|save toward|goal to save|financial goal|want to save|goal of)\b", re.I)),
    ("cash", re.compile(r"\b(?:checking|bank balance|cash balance|in cash)\b", re.I)),
    ("hysa", re.compile(r"\b(?:hysa|high[- ]yield|savings accounts?|in savings)\b", re.I)),
    ("roth_ira", re.compile(r"\broth\s+ira\b", re.I)),
    ("income", re.compile(r"\b(?:paychecks?|salary|wages|earn|earning|make|income|take[- ]home|net pay|paid)\b", re.I)),
    ("expense", re.compile(r"\b(?:rent|housing|groceries|grocery|food|utilities|utility|internet|"
                            r"insurance|transport|gas|shopping|subscriptions?|dining|"
                            r"phone bill|electricity|water bill)\b", re.I)),
)

_EXPENSE_NAMES = (
    (r"\b(?:rent|housing|apartment)\b", "Rent / housing"),
    (r"\b(?:groceries|grocery|food)\b", "Groceries / food"),
    (r"\b(?:utilities|utility|electricity|water bill|internet)\b", "Utilities & internet"),
    (r"\b(?:transport|gas|commute)\b", "Transportation"),
    (r"\b(?:insurance)\b", "Insurance"),
    (r"\b(?:subscriptions?)\b", "Subscriptions"),
    (r"\b(?:shopping)\b", "Shopping"),
    (r"\b(?:dining)\b", "Dining out"),
    (r"\b(?:phone bill)\b", "Phone bill"),
)
_FREQUENCIES = (
    ("biweekly", r"\b(?:bi[- ]?weekly|fortnightly|every (?:two|2) weeks?|every other week)\b"),
    ("weekly", r"\b(?:weekly|per week|a week|each week|every week|/week|/wk)\b"),
    ("yearly", r"\b(?:yearly|annually|annual|per year|a year|each year|/year|/yr)\b"),
    ("monthly", r"\b(?:monthly|per month|a month|each month|every month|/month|/mo)\b"),
)


def _frequency(text):
    for freq, pattern in _FREQUENCIES:
        if re.search(pattern, text, flags=re.I):
            return freq
    return None


def _money_values(text):
    """Extract monetary-looking tokens while excluding percent figures."""
    found = []
    for match in _MONEY_RE.finditer(text):
        after = text[match.end():match.end() + 4]
        if after.lstrip().startswith("%"):
            continue
        before = text[max(0, match.start() - 1):match.start()]
        if before.isalpha():
            continue
        num = Decimal(match.group("amount").replace(",", ""))
        if match.group("suffix"):
            num *= Decimal("1000")
        found.append((num, match.start(), match.end()))
    return found


def _category(text):
    for kind, rule in _TAGS:
        if rule.search(text):
            return kind
    return None


def _name(kind, text):
    if kind == "income":
        return "Take-home income"
    if kind == "cash":
        return "Checking / cash"
    if kind == "hysa":
        return "Savings account"
    if kind == "roth_ira":
        return "Roth IRA"
    if kind == "loan":
        for label, expr in (
            ("Student loan", r"\bstudent loans?\b"),
            ("Car loan", r"\bcar loans?\b"),
            ("Credit card", r"\bcredit cards?\b"),
            ("Mortgage", r"\bmortgage\b"),
        ):
            if re.search(expr, text, re.I):
                return label
        return "Loan / debt"
    if kind == "goal":
        return "Savings goal"
    for expr, label in _EXPENSE_NAMES:
        if re.search(expr, text, re.I):
            return label
    return "Living expense"


def _loan_details(text):
    """Recognize explicit rate/payment only; otherwise keep them missing."""
    rate = _PERCENT.search(text)
    payment = re.search(
        r"\b(?:monthly\s+payment|payment|minimum payment|paying)\b"
        r"(?:\s+(?:is|of|about|around))?\s*[:$ ]*\s*"
        r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)",
        text, re.I,
    )
    return (
        rate.group(1) if rate else None,
        payment.group(1).replace(",", "") if payment else None,
    )


def suggest_blocks_from_text(description):
    """Return reviewed-required drafts and unmatched text, without network calls.

    This parser is intentionally conservative, not 'AI'. Each quantity is
    contextualized only by phrases in the same short clause. Uncertain net
    pay, frequency, interest and monthly payments are explicit missing fields.
    """
    if not isinstance(description, str) or not 10 <= len(description.strip()) <= MAX_TEXT:
        raise ValueError("Enter 10–2,200 characters describing your finances.")
    clauses = []
    for part in _SEGMENTS.split(description.strip()):
        clauses.extend(_SPLIT_CATEGORY.split(part))
    raw, skipped = [], []
    for clause in clauses:
        text = clause.strip(" .!?:")
        if not text:
            continue
        kind = _category(text)
        numbers = _money_values(text)
        if kind is None or not numbers:
            skipped.append(text[:100])
            continue
        first = numbers[0][0]
        if first > Decimal("1000000000"):
            skipped.append(text[:100])
            continue
        if kind in ("income", "expense"):
            frequency = _frequency(text)
            amount = str(first)
            if kind == "income":
                explicitly_net = bool(re.search(
                    r"\b(?:take[- ]home|after[- ]tax|after taxes|net\b)\b",
                    text, re.I,
                ))
                explicitly_gross = bool(re.search(
                    r"\b(?:gross|before[- ]tax|before taxes|pre[- ]tax)\b",
                    text, re.I,
                ))
                if not explicitly_net or explicitly_gross:
                    # Salary/wages without a net qualifier should not be
                    # assumed to equal take-home pay.
                    amount = None
            raw.append({
                "kind": kind, "name": _name(kind, text),
                "amount": amount, "frequency": frequency,
            })
        elif kind == "cash":
            raw.append({"kind": kind, "name": _name(kind, text),
                        "balance": str(first)})
        elif kind in ("hysa", "roth_ira"):
            raw.append({"kind": kind, "name": _name(kind, text),
                        "balance": str(first)})
        elif kind == "loan":
            rate, payment = _loan_details(text)
            raw.append({
                "kind": "loan", "name": _name(kind, text),
                "balance": str(first), "annual_rate": rate,
                "monthly_payment": payment,
            })
        elif kind == "goal":
            # Goals need a target and deadline. A balance is not the target.
            months = re.search(r"\b(?:in|over|within)\s+(\d+)\s+months?\b", text, re.I)
            raw.append({
                "kind": "goal", "name": _name(kind, text),
                "target": str(first),
                "target_months": int(months.group(1)) if months else None,
            })
        if len(raw) >= DRAFT_MAX:
            break
    if not raw:
        raise ValueError(
            "I couldn't recognize any supported amounts. Try a short sentence like "
            "'My take-home pay is $1,800 biweekly, rent is $1,200 monthly'."
        )
    return parse_drafts(raw), skipped
