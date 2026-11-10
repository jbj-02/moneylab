"""Acceptance cases for explainable choices and conservative shared funding."""
from copy import deepcopy
from decimal import Decimal

import pytest
from moneylab.action_plan import (
    action_breakdown, build_action_plan, comparison_effects, explain_option,
    funding_breakdown, goal_options, stress_test,
)
from moneylab.planning import apply_preview, goal_alternative, goal_outlook, preview
from moneylab.scenario_changes import apply_scenario_changes
from test_planning import savings_profile


def option_map(blocks):
    return {o['key']: o for o in goal_options(blocks, 'goal')}


def test_fundable_goal_has_four_distinct_engine_evaluated_paths():
    blocks = savings_profile()
    original = deepcopy(blocks)
    options = option_map(blocks)
    assert set(options) == {'current', 'deadline', 'later', 'target'}
    assert options['current']['analysis']['goal']['completion_after'] == 10
    assert options['deadline']['analysis']['funding']['requested'] == Decimal('333.34')
    assert options['deadline']['analysis']['goal']['at_new_deadline'] == Decimal('10000.04')
    assert options['later']['analysis']['goal']['deadline_after'] == 10
    assert options['later']['analysis']['goal']['at_new_deadline'] == Decimal('10000')
    assert options['target']['analysis']['goal']['target_after'] == Decimal('9200')
    assert blocks == original


def test_unfundable_deadline_does_not_offer_invented_money():
    options = option_map(savings_profile('2400'))
    assert 'deadline' not in options
    assert options['later']['analysis']['goal']['completion_after'] == 10
    plan = build_action_plan(savings_profile('2400'), reviewed=True)
    detail = action_breakdown(savings_profile('2400'), plan['actions'][0])
    assert 'later deadline' in detail['proposed_action']
    assert detail['analysis']['goal']['on_track'] is False


def test_interest_and_competing_direct_deposits_are_part_of_the_pace_search():
    blocks = savings_profile()
    blocks[3]['annual_rate'] = '3.5'
    options = option_map(blocks)
    required = options['deadline']['analysis']['funding']['requested']
    assert required < Decimal('333.34')
    assert options['deadline']['analysis']['goal']['on_track']
    assert not goal_alternative(blocks, 'goal', required - Decimal('.01'))['alternative']['goals'][0]['on_track']
    blocks[0]['routes'] = [{'destination_id':'other','mode':'fixed','value':'600'}]
    blocks.insert(3, {'id':'other','kind':'hysa','name':'Other savings','balance':'0',
                     'annual_rate':'0','monthly_contribution':'100'})
    assert goal_outlook(blocks, 'goal')['required'] is None


def test_released_spending_and_redirected_goal_money_are_separate():
    blocks = savings_profile('2400')
    comparison = goal_alternative(blocks, 'goal', '260', expense_id='bills', reduction='100')
    funding = funding_breakdown(comparison, 'goal')
    assert funding['released'] == 100
    assert funding['goal_increase'] == 60
    assert funding['from_released'] == 60
    assert funding['released_left'] == 40
    assert funding['from_remainder'] == 0
    assert funding['remainder_before'] == 0
    assert funding['remainder_after'] == 40
    assert funding['first_month_funded'] == 260


def test_remainder_funding_math_conserves_recorded_income():
    c = option_map(savings_profile())['deadline']['comparison']
    f = funding_breakdown(c, 'goal')
    assert f['income'] - f['expenses'] - f['debt_payments'] - f['saving'] == f['remainder_before']
    assert f['from_remainder'] == Decimal('133.34')
    assert f['remainder_after'] == Decimal('466.66')


def test_goal_gain_that_crowds_out_another_goal_is_disclosed():
    blocks = savings_profile('1000', '0')
    blocks[3].update(balance='0', target='1500', target_months=2, monthly_contribution='250')
    blocks.append(dict(blocks[3], id='car', name='Car fund'))
    comparison = goal_alternative(blocks, 'goal', '1000')
    analysis = explain_option(comparison, 'goal')
    second = next(g for g in analysis['effects']['goals'] if g['id'] == 'car')
    assert second['before'] == 500
    assert second['after'] == 0
    assert any('Car fund' in t for t in analysis['tradeoffs'])
    # Independent suggestions cannot both claim the same surplus once applied.
    applied = apply_preview(blocks, goal_alternative(blocks, 'goal', '750'))
    assert goal_outlook(applied, 'car')['required'] is None


