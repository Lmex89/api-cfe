from typing import List, Optional

from fastapi import HTTPException
from starlette.status import HTTP_404_NOT_FOUND

from db.uow import TariffConsumptionUnitofWork
from model.billing_period_serializers import (
    BillingPeriodCreate,
    BillingPeriodResponse,
    BillingPeriodUpdate,
)
from model.domain.billing_period_model import BillingPeriod


def create_billing_period(payload: BillingPeriodCreate) -> BillingPeriodResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = BillingPeriod(**payload.model_dump())
        uow.billing_period_repository.add(item)
        uow.commit()
        return BillingPeriodResponse.model_validate(item)


def get_billing_period(billing_period_id: int) -> BillingPeriodResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.billing_period_repository.get(billing_period_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Billing period not found")
        return BillingPeriodResponse.model_validate(item)


def list_billing_periods(
    household_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[BillingPeriodResponse]:
    with TariffConsumptionUnitofWork() as uow:
        records = uow.billing_period_repository.list(
            household_id=household_id, limit=limit, offset=offset
        )
        return [BillingPeriodResponse.model_validate(item) for item in records]


def update_billing_period(
    billing_period_id: int, payload: BillingPeriodUpdate
) -> BillingPeriodResponse:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.billing_period_repository.get(billing_period_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Billing period not found")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)

        uow.billing_period_repository.add(item)
        uow.commit()
        return BillingPeriodResponse.model_validate(item)


def delete_billing_period(billing_period_id: int) -> None:
    with TariffConsumptionUnitofWork() as uow:
        item = uow.billing_period_repository.get(billing_period_id)
        if not item:
            raise HTTPException(HTTP_404_NOT_FOUND, detail="Billing period not found")
        uow.billing_period_repository.delete(item)
        uow.commit()
