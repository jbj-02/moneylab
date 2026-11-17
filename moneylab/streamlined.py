"""Small, immutable task proposals evaluated by the existing Python engine."""
from decimal import Decimal

from moneylab.blocks import serialize_blocks
from moneylab.engine import CENT, ZERO, validate_money
from moneylab.planning import preview, signature
from moneylab.scenario_changes import apply_scenario_changes


def cash_total(blocks):
    return sum((Decimal(b['balance']) for b in blocks if b['kind']=='cash'), ZERO)


def goal_effects(comparison):
    old={g['id']:g for g in comparison['baseline']['goals']}
    return [{'name':g['name'],'deadline':g['target_months'],'before':old[g['id']]['projected_at_deadline'],
             'after':g['projected_at_deadline'],'target':g['target']}
            for g in comparison['alternative']['goals'] if g['id'] in old]


def purchase_impact(blocks, price):
    items=serialize_blocks(blocks)
    amount=validate_money(price,'Purchase price')
    if amount<=ZERO:
        raise ValueError('Enter a purchase price greater than $0.')
    cash=cash_total(items)
    if amount>cash:
        return dict(price=amount,cash=cash,remaining=None,gap=amount-cash,comparison=None)
    candidate=apply_scenario_changes(items,[dict(operation='one_time_cash',amount=amount)])
    return dict(price=amount,cash=cash,remaining=cash-amount,gap=ZERO,
                comparison=preview(items,candidate,title='Purchase'))


def move_candidate(blocks, housing_id, rent, extra, upfront, *, reduce_id=None):
    """Replace an identified housing cost, keeping other entries and goals intact."""
    items=serialize_blocks(blocks)
    amount=validate_money(rent,'New rent')
    upfront=validate_money(upfront,'Upfront costs')
    delta=Decimal(str(extra))
    if not delta.is_finite() or abs(delta)>Decimal('100000000') or delta!=delta.quantize(CENT):
        raise ValueError('Enter a monthly cost change in dollars and cents.')
    if housing_id is not None:
        if not any(b['id']==housing_id and b['kind']=='expense' for b in items):
            raise ValueError('Choose the recorded housing expense to replace.')
        changes=[dict(operation='set_monthly',block_id=housing_id,amount=amount)]
    else:
        changes=[dict(operation='add_monthly_expense',name='Housing after move',amount=amount)]
    if delta>ZERO:
        changes.append(dict(operation='add_monthly_expense',name='Other cost changes after move',amount=delta))
    elif delta<ZERO:
        entry=next((b for b in items if b['id']==reduce_id and b['kind']=='expense' and b['id']!=housing_id),None)
        if entry is None:
            raise ValueError('Choose the recorded expense that would decrease.')
        updated=Decimal(entry['monthly_amount'])+delta
        if updated<ZERO:
            raise ValueError('The reduction cannot exceed that recorded expense.')
        changes.append(dict(operation='set_monthly',block_id=reduce_id,amount=updated))
    changes.append(dict(operation='one_time_cash',amount=upfront))
    candidate=apply_scenario_changes(items,changes)
    return preview(items,candidate,title='Moving plan')


def _viable(comparison):
    if comparison['alternative']['monthly_records'][1]['net_cash_flow']<ZERO:
        return False
    if any(a['unfunded_shortfall']>b['unfunded_shortfall'] for b,a in
           zip(comparison['baseline']['monthly_records'],comparison['alternative']['monthly_records'])):
        return False
    return all(g['after']>=g['before'] for g in goal_effects(comparison))


def moving_impact(blocks, housing_id, rent, extra, upfront, *, reduce_id=None):
    items=serialize_blocks(blocks)
    rent=validate_money(rent,'New rent')
    upfront=validate_money(upfront,'Upfront costs')
    cash=cash_total(items)
    # A recurring-cost-only simulation remains useful when the upfront bill
    # cannot be paid. It is labeled separately, never treated as a funded move.
    recurring=move_candidate(items,housing_id,rent,extra,ZERO,reduce_id=reduce_id)
    full=move_candidate(items,housing_id,rent,extra,upfront,reduce_id=reduce_id) if upfront<=cash else None
    result=dict(rent=rent,extra=Decimal(str(extra)),upfront=upfront,cash=cash,
                remaining=cash-upfront if full else None,gap=max(upfront-cash,ZERO),
                comparison=full,recurring=recurring,alternative=None,source_signature=signature(items))
    if full and _viable(full):
        return result
    # A budget to test, not a claimed rent offer or an assumed fee reduction.
    # Search includes existing debt, routing, account transfers and all goals.
    limit=min(upfront,cash)
    lowest=move_candidate(items,housing_id,ZERO,extra,limit,reduce_id=reduce_id)
    if not _viable(lowest):
        return result
    low,high=0,int(rent/CENT)
    while low<high:
        middle=(low+high+1)//2
        trial=move_candidate(items,housing_id,middle*CENT,extra,limit,reduce_id=reduce_id)
        if _viable(trial):
            low=middle
        else:
            high=middle-1
    option=move_candidate(items,housing_id,low*CENT,extra,limit,reduce_id=reduce_id)
    result['alternative']=dict(rent=low*CENT,upfront=limit,comparison=option)
    return result
