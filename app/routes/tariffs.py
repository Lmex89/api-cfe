from typing import List

from fastapi import APIRouter, Depends, Query, status

from common.api.responses import responses as HTTP_RESPONSES
from common.services.auth_dependency import get_current_user
from model.tariff_serializers import (
    TariffCreate,
    TariffDeleteResponse,
    TariffResponse,
    TariffUpdate,
)
from services import tariff_handler

router = APIRouter(
    prefix="/tariffs",
    tags=["tariffs"],
    responses=HTTP_RESPONSES,
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=TariffResponse, status_code=status.HTTP_201_CREATED)
def create_tariff(payload: TariffCreate) -> TariffResponse:
    return tariff_handler.create_tariff(payload)


@router.get("", response_model=List[TariffResponse])
def list_tariffs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[TariffResponse]:
    return tariff_handler.list_tariffs(limit=limit, offset=offset)


@router.get("/{tariff_id}", response_model=TariffResponse)
def get_tariff(tariff_id: int) -> TariffResponse:
    return tariff_handler.get_tariff(tariff_id)


@router.put("/{tariff_id}", response_model=TariffResponse)
def update_tariff(tariff_id: int, payload: TariffUpdate) -> TariffResponse:
    return tariff_handler.update_tariff(tariff_id, payload)


@router.delete("/{tariff_id}", response_model=TariffDeleteResponse)
def delete_tariff(tariff_id: int) -> TariffDeleteResponse:
    tariff_handler.delete_tariff(tariff_id)
    return TariffDeleteResponse(deleted=True)
