"""Short, contextual personal-finance lessons for MoneyLab.

This is educational content rather than financial advice. Each question
has one explanatory answer; no account data is sent to a third party.
"""

LESSONS = {
    "paycheck": {
        "title": "Understand your first paycheck",
        "summary": "Take-home pay is what you actually receive after deductions.",
        "explanation": (
            "Your gross salary and your take-home salary are not the same. "
            "MoneyLab currently asks for take-home (net) income, so expenses "
            "and savings should be planned using the amount actually deposited. "
            "Do not subtract a payroll deduction again if it is already excluded."
        ),
        "question": "If your take-home pay already excludes a payroll retirement deduction, should you deduct that same amount again in MoneyLab?",
        "options": ["Yes, every month", "No, that would double-count it"],
        "answer": 1,
        "feedback": "Correct: subtracting a deduction already excluded from net pay would count it twice.",
    },
    "budget": {
        "title": "Understand spending flexibility",
        "summary": "A monthly surplus only means something if your expenses are complete.",
        "explanation": (
            "Start with take-home income, subtract planned spending and loan "
            "payments, then account for intended savings. MoneyLab's extra "
            "spending estimate is a planning number—not a bank balance. "
            "Leaving out insurance, annual bills, or variable spending can "
            "make the estimate look too optimistic."
        ),
        "question": "If you forget an annual bill when entering expenses, what happens to your estimated spending flexibility?",
        "options": ["It may look too high", "It becomes more accurate"],
        "answer": 0,
        "feedback": "Correct: unrecorded costs can make an affordable-looking plan misleading.",
    },
    "savings": {
        "title": "Why an emergency fund matters",
        "summary": "Accessible savings can help with unexpected costs.",
        "explanation": (
            "An emergency fund is money intentionally set aside for surprises "
            "such as repairs or a temporary loss of income. Checking, savings "
            "and many HYSAs may be accessible, but a retirement account "
            "should not automatically be treated as emergency cash. "
            "MoneyLab can estimate how many months of listed spending your "
            "liquid balances might cover; this is not a guarantee."
        ),
        "question": "Which is usually more appropriate for a short-notice emergency?",
        "options": ["Accessible savings", "Money locked up for retirement"],
        "answer": 0,
        "feedback": "Correct: access and restrictions matter, not just account value.",
    },
    "debt": {
        "title": "What a loan payment actually does",
        "summary": "Part of a loan payment may cover interest instead of principal.",
        "explanation": (
            "MoneyLab estimates monthly loan interest using the opening "
            "balance and an annual rate divided by twelve. Payments go to "
            "interest first, then reduce principal. The actual rules of "
            "student loans, cards and mortgages can differ. If a payment "
            "does not cover interest, a balance can grow in this simplified model."
        ),
        "question": "If a monthly loan payment is smaller than the interest charged, what can happen?",
        "options": ["The balance can grow", "The debt automatically disappears"],
        "answer": 0,
        "feedback": "Correct: unpaid interest can increase debt under some loan arrangements.",
    },
    "interest": {
        "title": "Savings growth is an assumption",
        "summary": "A projected yield is not the same as a guaranteed outcome.",
        "explanation": (
            "MoneyLab uses a fixed annual assumption to illustrate how account "
            "balances might change over time. Advertised APY, monthly crediting "
            "methods, rate changes, taxes and fees can produce different "
            "real-world results. Investment returns can vary and may be negative."
        ),
        "question": "Does a five-year savings projection guarantee that the account will earn the assumed rate?",
        "options": ["Yes", "No, it is an illustration"],
        "answer": 1,
        "feedback": "Correct: future results can differ from fixed-rate assumptions.",
    },
    "retirement": {
        "title": "Retirement accounts aren't spending accounts",
        "summary": "Long-term accounts follow different rules from everyday cash.",
        "explanation": (
            "A Roth IRA, 401(k), 403(b) or similar account is intended for "
            "specific long-term or tax-advantaged purposes. Eligibility, "
            "tax treatment, withdrawal rules and contribution limits vary. "
            "MoneyLab models a hypothetical balance, not those legal rules. "
            "Don't treat retirement balances as automatically spendable today."
        ),
        "question": "Should MoneyLab's weekly spending estimate automatically include your Roth IRA balance?",
        "options": ["Yes", "No"],
        "answer": 1,
        "feedback": "Correct: long-term investments are not ordinary weekly spending cash.",
    },
    "special_accounts": {
        "title": "Special-purpose savings accounts",
        "summary": "HSA and 529 accounts follow rules that differ from ordinary savings.",
        "explanation": (
            "An HSA is intended for eligible healthcare expenses, and a 529 "
            "plan is primarily an education savings arrangement. Their "
            "eligibility, tax treatment and withdrawal rules can vary. "
            "MoneyLab currently models the balances and hypothetical growth, "
            "not the legal or tax requirements. Do not automatically treat "
            "these balances as unrestricted spending cash."
        ),
        "question": "Does a balance in an HSA or 529 automatically mean you can spend it on anything without consequences?",
        "options": ["Yes", "No, restrictions may apply"],
        "answer": 1,
        "feedback": "Correct: account-specific restrictions and tax rules matter.",
    },
    "routing": {
        "title": "Money movements are not new income",
        "summary": "Depositing part of your paycheck into savings doesn't create more money.",
        "explanation": (
            "If you earn $3,000 in take-home pay and direct $300 into a savings "
            "account, your total pay is still $3,000. The $300 changes where "
            "the money lives—it isn't a new paycheck or an extra expense. "
            "Use MoneyLab's routing feature to see your chosen allocation."
        ),
        "question": "If $200 of a $2,000 paycheck goes to an HYSA, what is your total monthly income?",
        "options": ["$2,200", "$2,000"],
        "answer": 1,
        "feedback": "Correct: an internal allocation does not increase total income.",
    },
    "goals": {
        "title": "Turn a wish into a savings goal",
        "summary": "A goal is more actionable with a target and a timeline.",
        "explanation": (
            "Try specifying an amount, what you have already saved, a deadline, "
            "and a realistic monthly contribution. MoneyLab can test whether "
            "the scenario reaches your goal under fixed assumptions. A missed "
            "deadline in a simulation suggests a possible adjustment, not failure."
        ),
        "question": "Which goal is easier to plan for?",
        "options": ["Save more someday", "Save $1,000 over the next 10 months"],
        "answer": 1,
        "feedback": "Correct: the amount and timeline allow a concrete calculation.",
    },
}

