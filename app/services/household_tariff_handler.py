from typing import List, Optional

from fastapi import HTTPException
from starlette.status import HTTP_404_NOT_FOUND

from db.uow import TariffConsumptionUnitofWork
from model.domain.household_tariff_model import HouseholdTariff
from model.household_tariff_serializers import (
    HouseholdTariffCreate,
    HouseholdTariffResponse,
    HouseholdTariffUpdate,
)


def create_household_tariff(payload: HouseholdTariffCreate) -> HouseholdTariffResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = HouseholdTariff(**payload.model_dump())
        uow.household_tariff_repository.add(item)
        uow.commit()
        return HouseholdTariffResponse.model_validate(item)


def get_household_tariff(household_tariff_id: int) -> HouseholdTariffResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.household_tariff_repository.get(household_tariff_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Household tariff not found")
        return HouseholdTariffResponse.model_validate(item)


def list_household_tariffs(
    household_id: Optional[int] = None,
    tariff_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[HouseholdTariffResponse]:
    with TariffConsumptionUnitofWork() as uow:
        records = uow.household_tariff_repository.list(
            household_id=household_id,
            tariff_id=tariff_id,
            limit=limit,
            offset=offset,
        )
        return [HouseholdTariffResponse.model_validate(item) for item in records]


def update_household_tariff(
    household_tariff_id: int, payload: HouseholdTariffUpdate
) -> HouseholdTariffResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.household_tariff_repository.get(household_tariff_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Household tariff not found")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)

        uow.household_tariff_repository.add(item)
        uow.commit()
        return HouseholdTariffResponse.model_validate(item)


def delete_household_tariff(household_tariff_id: int) -> None:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.household_tariff_repository.get(household_tariff_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Household tariff not found")
        uow.household_tariff_repository.delete(item)
        uow.commit()
