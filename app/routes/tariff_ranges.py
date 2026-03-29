from typing import List, Optional

from fastapi import APIRouter, Query, status

from common.api.responses import responses as HTTP_RESPONSES
from model.tariff_range_serializers import (
    TariffRangeCreate,
    TariffRangeDeleteResponse,
    TariffRangeResponse,
    TariffRangeUpdate,
)
from services import tariff_range_handler

router = APIRouter(prefix="/tariff-ranges", tags=["tariff-ranges"], responses=HTTP_RESPONSES)


@router.post("", response_model=TariffRangeResponse, status_code=status.HTTP_201_CREATED)
def create_tariff_range(payload: TariffRangeCreate) -> TariffRangeResponse:
    return tariff_range_handler.create_tariff_range(payload)


@router.get("", response_model=List[TariffRangeResponse])
def list_tariff_ranges(
    tariff_version_id: Optional[int] = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[TariffRangeResponse]:
    return tariff_range_handler.list_tariff_ranges(
        tariff_version_id=tariff_version_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{tariff_range_id}", response_model=TariffRangeResponse)
def get_tariff_range(tariff_range_id: int) -> TariffRangeResponse:
    return tariff_range_handler.get_tariff_range(tariff_range_id)


@router.put("/{tariff_range_id}", response_model=TariffRangeResponse)
def update_tariff_range(
    tariff_range_id: int,
    payload: TariffRangeUpdate,
) -> TariffRangeResponse:
    return tariff_range_handler.update_tariff_range(tariff_range_id, payload)


@router.delete("/{tariff_range_id}", response_model=TariffRangeDeleteResponse)
def delete_tariff_range(tariff_range_id: int) -> TariffRangeDeleteResponse:
    tariff_range_handler.delete_tariff_range(tariff_range_id)
    return TariffRangeDeleteResponse(deleted=True)
