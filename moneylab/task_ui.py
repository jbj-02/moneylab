"""Three short tasks: one answer, one primary action, one place for details."""
from datetime import date
from decimal import Decimal
from html import escape

import streamlit as st

from moneylab.action_plan import MISSING_LABELS
from moneylab.blocks import profile_to_json, serialize_blocks
from moneylab.goal_result import goal_result, money
from moneylab.moving_profile import housing_candidates
from moneylab.planning import apply_preview, signature
from moneylab.progress import accept_comparison, tracking_signature
from moneylab.streamlined import cash_total, goal_effects, moving_impact, purchase_impact


def _h():
    from moneylab import plan_ui
    return plan_ui


def _back(label, callback, key):
    if st.button(label,key=key):
        callback()
        st.rerun()


def _missing(metadata, *, cash_only=False):
    missing=metadata.get('unknown',[])
    if missing:
        names=', '.join(MISSING_LABELS.get(k,k) for k in missing)
        st.warning(('Cash today can be checked, but the monthly and goal impact needs ' if cash_only else
                    'The monthly result needs ') + names + '. These amounts are unknown, not $0.')
    return missing


def _reserve_warning(comparison, metadata):
    preference=metadata.get('action_preference',{})
    if comparison and preference.get('focus')=='cash':
        floor=Decimal(preference['cash_floor'])
        lowest=min(r['cash_position'] for r in comparison['alternative']['monthly_records'])
        if lowest<floor:
            st.warning(f"This test falls below your chosen {money(floor)} cash cushion; projected cash reaches {money(lowest)}.".replace('$',r'\$'))


def apply_controls(blocks, comparison, *, missing=(), primary=True, discard=True):
    """One explicit approval; never a separate confirmation just to run a test."""
    h=_h()
    try:
        apply_preview(blocks,comparison)
        if comparison.get('tracking_signature') and comparison['tracking_signature']!=tracking_signature(h._metadata().get('accepted_plan')):
            raise ValueError('Your selected schedule changed. Compare progress again.')
    except ValueError as exc:
        st.warning(str(exc))
        return
    choosing=comparison['source_signature']==comparison['candidate_signature'] and not comparison.get('progress')
    approved=st.checkbox('Use this plan as my selected schedule' if choosing else
                         'I want to replace my plan with these exact changes',key='plan_apply_confirm')
    if st.button('Choose this plan' if choosing else 'Apply these changes to my plan',
                 type='primary' if primary else 'secondary',disabled=not approved or bool(missing),key='plan_apply'):
        from moneylab.action_ui import model_date
        anchor=date.fromisoformat(comparison['progress']['as_of']) if comparison.get('progress') else model_date(h._metadata())
        try:
            updated,metadata=accept_comparison(blocks,comparison,h._metadata(),on_date=anchor)
            st.session_state.ml_blocks=updated
            st.session_state.ml_plan_metadata=metadata
            st.session_state.ml_reviewed_signature=profile_to_json(updated)
            st.session_state.ml_plan_preview=None
            st.session_state.ml_preview_inline=False
            st.session_state.task_purchase_editing=True
            st.session_state.task_move_editing=True
            st.session_state.plan_applied=True
            st.switch_page('pages/0_Home.py')
        except ValueError as exc:
            st.error(str(exc))
    if discard and st.button('Discard alternative',key='plan_discard'):
        st.session_state.ml_plan_preview=None
        st.session_state.ml_preview_inline=False
        st.rerun()


