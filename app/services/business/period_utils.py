"""Date utilities for period-based business rules."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import List


def first_day_of_month(value: date) -> date:
    return value.replace(day=1)


def last_day_of_month(value: date) -> date:
    return value.replace(day=monthrange(value.year, value.month)[1])


def midpoint_date(start_date: date, end_date: date) -> date:
    """Return midpoint date using floor((end - start) / 2) offset."""
    if end_date < start_date:
        raise ValueError("end_date must be greater than or equal to start_date")
    return start_date + timedelta(days=(end_date - start_date).days // 2)


@dataclass
class MonthSegment:
    """A slice of a billing period that falls within a single calendar month."""
    year: int
    month: int
    calendar_days: int   # total days in the calendar month
    segment_days: int    # days this segment spans within the billing period
    start_date: date
    end_date: date
    capacity_factor: Decimal = Decimal("1")  # tier-capacity multiplier for this segment


def split_by_month_segments(start_date: date, end_date: date) -> List[MonthSegment]:
    """
    Split [start_date, end_date] (inclusive) into per-calendar-month segments.

    Each segment carries:
      - calendar_days: length of the full calendar month (for proration divisor)
      - segment_days:  actual days in the billing period that fall in this month
    """
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    segments: List[MonthSegment] = []
    cursor = start_date

    while cursor <= end_date:
        year, month = cursor.year, cursor.month
        cal_days = monthrange(year, month)[1]
        month_end = date(year, month, cal_days)

        seg_end = min(end_date, month_end)
        seg_days = (seg_end - cursor).days + 1

        segments.append(MonthSegment(
            year=year,
            month=month,
            calendar_days=cal_days,
            segment_days=seg_days,
            start_date=cursor,
            end_date=seg_end,
        ))

        # Advance to first day of next month
        if month == 12:
            cursor = date(year + 1, 1, 1)
        else:
            cursor = date(year, month + 1, 1)

    return segments
