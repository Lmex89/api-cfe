"""The one module that derives Consumo from Lecturas (history rows, totals, daily average)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional, Sequence, Tuple

from model.domain.meter_reading_model import MeterReading


def consumption_between(first: MeterReading, last: MeterReading) -> Decimal:
    """Consumo from `first` to `last` (a Lectura with itself gives 0)."""
    return last.reading_kwh - first.reading_kwh


def daily_average(consumption, start: date, end: date) -> Decimal:
    """Consumo per day over [start, end]; a zero-day range counts as one day."""
    return Decimal(consumption) / Decimal((end - start).days or 1)


@dataclass(frozen=True)
class HistoryRow:
    reading: MeterReading
    consumption_since_last: Optional[float]
    days_since_last: Optional[int]
    average_daily_consumption: Optional[float]
    cumulative_consumption: Decimal  # from the first reading to this one


def build_history_rows(
    readings: Sequence[MeterReading],
) -> Tuple[List[HistoryRow], float]:
    """Rows for date-ordered readings plus the total Consumo (sum of intervals)."""
    rows: List[HistoryRow] = []
    total = 0.0
    for i, reading in enumerate(readings):
        cumulative = consumption_between(readings[0], reading)
        if i == 0:
            rows.append(HistoryRow(reading, None, None, None, cumulative))
            continue
        prev = readings[i - 1]
        consumption = float(consumption_between(prev, reading))
        days = (reading.reading_date - prev.reading_date).days
        avg = consumption / days if days > 0 else None
        total += consumption
        rows.append(HistoryRow(reading, consumption, days, avg, cumulative))
    return rows, total
