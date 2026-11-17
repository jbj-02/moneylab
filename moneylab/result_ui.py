"""Result-first goal experience: one finding, one test, the details on demand."""
from decimal import Decimal
from html import escape

import streamlit as st

from moneylab.action_plan import MISSING_LABELS
from moneylab.blocks import serialize_blocks
from moneylab.engine import validate_money
from moneylab.goal_result import goal_result, money
from moneylab.planning import signature
from moneylab.plan_setup import EXPENSES


def complete_figure(blocks, metadata, field, value):
    """Resolve one named unknown only after an explicit, validated answer."""
    if field not in metadata['unknown']:
        raise ValueError('This figure is already recorded. Edit its entry below.')
    items = serialize_blocks(blocks)
    if field == 'debts':
        if value == 'none' and any(b['kind'] == 'loan' and Decimal(b['balance']) > 0 for b in items):
            raise ValueError('You have a recorded debt. Update it before confirming no debt.')
        if value not in ('none', 'recorded'):
            raise ValueError('Confirm whether you have debt.')
        if value == 'recorded' and not any(b['kind'] == 'loan' for b in items):
            raise ValueError('Add your debt details below, or choose I have no debt.')
    else:
        if value is None:
            raise ValueError('Enter a figure, including $0 if you know it is zero.')
        amount = validate_money(value, 'Missing figure')
        if field in ('income','checking'):
            kind='income' if field=='income' else 'cash'
            numeric='monthly_amount' if field=='income' else 'balance'
            existing=[b for b in items if b['kind']==kind]
            if len(existing)>1:
                if sum(Decimal(b[numeric]) for b in existing)!=amount:
                    raise ValueError('Update the existing entries below to match this total before confirming it.')
                return items,{**metadata,'unknown':[k for k in metadata['unknown'] if k!=field]}
            if existing:
                entry={**existing[0],numeric:str(amount)}
                if field=='income':
                    for key in ('frequency','period_amount','next_date'):
                        entry.pop(key,None)
                return serialize_blocks([entry if b['id']==entry['id'] else b for b in items]),{**metadata,'unknown':[k for k in metadata['unknown'] if k!=field]}
        if field == 'savings':
            assigned = sum(Decimal(b['balance']) for b in items if b['id'] != 'setup_savings' and
                           (b['kind'] in ('goal','hysa') or b['kind']=='account' and b['account_type'] in ('savings','hysa','money_market','cd')))
            if amount < assigned:
                raise ValueError('Total savings cannot be below the amount already assigned to goals.')
            entry = dict(id='setup_savings',kind='hysa',name='Other savings',balance=str(amount-assigned),annual_rate='0',monthly_contribution='0')
        elif field == 'checking':
            entry = dict(id='setup_checking',kind='cash',name='Checking / cash',balance=str(amount))
        elif field == 'income' or field in EXPENSES:
            entry = dict(id=f'setup_{field}',kind='income' if field == 'income' else 'expense',
                         name='Take-home pay' if field == 'income' else EXPENSES[field],monthly_amount=str(amount))
        else:
            raise ValueError('Choose a supported missing figure.')
        # An imported unknown may coexist with an already recorded amount.
        # Confirm or update it once rather than adding a duplicate income/cash.
        if field in ('income','checking'):
            matches=[b for b in items if b['kind']==entry['kind']]
        else:
            matches=[b for b in items if b['id']==entry['id']]
        amount_field='balance' if field=='checking' else 'monthly_amount'
        if field in ('income','checking') and len(matches)>1:
            if sum(Decimal(b[amount_field]) for b in matches)!=amount:
                raise ValueError('Update the existing entries below to match this confirmed total, then confirm it here.')
            return items,{**metadata,'unknown':[k for k in metadata['unknown'] if k!=field]}
        if matches:
            if field=='savings':
                entry={**matches[0],'balance':entry['balance']}
            else:
                entry={**matches[0],amount_field:str(amount)}
            if amount_field=='monthly_amount':
                entry.pop('frequency',None)
                entry.pop('period_amount',None)
                entry.pop('next_date',None)
        items = [b for b in items if b['id'] != entry['id']] + [entry]
    return serialize_blocks(items), {**metadata, 'unknown':[k for k in metadata['unknown'] if k != field]}


