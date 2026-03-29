from datetime import date
from typing import List, Optional

from fastapi import HTTPException
from starlette.status import HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from db.url_uow import UrlShortenerUnitofWork
from model.domain.meter_reading_model import MeterReading
from model.meter_reading_serializers import (
    MeterReadingCreate,
    MeterReadingResponse,
    MeterReadingUpdate,
)


def create_meter_reading(payload: MeterReadingCreate) -> MeterReadingResponse:
    with UrlShortenerUnitofWork() as uow:
        existing = uow.meter_reading_repository.get_by_household_and_date(
            household_id=payload.household_id,
            reading_date=payload.reading_date,
        )
        if existing:
            raise HTTPException(
                status_code=HTTP_409_CONFLICT,
                detail="A meter reading for this household and date already exists",
            )

        meter_reading = MeterReading(
            household_id=payload.household_id,
            reading_date=payload.reading_date,
            reading_kwh=payload.reading_kwh,
            is_initial=payload.is_initial,
        )
        uow.meter_reading_repository.add(meter_reading)
        uow.commit()
        return MeterReadingResponse.model_validate(meter_reading)


def get_meter_reading(meter_reading_id: int) -> MeterReadingResponse:
    with UrlShortenerUnitofWork() as uow:
        meter_reading = uow.meter_reading_repository.get(meter_reading_id)
        if not meter_reading:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Meter reading not found",
            )
        return MeterReadingResponse.model_validate(meter_reading)


def list_meter_readings(
    household_id: Optional[int] = None,
    reading_date_from: Optional[date] = None,
    reading_date_to: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[MeterReadingResponse]:
    with UrlShortenerUnitofWork() as uow:
        records = uow.meter_reading_repository.list(
            household_id=household_id,
            reading_date_from=reading_date_from,
            reading_date_to=reading_date_to,
            limit=limit,
            offset=offset,
        )
        return [MeterReadingResponse.model_validate(item) for item in records]


def update_meter_reading(
    meter_reading_id: int, payload: MeterReadingUpdate
) -> MeterReadingResponse:
    with UrlShortenerUnitofWork() as uow:
        meter_reading = uow.meter_reading_repository.get(meter_reading_id)
        if not meter_reading:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Meter reading not found",
            )

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(meter_reading, field, value)

        uow.meter_reading_repository.add(meter_reading)
        uow.commit()
        return MeterReadingResponse.model_validate(meter_reading)


def delete_meter_reading(meter_reading_id: int) -> None:
    with UrlShortenerUnitofWork() as uow:
        meter_reading = uow.meter_reading_repository.get(meter_reading_id)
        if not meter_reading:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Meter reading not found",
            )
        uow.meter_reading_repository.delete(meter_reading)
        uow.commit()
