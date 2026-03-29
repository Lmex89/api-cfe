from typing import List

from fastapi import HTTPException
from starlette.status import HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from db.url_uow import UrlShortenerUnitofWork
from model.domain.tariff_model import Tariff
from model.tariff_serializers import TariffCreate, TariffResponse, TariffUpdate


def create_tariff(payload: TariffCreate) -> TariffResponse:
    with UrlShortenerUnitofWork() as uow:
        existing = uow.tariff_repository.get_by_code(payload.code)
        if existing:
            raise HTTPException(
                HTTP_409_CONFLICT, detail="Tariff code already exists"
            )

        item = Tariff(**payload.model_dump())
        uow.tariff_repository.add(item)
        uow.commit()
        return TariffResponse.model_validate(item)


def get_tariff(tariff_id: int) -> TariffResponse:
    with UrlShortenerUnitofWork() as uow:
        item = uow.tariff_repository.get(tariff_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff not found")
        return TariffResponse.model_validate(item)


def list_tariffs(limit: int = 100, offset: int = 0) -> List[TariffResponse]:
    with UrlShortenerUnitofWork() as uow:
        records = uow.tariff_repository.list(limit=limit, offset=offset)
        return [TariffResponse.model_validate(item) for item in records]


def update_tariff(tariff_id: int, payload: TariffUpdate) -> TariffResponse:
    with UrlShortenerUnitofWork() as uow:
        item = uow.tariff_repository.get(tariff_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff not found")

        incoming = payload.model_dump(exclude_unset=True)
        if "code" in incoming and incoming["code"] != item.code:
            existing = uow.tariff_repository.get_by_code(incoming["code"])
            if existing and existing.id != tariff_id:
                raise HTTPException(
                    HTTP_409_CONFLICT, detail="Tariff code already exists"
                )

        for field, value in incoming.items():
            setattr(item, field, value)

        uow.tariff_repository.add(item)
        uow.commit()
        return TariffResponse.model_validate(item)


def delete_tariff(tariff_id: int) -> None:
    with UrlShortenerUnitofWork() as uow:
        item = uow.tariff_repository.get(tariff_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Tariff not found")
        uow.tariff_repository.delete(item)
        uow.commit()
