from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HouseholdBase(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)


class HouseholdCreate(HouseholdBase):
    pass


class HouseholdUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)


class HouseholdResponse(HouseholdBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HouseholdDeleteResponse(BaseModel):
    deleted: bool = True
