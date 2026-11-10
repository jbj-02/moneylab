"""Real plan journeys through Streamlit, with the production Python engine."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from streamlit.testing.v1 import AppTest
from moneylab.blocks import profile_to_json, serialize_blocks
from moneylab.planning import goal_alternative
from test_planning import savings_profile

ROOT = Path(__file__).resolve().parents[1]


def start():
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    assert not app.exception
    return app


def click(app, label):
    app = next(b for b in app.button if b.label == label).click().run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def navigate(app, page):
    app = app.switch_page(f'pages/{page}').run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def sample():
    return click(start(), 'Load optional example profile')


def reviewed_profile():
    app = start()
    blocks = savings_profile()
    app.session_state['ml_blocks'] = blocks
    app.session_state['ml_plan_metadata'] = {'priority':'Build an emergency fund','unknown':[]}
    app.session_state['ml_reviewed_signature'] = profile_to_json(blocks)
    return app.run()


def test_home_starts_empty_with_one_setup_and_optional_example():
    app = start()
    assert app.session_state['ml_blocks'] == []
    assert any(t.value == 'My Plan' for t in app.title)
    assert any(b.label == 'Set up my finances' for b in app.button)
    assert any(b.label == 'Try a fictional plan' for b in app.button)
    assert not app.sidebar.slider


def test_sample_discloses_example_and_shows_signed_monthly_remainder():
    app = sample()
    assert any('Fictional example plan' in i.value for i in app.info)
    metrics = {m.label:m.value for m in app.metric}
    assert metrics['Monthly take-home'] == '$3,800.00'
    assert metrics['After bills, debt & saving'] == '$905.00'
    assert any(b.label == 'Preview this saving pace' for b in app.button)


def test_finances_has_compact_grouped_rows_and_single_entry_edit():
    app = navigate(sample(), '1_My_Money.py')
    assert len(app.tabs) == 3
    app = next(b for b in app.button if b.key == 'plan_edit_rent').click().run()
    assert not app.exception
    assert any(x.label == 'Save changes' for x in app.button)
    assert any(n.key == 'edit_rent_monthly_period_amount' for n in app.number_input)
    # Actual dialog edits are covered in Chromium. AppTest does not execute
    # dialog fragment reruns through the navigation shell.


def test_preview_does_not_edit_profile_and_requires_explicit_approval():
    app = reviewed_profile()
    original = deepcopy(app.session_state['ml_blocks'])
    app = click(app, 'Preview this saving pace')
    assert app.session_state['ml_blocks'] == original
    assert next(b for b in app.button if b.label == 'Apply these changes to my plan').disabled
    checkbox = next(c for c in app.checkbox if c.key == 'plan_apply_confirm')
    app = checkbox.check().run()
    app = click(app, 'Apply these changes to my plan')
    assert app.session_state['ml_blocks'][3]['monthly_contribution'] == '333.34'
    assert app.session_state._state.filtered_state.get('ml_plan_preview') is None


def test_editing_original_after_preview_blocks_stale_apply():
    app = reviewed_profile()
    app.session_state['ml_plan_preview'] = goal_alternative(savings_profile(), 'goal', '333.34')
    changed = savings_profile('2900')
    app.session_state['ml_blocks'] = changed
    app = app.run()
    assert any('Your figures changed' in w.value for w in app.warning)
    assert not any(b.label == 'Apply these changes to my plan' for b in app.button)


def test_purchase_comparison_is_immutable_and_can_be_discarded():
    app = navigate(reviewed_profile(), '3_Explore.py')
    original = deepcopy(app.session_state['ml_blocks'])
    app = next(n for n in app.number_input if n.key == 'dc_cost_value').set_value(1200.0).run()
    app = click(app, 'Compare with my current plan')
    assert app.session_state['ml_blocks'] == original
    assert app.session_state['ml_plan_preview']['alternative']['monthly_records'][0]['cash_savings'] == 800
    # AppTest retains an explicit switch_page request across runs; align it
    # with the navigation performed by the app before interacting again.
    app.switch_page('pages/9_Compare_Plan.py')
    app = click(app, 'Discard alternative')
    assert app.session_state['ml_blocks'] == original
    assert app.session_state._state.filtered_state.get('ml_plan_preview') is None


def test_struggling_user_sees_negative_remainder_and_realistic_guidance():
    app = start()
    app.session_state['ml_blocks'] = savings_profile('2000')
    app = app.run()
    assert next(m for m in app.metric if m.label == 'After bills, debt & saving').value == '-$200.00'
    assert any('Cash runs short' in m.value for m in app.markdown)
    assert not app.exception


def test_settings_export_and_clear_every_financial_draft():
    app = sample()
    app.session_state['smart_secret_test'] = 'fictional financial description'
    app.session_state['plan_setup_draft'] = {'income':3000}
    app = navigate(app, '6_Settings.py')
    assert len(app.get('download_button')) == 2
    app = next(c for c in app.checkbox if c.key == 'plan_delete_confirm').check().run()
    app = click(app, 'Delete my data')
    assert app.session_state['ml_blocks'] == []
    assert 'smart_secret_test' not in app.session_state
    assert 'plan_setup_draft' not in app.session_state


def test_local_saving_survives_a_new_session(tmp_path, monkeypatch):
    import moneylab.plan_session as session
    from moneylab.profile_store import LocalProfileStore
    store = LocalProfileStore(tmp_path / 'local')
    monkeypatch.setattr(session, 'configured_local_store', lambda address: store)
    app = sample()
    saved = app.session_state['ml_blocks']
    another = start()
    assert another.session_state['ml_blocks'] == serialize_blocks(saved)
    assert another.session_state['ml_save_status'] == 'Saved locally on this computer'
    assert any('Fictional example plan' in i.value for i in another.info)


def test_legacy_goals_bookmark_now_opens_integrated_plan():
    app = navigate(sample(), '2_Goals.py')
    assert any(t.value == 'My Plan' for t in app.title)
    assert any('Summer travel fund' in m.value for m in app.markdown)


def test_weekly_recurring_cost_keeps_cadence_and_exports_reviewed_inputs():
    app = navigate(reviewed_profile(), '3_Explore.py')
    app = next(r for r in app.radio if r.key == 'dc_cost_kind').set_value('Recurring commitment').run()
    next(n for n in app.number_input if n.key == 'dc_cost_value').set_value(45.0)
    app = next(s for s in app.selectbox if s.key == 'dc_cost_frequency').set_value('weekly').run()
    app = click(app, 'Compare with my current plan')
    comparison = app.session_state['ml_plan_preview']
    assert comparison['alternative']['summary']['monthly_expenses'] == 2395
    from moneylab.workspace_session import capture_decision_drafts
    drafts = capture_decision_drafts(app.session_state._state.filtered_state)
    assert Decimal(drafts[0]['values']['cost']) == 45
    assert drafts[0]['frequency'] == 'weekly'


def test_conflicting_local_writer_reports_unsaved_and_keeps_backup_available(tmp_path, monkeypatch):
    import moneylab.plan_session as session
    from moneylab.profile_store import LocalProfileStore
    store = LocalProfileStore(tmp_path / 'local')
    monkeypatch.setattr(session, 'configured_local_store', lambda address: store)
    first = sample()
    second = start()
    first.session_state['ml_blocks'] = savings_profile('2900')
    first = first.run()
    second.session_state['ml_blocks'] = savings_profile('2800')
    second = second.run()
    assert second.session_state['ml_save_status'] == 'Not saved · download a backup'
    assert second.session_state['ml_store_error']
    assert not second.exception
    second = navigate(second, '6_Settings.py')
    assert len(second.get('download_button')) == 2