def render_missing(blocks, metadata, *, first_only=False, prefix='missing'):
    """A concrete question, never a displayed zero standing in for an unknown."""
    from moneylab.plan_ui import prose
    fields = metadata['unknown'][:1] if first_only else metadata['unknown']
    for field in fields:
        label = MISSING_LABELS.get(field, field)
        with st.container(border=True):
            st.markdown(f'**Add {label} to check this answer**')
            if field == 'debts':
                choice = st.radio('Do you have loans or credit card debt?', ['Not answered', 'I have no debt', 'I have recorded all my debts'], key=f'{prefix}_debts')
                st.page_link('pages/1_My_Money.py', label='Edit figures to add or update a debt')
                value = {'I have no debt':'none','I have recorded all my debts':'recorded'}.get(choice)
            else:
                unit = 'today' if field in ('savings','checking') else 'per month'
                value = st.number_input(f'{label.capitalize()} {unit} ($)', min_value=0.0, max_value=1e12, value=None,
                                        format='%.2f', key=f'{prefix}_{field}')
                prose('Leave blank if you do not know yet. Enter $0 only when you have confirmed there is nothing to record.')
            if st.button('Use this figure' if field != 'debts' else 'Confirm debt details', key=f'{prefix}_save_{field}'):
                try:
                    updated, details = complete_figure(blocks, metadata, field, value)
                    st.session_state.ml_blocks = updated
                    st.session_state.ml_plan_metadata = details
                    st.session_state.pop('ml_reviewed_signature', None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def render_goal_result(blocks, metadata, reviewed):
    from moneylab.plan_ui import prose, _caption, _remember, _chart
    from moneylab.action_ui import funding_text, model_date, render_priorities
    answer = goal_result(blocks, missing=metadata['unknown'], preference=metadata.get('action_preference'))
    if answer is None:
        return None
    label = 'YOUR GOAL · PRELIMINARY' if not reviewed else 'YOUR GOAL'
    st.markdown(f'<section class="ml-result" aria-label="Your goal result"><div class="ml-eyebrow">{label}</div>'
                f'<h2>{escape(answer["finding"])}</h2></section>', unsafe_allow_html=True)
    if answer['kind'] == 'missing':
        _caption('This is a partial estimate. Missing amounts have not been confirmed as $0, so MoneyLab will not suggest committing extra money yet.')
        render_missing(blocks, metadata, first_only=True, prefix='result_missing')
    else:
        st.markdown('<div class="ml-eyebrow">ONE CHANGE TO TEST</div>',unsafe_allow_html=True)
        prose(answer['suggestion'])
        if answer['comparison']:
            label = 'Test this plan' if answer['kind'] == 'maintain' else 'Test this change'
            if st.button(label,type='primary',key='result_test'):
                _remember(answer['comparison'])
            _caption('A test changes nothing in your saved plan. You decide whether to apply it.')
        elif any(b['kind']=='expense' and Decimal(b['monthly_amount'])>0 for b in blocks):
            if st.button('Try my own adjustment',type='primary',key='result_custom'):
                st.session_state.ml_selected_action = {'id':f"goal:{answer['goal']['id']}",'kind':'goal','goal_id':answer['goal']['id']}
                st.session_state.setdefault('ml_action_drafts', {})[answer['goal']['id']] = {
                    'source_signature':signature(blocks),'option':'custom'}
                st.switch_page('pages/10_Action_Plan.py')
    for warning in answer['warnings']:
        st.warning(warning.replace('$',r'\$'))
    st.page_link('pages/1_My_Money.py',label='Edit figures')
    with st.expander('How we calculated this'):
        outlook = answer['outlook']
        if answer['missing']:
            _caption('A complete projection needs the missing figures. No blank has been confirmed as $0.')
        else:
            a,b,c=st.columns(3)
            a.metric('Monthly take-home',money(answer['baseline']['summary']['monthly_income']))
            b.metric('After bills, debt & saving',money(answer['flow']))
            c.metric('Cash available today',money(answer['baseline']['monthly_records'][0]['cash_savings']))
            prose(f"Start with {money(outlook['starting'])} saved for this goal. "
                  f"The model projects {money(outlook['projected'])} in {outlook['deadline']} months "
                  'using the recorded saving pace, available money and entered interest rate.')
        if answer['analysis']:
            funding_text(answer['analysis'])
            for text in answer['analysis']['tradeoffs']:
                prose(text)
        if answer['kind'] == 'expense':
            _caption('Automatic expense tests use only named dining, takeaways, coffee, entertainment or subscription entries. '
                     'The tested cut is at most half that entry and $150/month. This is an option to judge, not an assumption that a cut is practical for you.')
        _caption(f"Plan date: {model_date(metadata):%b %d, %Y}. Monthly averages repeat; daily bill timing and unexpected costs are excluded. "
                 'Savings use available money after bills and debt, in the order of recorded accounts. Goal money is not counted as checking.')
        if not answer['missing']:
            _chart(answer['baseline'])
    with st.expander('Other changes to explore'):
        render_priorities(blocks, metadata)
        if st.button('Choose a different goal adjustment',key='result_more_options'):
            st.session_state.ml_selected_action = {'id':f"goal:{answer['goal']['id']}",'kind':'goal','goal_id':answer['goal']['id']}
            st.switch_page('pages/10_Action_Plan.py')
        st.page_link('pages/3_Explore.py',label='Test a purchase, move or other decision')
    return answer


def render_comparison_summary(comparison):
    """Two honest columns: own deadline, own target, and first-month remainder."""
    from moneylab.plan_ui import prose, _caption
    goal_id = comparison.get('focus_goal_id')
    before, after = comparison['baseline'], comparison['alternative']
    if goal_id:
        old = next(g for g in before['goals'] if g['id'] == goal_id)
        new = next(g for g in after['goals'] if g['id'] == goal_id)
        difference = new['projected_at_deadline'] - old['projected_at_deadline']
        if old['target_months'] == new['target_months']:
            prose(f"**The difference:** {money(abs(difference))} {'more' if difference >= 0 else 'less'} toward {old['name']} "
                  f"at month {old['target_months']}.")
        else:
            prose(f"**The difference:** allow {new['target_months']} months instead of {old['target_months']}. "
                  'This changes the deadline, not the monthly amount saved.')
    columns = st.columns(2)
    for col, label, projection in zip(columns, ('Current plan','With this change'), (before,after)):
        with col, st.container(border=True):
            st.subheader(label)
            if goal_id:
                goal = next(g for g in projection['goals'] if g['id'] == goal_id)
                st.metric(f"{goal['name']} in {goal['target_months']} months", money(goal['projected_at_deadline']))
                gap = max(goal['target'] - goal['projected_at_deadline'], Decimal(0))
                _caption(f"{money(gap)} short of {money(goal['target'])}" if gap else f"Meets the {money(goal['target'])} target")
                entry = next(b for b in (comparison['source_blocks'] if label == 'Current plan' else comparison['blocks']) if b['id'] == goal_id)
                _caption(f"{money(Decimal(entry['monthly_contribution']))} set aside each month")
            st.metric('Money left each month', money(projection['monthly_records'][1]['net_cash_flow']))
            _caption('First month, after recorded bills, debt payments and savings.')
            if not goal_id:
                st.metric('Checking / cash now',money(projection['monthly_records'][0]['cash_savings']))
    if not goal_id:
        old_goals={g['id']:g for g in before['goals']}
        for goal in after['goals']:
            old=old_goals.get(goal['id'])
            if old:
                prose(f"**{goal['name']} in {goal['target_months']} months:** {money(old['projected_at_deadline'])} → {money(goal['projected_at_deadline'])} "
                      f"toward a {money(goal['target'])} target.")
    if goal_id:
        from moneylab.action_plan import explain_option
        analysis = explain_option(comparison, goal_id)
        for other in analysis['effects']['goals']:
            if other['id'] != goal_id and other['change'] < 0:
                st.warning(f"This change leaves {other['name']} with {money(-other['change'])} less at its original deadline.".replace('$',r'\$'))