TOPIC_BY_KIND = {
    "income": ("paycheck", "routing"),
    "expense": ("budget",),
    "loan": ("debt",),
    "cash": ("savings",),
    "hysa": ("savings", "interest"),
    "roth_ira": ("retirement", "interest"),
    "goal": ("goals",),
    "account": ("interest",),
}
RETIREMENT_TYPES = {"roth_ira", "traditional_ira", "traditional_401k",
                    "roth_401k", "403b"}
SPECIAL_ACCOUNT_TYPES = {"hsa", "529"}


def recommended_lesson_ids(blocks):
    """Prioritize what a person actually added; allow learning before setup."""
    discovered = []
    if not blocks:
        return ["paycheck", "budget", "savings"]
    for block in blocks:
        kind = block["kind"]
        account_type = block.get("account_type")
        if kind == "account" and account_type in RETIREMENT_TYPES:
            topics = ("retirement", "interest")
        elif kind == "account" and account_type in SPECIAL_ACCOUNT_TYPES:
            topics = ("special_accounts", "interest")
        else:
            topics = TOPIC_BY_KIND.get(kind, ())
        for topic in topics:
            if topic not in discovered:
                discovered.append(topic)
    for topic in ("budget", "savings", "goals"):
        if topic not in discovered:
            discovered.append(topic)
    return discovered


def check_answer(lesson_id, selected_index):
    """Pure assessment helper; input must use the lesson's option index."""
    if lesson_id not in LESSONS:
        raise ValueError("Unknown lesson.")
    lesson = LESSONS[lesson_id]
    if isinstance(selected_index, bool) or not isinstance(selected_index, int):
        raise ValueError("Choose an available answer.")
    if not 0 <= selected_index < len(lesson["options"]):
        raise ValueError("Choose an available answer.")
    return {"correct": selected_index == lesson["answer"],
            "explanation": lesson["feedback"] if selected_index == lesson["answer"]
            else "Not quite. " + lesson["explanation"]}
