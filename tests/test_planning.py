"""Financial acceptance cases for the presentation-independent plan service."""
from copy import deepcopy
from decimal import Decimal
import pytest

from moneylab.blocks import project_blocks
from moneylab.planning import apply_preview, goal_alternative, goal_outlook, plan_actions, preview
from moneylab.scenario_changes import apply_scenario_changes


def savings_profile(income='3000', expenses='2200'):
    return [
        {'id':'pay','kind':'income','name':'Pay','monthly_amount':income},
        {'id':'bills','kind':'expense','name':'Bills','monthly_amount':expenses},
        {'id':'cash','kind':'cash','name':'Checking','balance':'2000'},
        {'id':'goal','kind':'goal','name':'Emergency fund','balance':'8000',
         'target':'10000','target_months':6,'annual_rate':'0','monthly_contribution':'200'},
    ]


def test_emergency_fund_required_pace_is_minimum_cent_and_simulated():
    blocks = savings_profile()
    original = deepcopy(blocks)
    result = goal_outlook(blocks, 'goal')
    assert result['gap'] == Decimal('800')
    assert result['completion_month'] == 10
    assert result['required'] == Decimal('333.34')
    assert result['extra'] == Decimal('133.34')
    comparison = goal_alternative(blocks, 'goal', result['required'])
    assert comparison['alternative']['goals'][0]['on_track']
    too_small = goal_alternative(blocks, 'goal', result['required'] - Decimal('.01'))
    assert not too_small['alternative']['goals'][0]['on_track']
    assert blocks == original


def test_struggling_user_is_not_told_to_save_unavailable_money():
    result = goal_outlook(savings_profile('2400'), 'goal')
    assert result['required'] is None
    assert result['best_possible'] == Decimal('9200')
    action = plan_actions(savings_profile('2400'), reviewed=True)['actions'][0]
    assert 'Even directing available monthly money' in action['detail']
    assert action['outlook']['extra'] is None


def test_recommendations_compete_for_same_money_and_are_recomputed_on_apply():
    blocks = savings_profile('1000', '0')
    blocks[3].update(balance='0', target='1500', target_months=2, monthly_contribution='250')
    second = dict(blocks[3], id='second', name='Move-out fund')
    blocks.append(second)
    actions = plan_actions(blocks, reviewed=True)['actions']
    assert [a['outlook']['required'] for a in actions] == [Decimal('750'), Decimal('750')]
    applied = apply_preview(blocks, goal_alternative(blocks, 'goal', '750'))
    assert goal_outlook(applied, 'second')['required'] is None


def test_existing_accounts_and_direct_deposits_reduce_available_goal_funding():
    blocks = savings_profile()
    blocks[0]['routes'] = [{'destination_id':'savings','mode':'fixed','value':'300'}]
    blocks.insert(3, {'id':'savings','kind':'hysa','name':'Savings','balance':'0',
                      'annual_rate':'0','monthly_contribution':'300'})
    assert goal_outlook(blocks, 'goal')['required'] is None
    result = goal_outlook(blocks, 'goal')
    assert result['best_possible'] == Decimal('9200')


def test_shortfall_month_and_growing_debt_are_prioritized_before_goals():
    blocks = savings_profile('1000', '1100')
    blocks[2]['balance'] = '100'
    blocks.append({'id':'debt','kind':'loan','name':'Credit card','balance':'1000',
                   'annual_rate':'24','monthly_payment':'10'})
    actions = plan_actions(blocks, reviewed=True)['actions']
    assert [a['kind'] for a in actions][:2] == ['shortfall', 'debt']
    assert 'month 1' in actions[0]['title']
    assert '$20.00' in actions[1]['detail']


def test_reduction_is_only_to_selected_recorded_expense_and_preserves_source():
    blocks = savings_profile('2400')
    original = deepcopy(blocks)
    comparison = goal_alternative(blocks, 'goal', '334', expense_id='bills', reduction='134')
    assert comparison['alternative']['goals'][0]['on_track']
    assert blocks == original
    with pytest.raises(ValueError):
        goal_alternative(blocks, 'goal', '334', expense_id='invented', reduction='134')
    with pytest.raises(ValueError):
        goal_alternative(blocks, 'goal', '334', expense_id='bills', reduction='2201')


def test_recurring_decision_shows_multiple_goal_impacts_without_touching_plan():
    blocks = savings_profile('2600')
    blocks.append(dict(blocks[3], id='second', name='Car fund'))
    alternative = apply_scenario_changes(blocks, [{'operation':'add_monthly_expense','amount':'300'}])
    result = preview(blocks, alternative, title='New commitment')
    old, new = result['baseline']['goals'], result['alternative']['goals']
    assert all(a['projected_at_deadline'] < b['projected_at_deadline'] for a,b in zip(new,old))
    assert len(blocks) == 5


def test_preview_is_detached_and_stale_approval_is_rejected():
    blocks = savings_profile()
    comparison = goal_alternative(blocks, 'goal', '333.34')
    applied = apply_preview(blocks, comparison)
    applied[0]['name'] = 'Changed outside comparison'
    assert comparison['blocks'][0]['name'] == 'Pay'
    with pytest.raises(ValueError, match='changed'):
        apply_preview(applied, comparison)


def test_already_funded_goal_and_deadline_beyond_dashboard_horizon():
    blocks = savings_profile()
    blocks[3].update(balance='10000', target_months=60)
    result = goal_outlook(blocks, 'goal')
    assert result['required'] == 0
    assert result['completion_month'] == 0
    assert result['on_track']
    assert plan_actions(blocks, reviewed=True)['actions'][0]['kind'] == 'maintain'


def test_savings_alternative_never_skips_earlier_unfunded_cash():
    blocks = savings_profile('2200')
    blocks[3]['annual_rate'] = '3.5'
    result = goal_outlook(blocks, 'goal')
    assert result['required'] is None
    comparison = goal_alternative(blocks, 'goal', '500')
    assert comparison['alternative']['summary']['total_asset_contributions'] == 0


def test_student_loan_extra_payment_discloses_goal_tradeoff_and_interest_change():
    blocks = savings_profile()
    blocks.append({'id':'student','kind':'loan','name':'Student loan','balance':'18000',
                   'annual_rate':'5','monthly_payment':'200'})
    alternative = deepcopy(blocks)
    alternative[-1]['monthly_payment'] = '700'
    comparison = preview(blocks, alternative, title='Higher loan payment')
    assert comparison['alternative']['summary']['total_interest'] < comparison['baseline']['summary']['total_interest']
    assert comparison['alternative']['goals'][0]['projected_at_deadline'] < comparison['baseline']['goals'][0]['projected_at_deadline']
