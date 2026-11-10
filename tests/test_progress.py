"""Selected schedules, transparent check-ins and storage round trips."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
import pytest

from moneylab.planning import goal_alternative, goal_outlook
from moneylab.progress import (
    accept_comparison, add_months, progress_preview, select_plan, validate_tracking, whole_months,
)
from moneylab.profile_store import plan_from_json, plan_to_json
from test_planning import savings_profile

META = {'priority':'Build an emergency fund','unknown':[],'is_example':False}


def selected():
    blocks = savings_profile()
    comparison = goal_alternative(blocks, 'goal', '333.34')
    return accept_comparison(blocks, comparison, META, on_date=date(2026,1,10))


def test_acceptance_records_contribution_target_and_dated_schedule_atomically():
    blocks, metadata = selected()
    record = metadata['accepted_plan']
    assert record['started_on'] == '2026-01-10'
    assert record['blocks'] == blocks
    assert blocks[3]['monthly_contribution'] == '333.34'
    assert blocks[3]['target'] == '10000.00'
    assert META == {'priority':'Build an emergency fund','unknown':[],'is_example':False}


def test_checkin_reports_actual_gap_and_does_not_grant_a_new_six_month_deadline():
    blocks, metadata = selected()
    original = deepcopy(blocks)
    record = metadata['accepted_plan']
    c = progress_preview(blocks, record, 'goal', '8500', date(2026,3,10))
    assert c['progress']['expected'] == Decimal('8666.68')
    assert c['progress']['behind'] == Decimal('166.68')
    assert c['blocks'][3]['target_months'] == 4
    assert c['baseline']['goals'][0]['target_months'] == 4
    assert c['alternative']['goals'][0]['target_months'] == 4
    assert goal_outlook(c['blocks'], 'goal')['required'] == 375
    assert blocks == original
    assert record['last_as_of'] == '2026-01-10'


def test_approved_checkin_keeps_original_schedule_and_repeated_date_is_idempotent():
    blocks, metadata = selected()
    initial = deepcopy(metadata['accepted_plan']['blocks'])
    c = progress_preview(blocks, metadata['accepted_plan'], 'goal', '8500', date(2026,3,10))
    changed, meta = accept_comparison(blocks, c, metadata, on_date=date(2026,3,10))
    assert meta['accepted_plan']['blocks'] == initial
    assert meta['accepted_plan']['last_as_of'] == '2026-03-10'
    same_date = progress_preview(changed, meta['accepted_plan'], 'goal', '8550', date(2026,3,10))
    assert same_date['blocks'][3]['target_months'] == 4
    assert same_date['progress']['expected'] == Decimal('8666.68')
    next_date = progress_preview(changed, meta['accepted_plan'], 'goal', '8900', date(2026,4,10))
    assert next_date['blocks'][3]['target_months'] == 3
    assert next_date['progress']['expected'] == Decimal('9000.02')


def test_all_goal_deadlines_advance_but_unverified_balances_are_not_invented():
    blocks, metadata = selected()
    blocks.append(dict(blocks[3], id='move', name='Move-out fund', balance='500', target_months=12))
    record = select_plan(blocks, date(2026,1,10))
    c = progress_preview(blocks, record, 'goal', '8500', date(2026,3,10))
    assert c['blocks'][-1]['target_months'] == 10
    assert c['blocks'][-1]['balance'] == '500.00'
    assert c['blocks'][2]['balance'] == '2000.00'


def test_overdue_goal_is_flagged_instead_of_silently_renewed():
    blocks, metadata = selected()
    c = progress_preview(blocks, metadata['accepted_plan'], 'goal', '9000', date(2026,8,10))
    assert c['progress']['overdue'] == ['Emergency fund']
    assert c['blocks'][3]['target_months'] == 1


def test_profile_change_or_different_selected_schedule_blocks_approval():
    blocks, metadata = selected()
    c = progress_preview(blocks, metadata['accepted_plan'], 'goal', '8500', date(2026,3,10))
    other = deepcopy(metadata)
    other['accepted_plan']['started_on'] = '2025-12-10'
    with pytest.raises(ValueError, match='selected plan changed'):
        accept_comparison(blocks, c, other, on_date=date(2026,3,10))
    blocks[0]['monthly_amount'] = '2800'
    with pytest.raises(ValueError, match='figures changed'):
        accept_comparison(blocks, c, metadata, on_date=date(2026,3,10))


def test_backward_checkin_and_missing_goal_are_validation_errors():
    blocks, metadata = selected()
    with pytest.raises(ValueError):
        progress_preview(blocks, metadata['accepted_plan'], 'goal', '8500', date(2025,12,10))
    with pytest.raises(ValueError, match='no longer'):
        progress_preview(blocks[:-1], metadata['accepted_plan'], 'goal', '8500', date(2026,3,10))


def test_calendar_math_handles_month_ends_and_leap_years():
    assert add_months(date(2028,1,31), 1) == date(2028,2,29)
    assert whole_months(date(2026,1,31), date(2026,2,28)) == 1
    assert whole_months(date(2026,1,31), date(2026,3,30)) == 1


def test_midmonth_checkins_keep_calendar_deadlines_without_cumulative_drift():
    blocks, metadata = selected()
    c = progress_preview(blocks, metadata['accepted_plan'], 'goal', '8100', date(2026,1,20))
    updated, meta = accept_comparison(blocks, c, metadata, on_date=date(2026,1,20))
    assert meta['accepted_plan']['due_dates']['goal'] == '2026-07-10'
    assert c['blocks'][3]['target_months'] == 5
    another = progress_preview(updated, meta['accepted_plan'], 'goal', '8150', date(2026,1,21))
    assert another['blocks'][3]['target_months'] == 5
    assert another['tracking_update']['due_dates']['goal'] == '2026-07-10'


def test_deadline_with_less_than_one_month_remaining_is_flagged_not_called_overdue():
    blocks, metadata = selected()
    c = progress_preview(blocks, metadata['accepted_plan'], 'goal', '9900', date(2026,7,8))
    assert c['progress']['overdue'] == []
    assert c['progress']['partial_deadlines'] == ['Emergency fund']
    assert c['tracking_update']['due_dates']['goal'] == '2026-07-10'


def test_explicit_deadline_edit_is_kept_when_checking_progress():
    blocks, metadata = selected()
    blocks[3]['target_months'] = 10
    c = progress_preview(blocks, metadata['accepted_plan'], 'goal', '8500', date(2026,3,10))
    assert c['tracking_update']['due_dates']['goal'] == '2026-11-10'
    assert c['blocks'][3]['target_months'] == 8


def test_v5_roundtrip_preserves_preference_and_selected_plan_without_cached_results():
    blocks, metadata = selected()
    metadata['action_preference'] = {'focus':'goals','goal_id':'goal','cash_floor':'1500'}
    text = plan_to_json(blocks, [], [], metadata)
    assert json.loads(text)['schema_version'] == 5
    restored, _, _, meta = plan_from_json(text)
    assert restored == blocks
    assert meta['accepted_plan'] == metadata['accepted_plan']
    assert meta['action_preference']['cash_floor'] == '1500.00'
    assert 'monthly_records' not in text


def test_v4_workspace_still_imports_with_financial_details_intact():
    blocks, metadata = selected()
    payload = json.loads(plan_to_json(blocks, [], [], META))
    payload['schema_version'] = 4
    restored, _, _, meta = plan_from_json(json.dumps(payload))
    assert restored == blocks
    assert meta == META


def test_invalid_selected_snapshot_cannot_crash_import():
    payload = {'schema_version':5,'workspace':{'schema_version':3,'blocks':[], 'scenarios':[], 'decision_drafts':[]},
               'plan':dict(META, accepted_plan={'started_on':'2026-01-10','last_as_of':'2026-01-10','blocks':[{'kind':[]}]})}
    with pytest.raises(ValueError):
        plan_from_json(json.dumps(payload))
