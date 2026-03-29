from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class HouseholdTariff:
    household_id: int
    tariff_id: int
    start_date: date
    end_date: Optional[date] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
