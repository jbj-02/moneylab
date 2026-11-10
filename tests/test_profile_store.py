"""Continuity, privacy boundaries, unknowns and old workspace migration."""
import json
import os
import pytest
from moneylab.plan_setup import EXPENSES, build_profile
from moneylab.profile_store import LocalProfileStore, configured_local_store, plan_from_json, plan_to_json
from moneylab.workspace import workspace_to_json
from moneylab.blocks import profile_to_json


def answers():
    return dict(priority='Build an emergency fund', target='10000', goal_months=12,
                income='3000', checking='1000', savings='8000', goal_saved='6000',
                goal_monthly='200', debt_status='I have no debt', **{k:'0' for k in EXPENSES})


def test_setup_never_counts_goal_money_twice():
    blocks, metadata = build_profile(answers())
    balances = {b['id']: b.get('balance') for b in blocks}
    assert balances['setup_savings'] == '2000.00'
    assert balances['setup_goal'] == '6000.00'
    assert metadata['unknown'] == []


def test_skipped_balances_are_unknown_and_explicit_zeros_are_known():
    data = dict(answers(), priority='Understand my money', checking=None, savings=None, debt_status="I'll add this later")
    blocks, metadata = build_profile(data)
    assert set(metadata['unknown']) == {'checking', 'savings', 'debts'}
    assert any(b['kind'] == 'expense' and b['monthly_amount'] == '0.00' for b in blocks)
    assert not any(b['kind'] == 'cash' for b in blocks)
    decoded = plan_from_json(plan_to_json(blocks, [], [], metadata))
    assert decoded[3] == metadata


@pytest.mark.parametrize('change', [dict(goal_saved='8001'), dict(savings=None), dict(debt_status='I have debt'), dict(target='0')])
def test_incomplete_or_double_counted_setup_cannot_commit(change):
    with pytest.raises(ValueError):
        build_profile(dict(answers(), **change))


def test_old_profiles_and_both_workspace_versions_migrate_without_loss():
    blocks, _ = build_profile(answers())
    for text in (profile_to_json(blocks), workspace_to_json(blocks, []), workspace_to_json(blocks, [], [])):
        restored, _, _, metadata = plan_from_json(text)
        assert restored == blocks
        assert metadata['unknown'] == ['debts']


def test_local_store_reopen_and_deletion_preserve_conflict_generation(tmp_path):
    blocks, metadata = build_profile(answers())
    text = plan_to_json(blocks, [], [], metadata)
    store = LocalProfileStore(tmp_path / 'private')
    assert store.load() == (None, 0)
    assert store.save(text, 0) == 1
    reopened = LocalProfileStore(tmp_path / 'private')
    assert reopened.load() == (text, 1)
    assert (store.path.stat().st_mode & 0o777) == 0o600
    assert (store.path.parent.stat().st_mode & 0o777) == 0o700
    reopened.delete(1)
    assert store.load() == (None, 2)
    with pytest.raises(ValueError, match='Another session'):
        store.save(text, 1)
    assert b'Take-home pay' not in store.path.read_bytes()


def test_shared_deployment_cannot_enable_anonymous_local_storage(tmp_path, monkeypatch):
    monkeypatch.setenv('MONEYLAB_LOCAL_STORE', str(tmp_path / 'private'))
    for address in (None, '', '0.0.0.0', '::', 'example.com'):
        with pytest.raises(ValueError, match='loopback'):
            configured_local_store(address)
    assert isinstance(configured_local_store('127.0.0.1'), LocalProfileStore)
    monkeypatch.delenv('MONEYLAB_LOCAL_STORE')
    assert configured_local_store('0.0.0.0') is None


def test_bad_import_is_validated_before_writing(tmp_path):
    store = LocalProfileStore(tmp_path / 'private')
    with pytest.raises(ValueError):
        store.save('{"schema_version":4}', 0)
    assert store.load() == (None, 0)
    with pytest.raises(ValueError):
        plan_from_json(' ' * 200001)


def test_separate_local_directories_cannot_read_each_others_plans(tmp_path):
    blocks, metadata = build_profile(answers())
    a, b = LocalProfileStore(tmp_path / 'a'), LocalProfileStore(tmp_path / 'b')
    a.save(plan_to_json(blocks, [], [], metadata), 0)
    assert b.load() == (None, 0)


def test_setup_preserves_rate_precision_from_the_financial_engine():
    blocks, _ = build_profile(dict(answers(), debt_status='I have debt',
                                   debt_balance='1000', debt_rate='5.125', debt_payment='100'))
    assert blocks[-1]['annual_rate'] == '5.125'


@pytest.mark.parametrize('payload', [
    {'schema_version':True,'blocks':[]},
    {'schema_version':1,'blocks':[{'kind':[]}]},
    {'schema_version':2,'blocks':[],'scenarios':[{'name':[], 'expense_id':{}, 'monthly_change':0}]},
])
def test_malformed_imports_report_validation_errors_instead_of_crashing(payload):
    with pytest.raises(ValueError):
        plan_from_json(json.dumps(payload))
