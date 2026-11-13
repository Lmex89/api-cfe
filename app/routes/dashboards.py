"""Dashboard routes - expose consumption and billing calculations via API."""

from contextlib import contextmanager
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.params import Depends

from common.services.auth_dependency import get_current_user
from db.uow import TariffConsumptionUnitofWork
from model.dashboard_serializers import (
    BillingPeriodCostResponse,
    HouseholdConsumptionDashboardResponse,
    MeterReadingHistoryDashboardResponse,
    MultiplePeriodsSummaryResponse,
)
from services.dashboard_service import DashboardService
from services.business.billing_service import BillingService, BillingServiceError
from services.errors import (
    BillingPeriodNotFoundError,
    BillingPeriodOwnershipError,
    HouseholdNotFoundError,
    InvalidFilterError,
)

router = APIRouter(
    prefix="/dashboards",
    tags=["dashboards"],
    dependencies=[Depends(get_current_user)],
)

# The single domain error -> HTTP status map for every dashboard route.
HTTP_STATUS_BY_ERROR = {
    InvalidFilterError: status.HTTP_400_BAD_REQUEST,
    BillingPeriodOwnershipError: status.HTTP_400_BAD_REQUEST,
    HouseholdNotFoundError: status.HTTP_404_NOT_FOUND,
    BillingPeriodNotFoundError: status.HTTP_404_NOT_FOUND,
    BillingServiceError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


@contextmanager
def domain_errors_as_http():
    try:
        yield
    except tuple(HTTP_STATUS_BY_ERROR) as exc:
        code = next(
            HTTP_STATUS_BY_ERROR[c] for c in type(exc).__mro__ if c in HTTP_STATUS_BY_ERROR
        )
        raise HTTPException(status_code=code, detail=exc.message) from exc


def dashboard_service() -> DashboardService:
    """The one DashboardService factory; reads the UoW at call time so tests can swap it."""
    return DashboardService(TariffConsumptionUnitofWork)


def _check_range(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise InvalidFilterError("start_date must be before end_date")


@router.get(
    "/billing-period/{billing_period_id}",
    status_code=status.HTTP_200_OK,
    response_model=BillingPeriodCostResponse,
)
def get_billing_period_dashboard(
    billing_period_id: int,
) -> BillingPeriodCostResponse:
    """Get complete billing calculation for a period (consumption + cost)."""
    with domain_errors_as_http(), TariffConsumptionUnitofWork() as uow:
        return BillingService(uow).calculate_billing_period_cost(billing_period_id)


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
    with domain_errors_as_http():
        _check_range(start_date, end_date)
        return dashboard_service().get_household_consumption_dashboard(
            household_id, start_date, end_date
        )


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
    with domain_errors_as_http():
        _check_range(start_date, end_date)
        with TariffConsumptionUnitofWork() as uow:
            return BillingService(uow).get_multiple_periods_summary(
                household_id, start_date, end_date
            )


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
    with domain_errors_as_http():
        return dashboard_service().get_household_meter_readings_with_history(
            household_id=household_id,
            billing_period_id=billing_period_id,
            start_date=start_date,
            end_date=end_date,
        )
