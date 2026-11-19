"""Acceptance coverage for the inline, detached savings scenario."""

from copy import deepcopy
from decimal import Decimal

import pytest

from moneylab.planning import apply_preview
from moneylab.savings_change import (
    comparison_summary, flexible_expenses, goal_balance_series, savings_scenario, scenario_headline,
)


def acceptance_profile():
    return [
        dict(id='pay',kind='income',name='Take-home pay',monthly_amount='3000'),
        dict(id='rent',kind='expense',name='Rent',monthly_amount='2450'),
        dict(id='dining',kind='expense',name='Dining out',monthly_amount='350'),
        dict(id='cash',kind='cash',name='Checking',balance='0'),
        dict(id='goal',kind='goal',name='Emergency fund',balance='2500',annual_rate='0',
             monthly_contribution='200',target='4000',target_months=6),
    ]


@pytest.mark.parametrize(('spending','redirect','available','saving','left','projected'),[
    ('350','0','200','200','0','3700'),
    ('300','0','250','200','50','3700'),
    ('300','50','250','250','0','4000'),
    ('325','25','225','225','0','3850'),
])
def test_inline_savings_acceptance_scenarios(spending,redirect,available,saving,left,projected):
    blocks=acceptance_profile();original=deepcopy(blocks)
    comparison=savings_scenario(blocks,'goal','dining',spending,redirect)
    facts=comparison_summary(comparison['alternative'],'goal')
    assert facts['take_home']==Decimal('3000')
    assert facts['available_before_savings']==Decimal(available)
    assert facts['savings_contributions']==Decimal(saving)
    assert facts['left_after_savings']==Decimal(left)
    assert facts['projected']==Decimal(projected)
    assert blocks==original


def test_inline_savings_scenario_is_bound_to_source_and_redirect_limit():
    blocks=acceptance_profile()
    comparison=savings_scenario(blocks,'goal','dining','300','50')
    changed=deepcopy(blocks);changed[2]['monthly_amount']='340'
    with pytest.raises(ValueError,match='changed'):
        apply_preview(changed,comparison)
    with pytest.raises(ValueError,match='cannot exceed'):
        savings_scenario(blocks,'goal','dining','325','50')


def profile_with_expenses(*named):
    blocks=acceptance_profile()
    for index,(name,amount) in enumerate(named):
        blocks.append(dict(id=f'extra{index}',kind='expense',name=name,monthly_amount=amount))
    return blocks


def test_flexible_expenses_accept_ordinary_names_but_skip_essentials_and_fixed_costs():
    blocks=profile_with_expenses(('Fun money','60'),('Eating out','40'),('Groceries','300'),
                                 ('Student loan payment','150'),('Phone plan','50'),('Utilities','90'))
    names=[block['name'] for block in flexible_expenses(blocks)]
    assert 'Fun money' in names and 'Eating out' in names
    for skipped in ('Rent','Groceries','Student loan payment','Phone plan','Utilities'):
        assert skipped not in names


def test_flexible_expenses_list_discretionary_keywords_first_and_keep_old_matches():
    blocks=profile_with_expenses(('Fun money','60'),('Phone & streaming subscriptions','15'))
    names=[block['name'] for block in flexible_expenses(blocks)]
    assert names[:2]==['Dining out','Phone & streaming subscriptions']
    assert names[-1]=='Fun money'


def test_flexible_expenses_skip_zero_amounts():
    assert 'Fun money' not in [b['name'] for b in flexible_expenses(profile_with_expenses(('Fun money','0')))]


def test_extra_monthly_saving_is_funded_only_from_available_money():
    blocks=acceptance_profile()
    # Nothing is left after bills, so extra saving cannot be funded without a cut.
    unfunded=comparison_summary(savings_scenario(blocks,'goal','dining','350','0',extra='50')['alternative'],'goal')
    assert unfunded['savings_contributions']==Decimal('200')
    assert unfunded['projected']==Decimal('3700')
    # Cutting $50 creates the room, so the same extra saving is fully funded.
    funded=comparison_summary(savings_scenario(blocks,'goal','dining','300','0',extra='50')['alternative'],'goal')
    assert funded['savings_contributions']==Decimal('250')
    assert funded['projected']==Decimal('4000')


def test_scenario_with_no_changes_matches_the_plan_and_records_extra_saving():
    blocks=acceptance_profile()
    unchanged=savings_scenario(blocks,'goal','dining','350','0')
    assert unchanged['source_signature']==unchanged['candidate_signature']
    assert unchanged['savings_change']['extra']==Decimal('0.00')
    extra=savings_scenario(blocks,'goal','dining','300','0',extra='50')
    assert extra['source_signature']!=extra['candidate_signature']
    assert extra['savings_change']['extra']==Decimal('50.00')


def test_extra_saving_validates_input():
    with pytest.raises(ValueError):
        savings_scenario(acceptance_profile(),'goal','dining','350','0',extra='-5')


def headline(blocks,spending,redirect,*,extra='0',expense='dining'):
    comparison=savings_scenario(blocks,'goal',expense,spending,redirect,extra=extra)
    current=comparison_summary(comparison['baseline'],'goal')
    tested=comparison_summary(comparison['alternative'],'goal')
    return scenario_headline(current,tested,'Emergency fund',added_saving=Decimal(redirect)+Decimal(extra))


def test_headline_when_a_change_closes_the_gap():
    result=headline(acceptance_profile(),'300','50')
    assert result['tone']=='success'
    assert 'reaches your $4,000.00 Emergency fund goal by month 6' in result['text']
    assert '$300.00 short' in result['text']
    assert result['note'] is None


def test_headline_when_a_change_helps_but_does_not_finish_the_job():
    result=headline(acceptance_profile(),'325','25')
    assert result['tone']=='info'
    assert 'Still $150.00 short' in result['text'] and '$150.00 closer' in result['text']


def test_headline_when_only_spending_changes():
    result=headline(acceptance_profile(),'300','0')
    assert result['tone']=='info'
    assert 'No effect' in result['text'] and '$0.00' in result['text'] and '$50.00' in result['text']


def test_headline_explains_when_the_budget_cannot_fund_extra_saving():
    result=headline(acceptance_profile(),'350','0',extra='50')
    assert result['note'] and '$0.00 of the $50.00' in result['note']


def test_headline_reports_months_sooner_when_already_on_track():
    blocks=acceptance_profile();blocks[-1]['target_months']=12
    result=headline(blocks,'300','50')
    assert result['tone']=='success'
    assert '6 months' in result['text'] and '2 months sooner' in result['text'] and '8 months' in result['text']


def test_headline_warns_when_the_result_is_worse():
    facts=dict(take_home=Decimal(0),spending_and_bills=Decimal(0),available_before_savings=Decimal(0),
               savings_contributions=Decimal(0),left_after_savings=Decimal(0),projected=Decimal(3700),
               gap=Decimal(300),target=Decimal(4000),deadline=6,completion_month=None)
    worse={**facts,'projected':Decimal(3600),'gap':Decimal(400)}
    result=scenario_headline(facts,worse,'Emergency fund')
    assert result['tone']=='warning' and '$100.00 further' in result['text']


def test_goal_balance_series_lines_up_with_the_summaries():
    comparison=savings_scenario(acceptance_profile(),'goal','dining','300','50')
    series=goal_balance_series(comparison,'goal')
    assert series['months'][0]==0
    assert len(series['months'])==len(series['current'])==len(series['test'])
    assert series['target']==4000.0 and series['deadline']==6
    assert series['current'][6]==3700.0 and series['test'][6]==4000.0
    assert series['months'][-1]>=series['deadline']
