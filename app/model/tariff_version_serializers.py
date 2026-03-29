from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TariffVersionBase(BaseModel):
    tariff_id: int = Field(gt=0)
    start_date: date
    end_date: Optional[date] = None


class TariffVersionCreate(TariffVersionBase):
    pass


class TariffVersionUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class TariffVersionResponse(TariffVersionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TariffVersionDeleteResponse(BaseModel):
    deleted: bool = True
