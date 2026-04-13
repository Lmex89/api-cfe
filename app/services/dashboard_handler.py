from datetime import date
from typing import List, Optional

from fastapi import HTTPException, status

from db.uow import TariffConsumptionUnitofWork
from model.dashboard_serializers import (
    BillingPeriodInfoResponse,
    DateRangeResponse,
    HouseholdResponse,
    MeterReadingHistoryDashboardResponse,
    MeterReadingWithHistoryResponse,
)
from model.domain.billing_period_model import BillingPeriod
from services.business.billing_service import BillingService, BillingServiceError


def get_household_meter_readings_with_history(
    household_id: int,
    billing_period_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> MeterReadingHistoryDashboardResponse:
    
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
        billing_service = BillingService(uow)
        household = uow.household_repository.get(household_id)
        if not household:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Household not found",
            )

        billing_period: Optional[BillingPeriod] = None
        if billing_period_id is not None:
            billing_period = uow.billing_period_repository.get(billing_period_id)
            if not billing_period:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Billing period not found",
                )

            if billing_period.household_id != household_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Billing period does not belong to this household",
                )

            if start_date is None:
                start_date = billing_period.start_date
            if end_date is None:
                end_date = billing_period.end_date

        readings = uow.meter_reading_repository.get_by_billing_period_and_date_range(
            household_id=household_id,
            reading_date_from=start_date,
            reading_date_to=end_date,
        )

        readings_with_history: List[MeterReadingWithHistoryResponse] = []
        total_consumption = 0.0

        for idx, reading in enumerate(readings):
            consumption_since_last = None
            days_since_last = None
            avg_daily_consumption = None
            billing_period_cost = None
            initial_reading = readings[0] if readings else 0.0

            if idx > 0:
                prev_reading = readings[idx - 1]
                consumption_since_last = float(
                    reading.reading_kwh - prev_reading.reading_kwh
                )
                days_since_last = (reading.reading_date - prev_reading.reading_date).days

                if days_since_last > 0:
                    avg_daily_consumption = consumption_since_last / days_since_last

                try:
                    billing_period_cost = billing_service.calculate_cost_for_date_range(
                        household_id=household_id,
                        start_date=prev_reading.reading_date,
                        end_date=reading.reading_date,
                    )
                except BillingServiceError:
                    billing_period_cost = None

            if idx > 0:
                total_consumption += (
                    consumption_since_last if consumption_since_last else 0.0
                )

            readings_with_history.append(
                MeterReadingWithHistoryResponse(
                    id=reading.id,
                    household_id=reading.household_id,
                    reading_date=reading.reading_date,
                    reading_kwh=float(reading.reading_kwh - initial_reading.reading_kwh),
                    is_initial=reading.is_initial,
                    created_at=reading.created_at,
                    consumption_since_last=consumption_since_last,
                    days_since_last=days_since_last,
                    average_daily_consumption_since_last=avg_daily_consumption,
                    billing_period_cost=billing_period_cost,
                )
            )

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
