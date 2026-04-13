"""Dashboard routes - expose consumption and billing calculations via API."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from db.uow import TariffConsumptionUnitofWork
from model.dashboard_serializers import (
    BillingPeriodCostResponse,
    HouseholdConsumptionDashboardResponse,
    MeterReadingHistoryDashboardResponse,
    MultiplePeriodsSummaryResponse,
)
from services import dashboard_handler
from services.business.billing_service import BillingService, BillingServiceError

router = APIRouter(
    prefix="/dashboards",
    tags=["dashboards"],
)


@router.get(
    "/billing-period/{billing_period_id}",
    status_code=status.HTTP_200_OK,
    response_model=BillingPeriodCostResponse,
)
def get_billing_period_dashboard(
    billing_period_id: int,
) -> BillingPeriodCostResponse:
    """Get complete billing calculation for a period (consumption + cost)."""
    with TariffConsumptionUnitofWork() as uow:
        service = BillingService(uow)
        try:
            return service.calculate_billing_period_cost(billing_period_id)
        except BillingServiceError as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.message
            ) from exc


@router.get(
    "/household/{household_id}/consumption",
    response_model=HouseholdConsumptionDashboardResponse,
)
def get_household_consumption(
    household_id: int,
    start_date: date = Query(..., description="Period start (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Period end (YYYY-MM-DD)"),
) -> HouseholdConsumptionDashboardResponse:
    """Get household consumption overview for date range."""
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    with TariffConsumptionUnitofWork() as uow:
        service = BillingService(uow)
        try:
            return service.get_household_consumption_dashboard(
                household_id, start_date, end_date
            )
        except BillingServiceError as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.message
            ) from exc


@router.get(
    "/household/{household_id}/billing-summary",
    response_model=MultiplePeriodsSummaryResponse,
)
def get_household_billing_summary(
    household_id: int,
    start_date: date = Query(..., description="Summary start (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Summary end (YYYY-MM-DD)"),
) -> MultiplePeriodsSummaryResponse:
    """Get multi-period billing comparison for household."""
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    with TariffConsumptionUnitofWork() as uow:
        service = BillingService(uow)
        try:
            return service.get_multiple_periods_summary(
                household_id, start_date, end_date
            )
        except BillingServiceError as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.message
            ) from exc


@router.get(
    "/household/{household_id}/meter-readings",
    response_model=MeterReadingHistoryDashboardResponse,
)
def get_household_meter_readings_with_history(
    household_id: int,
    billing_period_id: Optional[int] = Query(
        default=None, gt=0, description="Filter by billing period ID"
    ),
    start_date: Optional[date] = Query(
        default=None, description="Period start (YYYY-MM-DD)"
    ),
    end_date: Optional[date] = Query(
        default=None, description="Period end (YYYY-MM-DD)"
    ),
) -> MeterReadingHistoryDashboardResponse:
    return dashboard_handler.get_household_meter_readings_with_history(
        household_id=household_id,
        billing_period_id=billing_period_id,
        start_date=start_date,
        end_date=end_date,
    )
