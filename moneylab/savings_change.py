"""Detached savings scenarios for the result-first flow, independent of Streamlit.

A scenario can cut one recorded expense, send some of that money to a goal, and
add extra monthly saving. Every outcome comes from the real projection engine.
"""

from decimal import Decimal
import re

from moneylab.blocks import serialize_blocks
from moneylab.engine import ZERO, validate_money
from moneylab.goal_result import DISCRETIONARY, ESSENTIALS, money
from moneylab.planning import goal_alternative

# Heuristic: recurring commitments that are rarely a sensible "what if I spent
# less?" test. A discretionary keyword (dining, coffee, subscriptions...) wins.
FIXED_COSTS = re.compile(r"\b(loans?|payments?|mortgage|tuition|childcare|medical|health|phone|internet|wifi)\b", re.I)


def _is_flexible(name):
    if ESSENTIALS.search(name):
        return False
    return bool(DISCRETIONARY.search(name)) or not FIXED_COSTS.search(name)


def flexible_expenses(blocks):
    """Return recorded spending a person can reasonably test cutting.

    Essentials (rent, groceries, utilities, insurance, debt, bills) and fixed
    commitments are left out. Entries with a discretionary keyword are listed
    first so they stay the default choice.
    """
    candidates = [
        block for block in serialize_blocks(blocks)
        if block['kind'] == 'expense'
        and _is_flexible(block['name'])
        and Decimal(block['monthly_amount']) > ZERO
    ]
    return sorted(candidates, key=lambda block: 0 if DISCRETIONARY.search(block['name']) else 1)


def savings_scenario(blocks, goal_id, expense_id, spending, redirect, *, extra=0, months=120):
    """Build an engine-backed comparison without changing the source profile.

    Beyond the redirected amount, ``extra`` is additional monthly saving for the
    goal. The engine funds it only from money actually available each month.
    """
    items = serialize_blocks(blocks)
    expense = next((b for b in items if b['id'] == expense_id and b['kind'] == 'expense'), None)
    goal = next((b for b in items if b['id'] == goal_id and b['kind'] == 'goal'), None)
    if expense is None or expense not in flexible_expenses(items):
        raise ValueError('Choose a recorded flexible spending category.')
    if goal is None:
        raise ValueError('Choose an existing savings goal.')
    current = Decimal(expense['monthly_amount'])
    tested = validate_money(spending, 'Test spending amount')
    redirected = validate_money(redirect, 'Amount redirected to the goal')
    extra_saving = validate_money(extra, 'Extra monthly saving')
    if tested > current:
        raise ValueError('This focused test can reduce spending, but cannot increase it.')
    freed = current - tested
    if redirected > freed:
        raise ValueError('The amount sent to the goal cannot exceed the spending reduction.')
    comparison = goal_alternative(
        items,
        goal_id,
        Decimal(goal['monthly_contribution']) + redirected + extra_saving,
        expense_id=expense_id,
        reduction=freed,
        months=max(months, goal['target_months']),
    )
    comparison['title'] = f"Test a change to {expense['name']}"
    comparison['savings_change'] = {
        'expense_id': expense_id,
        'spending': tested,
        'freed': freed,
        'redirect': redirected,
        'extra': extra_saving,
    }
    return comparison


def comparison_summary(projection, goal_id):
    """Return the first-month budget and goal facts shown in each column."""
    row = projection['monthly_records'][1]
    goal = next(g for g in projection['goals'] if g['id'] == goal_id)
    completion = next(
        (record['month'] for record in projection['monthly_records']
         if record['balances'].get(goal_id, ZERO) >= goal['target']),
        None,
    )
    return {
        'take_home': row['income'],
        'spending_and_bills': row['living_expenses'] + row['loan_payments'],
        'available_before_savings': row['income'] - row['living_expenses'] - row['loan_payments'],
        'savings_contributions': row['asset_contributions'],
        'left_after_savings': row['net_cash_flow'],
        'projected': goal['projected_at_deadline'],
        'gap': max(goal['target'] - goal['projected_at_deadline'], ZERO),
        'target': goal['target'],
        'deadline': goal['target_months'],
        'completion_month': completion,
    }


