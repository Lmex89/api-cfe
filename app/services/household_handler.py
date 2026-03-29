from typing import List

from fastapi import HTTPException
from starlette.status import HTTP_404_NOT_FOUND

from db.url_uow import UrlShortenerUnitofWork
from model.domain.household_model import Household
from model.household_serializers import (
    HouseholdCreate,
    HouseholdResponse,
    HouseholdUpdate,
)


def create_household(payload: HouseholdCreate) -> HouseholdResponse:
    with UrlShortenerUnitofWork() as uow:
        item = Household(**payload.model_dump())
        uow.household_repository.add(item)
        uow.commit()
        return HouseholdResponse.model_validate(item)


def get_household(household_id: int) -> HouseholdResponse:
    with UrlShortenerUnitofWork() as uow:
        item = uow.household_repository.get(household_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Household not found")
        return HouseholdResponse.model_validate(item)


def list_households(limit: int = 100, offset: int = 0) -> List[HouseholdResponse]:
    with UrlShortenerUnitofWork() as uow:
        records = uow.household_repository.list(limit=limit, offset=offset)
        return [HouseholdResponse.model_validate(item) for item in records]


def update_household(household_id: int, payload: HouseholdUpdate) -> HouseholdResponse:
    with UrlShortenerUnitofWork() as uow:
        item = uow.household_repository.get(household_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Household not found")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)

        uow.household_repository.add(item)
        uow.commit()
        return HouseholdResponse.model_validate(item)


def delete_household(household_id: int) -> None:
    with UrlShortenerUnitofWork() as uow:
        item = uow.household_repository.get(household_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Household not found")
        uow.household_repository.delete(item)
        uow.commit()
