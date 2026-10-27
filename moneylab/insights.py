"""Explainable what-if comparisons grounded entirely in model results."""

from decimal import Decimal

from moneylab.engine import ZERO


def _money(amount):
    return f"${amount:,.2f}" if amount >= ZERO else f"-${abs(amount):,.2f}"


def scenario_impacts(baseline, alternative, blocks):
    """Return human-readable, deterministic impact alerts for a scenario.

    Alerts are generated only when actual simulated quantities change.
    Each item has a type ('warning', 'positive', 'info'), a heading, a text
    explanation, and an exact Decimal delta where applicable.
    """
    b = baseline["summary"]
    a = alternative["summary"]
    events = []

    def add(level, title, detail, change=None):
        events.append({"level": level, "title": title, "detail": detail, "change": change})

    b_buffer = b["unallocated_monthly_buffer"]
    a_buffer = a["unallocated_monthly_buffer"]
    if a_buffer != b_buffer:
        delta = a_buffer - b_buffer
        add(
            "warning" if delta < ZERO else "positive",
            "Monthly spending flexibility changed",
            f"The unallocated monthly buffer changed from {_money(b_buffer)} "
            f"to {_money(a_buffer)} ({_money(delta)}).",
            delta,
        )

    fields = (
        ("ending_cash_savings", "Projected checking / cash"),
        ("ending_assets", "Projected savings and investment accounts"),
        ("ending_debt", "Projected loan balance"),
        ("ending_net_position", "Projected modeled net position"),
        ("ending_unfunded_shortfall", "Unfunded cash shortfall"),
    )
    for key, description in fields:
        delta = a[key] - b[key]
        if delta == ZERO:
            continue
        worse = delta < ZERO if key not in ("ending_debt", "ending_unfunded_shortfall") else delta > ZERO
        add(
            "warning" if worse else "positive",
            description,
            f"At month {b['months']}, {description.lower()} changes "
            f"from {_money(b[key])} to {_money(a[key])} ({_money(delta)}).",
            delta,
        )

    transfer_delta = a["total_asset_contributions"] - b["total_asset_contributions"]
    if transfer_delta != ZERO:
        add(
            "warning" if transfer_delta < ZERO else "positive",
            "Savings contributions affected",
            f"Total transfers into modeled savings, goal and investment accounts "
            f"change by {_money(transfer_delta)} over the projection.",
            transfer_delta,
        )

    b_goals = {g["id"]: g for g in baseline["goals"]}
    for goal in alternative["goals"]:
        old = b_goals.get(goal["id"])
        if old is None or old["projected_at_deadline"] is None or goal["projected_at_deadline"] is None:
            continue
        change = goal["projected_at_deadline"] - old["projected_at_deadline"]
        if change == ZERO:
            continue
        level = "warning" if change < ZERO else "positive"
        status = (
            "now misses the target" if old["on_track"] and not goal["on_track"]
            else "now reaches the target" if not old["on_track"] and goal["on_track"]
            else "remains on track" if goal["on_track"]
            else "remains below target"
        )
        add(
            level, f"Goal: {goal['name']}",
            f"At month {goal['target_months']}, projected funds change by "
            f"{_money(change)}; the goal {status}.",
            change,
        )

    before = baseline["monthly_records"][-1]["balances"]
    after = alternative["monthly_records"][-1]["balances"]
    by_id = {item["id"]: item["name"] for item in blocks}
    changed_accounts = [
        (by_id.get(key, key), after.get(key, ZERO) - old_balance)
        for key, old_balance in before.items()
        if after.get(key, ZERO) != old_balance
    ]
    if changed_accounts:
        details = "; ".join(f"{name}: {_money(delta)}" for name, delta in changed_accounts)
        add("info", "Specific accounts affected", details)

    if not events:
        add(
            "info", "No change in modeled outcomes",
            "Under the current assumptions and timeline, the scenario does not "
            "change the tracked financial values or goal progress.",
        )
    return events
