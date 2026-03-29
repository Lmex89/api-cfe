from typing import List

from fastapi import APIRouter, Query, status

from common.api.responses import responses as HTTP_RESPONSES
from model.household_serializers import (
    HouseholdCreate,
    HouseholdDeleteResponse,
    HouseholdResponse,
    HouseholdUpdate,
)
from services import household_handler

router = APIRouter(prefix="/households", tags=["households"], responses=HTTP_RESPONSES)


@router.post("", response_model=HouseholdResponse, status_code=status.HTTP_201_CREATED)
def create_household(payload: HouseholdCreate) -> HouseholdResponse:
    return household_handler.create_household(payload)


@router.get("", response_model=List[HouseholdResponse])
def list_households(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[HouseholdResponse]:
    return household_handler.list_households(limit=limit, offset=offset)


@router.get("/{household_id}", response_model=HouseholdResponse)
def get_household(household_id: int) -> HouseholdResponse:
    return household_handler.get_household(household_id)


@router.put("/{household_id}", response_model=HouseholdResponse)
def update_household(household_id: int, payload: HouseholdUpdate) -> HouseholdResponse:
    return household_handler.update_household(household_id, payload)


@router.delete("/{household_id}", response_model=HouseholdDeleteResponse)
def delete_household(household_id: int) -> HouseholdDeleteResponse:
    household_handler.delete_household(household_id)
    return HouseholdDeleteResponse(deleted=True)
