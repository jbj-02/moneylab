"""The short tasks use one form and preserve the plan until explicit approval."""
from pathlib import Path
from copy import deepcopy
from streamlit.testing.v1 import AppTest

from test_action_ui import start, click
from test_streamlined import profile

ROOT=Path(__file__).resolve().parents[1]


def purchase(blocks=None):
    app=start(blocks or profile())
    return app.switch_page('pages/3_Explore.py').run()


def fill(app,key,value):
    next(n for n in app.number_input if n.key==key).set_value(value)


def test_purchase_is_one_price_and_one_submit_for_a_returning_user():
    app=purchase();original=deepcopy(app.session_state['ml_blocks'])
    assert len(app.number_input)==1 and not app.radio
    fill(app,'task_purchase_price',200.0)
    app=click(app,'See impact')
    assert app.session_state['ml_blocks']==original
    assert next(m.value for m in app.metric if m.label=='Cash after purchase')=='$2,300.00'
    assert not any(b.label=='Confirm my figures' for b in app.button)
    assert next(b for b in app.button if b.key=='plan_apply').disabled
    app=click(app,'Back')
    assert next(n.value for n in app.number_input if n.key=='task_purchase_price')==200


def test_purchase_application_is_explicit_and_source_bound():
    app=purchase();fill(app,'task_purchase_price',200.0);app=click(app,'See impact')
    app=next(c for c in app.checkbox if c.key=='plan_apply_confirm').check().run()
    app=click(app,'Apply these changes to my plan')
    assert next(b for b in app.session_state['ml_blocks'] if b['id']=='cash')['balance']=='2300.00'
    assert 'accepted_plan' in app.session_state['ml_plan_metadata']


def test_purchase_rejects_applying_a_result_after_figures_change():
    app=purchase();fill(app,'task_purchase_price',200.0);app=click(app,'See impact')
    changed=profile();changed[0]['monthly_amount']='3000'
    app.session_state['ml_blocks']=changed;app=app.run()
    assert any('Your figures changed' in w.value for w in app.warning)
    assert not any(b.key=='plan_apply' for b in app.button)


def test_guest_purchase_needs_only_price_and_cash_and_never_creates_a_plan():
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run().switch_page('pages/3_Explore.py').run()
    assert len(app.number_input)==2 and not app.radio and not app.selectbox
    fill(app,'task_purchase_price',200.0);fill(app,'task_purchase_cash',2500.0)
    app=click(app,'See impact')
    assert app.session_state['ml_blocks']==[]
    assert not any(b.key=='plan_apply' for b in app.button)
    assert any('Income, regular commitments' in i.value for i in app.info)


def test_a_temporary_missing_cash_figure_is_used_without_saving_it():
    blocks=[b for b in profile() if b['kind']!='cash']
    app=purchase(blocks)
    fill(app,'task_purchase_price',200.0);fill(app,'task_purchase_cash',2500.0)
    app=click(app,'See impact')
    assert app.session_state['ml_blocks']==blocks
    assert next(m.value for m in app.metric if m.label=='Cash after purchase')=='$2,300.00'
    assert not any(b.key=='plan_apply' for b in app.button)


def test_move_uses_three_new_figures_and_one_modeled_alternative():
    app=start(profile()).switch_page('pages/7_Moving_Out_Alpha.py').run()
    assert len(app.number_input)==3 and not app.radio
    original=deepcopy(app.session_state['ml_blocks'])
    for key,value in [('rent',1700.0),('extra',150.0),('upfront',1200.0)]:
        fill(app,'task_move_'+key,value)
    app=click(app,'See impact')
    assert app.session_state['ml_blocks']==original
    assert next(m.value for m in app.metric if m.label=='Upfront costs')=='$1,200.00'
    assert next(m.value for m in app.metric if m.label=='Money left in first month')=='$250.00 short'
    app=click(app,'Test this alternative')
    assert app.session_state['task_move_draft']['rent']==1350
    assert next(m.value for m in app.metric if m.label=='Money left in first month')=='$0.00'
    app=click(app,'Back')
    assert next(n.value for n in app.number_input if n.key=='task_move_rent')==1350
    assert next(n.value for n in app.number_input if n.key=='task_move_upfront')==1200
    assert app.session_state['ml_blocks']==original