def render_goal(blocks,metadata,reviewed):
    h=_h()
    from moneylab.result_ui import render_missing
    from moneylab.action_ui import funding_text, render_followthrough, render_priorities
    answer=goal_result(blocks,missing=metadata['unknown'],preference=metadata.get('action_preference'))
    if answer is None:
        return None
    finding=answer['finding']
    record=metadata.get('accepted_plan')
    if record and record['last_as_of']!=date.today().isoformat():
        finding=f"From your {record['last_as_of']} figures: {finding[0].lower()+finding[1:]}"
    st.markdown(f'<section class="ml-result" aria-label="Your goal result"><h2>{escape(finding)}</h2></section>',unsafe_allow_html=True)
    if record:
        for goal in (b for b in blocks if b['kind']=='goal'):
            due=record.get('due_dates',{}).get(goal['id'])
            if due and date.fromisoformat(due)<date.today() and Decimal(goal['balance'])<Decimal(goal['target']):
                st.warning(f"The chosen deadline for {goal['name']} has passed. Record a current balance under See details before treating the saved projection as a plan from today.")
    if answer['kind']=='missing':
        h.prose('This figure is needed to check the money available for your goal. Blank does not mean $0.')
        render_missing(blocks,metadata,first_only=True,prefix='result_missing')
    else:
        h.prose(answer['suggestion'])
        if answer['comparison']:
            if st.button('Test this plan' if answer['kind']=='maintain' else 'Test this change',type='primary',key='result_test'):
                h._remember(answer['comparison'],inline=True)
        elif st.button('Try my own adjustment',type='primary',key='result_custom'):
            st.session_state.ml_selected_action={'id':f"goal:{answer['goal']['id']}",'kind':'goal','goal_id':answer['goal']['id']}
            st.switch_page('pages/10_Action_Plan.py')
    for warning in answer['warnings']:
        st.warning(warning.replace('$',r'\$'))
    pending=st.session_state.get('ml_plan_preview')
    if pending and pending['source_signature']!=signature(blocks):
        st.warning('Your figures changed. Test again before applying the earlier alternative.')
    st.page_link('pages/1_My_Money.py',label='Edit figures')
    with st.expander('See details'):
        if not metadata['unknown']:
            a,b,c=st.columns(3)
            a.metric('Monthly take-home',money(answer['baseline']['summary']['monthly_income']))
            b.metric('After bills, debt & saving',money(answer['flow']))
            c.metric('Cash available today',money(cash_total(blocks)))
        if answer['analysis']:
            funding_text(answer['analysis'])
            for text in answer['analysis']['tradeoffs']:
                h.prose(text)
        if answer['kind']=='expense':
            st.caption('Automatic expense tests use named discretionary entries only, capped at half the entry and $150/month. Judge whether the cut is practical for you.')
        st.caption('Monthly averages repeat at entered rates. Daily bill timing and unexpected costs are excluded. Other account transfers and debts remain in the model.')
        if not metadata['unknown']:
            h._chart(answer['baseline'])
        h._pending(blocks)
        render_priorities(blocks,metadata)
        for goal in (b for b in blocks if b['kind']=='goal'):
            render_followthrough(blocks,goal,metadata)
        if st.button('Other goal adjustments',key='result_more_options'):
            st.session_state.ml_selected_action={'id':f"goal:{answer['goal']['id']}",'kind':'goal','goal_id':answer['goal']['id']}
            st.switch_page('pages/10_Action_Plan.py')
    return answer


def render_goal_test(blocks):
    h=_h()
    comparison=st.session_state.ml_plan_preview
    st.title('Current plan vs alternative')
    def back():
        st.session_state.ml_preview_inline=False
    with st.container(horizontal=True,vertical_alignment='center'):
        _back('Back',back,'goal_test_back')
        st.page_link('pages/1_My_Money.py',label='Edit figures')
    try:
        apply_preview(blocks,comparison)
    except ValueError as exc:
        st.warning(str(exc))
        if st.button('Discard alternative'):
            st.session_state.ml_plan_preview=None
            st.session_state.ml_preview_inline=False
            st.rerun()
        return
    import pandas as pd
    focus=comparison.get('focus_goal_id')
    old=next(g for g in comparison['baseline']['goals'] if g['id']==focus)
    new=next(g for g in comparison['alternative']['goals'] if g['id']==focus)
    old_gap=max(old['target']-old['projected_at_deadline'],Decimal(0));new_gap=max(new['target']-new['projected_at_deadline'],Decimal(0))
    if old['target_months']!=new['target_months']:
        h.prose(f"Allow {new['target_months']} months instead of {old['target_months']} for {old['name']}.")
    elif old_gap and not new_gap:
        h.prose(f"This change closes the **{money(old_gap)} gap** for {old['name']} in {new['target_months']} months.")
    else:
        h.prose(f"Compare {old['name']} and the money left for the rest of your plan.")
    left=f"Current · month {old['target_months']}";right=f"Test · month {new['target_months']}"
    st.table(pd.DataFrame([
        {'Measure':'Goal balance',left:money(old['projected_at_deadline']),right:money(new['projected_at_deadline'])},
        {'Measure':f"Gap to {money(new['target'])}",left:money(old_gap),right:money(new_gap)},
        {'Measure':'Money left / month',left:money(comparison['baseline']['monthly_records'][1]['net_cash_flow']),right:money(comparison['alternative']['monthly_records'][1]['net_cash_flow'])},
    ]).set_index('Measure'))
    for goal in goal_effects(comparison):
        if goal['name']!=old['name'] and goal['after']<goal['before']:
            st.warning(f"{goal['name']} has {money(goal['before']-goal['after'])} less at its deadline.".replace('$',r'\$'))
    missing=_missing(h._metadata())
    with st.expander('See details'):
        from moneylab.action_plan import explain_option
        from moneylab.action_ui import funding_text, render_stress_test
        analysis=explain_option(comparison,comparison.get('focus_goal_id'))
        _edits(comparison)
        funding_text(analysis)
        for text in analysis['tradeoffs']:
            h.prose(text)
        h._chart(comparison['baseline'],comparison['alternative'])
        render_stress_test(comparison)
    apply_controls(blocks,comparison,missing=missing)


