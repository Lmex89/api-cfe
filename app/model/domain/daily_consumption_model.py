from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class DailyConsumption:
    household_id: int
    consumption_date: date
    kwh: Decimal
    id: Optional[int] = None
    created_at: Optional[datetime] = None
