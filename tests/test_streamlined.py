"""Financial acceptance for the short purchase and move tasks."""
from copy import deepcopy
from decimal import Decimal
import pytest

from moneylab.planning import apply_preview
from moneylab.streamlined import moving_impact, purchase_impact, goal_effects


def profile():
    return [dict(id='pay',kind='income',name='Pay',monthly_amount='2400'),
            dict(id='rent',kind='expense',name='Rent',monthly_amount='1500'),
            dict(id='bills',kind='expense',name='Other costs',monthly_amount='500'),
            dict(id='dining',kind='expense',name='Dining out',monthly_amount='300'),
            dict(id='cash',kind='cash',name='Checking',balance='2500'),
            dict(id='goal',kind='goal',name='Emergency fund',balance='3620',annual_rate='0',monthly_contribution='100',target='5000',target_months=6)]


def test_purchase_uses_cash_and_keeps_the_original_until_explicit_application():
    blocks=profile();original=deepcopy(blocks)
    facts=purchase_impact(blocks,200)
    assert facts['remaining']==2300
    assert blocks==original
    assert facts['comparison']['alternative']['monthly_records'][1]['net_cash_flow']==0
    assert goal_effects(facts['comparison'])[0]['after']==4220
    applied=apply_preview(blocks,facts['comparison'])
    assert next(b for b in applied if b['kind']=='cash')['balance']=='2300.00'


def test_a_purchase_cannot_borrow_or_spend_earmarked_goal_savings():
    facts=purchase_impact(profile(),3000)
    assert facts['comparison'] is None and facts['gap']==500


def test_move_keeps_goals_and_loan_budget_and_tests_a_real_rent_limit():
    blocks=profile();original=deepcopy(blocks)
    result=moving_impact(blocks,'rent',1700,150,1200)
    assert result['remaining']==1300
    assert result['comparison']['alternative']['monthly_records'][1]['net_cash_flow']==-250
    assert goal_effects(result['comparison'])[0]['after']==3620
    alternative=result['alternative']
    assert alternative['rent']==1350 and alternative['upfront']==1200
    assert alternative['comparison']['alternative']['monthly_records'][1]['net_cash_flow']==0
    assert goal_effects(alternative['comparison'])[0]['after']==4220
    assert blocks==original
    too_much=moving_impact(blocks,'rent','1350.01',150,1200)
    assert goal_effects(too_much['comparison'])[0]['after']<4220


def test_unfunded_move_does_not_simulate_a_paid_upfront_bill():
    result=moving_impact(profile(),'rent',1700,150,3000)
    assert result['comparison'] is None and result['remaining'] is None
    assert result['gap']==500
    assert result['alternative']['upfront']==2500
    assert result['alternative']['rent']==1350


def test_negative_cost_change_requires_a_recorded_expense_and_fits_it():
    with pytest.raises(ValueError,match='Choose the recorded expense'):
        moving_impact(profile(),'rent',1500,-50,100)
    result=moving_impact(profile(),'rent',1500,-50,100,reduce_id='dining')
    assert next(b for b in result['comparison']['blocks'] if b['id']=='dining')['monthly_amount']=='250.00'
    with pytest.raises(ValueError,match='cannot exceed'):
        moving_impact(profile(),'rent',1500,-301,100,reduce_id='dining')


def test_a_changed_source_cannot_apply_a_move_test():
    blocks=profile();comparison=moving_impact(blocks,'rent',1350,150,1200)['comparison']
    blocks[0]['monthly_amount']='2500'
    with pytest.raises(ValueError,match='figures changed'):
        apply_preview(blocks,comparison)


def test_rent_limit_includes_competing_goals_and_entered_debt_payments():
    baseline=profile();baseline[0]['monthly_amount']='2600'
    control=moving_impact(baseline,'rent',1700,150,1200)
    blocks=baseline+[dict(id='loan',kind='loan',name='Loan',balance='5000',annual_rate='5',monthly_payment='100'),
                      dict(id='other',kind='goal',name='Car fund',balance='0',annual_rate='0',monthly_contribution='100',target='1000',target_months=12)]
    result=moving_impact(blocks,'rent',1700,150,1200)
    assert result['alternative']['rent']<control['alternative']['rent']
    assert all(g['after']>=g['before'] for g in goal_effects(result['alternative']['comparison']))