def test_a_tested_move_only_updates_the_plan_after_the_apply_checkbox():
    app=start(profile()).switch_page('pages/7_Moving_Out_Alpha.py').run()
    for key,value in [('rent',1350.0),('extra',150.0),('upfront',1200.0)]:
        fill(app,'task_move_'+key,value)
    app=click(app,'See impact')
    assert next(b for b in app.button if b.key=='plan_apply').disabled
    app=next(c for c in app.checkbox if c.key=='plan_apply_confirm').check().run()
    app=click(app,'Apply these changes to my plan')
    entries={b['id']:b for b in app.session_state['ml_blocks']}
    assert entries['rent']['monthly_amount']=='1350.00'
    assert entries['cash']['balance']=='1300.00'
    assert entries['goal']['monthly_contribution']=='100.00'


def test_goal_has_one_details_area_and_keeps_the_test_on_my_plan():
    app=start(profile());original=deepcopy(app.session_state['ml_blocks'])
    assert [e.label for e in app.main.expander]==['See details']
    assert any(s.value=='Current plan' for s in app.subheader)
    assert any(s.value=='Test scenario' for s in app.subheader)
    summaries=[m.value for m in app.markdown if 'ml-compare-summary' in m.value]
    assert len(summaries)==2 and '$4,220.00' in summaries[0] and '$5,000.00' in summaries[1]
    assert app.session_state['ml_blocks']==original
    assert any('$780.00 short' in m.value for m in app.markdown)


def test_move_with_missing_income_does_not_display_a_zero_income_projection():
    app=start(profile()[1:]);app.session_state['ml_plan_metadata']={'priority':'Build an emergency fund','unknown':['income']}
    app=app.switch_page('pages/7_Moving_Out_Alpha.py').run()
    for key,value in [('rent',1700.0),('extra',150.0),('upfront',1200.0)]:
        fill(app,'task_move_'+key,value)
    app=click(app,'See impact')
    assert next(m.value for m in app.metric if m.label=='Money left in first month')=='Not checked'
    assert not any(b.label=='Test this alternative' for b in app.button)
    assert next(b for b in app.button if b.key=='plan_apply').disabled


def test_purchase_keeps_a_recorded_cash_cushion_warning_next_to_the_result():
    app=purchase()
    app.session_state['ml_plan_metadata']={**app.session_state['ml_plan_metadata'],
        'action_preference':{'focus':'cash','cash_floor':'2000.00','goal_id':None}}
    app=app.run();fill(app,'task_purchase_price',700.0);app=click(app,'See impact')
    assert any('cash cushion' in w.value for w in app.warning)
    assert not any('cash cushion' in w.value for e in app.expander for w in e.warning)


def test_purchase_after_an_inline_goal_test_can_return_to_my_plan():
    app=start(profile());original=deepcopy(app.session_state['ml_blocks'])
    app=app.switch_page('pages/3_Explore.py').run()
    fill(app,'task_purchase_price',200.0);app=click(app,'See impact')
    app=app.switch_page('pages/0_Home.py').run()
    assert not app.exception
    assert not app.session_state['ml_preview_inline']
    assert app.session_state['ml_blocks']==original
    assert any('$780.00 short' in m.value for m in app.markdown)


def test_move_result_recalculates_monthly_summary_when_rent_is_committed():
    blocks=[
        dict(id='pay',kind='income',name='Take-home pay',monthly_amount='3500'),
        dict(id='housing',kind='expense',name='Current housing',monthly_amount='0'),
        dict(id='other',kind='expense',name='Other monthly commitments',monthly_amount='1900'),
        dict(id='cash',kind='cash',name='Checking',balance='2200'),
    ]
    app=start(blocks).switch_page('pages/7_Moving_Out_Alpha.py').run()
    original=deepcopy(app.session_state['ml_blocks'])
    for key,value in [('rent',1500.0),('extra',150.0),('upfront',3000.0)]:
        fill(app,'task_move_'+key,value)
    app=click(app,'See impact')
    metrics={m.label:m.value for m in app.metric}
    assert metrics['Money left in first month']=='$50.00 short'
    assert metrics['Monthly take-home pay']=='$3,500.00'
    assert metrics['Projected monthly expenses and commitments']=='$3,550.00'
    assert metrics['Upfront costs']=='$3,000.00'
    assert app.session_state['task_move_result']['facts']['gap']==800
    rent=next(n for n in app.number_input if n.label=='Proposed rent ($/month)')
    app=rent.set_value(1300.0).run()
    metrics={m.label:m.value for m in app.metric}
    assert metrics['Money left in first month']=='$150.00 left'
    assert metrics['Projected monthly expenses and commitments']=='$3,350.00'
    assert app.session_state['task_move_result']['facts']['gap']==800
    assert app.session_state['task_move_draft']['rent']==1300
    assert app.session_state['ml_blocks']==original
