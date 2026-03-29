from typing import List, Optional

from fastapi import APIRouter, Query, status

from common.api.responses import responses as HTTP_RESPONSES
from model.household_tariff_serializers import (
    HouseholdTariffCreate,
    HouseholdTariffDeleteResponse,
    HouseholdTariffResponse,
    HouseholdTariffUpdate,
)
from services import household_tariff_handler

router = APIRouter(prefix="/household-tariffs", tags=["household-tariffs"], responses=HTTP_RESPONSES)


@router.post("", response_model=HouseholdTariffResponse, status_code=status.HTTP_201_CREATED)
def create_household_tariff(payload: HouseholdTariffCreate) -> HouseholdTariffResponse:
    return household_tariff_handler.create_household_tariff(payload)


@router.get("", response_model=List[HouseholdTariffResponse])
def list_household_tariffs(
    household_id: Optional[int] = Query(default=None, gt=0),
    tariff_id: Optional[int] = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[HouseholdTariffResponse]:
    return household_tariff_handler.list_household_tariffs(
        household_id=household_id,
        tariff_id=tariff_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{household_tariff_id}", response_model=HouseholdTariffResponse)
def get_household_tariff(household_tariff_id: int) -> HouseholdTariffResponse:
    return household_tariff_handler.get_household_tariff(household_tariff_id)


@router.put("/{household_tariff_id}", response_model=HouseholdTariffResponse)
def update_household_tariff(
    household_tariff_id: int,
    payload: HouseholdTariffUpdate,
) -> HouseholdTariffResponse:
    return household_tariff_handler.update_household_tariff(household_tariff_id, payload)


@router.delete("/{household_tariff_id}", response_model=HouseholdTariffDeleteResponse)
def delete_household_tariff(household_tariff_id: int) -> HouseholdTariffDeleteResponse:
    household_tariff_handler.delete_household_tariff(household_tariff_id)
    return HouseholdTariffDeleteResponse(deleted=True)
