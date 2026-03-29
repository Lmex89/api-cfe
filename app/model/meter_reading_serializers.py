from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class MeterReadingBase(BaseModel):
    household_id: int = Field(gt=0)
    reading_date: date
    reading_kwh: Decimal = Field(gt=0)
    is_initial: bool = False


class MeterReadingCreate(MeterReadingBase):
    pass


class MeterReadingUpdate(BaseModel):
    reading_kwh: Optional[Decimal] = Field(default=None, gt=0)
    is_initial: Optional[bool] = None


class MeterReadingResponse(MeterReadingBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MeterReadingDeleteResponse(BaseModel):
    deleted: bool = True
