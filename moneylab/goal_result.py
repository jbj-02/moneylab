"""A short goal answer and one verified experiment, independent of Streamlit.

Suggestions are detached engine simulations. Expense suggestions are restricted
to recorded discretionary categories, at most half the entry and $150/month.
Those bounds are product heuristics, not claims about a person's ability to cut.
"""
from decimal import Decimal, ROUND_FLOOR
import re

from moneylab.action_plan import MISSING_LABELS, explain_option, first_reached
from moneylab.blocks import ASSET_KINDS, MAX_AMOUNT, project_blocks, serialize_blocks
from moneylab.engine import CENT, ZERO
from moneylab.planning import goal_alternative, goal_outlook

DISCRETIONARY = re.compile(r"\b(dining|takeaways?|takeout|restaurants?|entertainment|subscriptions?|coffee)\b", re.I)
ESSENTIALS = re.compile(r"\b(rent|housing|groceries|utilities|insurance|debt|bills)\b", re.I)


def money(value):
    return f"${value:,.2f}" if value >= 0 else f"-${abs(value):,.2f}"


def _not_worse_cash(comparison):
    return all(a['unfunded_shortfall'] <= b['unfunded_shortfall']
               for b, a in zip(comparison['baseline']['monthly_records'], comparison['alternative']['monthly_records']))


def _hits(comparison, goal_id):
    goal = next(g for g in comparison['alternative']['goals'] if g['id'] == goal_id)
    return goal['on_track'] and _not_worse_cash(comparison)


def _expense_rescue(blocks, goal, room):
    """Search the minimum bounded cut; redirect only modeled monthly room.

    The existing saving request plus room plus the cut is an upper bound on
    the new request. This does not assume access to earmarked account balances.
    """
    expenses = [b for b in blocks if b['kind'] == 'expense' and DISCRETIONARY.search(b['name']) and not ESSENTIALS.search(b['name'])]
    for expense in expenses:
        cap = min(Decimal(expense['monthly_amount']) / 2, Decimal('150')).quantize(CENT, rounding=ROUND_FLOOR)
        if cap <= ZERO:
            continue
        def trial(cut):
            return goal_alternative(blocks, goal['id'], Decimal(goal['monthly_contribution']) + room + cut,
                                    expense_id=expense['id'], reduction=cut)
        if not _hits(trial(cap), goal['id']):
            continue
        low, high = 1, int(cap / CENT)
        while low < high:
            middle = (low + high) // 2
            if _hits(trial(middle * CENT), goal['id']):
                high = middle
            else:
                low = middle + 1
        cut = low * CENT
        comparison = trial(cut)
        comparison['title'] = f"Reduce {expense['name']} and redirect the saving"
        return expense, cut, comparison
    return None


def _additional_savings_needed(blocks, goal, outlook):
    """Find the extra monthly goal transfer needed, independent of affordability.

    A temporary income block supplies only the tested increment. This lets the
    existing projection calculate interest and allocation order without
    claiming that the user's recorded budget can fund the result.
    """
    if outlook['on_track']:
        return ZERO
    items = serialize_blocks(blocks)
    planned = Decimal(goal['monthly_contribution'])
    prior = sum((Decimal(b['monthly_contribution']) for b in items
                 if b['kind'] in ASSET_KINDS and b['id'] != goal['id']), ZERO)
    ceiling = max(ZERO, min(Decimal(goal['target']) + prior, MAX_AMOUNT - planned))
    capacity_id = 'goal_feedback_capacity'
    used_ids = {item['id'] for item in items}
    while capacity_id in used_ids:
        capacity_id += '_temporary'

    def reaches(extra):
        candidate = serialize_blocks(items)
        target = next(b for b in candidate if b['id'] == goal['id'])
        target['monthly_contribution'] = str(planned + extra)
        candidate.append(dict(id=capacity_id, kind='income',
                              name='Temporary goal capacity', monthly_amount=str(extra)))
        projected = project_blocks(candidate, goal['target_months'])
        outcome = next(g for g in projected['goals'] if g['id'] == goal['id'])
        return outcome['on_track']

    if not reaches(ceiling):
        return None
    low, high = 0, int(ceiling / CENT)
    while low < high:
        middle = (low + high) // 2
        if reaches(middle * CENT):
            high = middle
        else:
            low = middle + 1
    return low * CENT


