from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class BillingPeriod:
    household_id: int
    start_date: date
    end_date: date
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
