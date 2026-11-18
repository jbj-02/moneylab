"""Acceptance coverage for the inline, detached savings scenario."""

from copy import deepcopy
from decimal import Decimal

import pytest

from moneylab.planning import apply_preview
from moneylab.savings_change import comparison_summary, savings_scenario


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