def test_later_deadline_is_compared_at_a_common_checkpoint_as_well():
    c = option_map(savings_profile())['later']['comparison']
    goal = comparison_effects(c)['goals'][0]
    assert goal['checkpoint'] == 6
    assert goal['before'] == goal['after'] == 9200
    assert goal['at_new_deadline'] == 10000
    assert goal['deadline_after'] == 10
    assert goal['change'] == 0


def test_reducing_target_does_not_claim_to_create_money():
    c = option_map(savings_profile())['target']['comparison']
    assert c['alternative']['summary']['ending_net_position'] == c['baseline']['summary']['ending_net_position']
    assert c['alternative']['summary']['total_asset_contributions'] == c['baseline']['summary']['total_asset_contributions']


def test_major_recurring_decision_delays_both_priorities_in_the_same_engine():
    blocks = savings_profile('2600')
    blocks.append(dict(blocks[3], id='move', name='Move-out fund'))
    changed = apply_scenario_changes(blocks, [{'operation':'add_monthly_expense','amount':'300'}])
    effects = comparison_effects(preview(blocks, changed, title='New car costs'))
    goal, move = effects['goals']
    assert goal['completion_before'] == 10
    assert goal['completion_after'] == 20
    assert move['completion_before'] == 10
    assert move['completion_after'] is None
    assert len(blocks) == 5


def test_goal_preference_changes_soft_ranking_but_not_cash_risk_priority():
    blocks = savings_profile()
    blocks[3].update(target_months=6, target='10000')
    blocks.append(dict(blocks[3], id='move', name='Move-out fund', target_months=12, target='15000'))
    normal = build_action_plan(blocks, reviewed=True)
    assert normal['actions'][0]['goal_id'] == 'goal'
    chosen = build_action_plan(blocks, reviewed=True,
                               preference={'focus':'goals','goal_id':'move','cash_floor':'0'})
    assert chosen['actions'][0]['goal_id'] == 'move'
    assert 'You selected' in chosen['actions'][0]['rank_reason']
    blocks[0]['monthly_amount'] = '1000'
    risk = build_action_plan(blocks, reviewed=True,
                             preference={'focus':'goals','goal_id':'move','cash_floor':'0'})
    assert risk['actions'][0]['kind'] == 'shortfall'


def test_growing_debt_and_cash_shortfall_remain_ahead_of_review_and_goals():
    blocks = savings_profile('1000', '1100')
    blocks[2]['balance'] = '100'
    blocks.append({'id':'card','kind':'loan','name':'Credit card','balance':'1000',
                   'annual_rate':'24','monthly_payment':'10'})
    actions = build_action_plan(blocks, reviewed=False, missing=['income'])['actions']
    assert [a['kind'] for a in actions][:3] == ['shortfall','debt','review']
    assert 'unfunded' in actions[0]['rank_reason']
    detail = action_breakdown(blocks, actions[1])
    assert detail['comparison']['blocks'][-1]['monthly_payment'] == '20.01'
    assert any('Not yet confirmed: take-home income' in a for a in detail['assumptions'])


def test_interest_preference_creates_a_funded_payment_comparison():
    blocks = savings_profile()
    blocks.append({'id':'student','kind':'loan','name':'Student loan','balance':'18000',
                   'annual_rate':'5','monthly_payment':'200'})
    plan = build_action_plan(blocks, reviewed=True,
                             preference={'focus':'interest','goal_id':None,'cash_floor':'0'})
    assert plan['actions'][0]['kind'] == 'interest'
    detail = action_breakdown(blocks, plan['actions'][0])
    assert detail['analysis']['effects']['interest_change'] < 0
    assert detail['analysis']['funding']['remainder_after'] == 0


