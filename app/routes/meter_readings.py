from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Query, status

from common.api.responses import responses as HTTP_RESPONSES
from model.meter_reading_serializers import (
    MeterReadingCreate,
    MeterReadingDeleteResponse,
    MeterReadingResponse,
    MeterReadingUpdate,
)
from services import meter_reading_handler

router = APIRouter(prefix="/meter-readings", tags=["meter-readings"], responses=HTTP_RESPONSES)


@router.post("", response_model=MeterReadingResponse, status_code=status.HTTP_201_CREATED)
def create_meter_reading(payload: MeterReadingCreate) -> MeterReadingResponse:
    return meter_reading_handler.create_meter_reading(payload)


@router.get("", response_model=List[MeterReadingResponse])
def list_meter_readings(
    household_id: Optional[int] = Query(default=None, gt=0),
    reading_date_from: Optional[date] = None,
    reading_date_to: Optional[date] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[MeterReadingResponse]:
    return meter_reading_handler.list_meter_readings(
        household_id=household_id,
        reading_date_from=reading_date_from,
        reading_date_to=reading_date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/{meter_reading_id}", response_model=MeterReadingResponse)
def get_meter_reading(meter_reading_id: int) -> MeterReadingResponse:
    return meter_reading_handler.get_meter_reading(meter_reading_id)


@router.put("/{meter_reading_id}", response_model=MeterReadingResponse)
def update_meter_reading(
    meter_reading_id: int,
    payload: MeterReadingUpdate,
) -> MeterReadingResponse:
    return meter_reading_handler.update_meter_reading(meter_reading_id, payload)


@router.delete("/{meter_reading_id}", response_model=MeterReadingDeleteResponse)
def delete_meter_reading(meter_reading_id: int) -> MeterReadingDeleteResponse:
    meter_reading_handler.delete_meter_reading(meter_reading_id)
    return MeterReadingDeleteResponse(deleted=True)
