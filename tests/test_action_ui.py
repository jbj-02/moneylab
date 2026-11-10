"""Action workflow integrations: ranking, options, approval and progress."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from streamlit.testing.v1 import AppTest
from pathlib import Path

from moneylab.blocks import profile_to_json
from moneylab.planning import goal_alternative
from moneylab.progress import select_plan
from test_planning import savings_profile

ROOT = Path(__file__).resolve().parents[1]


def start(blocks=None, *, reviewed=True):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=30).run()
    blocks = blocks or savings_profile()
    app.session_state['ml_blocks'] = blocks
    app.session_state['ml_plan_metadata'] = {'priority':'Build an emergency fund','unknown':[]}
    if reviewed:
        app.session_state['ml_reviewed_signature'] = profile_to_json(blocks)
    app = app.run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def click(app, label):
    app = next(b for b in app.button if b.label == label).click().run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def open_goal(app):
    app.session_state['ml_selected_action'] = {'id':'goal:goal','kind':'goal','goal_id':'goal'}
    app = app.switch_page('pages/10_Action_Plan.py').run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def test_dashboard_has_finding_funding_and_reason_for_ranking():
    app = start()
    assert any(h.value == 'What should I do next?' for h in app.subheader)
    assert any(e.label == 'How MoneyLab worked this out' for e in app.expander)
    assert any('Month 1 funding' in m.value for m in app.markdown)
    assert any('nearer deadline' in c.value for c in app.caption)
    assert any(b.label == 'View action & alternatives' for b in app.button)


def test_goal_options_show_current_finish_and_smaller_target_tradeoff():
    app = open_goal(start())
    radio = next(r for r in app.radio if r.key == 'action_option_goal')
    assert set(radio.options) == {'Keep my current pace','Save more to meet the deadline','Give myself more time',
                                   'Choose a smaller target','Try my own adjustment or expense reduction'}
    app = radio.set_value('current').run()
    assert any('10 months' in m.value for m in app.markdown)
    app = next(r for r in app.radio if r.key == 'action_option_goal').set_value('target').run()
    assert any('changes the size of the goal' in i.value for i in app.info)
    original = deepcopy(app.session_state['ml_blocks'])
    app = click(app, 'Inspect this option')
    assert app.session_state['ml_blocks'] == original
    assert app.session_state['ml_plan_preview']['blocks'][3]['target'] == '9200.00'


def test_custom_expense_redirect_is_explicit_and_never_exceeds_reduction():
    app = open_goal(start(savings_profile('2400')))
    app = next(r for r in app.radio if r.key == 'action_option_goal').set_value('custom').run()
    app = next(s for s in app.selectbox if s.key == 'action_expense_goal').set_value('bills').run()
    assert not app.exception
    app = next(n for n in app.number_input if n.key == 'action_cut_goal_bills').set_value(100.0).run()
    redirect = next(n for n in app.number_input if n.label == 'Of that reduction, put toward this goal ($)')
    app = redirect.set_value(60.0).run()
    app = click(app, 'Inspect my adjustment')
    proposed = app.session_state['ml_plan_preview']['blocks']
    assert next(b for b in proposed if b['id'] == 'bills')['monthly_amount'] == '2100.00'
    assert next(b for b in proposed if b['id'] == 'goal')['monthly_contribution'] == '260.00'
    assert app.session_state['ml_blocks'][3]['monthly_contribution'] == '200'
    app = app.switch_page('pages/10_Action_Plan.py').run()
    assert not app.exception
    assert next(r for r in app.radio if r.key == 'action_option_goal').value == 'custom'
    assert next(n for n in app.number_input if n.key == 'action_cut_goal_bills').value == 100
    assert next(n for n in app.number_input if n.label == 'Of that reduction, put toward this goal ($)').value == 60


def test_priority_preference_does_not_edit_financial_profile():
    app = start()
    original = deepcopy(app.session_state['ml_blocks'])
    app = next(r for r in app.radio if r.key == 'action_focus').set_value('interest').run()
    app = click(app, 'Save priority')
    assert app.session_state['ml_plan_metadata']['action_preference']['focus'] == 'interest'
    assert app.session_state['ml_blocks'] == original


def test_stress_result_never_replaces_the_candidate_or_actual_profile():
    app = start()
    app.session_state['ml_plan_preview'] = goal_alternative(savings_profile(), 'goal', '333.34')
    app = app.switch_page('pages/9_Compare_Plan.py').run()
    original = deepcopy(app.session_state['ml_blocks'])
    candidate = deepcopy(app.session_state['ml_plan_preview'])
    app = next(r for r in app.radio if r.key == 'action_stress_kind').set_value('Lower income').run()
    app = next(n for n in app.number_input if n.key == 'action_stress_delta_pay').set_value(600.0).run()
    app = click(app, 'Run stress test')
    assert not app.session_state['ml_stress_result']['allow_apply']
    assert app.session_state['ml_plan_preview'] == candidate
    assert app.session_state['ml_blocks'] == original
    assert any('Chosen option under stress' in m.value for m in app.markdown)


def test_acceptance_displays_chosen_schedule_and_storage_status():
    app = start()
    app = click(app, 'Preview this saving pace')
    app = next(c for c in app.checkbox if c.key == 'plan_apply_confirm').check().run()
    app = click(app, 'Apply these changes to my plan')
    assert 'accepted_plan' in app.session_state['ml_plan_metadata']
    assert any('Your chosen plan:' in m.value for m in app.markdown)
    assert any('Session only' in c.value and 'workspace backups' in c.value for c in app.caption)


def test_unchanged_option_can_be_chosen_as_a_schedule_without_editing_figures():
    app = open_goal(start())
    original = deepcopy(app.session_state['ml_blocks'])
    app = next(r for r in app.radio if r.key == 'action_option_goal').set_value('current').run()
    app = click(app, 'Inspect this option')
    app.switch_page('pages/9_Compare_Plan.py')
    app = next(c for c in app.checkbox if c.key == 'plan_apply_confirm').check().run()
    app = click(app, 'Choose this plan')
    from moneylab.blocks import serialize_blocks
    assert app.session_state['ml_blocks'] == serialize_blocks(original)
    assert app.session_state['ml_plan_metadata']['accepted_plan']['blocks'] == serialize_blocks(original)


def test_progress_explains_gap_and_revised_pace_before_profile_update():
    blocks = savings_profile()
    blocks[3]['monthly_contribution'] = '333.34'
    app = start(blocks)
    app.session_state['ml_plan_metadata'] = {'priority':'Build an emergency fund','unknown':[],
                                             'accepted_plan':select_plan(blocks, date(2026,1,10))}
    app = app.run()
    original = deepcopy(app.session_state['ml_blocks'])
    next(d for d in app.date_input if d.key == 'action_checkin_date_goal').set_value(date(2026,3,10))
    next(n for n in app.number_input if n.key == 'action_checkin_balance_goal').set_value(8500.0)
    app = click(app, 'Compare my progress')
    assert app.session_state['ml_blocks'] == original
    assert app.session_state['ml_plan_preview']['progress']['behind'] == Decimal('166.68')
    assert any('375.00' in m.value and 'remaining 4 months' in m.value for m in app.markdown)
    assert app.session_state['ml_plan_preview']['blocks'][3]['target_months'] == 4


def test_incomplete_profile_action_names_missing_figures_and_blocks_approval():
    app = start(reviewed=False)
    app.session_state['ml_plan_metadata'] = {'priority':'Build an emergency fund','unknown':['debts','savings']}
    app = app.run()
    assert any('debts and payments' in m.value and 'savings balance' in m.value for m in app.markdown)
    app = open_goal(app)
    app = click(app, 'Inspect this option')
    app.switch_page('pages/9_Compare_Plan.py')
    next(c for c in app.checkbox if c.key == 'plan_apply_confirm').check()
    app = app.run()
    assert next(b for b in app.button if b.label == 'Apply these changes to my plan').disabled


def test_selected_schedule_survives_an_actual_local_store_round_trip(tmp_path, monkeypatch):
    import moneylab.plan_session as session
    from moneylab.profile_store import LocalProfileStore
    store = LocalProfileStore(tmp_path / 'private')
    monkeypatch.setattr(session, 'configured_local_store', lambda address: store)
    app = click(start(), 'Preview this saving pace')
    app = next(c for c in app.checkbox if c.key == 'plan_apply_confirm').check().run()
    app = click(app, 'Apply these changes to my plan')
    chosen = app.session_state['ml_plan_metadata']['accepted_plan']
    another = AppTest.from_file(str(ROOT/'app.py'), default_timeout=30).run()
    assert not another.exception
    assert another.session_state['ml_plan_metadata']['accepted_plan'] == chosen
    assert any('Your chosen plan:' in m.value for m in another.markdown)
