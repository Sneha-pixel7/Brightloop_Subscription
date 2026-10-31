"""Money and billing-period helpers. Money is ALWAYS Decimal, never float."""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from dateutil.relativedelta import relativedelta

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

# Shared kwargs so every money column has the same precision.
MONEY_FIELD = {"max_digits": 14, "decimal_places": 2}


def money(value) -> Decimal:
    """Quantize any numeric-like value to 2 decimal places (half-up)."""
    if isinstance(value, float):
        raise TypeError("Floats are not allowed for money; pass Decimal or str.")
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def add_period(start: date, billing_period: str, count: int = 1) -> date:
    """Return `start` advanced by `count` billing periods."""
    if billing_period == "daily":
        return start + timedelta(days=count)
    if billing_period == "weekly":
        return start + timedelta(weeks=count)
    if billing_period == "monthly":
        return start + relativedelta(months=count)
    if billing_period == "yearly":
        return start + relativedelta(years=count)
    raise ValueError(f"Unknown billing period: {billing_period!r}")


def period_end_for(start: date, billing_period: str) -> date:
    """Last day (inclusive) of the period that begins on `start`."""
    return add_period(start, billing_period) - timedelta(days=1)
