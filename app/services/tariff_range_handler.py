from typing import List, Optional

from fastapi import HTTPException
from starlette.status import HTTP_404_NOT_FOUND

from db.uow import TariffConsumptionUnitofWork
from model.domain.tariff_range_model import TariffRange
from model.tariff_range_serializers import (
    TariffRangeCreate,
    TariffRangeResponse,
    TariffRangeUpdate,
)


def create_tariff_range(payload: TariffRangeCreate) -> TariffRangeResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = TariffRange(**payload.model_dump())
        uow.tariff_range_repository.add(item)
        uow.commit()
        return TariffRangeResponse.model_validate(item)


def get_tariff_range(tariff_range_id: int) -> TariffRangeResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.tariff_range_repository.get(tariff_range_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff range not found")
        return TariffRangeResponse.model_validate(item)


def list_tariff_ranges(
    tariff_version_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[TariffRangeResponse]:
    with TariffConsumptionUnitofWork() as uow:
        records = uow.tariff_range_repository.list(
            tariff_version_id=tariff_version_id,
            limit=limit,
            offset=offset,
        )
        return [TariffRangeResponse.model_validate(item) for item in records]


def update_tariff_range(
    tariff_range_id: int, payload: TariffRangeUpdate
) -> TariffRangeResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.tariff_range_repository.get(tariff_range_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff range not found")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)

        uow.tariff_range_repository.add(item)
        uow.commit()
        return TariffRangeResponse.model_validate(item)


def delete_tariff_range(tariff_range_id: int) -> None:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.tariff_range_repository.get(tariff_range_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff range not found")
        uow.tariff_range_repository.delete(item)
        uow.commit()