def goal_result(blocks, *, missing=(), preference=None):
    """Return what we found, what to test and its actual simulated difference."""
    items = serialize_blocks(blocks)
    goals = [g for g in items if g['kind'] == 'goal']
    if not goals:
        return None
    outlooks = {g['id']: goal_outlook(items, g['id']) for g in goals}
    preferred = (preference or {}).get('goal_id')
    goal = min(goals, key=lambda g: (g['id'] != preferred if preferred else outlooks[g['id']]['on_track'], g['target_months']))
    outlook = outlooks[goal['id']]
    horizon = max(120, *[g['target_months'] for g in goals])
    baseline = project_blocks(items, horizon)
    flow = baseline['monthly_records'][1]['net_cash_flow']
    room = max(flow, ZERO)
    qualifier = 'Based on the figures entered, ' if missing else ''
    if outlook['on_track']:
        finding = (f"{qualifier}you're on track for your {money(outlook['target'])} {goal['name']} goal "
                   f"in {outlook['deadline']} months, with {money(outlook['projected'])} projected.")
    else:
        finding = (f"{qualifier}you're projected to be {money(outlook['gap'])} short of your "
                   f"{money(outlook['target'])} {goal['name']} goal in {outlook['deadline']} months.")
    finding = finding[0].upper() + finding[1:]
    if missing:
        finding = (f"Add your {MISSING_LABELS.get(missing[0],missing[0])} to check your "
                   f"{money(outlook['target'])} {goal['name']} goal in {outlook['deadline']} months.")
    difference = outlook['projected'] - outlook['target']
    additional_needed = None if missing else _additional_savings_needed(items, goal, outlook)
    if missing:
        labels = ', '.join(MISSING_LABELS.get(item, item) for item in missing)
        status = 'More information needed'
        deadline_summary = f"{money(outlook['target'])} goal in {outlook['deadline']} months"
        position_summary = f"Add {labels} to calculate a reliable deadline balance and recommendation."
    elif outlook['on_track']:
        status = 'On track'
        deadline_summary = f"{money(outlook['projected'])} projected in {outlook['deadline']} months"
        position_summary=(f"You are {money(difference)} ahead of your {money(outlook['target'])} {goal['name']} target."
                          if difference > ZERO else
                          f"You are on pace to meet the {money(outlook['target'])} {goal['name']} target exactly.")
    else:
        status = f"{money(outlook['gap'])} behind"
        deadline_summary = f"{money(outlook['projected'])} projected in {outlook['deadline']} months"
        needed = (f" Saving {money(additional_needed)} more each month would close the gap."
                  if additional_needed is not None else '')
        position_summary=(f"The current pace leaves you {money(outlook['gap'])} short of your "
                          f"{money(outlook['target'])} {goal['name']} target.{needed}")
    result = dict(goal=goal, outlook=outlook, finding=finding, kind='missing' if missing else 'unreachable',
                  suggestion='', comparison=None, analysis=None, warnings=[], baseline=baseline, flow=flow,
                  missing=list(missing), expense_id=None, cut=ZERO, status=status,
                  deadline_summary=deadline_summary, position_summary=position_summary,
                  additional_needed=additional_needed)
    gap = next((r for r in baseline['monthly_records'][1:] if r['unfunded_shortfall'] > ZERO), None)
    if gap and not set(missing).intersection({'income','checking'}):
        result['warnings'].append(f"Recorded bills run short by {money(gap['unfunded_shortfall'])} in month {gap['month']}. Savings slow or stop when money is unavailable.")
    if any(r['negative_amortization'] for r in baseline['monthly_records'][1:]):
        result['warnings'].append('A recorded loan grows because its payment does not cover interest. Review that payment before committing more to savings.')
    if missing:
        return result
    comparison = None
    if outlook['on_track']:
        comparison = goal_alternative(items, goal['id'], outlook['planned'])
        result.update(kind='maintain',
                      suggestion=f"Keep saving {money(outlook['planned'])} each month to maintain this pace.")
    elif outlook['required'] is not None and outlook['extra'] <= room:
        comparison = goal_alternative(items, goal['id'], outlook['required'])
        if _hits(comparison, goal['id']):
            result.update(kind='set_aside', suggestion=f"Setting aside {money(outlook['extra'])} more each month from the {money(room)} left in your monthly plan would close the gap.")
        else:
            comparison = None
    if comparison is None and not outlook['on_track']:
        rescue = _expense_rescue(items, goal, room)
        if rescue:
            expense, cut, comparison = rescue
            extra_room = f", together with {money(room)} already left each month," if room else ''
            result.update(kind='expense', expense_id=expense['id'], cut=cut,
                          suggestion=f"Reduce {expense['name']} by {money(cut)} a month and redirect that money{extra_room} to savings. The verified projection reaches {money(outlook['target'])} by the deadline, closing the {money(outlook['gap'])} gap.")
    if comparison is None:
        completion = first_reached(baseline, goal)
        if completion is not None and completion > outlook['deadline']:
            comparison = goal_alternative(items, goal['id'], outlook['planned'], deadline=completion)
            if _hits(comparison, goal['id']):
                deadline_label = 'six-month' if outlook['deadline'] == 6 else f"{outlook['deadline']}-month"
                result.update(kind='later', suggestion=f"Revise the goal: use {money(outlook['projected'])} as the {deadline_label} target, or keep saving {money(outlook['planned'])} a month and allow {completion} months to reach {money(outlook['target'])}.")
            else:
                comparison = None
        if comparison is None:
            next_question = ('What amount could you reduce from a recorded expense? Enter a change to test its effect.'
                             if any(b['kind']=='expense' and Decimal(b['monthly_amount'])>0 for b in items) else
                             'What monthly income can you confirm? Update that figure to calculate a new plan.')
            result['suggestion'] = (f"At the current pace, the model does not reach {money(outlook['target'])} within {horizon} months. "
                                    f"Use {money(outlook['projected'])} as the {outlook['deadline']}-month target, or update the plan. {next_question}")
    if comparison:
        analysis = explain_option(comparison, goal['id'])
        for other in analysis['effects']['goals']:
            if other['id'] != goal['id'] and other['change'] < ZERO:
                result['warnings'].append(f"This would leave {other['name']} with {money(-other['change'])} less at its original deadline.")
        deposits = analysis['funding']['direct_goal_deposit']
        if deposits:
            result['warnings'].append(f"The recorded {money(deposits)} direct deposit to this goal also continues each month.")
        result.update(comparison=comparison, analysis=analysis)
    floor = Decimal((preference or {}).get('cash_floor', '0'))
    if comparison and (preference or {}).get('focus') == 'cash' and result['analysis']['effects']['min_cash_after'] < floor:
        result['warnings'].append(f"This change would fall below your chosen {money(floor)} cash cushion.")
    return result
