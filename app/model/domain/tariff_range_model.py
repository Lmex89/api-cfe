from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class TariffRange:
    tariff_version_id: int
    range_min: Decimal
    price_per_kwh: Decimal
    range_max: Optional[Decimal] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