def _months(count):
    if count is None:
        return 'not reached within 120 months'
    return f"{count} month{'' if count == 1 else 's'}"


def scenario_headline(current, tested, goal_name, *, added_saving=ZERO):
    """Summarize a scenario in one plain sentence.

    ``current`` and ``tested`` come from ``comparison_summary``. Returns a dict
    with ``tone`` ('success', 'info' or 'warning'), ``text`` and an optional
    ``note`` explaining when the budget cannot fund the requested saving.
    """
    deadline = tested['deadline']
    target = money(tested['target'])
    cur_gap, new_gap = current['gap'], tested['gap']
    cur_done, new_done = current['completion_month'], tested['completion_month']
    tone = 'info'
    if new_gap == ZERO:
        tone = 'success'
        if cur_gap > ZERO:
            early = f", in {_months(new_done)}" if new_done is not None and new_done < deadline else ''
            text = (f"This reaches your {target} {goal_name} goal by month {deadline}{early}. "
                    f"Your current plan is {money(cur_gap)} short.")
        elif new_done is not None and cur_done is not None and new_done != cur_done:
            difference = abs(cur_done - new_done)
            sooner = new_done < cur_done
            tone = 'success' if sooner else 'warning'
            text = (f"You reach your {goal_name} goal in {_months(new_done)}: {_months(difference)} "
                    f"{'sooner' if sooner else 'later'} than your current plan ({_months(cur_done)}).")
        else:
            text = f"Your {goal_name} goal timing does not change ({_months(new_done)})."
    elif new_gap < cur_gap:
        text = (f"Still {money(new_gap)} short of {target} at month {deadline}, but "
                f"{money(cur_gap - new_gap)} closer than your current plan.")
    elif new_gap > cur_gap:
        tone = 'warning'
        text = (f"This leaves you {money(new_gap - cur_gap)} further from your {goal_name} "
                f"goal at month {deadline}.")
    else:
        text = f"No effect on your {goal_name} goal at month {deadline}."
        if tested['left_after_savings'] != current['left_after_savings']:
            text += (f" Money left each month goes from {money(current['left_after_savings'])} "
                     f"to {money(tested['left_after_savings'])}.")
    note = None
    if added_saving > ZERO:
        achieved = tested['savings_contributions'] - current['savings_contributions']
        if achieved < added_saving:
            note = (f"Your monthly budget only has room for {money(max(achieved, ZERO))} of the "
                    f"{money(added_saving)} extra saving, so this result uses that smaller amount.")
    return {'tone': tone, 'text': text, 'note': note}


def goal_balance_series(comparison, goal_id):
    """Month-by-month goal balances for the current plan and the test scenario.

    Returns ``months``, ``current`` and ``test`` lists of equal length (floats,
    for charting), plus the goal ``target`` and ``deadline``. The window runs a
    few months past the deadline and past either completion month.
    """
    before, after = comparison['baseline'], comparison['alternative']
    goal = next(g for g in after['goals'] if g['id'] == goal_id)
    deadline, target = goal['target_months'], goal['target']

    def completion(projection):
        return next((r['month'] for r in projection['monthly_records']
                     if r['balances'].get(goal_id, ZERO) >= target), None)

    last = min(len(before['monthly_records']), len(after['monthly_records'])) - 1
    window = max(deadline + 6, (completion(before) or 0) + 3, (completion(after) or 0) + 3)
    last = min(last, window)
    months = list(range(last + 1))
    return {
        'months': months,
        'current': [float(before['monthly_records'][m]['balances'].get(goal_id, ZERO)) for m in months],
        'test': [float(after['monthly_records'][m]['balances'].get(goal_id, ZERO)) for m in months],
        'target': float(target),
        'deadline': deadline,
    }
