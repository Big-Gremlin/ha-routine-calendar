"""Date arithmetic for routine intervals.

Months and years preserve the "intended" day-of-month and clamp to the
last valid day if the target month is shorter (Jan 31 + 1 month -> Feb 28/29).
"""
from __future__ import annotations

import calendar
from datetime import date

from .const import UNIT_DAYS, UNIT_MONTHS, UNIT_WEEKS, UNIT_YEARS


def add_interval(base: date, value: int, unit: str) -> date:
    """Return base + (value, unit). Raises ValueError on unknown unit."""
    if value <= 0:
        raise ValueError(f"interval value must be positive, got {value}")
    if unit == UNIT_DAYS:
        return _add_days(base, value)
    if unit == UNIT_WEEKS:
        return _add_days(base, value * 7)
    if unit == UNIT_MONTHS:
        return _add_months(base, value)
    if unit == UNIT_YEARS:
        return _add_months(base, value * 12)
    raise ValueError(f"unknown interval unit: {unit}")


def _add_days(base: date, days: int) -> date:
    from datetime import timedelta
    return base + timedelta(days=days)


def _add_months(base: date, months: int) -> date:
    total = base.month - 1 + months
    new_year = base.year + total // 12
    new_month = total % 12 + 1
    last_day = calendar.monthrange(new_year, new_month)[1]
    return date(new_year, new_month, min(base.day, last_day))