def _result_controls(kind):
    def edit():
        st.session_state[f'task_{kind}_editing']=True
        st.session_state.pop('plan_apply_confirm',None)
    with st.container(horizontal=True,vertical_alignment='center'):
        _back('Back',edit,f'{kind}_back')
        st.page_link('pages/1_My_Money.py',label='Edit figures')


def _edits(comparison):
    h=_h();old={b['id']:b for b in comparison['source_blocks']}
    for block in comparison['blocks']:
        previous=old.get(block['id'])
        if previous is None:
            h.prose(f"Add {block['name']}: {money(Decimal(block.get('monthly_amount',0)))}/month.")
        else:
            for field,label in (('monthly_amount','monthly amount'),('balance','balance'),('monthly_contribution','monthly saving'),('target','target'),('target_months','months to goal')):
                if previous.get(field)!=block.get(field):
                    value=lambda n:str(n) if field=='target_months' else money(Decimal(n))
                    h.prose(f"{block['name']} · {label}: {value(previous[field])} → {value(block[field])}.")


def _goal_lines(comparison):
    h=_h()
    for goal in goal_effects(comparison):
        before=max(goal['target']-goal['before'],Decimal(0));after=max(goal['target']-goal['after'],Decimal(0))
        if before!=after:
            h.prose(f"**{goal['name']} in {goal['deadline']} months:** the goal gap changes from {money(before)} to {money(after)}.")
        elif after:
            h.prose(f"**{goal['name']}:** the existing {money(after)} gap in {goal['deadline']} months stays the same.")


