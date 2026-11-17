"""One temporary purchase test, without making a user build a whole profile."""
import streamlit as st

from moneylab.cadence import FREQUENCIES
from moneylab.decisions import decision_check


def render_purchase_start(description=None):
    from moneylab.plan_ui import prose, _caption
    from moneylab.ui_app import dollars
    st.title('Test a purchase')
    prose('Start with the cost and the money it would use. These figures stay temporary; they do not create or change your plan.')
    if description:
        description()
    saved = st.session_state.get('dc_guest_draft', {})
    for key, value in saved.items():
        if key not in st.session_state:
            st.session_state[key] = value
    with st.form('purchase_start_form'):
        kind = st.radio('Type of cost', ['one_time','recurring'], format_func=lambda k:'One-time purchase' if k == 'one_time' else 'Recurring cost', key='dc_guest_cost_kind')
        def amount(label,key):
            return st.number_input(label,min_value=0.0,max_value=1e8,value=None,format='%.2f',key=f'dc_guest_{key}')
        cost = amount('Purchase or recurring cost ($)','cost')
        cadence = st.selectbox('Frequency for a recurring cost',list(FREQUENCIES),index=list(FREQUENCIES).index(st.session_state.get('dc_guest_frequency','monthly')),format_func=lambda k:FREQUENCIES[k][0],key='dc_guest_frequency')
        _caption('Frequency is ignored for a one-time purchase.')
        income = amount('Monthly take-home pay ($)','income')
        spending = amount('Monthly bills, debt payments and planned savings ($)','spending')
        cash = amount('Checking / cash available for this purchase ($)','checking')
        _caption('Include all recurring costs and savings in the monthly total. Exclude earmarked savings from available checking. Blank means unknown; enter $0 only if confirmed.')
        run = st.form_submit_button('Test this purchase',type='primary')
    if run:
        draft = dict(kind=kind,cost=cost,cadence=cadence,income=income,spending=spending,cash=cash)
        st.session_state.dc_guest_draft = {key:st.session_state[key] for key in ('dc_guest_cost_kind','dc_guest_cost','dc_guest_income','dc_guest_spending','dc_guest_checking','dc_guest_frequency')}
        if any(value is None for value in (cost,income,spending,cash)):
            st.error('Enter each figure to compare. A blank amount is not a confirmed $0.')
        elif cost <= 0:
            st.error('Enter a purchase cost greater than $0.')
        else:
            blocks = [dict(id='pay',kind='income',name='Take-home pay',monthly_amount=str(income)),
                      dict(id='costs',kind='expense',name='Recorded commitments',monthly_amount=str(spending)),
                      dict(id='cash',kind='cash',name='Available checking',balance=str(cash))]
            report = decision_check(blocks,cost=cost,cost_type='one_time' if kind == 'one_time' else 'recurring',frequency=cadence,reviewed=False)
            st.session_state.purchase_start_result = (draft,report)
            st.session_state.dc_guest_compared = True
    result = st.session_state.get('purchase_start_result')
    if run and (any(value is None for value in (cost,income,spending,cash)) or cost <= 0):
        st.session_state.pop('purchase_start_result', None)
        result = None
    if result:
        previous, report = result
        st.subheader('What this purchase would change')
        if not report['comparable']:
            st.warning(report['reason'])
        else:
            before_flow=report['baseline']['monthly_records'][1]['net_cash_flow']
            after_flow=report['alternative']['monthly_records'][1]['net_cash_flow']
            if previous['kind'] == 'one_time':
                prose(f"This {dollars(report['cost'])} purchase would leave {dollars(report['remaining_checking_now'])} in the checking amount you entered.")
            else:
                prose(f"This recurring cost would leave {dollars(after_flow)} each month after the commitments entered.")
            a,b = st.columns(2)
            for col,label,flow in ((a,'Current plan',before_flow),(b,'With this purchase',after_flow)):
                with col,st.container(border=True):
                    st.subheader(label)
                    st.metric('Money left each month',dollars(flow))
                    st.metric('Checking now',dollars(previous['cash'] if label == 'Current plan' else report['remaining_checking_now']))
            if report['needs_attention']:
                st.warning('This purchase introduces or worsens a projected cash problem. Review the amounts before committing.')
            with st.expander('How we calculated this'):
                for note in report['cautions']:
                    prose(note)
                _caption('This snapshot has no separate goal, debt or account model. The monthly total includes your recorded commitments. It cannot verify affordability or exact bill dates.')
        _caption('Result uses the last submitted figures. Editing the form does not recalculate until you select Test this purchase.')
    st.page_link('pages/0_Home.py',label='Back to My Plan')
