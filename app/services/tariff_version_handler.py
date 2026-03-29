from typing import List, Optional

from fastapi import HTTPException
from starlette.status import HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from db.url_uow import UrlShortenerUnitofWork
from model.domain.tariff_version_model import TariffVersion
from model.tariff_version_serializers import (
    TariffVersionCreate,
    TariffVersionResponse,
    TariffVersionUpdate,
)


def create_tariff_version(payload: TariffVersionCreate) -> TariffVersionResponse:
    with UrlShortenerUnitofWork() as uow:
        existing = uow.tariff_version_repository.get_by_tariff_and_start_date(
            tariff_id=payload.tariff_id,
            start_date=payload.start_date,
        )
        if existing:
            raise HTTPException(
                HTTP_409_CONFLICT,
                detail="Tariff version already exists for this tariff and start_date",
            )

        item = TariffVersion(**payload.model_dump())
        uow.tariff_version_repository.add(item)
        uow.commit()
        return TariffVersionResponse.model_validate(item)


def get_tariff_version(tariff_version_id: int) -> TariffVersionResponse:
    with UrlShortenerUnitofWork() as uow:
        item = uow.tariff_version_repository.get(tariff_version_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff version not found")
        return TariffVersionResponse.model_validate(item)


def list_tariff_versions(
    tariff_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[TariffVersionResponse]:
    with UrlShortenerUnitofWork() as uow:
        records = uow.tariff_version_repository.list(
            tariff_id=tariff_id,
            limit=limit,
            offset=offset,
        )
        return [TariffVersionResponse.model_validate(item) for item in records]


def update_tariff_version(
    tariff_version_id: int, payload: TariffVersionUpdate
) -> TariffVersionResponse:
    with UrlShortenerUnitofWork() as uow:
        item = uow.tariff_version_repository.get(tariff_version_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff version not found")

        incoming = payload.model_dump(exclude_unset=True)
        if "start_date" in incoming and incoming["start_date"] != item.start_date:
            existing = uow.tariff_version_repository.get_by_tariff_and_start_date(
                tariff_id=item.tariff_id,
                start_date=incoming["start_date"],
            )
            if existing and existing.id != tariff_version_id:
                raise HTTPException(
                    HTTP_409_CONFLICT,
                    detail="Tariff version already exists for this tariff and start_date",
                )

        for field, value in incoming.items():
            setattr(item, field, value)

        uow.tariff_version_repository.add(item)
        uow.commit()
        return TariffVersionResponse.model_validate(item)


def delete_tariff_version(tariff_version_id: int) -> None:
    with UrlShortenerUnitofWork() as uow:
        item = uow.tariff_version_repository.get(tariff_version_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff version not found")
        uow.tariff_version_repository.delete(item)
        uow.commit()
