from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class BillingPeriodBase(BaseModel):
    household_id: int = Field(gt=0)
    start_date: date
    end_date: date


class BillingPeriodCreate(BillingPeriodBase):
    pass


class BillingPeriodUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class BillingPeriodResponse(BillingPeriodBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BillingPeriodDeleteResponse(BaseModel):
    deleted: bool = True
