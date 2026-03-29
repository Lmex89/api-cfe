from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class MeterReading:
    household_id: int
    reading_date: date
    reading_kwh: Decimal
    is_initial: bool = False
    id: Optional[int] = None
    created_at: Optional[datetime] = None