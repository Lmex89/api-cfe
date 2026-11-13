"""Pure derivation of meter-reading history rows (Consumo, days, daily average)."""

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from model.domain.meter_reading_model import MeterReading


@dataclass(frozen=True)
class HistoryRow:
    reading: MeterReading
    consumption_since_last: Optional[float]
    days_since_last: Optional[int]
    average_daily_consumption: Optional[float]
    cumulative_consumption: float  # from the first reading to this one


def build_history_rows(
    readings: Sequence[MeterReading],
) -> Tuple[List[HistoryRow], float]:
    """Rows for date-ordered readings plus the total Consumo (sum of intervals)."""
    rows: List[HistoryRow] = []
    total = 0.0
    for i, reading in enumerate(readings):
        cumulative = float(reading.reading_kwh - readings[0].reading_kwh)
        if i == 0:
            rows.append(HistoryRow(reading, None, None, None, cumulative))
            continue
        prev = readings[i - 1]
        consumption = float(reading.reading_kwh - prev.reading_kwh)
        days = (reading.reading_date - prev.reading_date).days
        avg = consumption / days if days > 0 else None
        total += consumption
        rows.append(HistoryRow(reading, consumption, days, avg, cumulative))
    return rows, total
