from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class HouseholdTariffBase(BaseModel):
    household_id: int = Field(gt=0)
    tariff_id: int = Field(gt=0)
    start_date: date
    end_date: Optional[date] = None


class HouseholdTariffCreate(HouseholdTariffBase):
    pass


class HouseholdTariffUpdate(BaseModel):
    tariff_id: Optional[int] = Field(default=None, gt=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class HouseholdTariffResponse(HouseholdTariffBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HouseholdTariffDeleteResponse(BaseModel):
    deleted: bool = True
