"""Date utilities for period-based business rules."""

from calendar import monthrange
from datetime import date, timedelta


def first_day_of_month(value: date) -> date:
    return value.replace(day=1)


def last_day_of_month(value: date) -> date:
    return value.replace(day=monthrange(value.year, value.month)[1])


def midpoint_date(start_date: date, end_date: date) -> date:
    """Return midpoint date using floor((end - start) / 2) offset."""
    if end_date < start_date:
        raise ValueError("end_date must be greater than or equal to start_date")
    return start_date + timedelta(days=(end_date - start_date).days // 2)
