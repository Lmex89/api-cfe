from typing import List, Optional

from fastapi import APIRouter, Query, status

from common.api.responses import responses as HTTP_RESPONSES
from model.billing_period_serializers import (
    BillingPeriodCreate,
    BillingPeriodDeleteResponse,
    BillingPeriodResponse,
    BillingPeriodUpdate,
)
from services import billing_period_handler

router = APIRouter(prefix="/billing-periods", tags=["billing-periods"], responses=HTTP_RESPONSES)


@router.post("", response_model=BillingPeriodResponse, status_code=status.HTTP_201_CREATED)
def create_billing_period(payload: BillingPeriodCreate) -> BillingPeriodResponse:
    return billing_period_handler.create_billing_period(payload)


@router.get("", response_model=List[BillingPeriodResponse])
def list_billing_periods(
    household_id: Optional[int] = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[BillingPeriodResponse]:
    return billing_period_handler.list_billing_periods(
        household_id=household_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{billing_period_id}", response_model=BillingPeriodResponse)
def get_billing_period(billing_period_id: int) -> BillingPeriodResponse:
    return billing_period_handler.get_billing_period(billing_period_id)


@router.put("/{billing_period_id}", response_model=BillingPeriodResponse)
def update_billing_period(
    billing_period_id: int,
    payload: BillingPeriodUpdate,
) -> BillingPeriodResponse:
    return billing_period_handler.update_billing_period(billing_period_id, payload)


@router.delete("/{billing_period_id}", response_model=BillingPeriodDeleteResponse)
def delete_billing_period(billing_period_id: int) -> BillingPeriodDeleteResponse:
    billing_period_handler.delete_billing_period(billing_period_id)
    return BillingPeriodDeleteResponse(deleted=True)
