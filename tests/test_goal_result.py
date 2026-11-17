"""Acceptance cases for the one-answer, one-verified-change service."""
from copy import deepcopy
from decimal import Decimal

import pytest

from moneylab.blocks import project_blocks
from moneylab.goal_result import goal_result
from moneylab.planning import apply_preview
from moneylab.result_ui import complete_figure


def rescue_profile():
    return [
        dict(id='pay',kind='income',name='Take-home pay',monthly_amount='2400'),
        dict(id='bills',kind='expense',name='Rent & essentials',monthly_amount='2000'),
        dict(id='dining',kind='expense',name='Dining out & takeaways',monthly_amount='300'),
        dict(id='cash',kind='cash',name='Checking',balance='500'),
        dict(id='goal',kind='goal',name='Emergency fund',balance='3620',annual_rate='0',monthly_contribution='100',target='5000',target_months=6),
    ]


def test_recorded_dining_cut_really_closes_the_780_gap_without_spending_twice():
    blocks=rescue_profile(); original=deepcopy(blocks)
    answer=goal_result(blocks)
    assert '$780.00 short' in answer['finding'] and '$5,000.00' in answer['finding'] and '6 months' in answer['finding']
    assert answer['kind']=='expense' and answer['cut']==Decimal('130')
    proposed=answer['comparison']['blocks']
    assert proposed[2]['monthly_amount']=='170.00'
    assert proposed[4]['monthly_contribution']=='230.00'
    assert answer['analysis']['goal']['at_new_deadline']==5000
    assert answer['analysis']['funding']['remainder_after']==0
    assert answer['analysis']['funding']['fully_funded_months']==6
    assert blocks==original
    too_small=deepcopy(proposed);too_small[2]['monthly_amount']='170.01';too_small[4]['monthly_contribution']='229.99'
    assert project_blocks(too_small,6)['goals'][0]['projected_at_deadline'] < 5000


def test_spare_monthly_room_is_used_before_any_expense_cut():
    blocks=rescue_profile();blocks[0]['monthly_amount']='2600'
    result=goal_result(blocks)
    assert result['kind']=='set_aside'
    assert result['comparison']['blocks'][2]['monthly_amount']=='300.00'
    assert result['analysis']['funding']['from_remainder']==130
    assert result['analysis']['funding']['remainder_after']==70


@pytest.mark.parametrize('name', ['Rent', 'Groceries & dining', 'Utilities, phone & subscriptions', 'Bills', 'Mystery expense'])
def test_no_automatic_cut_to_unrecorded_or_bundled_essential_spending(name):
    blocks=rescue_profile();blocks[2]['name']=name
    answer=goal_result(blocks)
    assert answer['kind']=='later'
    assert answer['comparison']['blocks'][2]['monthly_amount']=='300.00'
    assert answer['comparison']['blocks'][4]['target_months']==14


def test_an_expense_cut_never_exceeds_the_entry_or_product_bounds():
    blocks=rescue_profile();blocks[2]['monthly_amount']='40';blocks[1]['monthly_amount']='2260'
    result=goal_result(blocks)
    assert result['kind']=='later'  # A $130 cut cannot come out of $40.
    blocks[2]['monthly_amount']='1000';blocks[1]['monthly_amount']='1300'
    result=goal_result(blocks)
    assert 0 < result['cut'] <= 150


def test_too_distant_deadline_has_no_invented_later_date_or_income():
    blocks=rescue_profile();blocks[0]['monthly_amount']='2300';blocks[2]['name']='Other bills'
    result=goal_result(blocks)
    assert result['kind']=='unreachable'
    assert result['comparison'] is None
    assert '120 months' in result['suggestion']


def test_missing_income_is_asked_for_instead_of_a_funded_suggestion():
    blocks=rescue_profile()[1:]
    result=goal_result(blocks,missing=['income'])
    assert result['kind']=='missing' and result['comparison'] is None
    assert result['missing']==['income']
    assert 'Add your take-home income' in result['finding']
    assert not any('bills run short' in w for w in result['warnings'])


