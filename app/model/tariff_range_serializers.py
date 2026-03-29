from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class TariffRangeBase(BaseModel):
    tariff_version_id: int = Field(gt=0)
    range_min: Decimal
    range_max: Optional[Decimal] = None
    price_per_kwh: Decimal = Field(gt=0)


class TariffRangeCreate(TariffRangeBase):
    pass


class TariffRangeUpdate(BaseModel):
    range_min: Optional[Decimal] = None
    range_max: Optional[Decimal] = None
    price_per_kwh: Optional[Decimal] = Field(default=None, gt=0)


class TariffRangeResponse(TariffRangeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TariffRangeDeleteResponse(BaseModel):
    deleted: bool = True
