from datetime import date
from typing import List, Optional

from fastapi import HTTPException
from loguru import logger
from starlette.status import HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from db.uow import TariffConsumptionUnitofWork
from model.domain.meter_reading_model import MeterReading
from model.meter_reading_serializers import (
    MeterReadingCreate,
    MeterReadingResponse,
    MeterReadingUpdate,
)


def create_meter_reading(payload: MeterReadingCreate) -> MeterReadingResponse:
    log = logger.bind(
        operation="create_meter_reading",
        household_id=payload.household_id,
        reading_date=str(payload.reading_date),
    )
    log.info(
        "Create meter reading requested for household_id={} on reading_date={}",
        payload.household_id,
        payload.reading_date,
    )
    log.debug(
        "Create payload details: reading_kwh={}, is_initial={}",
        payload.reading_kwh,
        payload.is_initial,
    )

    with TariffConsumptionUnitofWork() as uow:
        existing = uow.meter_reading_repository.get_by_household_and_date(
            household_id=payload.household_id,
            reading_date=payload.reading_date,
        )
        if existing:
            log.info(
                "Create rejected for household_id={} on reading_date={} because record already exists",
                payload.household_id,
                payload.reading_date,
            )
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
        log.info(
            "Meter reading created successfully with meter_reading_id={} for household_id={}",
            meter_reading.id,
            meter_reading.household_id,
        )
        return MeterReadingResponse.model_validate(meter_reading)


def get_meter_reading(meter_reading_id: int) -> MeterReadingResponse:
    log = logger.bind(operation="get_meter_reading", meter_reading_id=meter_reading_id)
    log.info("Get meter reading requested for meter_reading_id={}", meter_reading_id)

    with TariffConsumptionUnitofWork() as uow:
        meter_reading = uow.meter_reading_repository.get(meter_reading_id)
        if not meter_reading:
            log.info(
                "Meter reading not found for meter_reading_id={}", meter_reading_id
            )
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Meter reading not found",
            )
        log.debug(
            "Meter reading retrieved: meter_reading_id={}, household_id={}, reading_date={}, reading_kwh={}",
            meter_reading.id,
            meter_reading.household_id,
            meter_reading.reading_date,
            meter_reading.reading_kwh,
        )
        return MeterReadingResponse.model_validate(meter_reading)


def list_meter_readings(
    household_id: Optional[int] = None,
    billing_period_id: Optional[int] = None,
    reading_date_from: Optional[date] = None,
    reading_date_to: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[MeterReadingResponse]:
    log = logger.bind(operation="list_meter_readings")
    log.info(
        "List meter readings requested with household_id={}, billing_period_id={}, reading_date_from={}, reading_date_to={}, limit={}, offset={}",
        household_id,
        billing_period_id,
        reading_date_from,
        reading_date_to,
        limit,
        offset,
    )

    with TariffConsumptionUnitofWork() as uow:
        if billing_period_id is not None:
            billing_period = uow.billing_period_repository.get(billing_period_id)
            if not billing_period:
                log.info(
                    "Billing period not found for billing_period_id={}",
                    billing_period_id,
                )
                raise HTTPException(
                    status_code=HTTP_404_NOT_FOUND,
                    detail="Billing period not found",
                )

            if household_id is None:
                household_id = billing_period.household_id
            if reading_date_from is None:
                reading_date_from = billing_period.start_date
            if reading_date_to is None:
                reading_date_to = billing_period.end_date

        records = uow.meter_reading_repository.list(
            household_id=household_id,
            reading_date_from=reading_date_from,
            reading_date_to=reading_date_to,
            limit=limit,
            offset=offset,
        )
        record_ids = [item.id for item in records]
        log.info(
            "List meter readings completed with total_records={} (offset={}, limit={})",
            len(records),
            offset,
            limit,
        )
        log.debug("List returned meter_reading_ids={}", record_ids)
        return [MeterReadingResponse.model_validate(item) for item in records]


def update_meter_reading(
    meter_reading_id: int, payload: MeterReadingUpdate
) -> MeterReadingResponse:
    log = logger.bind(
        operation="update_meter_reading", meter_reading_id=meter_reading_id
    )
    log.info("Update meter reading requested for meter_reading_id={}", meter_reading_id)

    with TariffConsumptionUnitofWork() as uow:
        meter_reading = uow.meter_reading_repository.get(meter_reading_id)
        if not meter_reading:
            log.info(
                "Update rejected because meter_reading_id={} was not found",
                meter_reading_id,
            )
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Meter reading not found",
            )

        update_data = payload.model_dump(exclude_unset=True)
        new_reading_date = update_data.get("reading_date")
        if new_reading_date is not None and new_reading_date != meter_reading.reading_date:
            existing = uow.meter_reading_repository.get_by_household_and_date(
                household_id=meter_reading.household_id,
                reading_date=new_reading_date,
            )
            if existing and existing.id != meter_reading.id:
                log.warning(
                    "Update rejected for meter_reading_id={} because household_id={} already has a reading on {}",
                    meter_reading_id,
                    meter_reading.household_id,
                    new_reading_date,
                )
                raise HTTPException(
                    status_code=HTTP_409_CONFLICT,
                    detail="A meter reading for this household and date already exists",
                )

        log.debug(
            "Applying update to meter_reading_id={} with fields={}",
            meter_reading_id,
            list(update_data.keys()),
        )
        for field, value in update_data.items():
            setattr(meter_reading, field, value)

        uow.meter_reading_repository.add(meter_reading)
        uow.commit()
        log.info(
            "Meter reading updated successfully for meter_reading_id={} (household_id={})",
            meter_reading.id,
            meter_reading.household_id,
        )
        return MeterReadingResponse.model_validate(meter_reading)


def delete_meter_reading(meter_reading_id: int) -> None:
    log = logger.bind(
        operation="delete_meter_reading", meter_reading_id=meter_reading_id
    )
    log.info("Delete meter reading requested for meter_reading_id={}", meter_reading_id)

    with TariffConsumptionUnitofWork() as uow:
        meter_reading = uow.meter_reading_repository.get(meter_reading_id)
        if not meter_reading:
            log.info(
                "Delete rejected because meter_reading_id={} was not found",
                meter_reading_id,
            )
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Meter reading not found",
            )
        log.debug(
            "Deleting meter reading meter_reading_id={} for household_id={} on reading_date={}",
            meter_reading.id,
            meter_reading.household_id,
            meter_reading.reading_date,
        )
        uow.meter_reading_repository.delete(meter_reading)
        uow.commit()
        log.info(
            "Meter reading deleted successfully for meter_reading_id={}",
            meter_reading_id,
        )
