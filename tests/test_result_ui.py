"""Real integration of the plain-language result, unknowns and comparisons."""
from copy import deepcopy

from moneylab.blocks import serialize_blocks
from moneylab.planning import goal_alternative
from test_action_ui import start, click
from test_goal_result import rescue_profile


def test_one_modelled_test_has_a_prefilled_comparison_and_no_implicit_application():
    original=rescue_profile()
    app=start(original)
    assert any('$780.00 short' in m.value for m in app.markdown)
    assert any('Dining out & takeaways by \\$130.00' in m.value for m in app.markdown)
    app=click(app,'Test this change')
    assert app.session_state['ml_blocks']==original
    assert app.session_state['ml_plan_preview']['blocks'][2]['monthly_amount']=='170.00'
    assert [m.value for m in app.metric if m.label=='Emergency fund in 6 months']==['$4,220.00','$5,000.00']
    assert [m.value for m in app.metric if m.label=='Money left each month']==['$0.00','$0.00']
    assert next(b for b in app.button if b.key=='plan_apply').disabled
    assert any(e.label=='How we calculated this' for e in app.expander)


def test_a_missing_figure_cannot_be_silently_confirmed_as_zero():
    app=start(rescue_profile()[1:],reviewed=False)
    app.session_state['ml_plan_metadata']={'priority':'Build an emergency fund','unknown':['income','food']}
    app=app.run()
    assert not any(b.label=='Test this change' for b in app.button)
    number=next(n for n in app.number_input if n.key=='result_missing_income')
    assert number.value is None
    app=click(app,'Use this figure')
    assert app.error and app.session_state['ml_plan_metadata']['unknown']==['income','food']
    next(n for n in app.number_input if n.key=='result_missing_income').set_value(0.0)
    app=click(app,'Use this figure')
    assert app.session_state['ml_plan_metadata']['unknown']==['food']
    assert next(b for b in app.session_state['ml_blocks'] if b['kind']=='income')['monthly_amount']=='0.00'
    assert not any(b.label=='Confirm my figures' for b in app.button)


def test_custom_comparison_shows_other_goal_loss_outside_calculations():
    blocks=rescue_profile();blocks[0]['monthly_amount']='2800'
    blocks[4].update(balance='0',target='1500',target_months=6,monthly_contribution='100')
    blocks.append(dict(blocks[4],id='car',name='Car fund',monthly_contribution='400'))
    app=start(blocks)
    app.session_state['ml_plan_preview']=goal_alternative(blocks,'goal','500')
    app=app.switch_page('pages/9_Compare_Plan.py').run()
    assert not app.exception
    assert any('Car fund' in w.value and 'less' in w.value for w in app.warning)
    assert not any('Car fund' in w.value for e in app.expander for w in e.warning)


def test_declining_a_test_leaves_all_original_expenses_and_saving_intact():
    blocks=rescue_profile();app=click(start(blocks),'Test this change')
    app=click(app,'Discard alternative')
    assert app.session_state['ml_blocks']==blocks
    assert app.session_state['ml_plan_preview'] is None
