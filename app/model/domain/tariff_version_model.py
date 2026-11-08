from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TariffVersion:
    tariff_id: int
    year: int
    month: int
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
