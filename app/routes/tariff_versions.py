from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from common.api.responses import responses as HTTP_RESPONSES
from common.services.auth_dependency import get_current_user
from model.tariff_version_serializers import (
    TariffVersionCreate,
    TariffVersionDeleteResponse,
    TariffVersionResponse,
    TariffVersionUpdate,
)
from services import tariff_version_handler

router = APIRouter(
    prefix="/tariff-versions",
    tags=["tariff-versions"],
    responses=HTTP_RESPONSES,
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=TariffVersionResponse, status_code=status.HTTP_201_CREATED)
def create_tariff_version(payload: TariffVersionCreate) -> TariffVersionResponse:
    return tariff_version_handler.create_tariff_version(payload)


@router.get("", response_model=List[TariffVersionResponse])
def list_tariff_versions(
    tariff_id: Optional[int] = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[TariffVersionResponse]:
    return tariff_version_handler.list_tariff_versions(
        tariff_id=tariff_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{tariff_version_id}", response_model=TariffVersionResponse)
def get_tariff_version(tariff_version_id: int) -> TariffVersionResponse:
    return tariff_version_handler.get_tariff_version(tariff_version_id)


@router.put("/{tariff_version_id}", response_model=TariffVersionResponse)
def update_tariff_version(
    tariff_version_id: int,
    payload: TariffVersionUpdate,
) -> TariffVersionResponse:
    return tariff_version_handler.update_tariff_version(tariff_version_id, payload)


@router.delete("/{tariff_version_id}", response_model=TariffVersionDeleteResponse)
def delete_tariff_version(tariff_version_id: int) -> TariffVersionDeleteResponse:
    tariff_version_handler.delete_tariff_version(tariff_version_id)
    return TariffVersionDeleteResponse(deleted=True)
