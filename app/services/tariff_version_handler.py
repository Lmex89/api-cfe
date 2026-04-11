from typing import List, Optional

from fastapi import HTTPException
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
)

from db.uow import TariffConsumptionUnitofWork
from model.domain.tariff_version_model import TariffVersion
from model.tariff_version_serializers import (
    TariffVersionCreate,
    TariffVersionResponse,
    TariffVersionUpdate,
)


def _validate_year_month(year: int, month: int) -> None:
    if year < 1900 or year > 3000:
        raise HTTPException(
            HTTP_422_UNPROCESSABLE_ENTITY,
            detail="year must be between 1900 and 3000",
        )

    if month < 1 or month > 12:
        raise HTTPException(
            HTTP_422_UNPROCESSABLE_ENTITY,
            detail="month must be between 1 and 12",
        )


def create_tariff_version(payload: TariffVersionCreate) -> TariffVersionResponse:
    _validate_year_month(payload.year, payload.month)

    with TariffConsumptionUnitofWork() as uow:
        existing = uow.tariff_version_repository.get_by_tariff_and_period(
            tariff_id=payload.tariff_id,
            year=payload.year,
            month=payload.month,
        )
        if existing:
            raise HTTPException(
                HTTP_409_CONFLICT,
                detail="Tariff version already exists for this tariff, year and month",
            )

        item = TariffVersion(**payload.model_dump())
        uow.tariff_version_repository.add(item)
        uow.commit()
        return TariffVersionResponse.model_validate(item)


def get_tariff_version(tariff_version_id: int) -> TariffVersionResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.tariff_version_repository.get(tariff_version_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff version not found")
        return TariffVersionResponse.model_validate(item)


def list_tariff_versions(
    tariff_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[TariffVersionResponse]:
    with TariffConsumptionUnitofWork() as uow:
        records = uow.tariff_version_repository.list(
            tariff_id=tariff_id,
            limit=limit,
            offset=offset,
        )
        return [TariffVersionResponse.model_validate(item) for item in records]


def update_tariff_version(
    tariff_version_id: int, payload: TariffVersionUpdate
) -> TariffVersionResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.tariff_version_repository.get(tariff_version_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff version not found")

        incoming = payload.model_dump(exclude_unset=True)

        new_year = incoming.get("year", item.year)
        new_month = incoming.get("month", item.month)
        _validate_year_month(new_year, new_month)

        year_or_month_updated = (
            ("year" in incoming and incoming["year"] != item.year)
            or ("month" in incoming and incoming["month"] != item.month)
        )

        if year_or_month_updated:
            existing = uow.tariff_version_repository.get_by_tariff_and_period(
                tariff_id=item.tariff_id,
                year=new_year,
                month=new_month,
            )
            if existing and existing.id != tariff_version_id:
                raise HTTPException(
                    HTTP_409_CONFLICT,
                    detail="Tariff version already exists for this tariff, year and month",
                )

        for field, value in incoming.items():
            setattr(item, field, value)

        uow.tariff_version_repository.add(item)
        uow.commit()
        return TariffVersionResponse.model_validate(item)


def delete_tariff_version(tariff_version_id: int) -> None:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.tariff_version_repository.get(tariff_version_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff version not found")
        uow.tariff_version_repository.delete(item)
        uow.commit()
