"""Goal-first onboarding: back navigation, unknowns, atomic approval."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def start():
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    return app.switch_page('pages/5_Quick_Start.py').run()


def click(app, label):
    app = next(b for b in app.button if b.label == label).click().run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def set_number(app, key, value):
    next(n for n in app.number_input if n.key == key).set_value(value)


def monthly_step():
    app = start()
    app = next(r for r in app.radio if r.key == 'setup_priority').set_value('Understand my money').run()
    return click(app, 'Continue')


def test_setup_begins_with_priority_not_income():
    app = start()
    assert any(t.value == 'Build your financial plan' for t in app.title)
    assert any(r.key == 'setup_priority' for r in app.radio)
    assert not any(n.key == 'setup_income' for n in app.number_input)
    assert not app.text_area
    assert app.session_state['ml_blocks'] == []


def test_back_retains_values_without_saving_profile():
    app = monthly_step()
    set_number(app, 'setup_income', 3000.0)
    app = click(app, 'Continue')
    app = click(app, 'Back')
    assert next(n for n in app.number_input if n.key == 'setup_income').value == 3000.0
    assert app.session_state['ml_blocks'] == []
    app = click(app, 'Back')
    app = click(app, 'Continue')
    assert next(n for n in app.number_input if n.key == 'setup_income').value == 3000.0


def test_unknowns_remain_explicit_and_build_requires_approval():
    app = monthly_step()
    set_number(app, 'setup_income', 3000.0)
    set_number(app, 'setup_housing', 0.0)
    app = click(app, 'Continue')
    app = click(app, 'Build my plan')
    assert app.session_state['ml_blocks'] == []
    assert any('check the box' in e.value for e in app.error)
    next(c for c in app.checkbox if c.label == 'Use these figures to build my preliminary plan').check()
    app = click(app, 'Build my plan')
    blocks = app.session_state['ml_blocks']
    assert len(blocks) == 2
    assert blocks[1]['monthly_amount'] == '0.00'
    assert 'food' in app.session_state['ml_plan_metadata']['unknown']
    assert 'housing' not in app.session_state['ml_plan_metadata']['unknown']
    assert any('Not yet confirmed' in i.value for i in app.info)


def test_goal_balance_cannot_be_counted_twice():
    app = start()
    set_number(app, 'setup_target', 10000.0)
    app = click(app, 'Continue')
    set_number(app, 'setup_income', 3000.0)
    app = click(app, 'Continue')
    set_number(app, 'setup_savings', 1000.0)
    set_number(app, 'setup_goal_saved', 1500.0)
    set_number(app, 'setup_goal_monthly', 200.0)
    next(c for c in app.checkbox if c.label == 'Use these figures to build my preliminary plan').check()
    app = click(app, 'Build my plan')
    assert app.session_state['ml_blocks'] == []
    assert any('cannot exceed' in e.value for e in app.error)


def test_setup_cannot_replace_an_existing_profile():
    app = start()
    app.session_state['ml_blocks'] = [{'id':'pay','kind':'income','name':'Pay','monthly_amount':'1000'}]
    app = app.run()
    assert any('already have a plan' in i.value for i in app.info)
    assert not any(b.label == 'Build my plan' for b in app.button)
