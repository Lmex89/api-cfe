from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TariffVersionBase(BaseModel):
    tariff_id: int = Field(gt=0)
    year: int = Field(ge=1900, le=3000)
    month: int = Field(ge=1, le=12)


class TariffVersionCreate(TariffVersionBase):
    pass


class TariffVersionUpdate(BaseModel):
    year: Optional[int] = Field(default=None, ge=1900, le=3000)
    month: Optional[int] = Field(default=None, ge=1, le=12)


class TariffVersionResponse(TariffVersionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TariffVersionDeleteResponse(BaseModel):
    deleted: bool = True