def test_same_named_loans_do_not_redirect_a_growing_debt_action_to_the_wrong_loan():
    blocks = savings_profile()
    blocks.extend([
        {'id':'low','kind':'loan','name':'Loan','balance':'5000','annual_rate':'2','monthly_payment':'100'},
        {'id':'high','kind':'loan','name':'Loan','balance':'1000','annual_rate':'24','monthly_payment':'10'},
    ])
    action = build_action_plan(blocks, reviewed=True)['actions'][0]
    assert action['loan_id'] == 'high'
    candidate = action_breakdown(blocks, action)['comparison']['blocks']
    assert next(b for b in candidate if b['id'] == 'low')['monthly_payment'] == '100.00'
    assert next(b for b in candidate if b['id'] == 'high')['monthly_payment'] == '20.01'


def test_cash_cushion_preference_reports_a_recorded_gap():
    plan = build_action_plan(savings_profile(), reviewed=True,
                             preference={'focus':'cash','goal_id':None,'cash_floor':'5000'})
    assert plan['actions'][0]['kind'] == 'reserve'
    assert '$3,000.00 below' in plan['actions'][0]['finding']
    detail = action_breakdown(savings_profile(), plan['actions'][0])
    assert 'first reached in month 5' in detail['outcome']
    assert detail['comparison']['alternative'] == detail['comparison']['baseline']


def test_lower_contribution_is_a_signed_change_without_invented_new_funding():
    c = goal_alternative(savings_profile(), 'goal', '100')
    f = funding_breakdown(c, 'goal')
    assert f['goal_change'] == -100
    assert f['goal_increase'] == 0
    assert f['remainder_after'] == 700


def test_equal_expense_shock_preserves_a_selected_spending_reduction():
    blocks = savings_profile()
    comparison = goal_alternative(blocks, 'goal', '300', expense_id='bills', reduction='100')
    original = deepcopy(comparison)
    result = stress_test(comparison, {'operation':'adjust_monthly','block_id':'bills','delta':'100'})
    assert result['current']['projection']['summary']['monthly_expenses'] == 2300
    assert result['chosen']['projection']['summary']['monthly_expenses'] == 2200
    assert comparison == original
    assert result['allow_apply'] is False
    with pytest.raises(ValueError, match='stress'):
        apply_preview(blocks, result)


def test_lower_income_stress_exposes_an_unfundable_goal_without_changing_profile():
    blocks = savings_profile()
    c = option_map(blocks)['deadline']['comparison']
    result = stress_test(c, {'operation':'adjust_monthly','block_id':'pay','delta':'-600'})
    assert not result['chosen']['projection']['goals'][0]['on_track']
    assert blocks[0]['monthly_amount'] == '3000'


def test_one_time_stress_reports_unfunded_upfront_cost_in_one_option():
    blocks = savings_profile()
    alternative = apply_scenario_changes(blocks, [{'operation':'one_time_cash','amount':'1200'}])
    c = preview(blocks, alternative, title='Purchase')
    result = stress_test(c, {'operation':'one_time_cash','amount':'1500'})
    assert result['current']['projection'] is not None
    assert result['chosen']['projection'] is None
    assert result['chosen']['upfront_gap'] == 700
    assert blocks[2]['balance'] == '2000'


def test_altered_candidate_is_rejected_even_when_source_did_not_change():
    blocks = savings_profile()
    c = goal_alternative(blocks, 'goal', '333.34')
    c['blocks'][3]['monthly_contribution'] = '700'
    with pytest.raises(ValueError, match='proposed'):
        apply_preview(blocks, c)


@pytest.mark.parametrize('delta', ['NaN', 'Infinity', True, 'not a number'])
def test_invalid_stress_never_changes_any_profile(delta):
    blocks = savings_profile()
    with pytest.raises(ValueError):
        stress_test(preview(blocks, blocks, title='Same plan'),
                    {'operation':'adjust_monthly','block_id':'pay','delta':delta})
    assert blocks[0]['monthly_amount'] == '3000'
