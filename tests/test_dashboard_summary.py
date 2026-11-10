"""Dashboard decisions are calculated alternatives, visible without extra pages."""
from copy import deepcopy
from decimal import Decimal

from moneylab.action_plan import build_action_plan, dashboard_action
from test_planning import savings_profile
from test_action_ui import start


def test_dashboard_shows_benefit_funding_and_two_distinct_alternatives():
    blocks = savings_profile()
    original = deepcopy(blocks)
    result = dashboard_action(blocks, build_action_plan(blocks, reviewed=True))
    chosen = result['recommended']
    assert chosen['key'] == 'deadline'
    assert '$333.34/month' in chosen['headline']
    assert '4 months sooner' in chosen['benefit']
    assert '$133.34' in chosen['funding_source']
    assert '$600.00' in chosen['funding_source']
    assert '$466.66' in chosen['funding_source']
    assert [a['key'] for a in result['alternatives']] == ['later','target']
    assert result['alternatives'][0]['analysis']['goal']['deadline_after'] == 10
    assert result['alternatives'][1]['analysis']['goal']['target_after'] == 9200
    assert 'smaller' in result['alternatives'][1]['benefit']
    assert 'sooner' not in result['alternatives'][1]['benefit']
    assert blocks == original


def test_unfundable_deadline_promotes_a_realistic_later_date():
    blocks = savings_profile('2400')
    result = dashboard_action(blocks, build_action_plan(blocks, reviewed=True))
    assert result['recommended']['key'] == 'later'
    assert result['recommended']['analysis']['funding']['requested'] == 200
    assert 'no extra monthly saving' in result['recommended']['funding_source']
    assert [a['key'] for a in result['alternatives']] == ['target','current']
    assert any('short' in t for t in result['alternatives'][1]['warnings'])


def test_incomplete_profile_can_understand_a_preliminary_option_without_mutation():
    blocks = savings_profile()
    plan = build_action_plan(blocks, reviewed=False, missing=['debts'])
    assert plan['actions'][0]['kind'] == 'review'
    result = dashboard_action(blocks, plan)
    assert result['action']['kind'] == 'goal'
    assert any('debts and payments' in x for x in result['detail']['assumptions'])
    assert blocks[3]['monthly_contribution'] == '200'


def test_no_funding_does_not_fabricate_a_second_calculated_path():
    blocks = savings_profile('0','0')
    blocks[2]['balance'] = '0'
    blocks[3].update(balance='0', monthly_contribution='0')
    result = dashboard_action(blocks, build_action_plan(blocks, reviewed=False))
    assert result['recommended']['key'] == 'current'
    assert 'not reached' in result['recommended']['benefit']
    assert [a['key'] for a in result['alternatives']] == ['custom','review']
    assert all(a['comparison'] is None for a in result['alternatives'])


def test_cash_risk_stays_above_a_goal_even_when_profile_review_is_incomplete():
    blocks = savings_profile('2000')
    blocks[2]['balance'] = '100'
    result = dashboard_action(blocks, build_action_plan(blocks, reviewed=False))
    assert result['action']['kind'] == 'shortfall'
    assert result['alternatives'][0]['comparison']['baseline']['monthly_records'][1]['unfunded_shortfall'] == 100


def test_direct_deposits_are_visible_in_the_funding_source():
    blocks = savings_profile()
    blocks[0]['routes'] = [{'destination_id':'goal','mode':'fixed','value':'100'}]
    result = dashboard_action(blocks, build_action_plan(blocks, reviewed=True))
    assert '$233.34/month' in result['recommended']['headline']
    assert '$100.00' in result['recommended']['funding_source']
    assert '$33.34' in result['recommended']['funding_source']


def test_crowding_out_another_goal_is_not_hidden_in_supporting_calculations():
    blocks = savings_profile('500', '0')
    blocks[3].update(balance='0', target='1000', target_months=2, monthly_contribution='100')
    blocks.append(dict(blocks[3], id='move', name='Move-out fund', target_months=6, monthly_contribution='400'))
    result = dashboard_action(blocks, build_action_plan(blocks, reviewed=True))
    assert result['recommended']['key'] == 'deadline'
    assert any('Move-out fund' in text and 'less' in text for text in result['recommended']['warnings'])


def test_benefit_funding_and_alternative_buttons_are_outside_expanders():
    app = start()
    summary = next(m.value for m in app.markdown if 'aria-label="Recommended action"' in m.value)
    assert 'Expected benefit' in summary
    assert 'Where the money comes from' in summary
    assert '$133.34' in summary
    assert any(b.label == 'Compare a later deadline' for b in app.button)
    assert any(b.label == 'Compare a smaller target' for b in app.button)
    assert not any(b.label.startswith('Compare a later') or b.label.startswith('Compare a smaller')
                   for expander in app.expander for b in expander.button)
    assert not app.exception
