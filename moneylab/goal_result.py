"""A short goal answer and one verified experiment, independent of Streamlit.

Suggestions are detached engine simulations. Expense suggestions are restricted
to recorded discretionary categories, at most half the entry and $150/month.
Those bounds are product heuristics, not claims about a person's ability to cut.
"""
from decimal import Decimal, ROUND_FLOOR
import re

from moneylab.action_plan import MISSING_LABELS, explain_option, first_reached
from moneylab.blocks import project_blocks, serialize_blocks
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
    result = dict(goal=goal, outlook=outlook, finding=finding, kind='missing' if missing else 'unreachable',
                  suggestion='', comparison=None, analysis=None, warnings=[], baseline=baseline, flow=flow,
                  missing=list(missing), expense_id=None, cut=ZERO)
    gap = next((r for r in baseline['monthly_records'][1:] if r['unfunded_shortfall'] > ZERO), None)
    if gap and not set(missing).intersection({'income','checking'}):
        result['warnings'].append(f"Recorded bills run short by {money(gap['unfunded_shortfall'])} in month {gap['month']}. Savings slow or stop when money is unavailable.")
    if any(r['negative_amortization'] for r in baseline['monthly_records'][1:]):
        result['warnings'].append('A recorded loan grows because its payment does not cover interest. Review that payment before committing more to savings.')
    if missing:
        return result
    comparison = None
    if outlook['on_track']:
        # A smaller request is a genuine, modeled change when the current pace exceeds what's needed.
        requested = outlook['required'] if outlook['required'] is not None else outlook['planned']
        comparison = goal_alternative(items, goal['id'], requested)
        if requested < outlook['planned'] and _hits(comparison, goal['id']):
            result.update(kind='release', suggestion=f"Setting aside {money(requested)} a month instead of {money(outlook['planned'])} would still meet the goal, leaving more for the rest of your plan.")
        else:
            comparison = goal_alternative(items, goal['id'], outlook['planned'])
            result.update(kind='maintain', suggestion=f"Keep setting aside {money(outlook['planned'])} a month. Test this pace to see the goal and the money left together.")
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
                          suggestion=f"Cutting {expense['name']} by {money(cut)} a month and putting that money{extra_room} toward the goal would close the gap.")
    if comparison is None:
        completion = first_reached(baseline, goal)
        if completion is not None and completion > outlook['deadline']:
            comparison = goal_alternative(items, goal['id'], outlook['planned'], deadline=completion)
            if _hits(comparison, goal['id']):
                result.update(kind='later', suggestion=f"The recorded plan cannot meet that deadline. Keeping {money(outlook['planned'])} a month and allowing {completion} months would reach the goal.")
            else:
                comparison = None
        if comparison is None:
            next_question = ('What amount could you reduce from a recorded expense? Enter a change to test its effect.'
                             if any(b['kind']=='expense' and Decimal(b['monthly_amount'])>0 for b in items) else
                             'What monthly income can you confirm? Update that figure to calculate a new plan.')
            result['suggestion'] = f"This plan does not reach the target within {horizon} months. {next_question}"
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