def render_purchase():
    h=_h();blocks,*_=h.context();metadata=h._metadata()
    st.title('Can I buy this?')
    draft=st.session_state.get('task_purchase_draft',{})
    result=st.session_state.get('task_purchase_result')
    if result and not st.session_state.get('task_purchase_editing',False):
        _result_controls('purchase')
        if result['source_signature']!=signature(blocks):
            st.warning('Your figures changed. Go Back and select See impact to update this result.')
            return
        facts=result['facts'];comparison=facts['comparison']
        if facts['gap']:
            st.warning(f"This purchase needs {money(facts['gap'])} more than the {money(facts['cash'])} in available cash.".replace('$',r'\$'))
        else:
            h.prose(f"This {money(facts['price'])} purchase would leave **{money(facts['remaining'])} in cash**.")
            st.metric('Cash after purchase',money(facts['remaining']))
        effective={**metadata,'unknown':[k for k in metadata.get('unknown',[]) if not (result.get('temporary_cash') and k=='checking')]}
        missing=_missing(effective,cash_only=True) if blocks else ['budget']
        if result['full_budget'] and not missing and comparison:
            _reserve_warning(comparison,metadata)
            _goal_lines(comparison)
            st.metric('Money left each month',money(comparison['alternative']['monthly_records'][1]['net_cash_flow']))
            gap=next((r for r in comparison['alternative']['monthly_records'][1:] if r['unfunded_shortfall']>0),None)
            if gap:
                st.warning(f"Cash runs short by {money(gap['unfunded_shortfall'])} in month {gap['month']}.".replace('$',r'\$'))
        elif not blocks:
            st.info('This checks cash today. Income, regular commitments and any goals are needed to check the monthly impact.')
        with st.expander('See details'):
            st.caption('Only recorded checking/cash pays for the purchase. Goal savings and borrowing are excluded.')
            if result['full_budget'] and comparison and not missing:
                _edits(comparison)
                h._chart(comparison['baseline'],comparison['alternative'])
            st.page_link('pages/12_More_Decisions.py',label='Other changes and recurring costs')
        if blocks and comparison and not result.get('temporary_cash'):
            apply_controls(blocks,comparison,missing=missing,discard=False)
        elif blocks and result.get('temporary_cash'):
            st.info('The cash figure is temporary. Record it in Edit figures before applying a change to the saved plan.')
        return
    st.caption('Enter the full price, including taxes and fees.')
    with st.form('task_purchase_form'):
        old=st.session_state.get('ml_profile_cost_draft',{})
        price=st.number_input('Purchase price ($)',min_value=0.0,max_value=1e8,
                              value=draft.get('price',float(old['cost']) if old.get('cost_type')=='one_time' else None),
                              format='%.2f',key='task_purchase_price')
        has_cash=any(b['kind']=='cash' for b in blocks)
        cash=None
        if not has_cash:
            guest=st.session_state.get('dc_guest_draft',{})
            cash=st.number_input('Available checking / cash ($)',min_value=0.0,max_value=1e8,
                                 value=draft.get('cash',guest.get('dc_guest_checking')),format='%.2f',key='task_purchase_cash')
        else:
            h._caption(f'Using {money(cash_total(blocks))} in recorded checking/cash.')
        submitted=st.form_submit_button('See impact',type='primary')
    if submitted:
        st.session_state.task_purchase_draft=dict(price=price,cash=cash)
        if price is None or not has_cash and cash is None:
            st.error('Enter the price and available cash. A blank amount is unknown, not $0.')
        else:
            try:
                source=blocks if has_cash else [*blocks,dict(id='temporary_cash',kind='cash',name='Available cash',balance=str(cash))]
                facts=purchase_impact(source,price)
                st.session_state.task_purchase_result=dict(facts=facts,source_signature=signature(blocks),full_budget=bool(blocks),temporary_cash=not has_cash)
                st.session_state.task_purchase_editing=False
                if blocks:
                    st.session_state.ml_profile_cost_draft={'cost':str(price),'cost_type':'one_time','frequency':'monthly'}
                    st.session_state.dc_profile_compared=True
                else:
                    st.session_state.dc_guest_draft={'dc_guest_cost':price,'dc_guest_checking':cash,'dc_guest_cost_kind':'one_time','dc_guest_frequency':'monthly'}
                    st.session_state.dc_guest_compared=True
                if blocks and has_cash and facts['comparison']:
                    st.session_state.ml_plan_preview=facts['comparison']
                    st.session_state.ml_plan_preview_origin='pages/3_Explore.py'
                st.session_state.pop('plan_apply_confirm',None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.page_link('pages/0_Home.py',label='Back')
    st.page_link('pages/1_My_Money.py',label='Edit figures')
    with st.expander('See details'):
        st.caption('Only checking/cash funds a purchase; no borrowing or goal withdrawals are assumed.')
        st.page_link('pages/12_More_Decisions.py',label='Other changes and recurring costs')


def render_move():
    h=_h();blocks,*_=h.context();metadata=h._metadata()
    st.title('Plan a move')
    draft=st.session_state.get('task_move_draft',{})
    result=st.session_state.get('task_move_result')
    if result and not st.session_state.get('task_move_editing',False):
        _result_controls('move')
        if result['source_signature']!=signature(blocks):
            st.warning('Your figures changed. Go Back and select See impact to update the comparison.')
            return
        facts=result['facts'];comparison=facts['comparison'];recurring=facts['recurring']
        missing=metadata.get('unknown',[]) if blocks else []
        flow=recurring['alternative']['monthly_records'][1]['net_cash_flow']
        monthly=('a monthly shortfall of '+money(-flow)) if flow<0 else (money(flow)+' left each month')
        h.prose(f"Moving needs **{money(facts['upfront'])} upfront**"+('. Add the missing budget figures to check the monthly impact.' if missing else f" and would leave **{monthly}**."))
        with st.container(horizontal=True):
            st.metric('Upfront costs',money(facts['upfront']))
            st.metric('Money left each month','Not checked' if missing else money(flow))
        if comparison:
            h._caption(f"Cash immediately after the move: {money(facts['remaining'])}. Monthly figure is the first month, after the savings transfers the model can fund.")
            if not missing:
                _goal_lines(comparison)
            gap=next((r for r in comparison['alternative']['monthly_records'][1:] if r['unfunded_shortfall']>0),None)
            if gap and flow>=0 and not missing:
                st.warning(f"Cash runs short by {money(gap['unfunded_shortfall'])} in month {gap['month']}.".replace('$',r'\$'))
        else:
            st.warning(f"Upfront costs exceed available cash by {money(facts['gap'])}. The monthly figure excludes that unpaid upfront bill; no funded move is projected.".replace('$',r'\$'))
        missing=_missing(metadata) if blocks else []
        if not missing:
            _reserve_warning(comparison,metadata)
        alternative=facts['alternative'] if not missing else None
        if alternative:
            h.prose(f"**One alternative:** test a rent share of {money(alternative['rent'])}/month"+
                    (f" and upfront costs of {money(alternative['upfront'])}" if alternative['upfront']!=facts['upfront'] else '')+
                    '. This monthly budget preserves the goal outcomes in your current plan.')
            if st.button('Test this alternative',type='primary',key='move_test_alternative'):
                updated={**result['inputs'],'rent':float(alternative['rent']),'upfront':float(alternative['upfront'])}
                new=moving_impact(result['source'],None if updated['housing_id']=='zero' else updated['housing_id'],updated['rent'],updated['extra'],updated['upfront'],reduce_id=updated.get('reduce_id'))
                st.session_state.task_move_result={**result,'facts':new,'inputs':updated}
                st.session_state.task_move_draft=updated
                st.session_state.pop('plan_apply_confirm',None)
                st.rerun()
        elif not comparison:
            st.info('Confirm a lower upfront cost or a source of available cash before this can become a funded move.')
        with st.expander('See details'):
            st.caption('An alternative is a budget to test, not a claimed rental offer. Confirm actual rent and fees before applying it.')
            st.caption('Current expenses and debt continue except the selected housing entry. Other monthly changes are additional to that budget. Upfront costs use checking/cash only; goal balances are excluded.')
            if blocks and not missing:
                if comparison:
                    _edits(comparison)
                h._chart(recurring['baseline'],comparison['alternative'] if comparison else recurring['alternative'])
            else:
                st.caption('Temporary figures include debt payments and other planned saving in the monthly total. Individual loan balances and rates are not modeled in this snapshot.')
            if alternative and blocks and comparison:
                st.caption('Apply the original tested move only if you accept the warnings above.')
                apply_controls(blocks,comparison,missing=missing,primary=False,discard=False)
        if blocks and comparison and not alternative:
            apply_controls(blocks,comparison,missing=missing,discard=False)
        return
    candidates=housing_candidates(blocks) if blocks else []
    clean=[b for b in candidates if not any(w in b['name'].lower() for w in ('living','essentials','bills'))]
    default=clean[0]['id'] if len(clean)==1 else None
    source_signature=signature(blocks)
    with st.form('task_move_form'):
        source=blocks
        if not blocks:
            guest=st.session_state.get('dc_guest_draft',{})
            def field(label,key,seed=None):
                return st.number_input(label,min_value=0.0,max_value=1e8,value=draft.get(key,seed),format='%.2f',key=f'task_move_{key}')
            income=field('Monthly take-home pay ($)','income',guest.get('dc_guest_income'))
            housing=field('Current rent / housing ($/month)','housing')
            other=field('Other monthly commitments ($)','other',guest.get('dc_guest_spending'))
            cash=field('Available checking / cash ($)','cash',guest.get('dc_guest_checking'))
            st.caption('Other commitments include debt payments and planned saving. Exclude current housing. Blank means unknown; enter $0 for a confirmed zero.')
            housing_id='temporary_housing'
        elif default:
            housing_id=draft.get('housing_id',default)
            selected=next((b for b in blocks if b['id']==housing_id),clean[0])
            h._caption(f"Using {selected['name']} at {money(Decimal(selected['monthly_amount']))}/month, plus your recorded income, other costs, debt, savings and cash.")
        else:
            options=[None,'zero',*[b['id'] for b in blocks if b['kind']=='expense']]
            housing_id=st.selectbox('Which current housing cost will this replace?',options,
                                    index=options.index(draft.get('housing_id')) if draft.get('housing_id') in options else 0,
                                    format_func=lambda v:'Choose a recorded housing cost' if v is None else 'No current housing cost (confirmed $0)' if v=='zero' else next(b['name'] for b in blocks if b['id']==v))
        rent=st.number_input('New rent share ($/month)',min_value=0.0,max_value=1e8,value=draft.get('rent'),format='%.2f',key='task_move_rent')
        extra=st.number_input('Other monthly costs: change ($)',min_value=-1e8,max_value=1e8,value=draft.get('extra'),format='%.2f',key='task_move_extra',help='Only the change in utilities, transport and other bills. Enter $0 if those costs stay the same.')
        upfront=st.number_input('Total upfront costs ($)',min_value=0.0,max_value=1e8,value=draft.get('upfront'),format='%.2f',key='task_move_upfront',help='Include deposits, fees, moving, furniture and any prepaid rent. Count each once.')
        reduce_id=None
        if blocks:
            with st.expander('See details'):
                choices=[None,*[b['id'] for b in blocks if b['kind']=='expense' and b['id']!=housing_id]]
                reduce_id=st.selectbox('If monthly costs decrease, which recorded expense changes?',choices,
                                       index=choices.index(draft.get('reduce_id')) if draft.get('reduce_id') in choices else 0,
                                       format_func=lambda v:'Only needed for a negative monthly change' if v is None else next(b['name'] for b in blocks if b['id']==v))
                st.caption('A reduction must fit this recorded expense. Positive changes add a new cost. Only the selected housing expense is replaced.')
        submitted=st.form_submit_button('See impact',type='primary')
    if submitted:
        inputs=dict(housing_id=housing_id,rent=rent,extra=extra,upfront=upfront,reduce_id=reduce_id)
        if not blocks:
            inputs.update(income=income,housing=housing,other=other,cash=cash)
        st.session_state.task_move_draft=inputs
        if any(v is None for v in (rent,extra,upfront)) or not blocks and any(v is None for v in (income,housing,other,cash)):
            st.error('Enter each relevant amount, including $0 when confirmed. Rent and monthly changes determine the budget; cash and upfront costs determine whether the move can be funded.')
        elif blocks and housing_id is None:
            st.error('Choose the current housing cost to replace, or confirm that it is $0.')
        elif blocks and not any(b['kind']=='cash' for b in blocks):
            st.error('Add available checking/cash in Edit figures. It is needed to check the upfront bill.')
        else:
            try:
                if not blocks:
                    source=[dict(id='temporary_pay',kind='income',name='Pay',monthly_amount=str(income)),
                            dict(id='temporary_housing',kind='expense',name='Current housing',monthly_amount=str(housing)),
                            dict(id='temporary_other',kind='expense',name='Other commitments',monthly_amount=str(other)),
                            dict(id='temporary_cash',kind='cash',name='Cash',balance=str(cash))]
                    reduce_id='temporary_other';inputs['reduce_id']=reduce_id
                elif housing_id=='zero':
                    housing_id=None
                facts=moving_impact(source,housing_id,rent,extra,upfront,reduce_id=reduce_id)
                st.session_state.task_move_result=dict(facts=facts,source_signature=source_signature,source=source,inputs=inputs)
                st.session_state.task_move_editing=False
                st.session_state.pop('plan_apply_confirm',None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.page_link('pages/0_Home.py',label='Back')
    st.page_link('pages/1_My_Money.py',label='Edit figures')
