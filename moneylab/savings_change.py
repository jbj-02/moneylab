"""Detached, one-expense savings scenarios for the result-first flow."""

from decimal import Decimal

from moneylab.blocks import serialize_blocks
from moneylab.engine import ZERO, validate_money
from moneylab.goal_result import DISCRETIONARY, ESSENTIALS
from moneylab.planning import goal_alternative


def flexible_expenses(blocks):
    """Return recorded flexible categories that are safe to offer for editing."""
    return [
        block for block in serialize_blocks(blocks)
        if block['kind'] == 'expense'
        and DISCRETIONARY.search(block['name'])
        and not ESSENTIALS.search(block['name'])
        and Decimal(block['monthly_amount']) > ZERO
    ]


def savings_scenario(blocks, goal_id, expense_id, spending, redirect, *, months=120):
    """Build an engine-backed comparison without changing the source profile."""
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
    if tested > current:
        raise ValueError('This focused test can reduce spending, but cannot increase it.')
    freed = current - tested
    if redirected > freed:
        raise ValueError('The amount sent to the goal cannot exceed the spending reduction.')
    comparison = goal_alternative(
        items,
        goal_id,
        Decimal(goal['monthly_contribution']) + redirected,
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
