"""Dashboard routes - expose consumption and billing calculations via API."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from common.services.auth_dependency import get_current_user
from db.uow import TariffConsumptionUnitofWork
from model.dashboard_serializers import (
    BillingPeriodCostResponse,
    BillingPeriodInfoResponse,
    DateRangeResponse,
    HouseholdConsumptionDashboardResponse,
    HouseholdResponse,
    MeterReadingHistoryDashboardResponse,
    MeterReadingWithHistoryResponse,
    MultiplePeriodsSummaryResponse,
)
from model.domain.billing_period_model import BillingPeriod
from services.business.billing_service import BillingService, BillingServiceError

router = APIRouter(
    prefix="/dashboards",
    tags=["dashboards"],
    dependencies=[Depends(get_current_user)],
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
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


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
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


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
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


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
    """
    Get all meter readings for a household with historical consumption data.
    
    Can filter by billing_period_id OR start_date/end_date OR both.
    Returns readings that match all provided criteria along with consumption history.
    """
    if billing_period_id is None and (start_date is None or end_date is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either billing_period_id or both start_date and end_date must be provided",
        )

    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    with TariffConsumptionUnitofWork() as uow:
        # Validate household exists
        household = uow.household_repository.get(household_id)
        if not household:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Household not found",
            )

        # If billing_period_id is provided, get the period details
        billing_period: Optional[BillingPeriod] = None
        if billing_period_id is not None:
            billing_period = uow.billing_period_repository.get(billing_period_id)
            if not billing_period:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Billing period not found",
                )
            # Verify billing period belongs to the household
            if billing_period.household_id != household_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Billing period does not belong to this household",
                )

            # Use billing period dates if start/end dates not explicitly provided
            if start_date is None:
                start_date = billing_period.start_date
            if end_date is None:
                end_date = billing_period.end_date

        # Get all meter readings in the date range
        readings = uow.meter_reading_repository.get_by_billing_period_and_date_range(
            household_id=household_id,
            reading_date_from=start_date,
            reading_date_to=end_date,
        )

        # Build response with historical consumption data
        readings_with_history: List[MeterReadingWithHistoryResponse] = []
        total_consumption = 0.0

        for idx, reading in enumerate(readings):
            # Calculate consumption since last reading
            consumption_since_last = None
            days_since_last = None
            avg_daily_consumption = None

            if idx > 0:
                prev_reading = readings[idx - 1]
                consumption_since_last = float(reading.reading_kwh - prev_reading.reading_kwh)
                days_since_last = (reading.reading_date - prev_reading.reading_date).days
                
                if days_since_last > 0:
                    avg_daily_consumption = consumption_since_last / days_since_last

            # Calculate total consumption for this reading period
            if idx == 0:
                # For first reading, we don't have a previous reading to compare
                total_consumption += 0.0
            else:
                total_consumption += consumption_since_last if consumption_since_last else 0.0

            readings_with_history.append(
                MeterReadingWithHistoryResponse(
                    id=reading.id,
                    household_id=reading.household_id,
                    reading_date=reading.reading_date,
                    reading_kwh=float(reading.reading_kwh),
                    is_initial=reading.is_initial,
                    created_at=reading.created_at,
                    consumption_since_last=consumption_since_last,
                    days_since_last=days_since_last,
                    average_daily_consumption_since_last=avg_daily_consumption,
                )
            )

        # Prepare billing period info for response
        billing_period_response = None
        if billing_period:
            billing_period_response = BillingPeriodInfoResponse(
                id=billing_period.id,
                start_date=billing_period.start_date,
                end_date=billing_period.end_date,
            )

        return MeterReadingHistoryDashboardResponse(
            household=HouseholdResponse(id=household.id, name=household.name),
            billing_period=billing_period_response,
            period=DateRangeResponse(start=start_date, end=end_date),
            number_of_readings=len(readings_with_history),
            total_consumption_kwh=total_consumption,
            readings=readings_with_history,
        )
