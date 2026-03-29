from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TariffBase(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    description: Optional[str] = Field(default=None, max_length=255)


class TariffCreate(TariffBase):
    pass


class TariffUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=10)
    description: Optional[str] = Field(default=None, max_length=255)


class TariffResponse(TariffBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TariffDeleteResponse(BaseModel):
    deleted: bool = True
