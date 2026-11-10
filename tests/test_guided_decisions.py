"""User journeys: retained drafts, truthful results, and backward navigation."""
from pathlib import Path
from decimal import Decimal
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def start(page):
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    return app.switch_page(page).run()


def click(app, label):
    app = next(b for b in app.button if b.label == label).click().run()
    assert not app.exception, [x.message for x in app.exception]
    return app


def set_number(app, key, value):
    next(n for n in app.number_input if n.key == key).set_value(value)


def test_move_guided_back_preserves_income_rent_and_unknown_savings():
    app = start('pages/7_Moving_Out_Alpha.py')
    assert app.session_state['move_step'] == 0 if 'move_step' in app.session_state else True
    mode = next(r for r in app.radio if r.key == 'move_start_mode')
    app = mode.set_value('Enter my own numbers').run()
    set_number(app, 'move_income', 3500.0)
    set_number(app, 'move_current_housing', 0.0)
    set_number(app, 'move_checking', 6000.0)
    app = click(app, 'Continue')
    assert app.session_state['move_step'] == 1
    set_number(app, 'move_rent', 1500.0)
    app = click(app, 'Back')
    assert next(n for n in app.number_input if n.key == 'move_income').value == 3500
    assert next(n for n in app.number_input if n.key == 'move_savings').value is None
    app = click(app, 'Continue')
    assert next(n for n in app.number_input if n.key == 'move_rent').value == 1500
    app = click(app, 'Continue')
    assert app.session_state['move_step'] == 2
    app = click(app, 'Compare stay vs move')
    assert app.session_state['move_result']['monthly_margin_after'] == Decimal('2000')
    assert app.session_state['ml_blocks'] == []
    assert not any(n.key in ('move_income', 'move_rent') for n in app.number_input)
    app = click(app, 'Edit original assumptions')
    assert not app.metric
    assert next(n for n in app.number_input if n.key == 'move_income').value == 3500


def test_move_guided_validation_and_export_between_steps():
    app = start('pages/7_Moving_Out_Alpha.py')
    app = next(r for r in app.radio if r.key == 'move_start_mode').set_value('Enter my own numbers').run()
    app = click(app, 'Continue')
    assert app.error
    assert app.session_state['move_step'] == 0
    set_number(app, 'move_income', 3200.0)
    set_number(app, 'move_current_housing', 0.0)
    app = click(app, 'Continue')
    app = app.switch_page('pages/6_Settings.py').run()
    assert not app.exception
    from moneylab.workspace_session import capture_decision_drafts
    drafts = capture_decision_drafts(app.session_state._state.filtered_state)
    assert Decimal(drafts[0]['values']['income']) == 3200
    assert drafts[0]['source'] == 'entered'
    app = app.switch_page('pages/7_Moving_Out_Alpha.py').run()
    app = click(app, 'Back')
    assert next(n for n in app.number_input if n.key == 'move_income').value == 3200


def test_guest_purchase_back_recalculate_and_export():
    app = start('pages/3_Explore.py')
    set_number(app, 'dc_guest_income', 3500.0)
    set_number(app, 'dc_guest_spending', 2000.0)
    set_number(app, 'dc_guest_checking', 6000.0)
    app = click(app, 'Continue')
    set_number(app, 'dc_guest_cost', 1200.0)
    app = click(app, 'Continue')
    app = click(app, 'Back')
    assert next(n for n in app.number_input if n.key == 'dc_guest_cost').value == 1200
    app = click(app, 'Continue')
    app = click(app, 'Check with these assumptions')
    assert next(m for m in app.metric if m.label == 'Checking after this one-time cost').value == '$4,800.00'
    assert not app.number_input
    app = click(app, 'Back to edit assumptions')
    assert not app.metric
    app = click(app, 'Continue')
    set_number(app, 'dc_guest_cost', 2200.0)
    app = click(app, 'Continue')
    app = click(app, 'Check with these assumptions')
    assert next(m for m in app.metric if m.label == 'Checking after this one-time cost').value == '$3,800.00'
    app = app.switch_page('pages/6_Settings.py').run()
    assert not app.exception
    from moneylab.workspace_session import capture_decision_drafts
    drafts = capture_decision_drafts(app.session_state._state.filtered_state)
    assert Decimal(drafts[0]['values']['cost']) == 2200
    assert app.session_state['ml_blocks'] == []


def test_manual_recurring_frequency_survives_review_and_back():
    app = start('pages/3_Explore.py')
    set_number(app, 'dc_guest_income', 3000.0)
    set_number(app, 'dc_guest_spending', 1000.0)
    set_number(app, 'dc_guest_checking', 1000.0)
    app = click(app, 'Continue')
    next(r for r in app.radio if r.key == 'dc_guest_cost_kind').set_value('recurring')
    next(r for r in app.selectbox if r.key == 'dc_guest_frequency').set_value('weekly')
    set_number(app, 'dc_guest_cost', 30.0)
    app = click(app, 'Continue')
    app = click(app, 'Back')
    assert next(r for r in app.selectbox if r.key == 'dc_guest_frequency').value == 'weekly'
    app = click(app, 'Continue')
    app = click(app, 'Check with these assumptions')
    assert next(m for m in app.metric if m.label == 'Monthly flexibility after the new cost').value == '$1,870.00'


def test_switching_source_clears_all_guided_example_values():
    app = start('pages/7_Moving_Out_Alpha.py')
    app = click(app, 'Continue')
    app = click(app, 'Continue')
    app = click(app, 'Compare stay vs move')
    assert app.session_state['move_result']['current_liquid'] == 7500
    app = next(r for r in app.radio if r.key == 'move_start_mode').set_value('Enter my own numbers').run()
    assert not app.exception
    assert not app.metric
    assert app.session_state['move_step'] == 0
    assert all(n.value is None for n in app.number_input)
    assert app.session_state['move_draft_values'] == {}


def test_move_goal_comparison_shows_the_change_in_timing():
    app = start('pages/7_Moving_Out_Alpha.py')
    app = click(app, 'Continue')
    app = click(app, 'Continue')
    app = click(app, 'Compare stay vs move')
    set_number(app, 'move_goal_savings', 200.0)
    set_number(app, 'move_goal_cushion', 6300.0)
    set_number(app, 'move_goal_deadline', 4)
    set_number(app, 'move_goal_expense_total', 250.0)
    app = app.run()
    app = click(app, 'Try cutting $100 per month to meet the target')
    app = app.selectbox(key='move_goal_comparison').select('Reduce an expense').run()
    assert not app.exception
    assert [m.value for m in app.metric if m.label == 'Move-in costs plus cushion'] == [
        'In 6 months', 'In 4 months',
    ]
    assert app.session_state['ml_blocks'] == []
