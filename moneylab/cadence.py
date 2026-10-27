"""Cadence normalization and optional pay/bill calendar utilities.

Financial projections use *monthly averages*, NOT an actual dated ledger.
A dated calendar is informational and does not claim a bill is funded on its
due date. Fixed weekly and biweekly cadences use 52 and 26 events/year.
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from moneylab.engine import CENT, validate_money

FREQUENCIES = {
    "weekly": ("Weekly", Decimal(52)),
    "biweekly": ("Every two weeks", Decimal(26)),
    "monthly": ("Monthly", Decimal(12)),
    "yearly": ("Yearly", Decimal(1)),
}


def monthly_equivalent(amount, frequency):
    """Normalize one per-period income/expense amount to a monthly average."""
    if frequency not in FREQUENCIES:
        raise ValueError("Frequency must be weekly, biweekly, monthly or yearly.")
    per_period = validate_money(amount, "Amount per period")
    return (per_period * FREQUENCIES[frequency][1] / Decimal(12)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def validate_schedule_date(value):
    """Accept only ISO YYYY-MM-DD strings, or None for no schedule."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Next occurrence must use YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Next occurrence must be a real YYYY-MM-DD date.") from None
    if parsed.isoformat() != value:
        raise ValueError("Next occurrence must use YYYY-MM-DD.")
    return value


def _add_calendar_month(anchor, offset):
    """Return the offset-th month at the anchor day, clipping month end."""
    month_index = anchor.year * 12 + anchor.month - 1 + offset
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))


def upcoming_events(blocks, *, from_date=None, days=45, limit=12):
    """Get future calendar events for income/expense blocks with a next date.

    This is not a daily bank cashflow ledger: it does not simulate payment
    execution, loan contractual dates, bank balances, or time-sensitive funds.
    """
    from moneylab.blocks import validate_blocks  # Avoid cyclic imports.

    if from_date is None:
        from_date = date.today()
    if not isinstance(from_date, date) or isinstance(from_date, bool):
        raise ValueError("from_date must be a date.")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 366:
        raise ValueError("days must be 1 to 366.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be 1 to 100.")
    end = from_date + timedelta(days=days)
    events = []
    for block in validate_blocks(blocks):
        if block["kind"] not in ("income", "expense") or "next_date" not in block:
            continue
        anchor = date.fromisoformat(block["next_date"])
        freq = block.get("frequency", "monthly")
        amount = block.get("period_amount", block["monthly_amount"])
        # A validated schedule date represents an occurrence, even if old.
        if freq in ("weekly", "biweekly"):
            step = 7 if freq == "weekly" else 14
            if anchor < from_date:
                n = (from_date - anchor).days // step
                anchor += timedelta(days=n * step)
                if anchor < from_date:
                    anchor += timedelta(days=step)
            while anchor <= end:
                events.append({
                    "date": anchor.isoformat(), "id": block["id"],
                    "name": block["name"], "kind": block["kind"],
                    "amount": amount, "frequency": freq,
                })
                anchor += timedelta(days=step)
        else:
            inc = 1 if freq == "monthly" else 12
            offset = max(0, (from_date.year - anchor.year) * 12
                         + from_date.month - anchor.month - 1)
            offset = (offset // inc) * inc
            current = _add_calendar_month(anchor, offset)
            while current < from_date:
                offset += inc
                current = _add_calendar_month(anchor, offset)
            while current <= end:
                events.append({
                    "date": current.isoformat(), "id": block["id"],
                    "name": block["name"], "kind": block["kind"],
                    "amount": amount, "frequency": freq,
                })
                offset += inc
                current = _add_calendar_month(anchor, offset)
    return sorted(events, key=lambda event: (event["date"], event["kind"], event["name"]))[:limit]