def test_known_zero_is_a_valid_answer_and_does_not_resolve_other_unknowns():
    blocks=rescue_profile()[1:];metadata=dict(priority='Build an emergency fund',unknown=['income','debts'])
    with pytest.raises(ValueError,match='Enter a figure'):
        complete_figure(blocks,metadata,'income',None)
    updated,details=complete_figure(blocks,metadata,'income',0)
    assert next(b for b in updated if b['kind']=='income')['monthly_amount']=='0.00'
    assert details['unknown']==['debts'] and metadata['unknown']==['income','debts']


def test_on_track_result_has_no_gap_and_tests_a_smaller_funded_pace():
    blocks=rescue_profile();blocks[0]['monthly_amount']='2800';blocks[4]['monthly_contribution']='300'
    answer=goal_result(blocks)
    assert "You're on track" in answer['finding']
    assert answer['kind']=='release'
    assert answer['comparison']['blocks'][4]['monthly_contribution']=='230.00'
    assert answer['analysis']['goal']['on_track']


def test_other_goal_impact_is_exposed_and_stale_changes_cannot_apply():
    blocks=rescue_profile();blocks[0]['monthly_amount']='2700'
    blocks.append(dict(blocks[-1],id='car',name='Car fund',balance='0',target='1800',monthly_contribution='300'))
    result=goal_result(blocks)
    # The suggestion must be tested against the other account, not an isolated goal.
    assert result['comparison'] is not None
    analysis=result['analysis']
    losses=[g for g in analysis['effects']['goals'] if g['id']!='goal' and g['change']<0]
    assert all(any(g['name'] in w for w in result['warnings']) for g in losses)
    changed=deepcopy(blocks);changed[0]['monthly_amount']='2500'
    with pytest.raises(ValueError,match='changed'):
        apply_preview(changed,result['comparison'])


def test_routed_income_and_interest_are_included_in_the_actual_test():
    blocks=rescue_profile();blocks[0]['routes']=[dict(destination_id='goal',mode='fixed',value='50')]
    blocks[4]['annual_rate']='3.5'
    result=goal_result(blocks)
    assert result['analysis']['funding']['direct_goal_deposit']==50
    assert result['analysis']['goal']['on_track']
    assert any('direct deposit' in w for w in result['warnings'])


def test_debt_cannot_be_confirmed_absent_over_a_positive_balance():
    blocks=rescue_profile()+[dict(id='debt',kind='loan',name='Loan',balance='500',annual_rate='5',monthly_payment='50')]
    with pytest.raises(ValueError,match='recorded debt'):
        complete_figure(blocks,dict(priority='Understand my money',unknown=['debts']),'debts','none')


def test_confirming_partial_existing_income_does_not_add_a_second_paycheck():
    blocks=rescue_profile()
    updated,metadata=complete_figure(blocks,dict(priority='Build an emergency fund',unknown=['income']),'income','2500')
    assert len([b for b in updated if b['kind']=='income'])==1
    assert updated[0]['id']=='pay' and updated[0]['monthly_amount']=='2500.00'
    assert metadata['unknown']==[]


def test_confirming_existing_income_or_cash_does_not_duplicate_it():
    blocks=rescue_profile()
    details=dict(priority='Build an emergency fund',unknown=['income','checking'])
    updated,details=complete_figure(blocks,details,'income','2500')
    updated,details=complete_figure(updated,details,'checking','600')
    assert len([b for b in updated if b['kind']=='income'])==1
    assert len([b for b in updated if b['kind']=='cash'])==1
    assert next(b for b in updated if b['id']=='pay')['monthly_amount']=='2500.00'
    assert next(b for b in updated if b['id']=='cash')['balance']=='600.00'
    assert details['unknown']==[]


def test_missing_savings_total_does_not_count_existing_accounts_twice():
    blocks=rescue_profile()+[dict(id='bank',kind='account',account_type='savings',name='Other savings',balance='1000',annual_rate='0',monthly_contribution='0')]
    updated,_=complete_figure(blocks,dict(priority='Build an emergency fund',unknown=['savings']),'savings','5000')
    assert next(b for b in updated if b['id']=='setup_savings')['balance']=='380.00'
