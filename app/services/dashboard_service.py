"""Dashboard service with meter-reading history business logic."""

from datetime import date
from typing import List, Optional

from fastapi import HTTPException, status
from loguru import logger

from common.model.rest import (
    IntervalDetails,
    MeterReadingFilters,
    ResolvedMeterReadingQuery,
)
from db.uow import TariffConsumptionUnitofWork
from model.dashboard_serializers import (
    BillingPeriodCostResponse,
    BillingPeriodInfoResponse,
    DateRangeResponse,
    HouseholdResponse,
    MeterReadingHistoryDashboardResponse,
    MeterReadingWithHistoryResponse,
)
from model.domain.billing_period_model import BillingPeriod
from model.domain.household_model import Household
from model.domain.meter_reading_model import MeterReading
from services.business.billing_service import BillingService, BillingServiceError


class DashboardService:
    """Service layer for dashboard meter-reading history use-cases."""

    def __init__(self, uow_factory=TariffConsumptionUnitofWork) -> None:
        self._uow_factory = uow_factory

    def get_household_meter_readings_with_history(
        self,
        household_id: int,
        billing_period_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> MeterReadingHistoryDashboardResponse:
        """Build the meter-reading history dashboard for a household query."""
        filters = MeterReadingFilters(
            billing_period_id=billing_period_id,
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(
            f"Building meter reading history dashboard: household_id={household_id}, "
            f"billing_period_id={filters.billing_period_id}, start_date={filters.start_date}, end_date={filters.end_date}"
        )
        self._validate_meter_reading_filters(filters)

        with self._uow_factory() as uow:
            billing_service = BillingService(uow)
            household = self._get_household_or_404(uow, household_id)
            resolved_query = self._resolve_meter_reading_query(
                uow=uow,
                household_id=household_id,
                filters=filters,
            )

            readings = (
                uow.meter_reading_repository.get_by_billing_period_and_date_range(
                    household_id=household_id,
                    reading_date_from=resolved_query.start_date,
                    reading_date_to=resolved_query.end_date,
                )
            )
            logger.debug(
                f"Fetched meter readings for dashboard: household_id={household_id}, "
                f"start_date={resolved_query.start_date}, end_date={resolved_query.end_date}, "
                f"count={len(readings)}"
            )
            readings_with_history, total_consumption = (
                self._build_meter_reading_history(
                    readings=readings,
                    household_id=household_id,
                    billing_service=billing_service,
                    resolved_query=resolved_query,
                )
            )

            logger.info(
                f"Meter reading history dashboard built: household_id={household_id}, "
                f"readings={len(readings_with_history)}, total_consumption={total_consumption}"
            )
            return self._build_dashboard_response(
                household=household,
                resolved_query=resolved_query,
                readings=readings_with_history,
                total_consumption=total_consumption,
            )

    def _validate_meter_reading_filters(self, filters: MeterReadingFilters) -> None:
        """Validate that the route filters define a valid date range query."""
        if filters.billing_period_id is None and (
            filters.start_date is None or filters.end_date is None
        ):
            logger.debug(
                "Invalid meter reading filters: missing billing_period_id and incomplete date range"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either billing_period_id or both start_date and end_date must be provided",
            )

        if (
            filters.start_date is not None
            and filters.end_date is not None
            and filters.start_date > filters.end_date
        ):
            logger.debug(
                f"Invalid meter reading filters: start_date={filters.start_date} "
                f"is after end_date={filters.end_date}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before end_date",
            )

    def _get_household_or_404(
        self, uow: TariffConsumptionUnitofWork, household_id: int
    ) -> Household:
        """Load a household or raise a 404 HTTP error."""
        household = uow.household_repository.get(household_id)
        if not household:
            logger.debug(
                f"Household not found for dashboard lookup: household_id={household_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Household not found",
            )
        logger.debug(
            f"Resolved household for dashboard lookup: household_id={household_id}"
        )
        return household

    def _resolve_meter_reading_query(
        self,
        uow: TariffConsumptionUnitofWork,
        household_id: int,
        filters: MeterReadingFilters,
    ) -> ResolvedMeterReadingQuery:
        """Resolve the effective date range and billing period for the request."""
        if filters.billing_period_id is None:
            assert filters.start_date is not None and filters.end_date is not None
            logger.debug(
                f"Resolved meter reading query from explicit dates: household_id={household_id}, "
                f"start_date={filters.start_date}, end_date={filters.end_date}"
            )
            return ResolvedMeterReadingQuery(
                start_date=filters.start_date,
                end_date=filters.end_date,
            )

        billing_period = self._get_billing_period_or_404(uow, filters.billing_period_id)
        if billing_period.household_id != household_id:
            logger.debug(
                f"Billing period ownership mismatch: billing_period_id={filters.billing_period_id}, "
                f"billing_period_household_id={billing_period.household_id}, household_id={household_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Billing period does not belong to this household",
            )

        resolved_start_date = filters.start_date or billing_period.start_date
        resolved_end_date = filters.end_date or billing_period.end_date
        logger.debug(
            f"Resolved meter reading query from billing period: household_id={household_id}, "
            f"billing_period_id={filters.billing_period_id}, start_date={resolved_start_date}, end_date={resolved_end_date}"
        )
        return ResolvedMeterReadingQuery(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            billing_period=billing_period,
        )

    def _get_billing_period_or_404(
        self, uow: TariffConsumptionUnitofWork, billing_period_id: int
    ) -> BillingPeriod:
        """Load a billing period or raise a 404 HTTP error."""
        billing_period = uow.billing_period_repository.get(billing_period_id)
        if not billing_period:
            logger.debug(
                f"Billing period not found for dashboard lookup: billing_period_id={billing_period_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing period not found",
            )
        logger.debug(f"Resolved billing period: billing_period_id={billing_period_id}")
        return billing_period

    def _build_meter_reading_history(
        self,
        readings: List[MeterReading],
        household_id: int,
        billing_service: BillingService,
        resolved_query: ResolvedMeterReadingQuery,
    ) -> tuple[List[MeterReadingWithHistoryResponse], float]:
        """Transform raw readings into dashboard rows and aggregate consumption."""
        logger.debug(
            f"Building meter reading history: household_id={household_id}, "
            f"reading_count={len(readings)}, "
            f"start_date={resolved_query.start_date}, end_date={resolved_query.end_date}, "
            f"billing_period_id={resolved_query.billing_period.id if resolved_query.billing_period else 'N/A'}"
        )
        if not readings:
            logger.debug(
                f"No meter readings found for dashboard history: household_id={household_id}"
            )
            return [], 0.0

        first_reading = readings[0]
        total_consumption = 0.0
        responses: List[MeterReadingWithHistoryResponse] = []

        for index, reading in enumerate(readings):
            logger.debug(
                f"Processing meter reading for history: household_id={household_id}, "
                f"reading_id={reading.id}, reading_date={reading.reading_date}, "
                f"reading_kwh={reading.reading_kwh}, is_initial={reading.is_initial}"
            )
            previous_reading = readings[index - 1] if index > 0 else None
            interval = self._build_interval_details(
                first_reading=first_reading,
                current_reading=reading,
                previous_reading=previous_reading,
                household_id=household_id,
                billing_service=billing_service,
                billing_period=resolved_query.billing_period,
            )
            total_consumption += interval.consumption_for_total
            responses.append(
                self._build_meter_reading_response(
                    reading=reading,
                    consumption_since_last=interval.consumption_since_last,
                    days_since_last=interval.days_since_last,
                    average_daily_consumption=interval.average_daily_consumption,
                    billing_period_cost=interval.billing_period_cost,
                )
            )

        logger.debug(
            f"Built meter reading history rows: household_id={household_id}, count={len(responses)}, "
            f"total_consumption={total_consumption}"
        )
        return responses, total_consumption

    def _build_interval_details(
        self,
        first_reading: MeterReading,
        current_reading: MeterReading,
        previous_reading: Optional[MeterReading],
        household_id: int,
        billing_service: BillingService,
        billing_period: Optional[BillingPeriod],
    ) -> IntervalDetails:
        """Compute row metrics and cumulative pricing from the first reading to the current one."""
        logger.debug(
            f"Calculating interval details: household_id={household_id}, "
            f"first_reading_id={first_reading.id}, current_reading_id={current_reading.id}, "
            f"billing_period_id={billing_period.id if billing_period else 'N/A'}"
        )
        billing_period_cost = self._calculate_interval_cost(
            household_id=household_id,
            start_date=first_reading.reading_date,
            end_date=current_reading.reading_date,
            billing_service=billing_service,
            billing_period=billing_period,
        )

        if previous_reading is None:
            logger.debug(
                f"First reading interval details: household_id={household_id}, "
                f"first_reading_id={first_reading.id}, current_reading_id={current_reading.id}, "
                f"billing_period_cost={billing_period_cost.total_cost if billing_period_cost else 'N/A'}"
            )
            return IntervalDetails(
                consumption_since_last=None,
                days_since_last=None,
                average_daily_consumption=None,
                billing_period_cost=billing_period_cost,
                consumption_for_total=0.0,
            )

        consumption_since_last = float(
            current_reading.reading_kwh - previous_reading.reading_kwh
        )
        days_since_last = (
            current_reading.reading_date - previous_reading.reading_date
        ).days
        average_daily_consumption = None
        if days_since_last > 0:
            average_daily_consumption = consumption_since_last / days_since_last

        logger.debug(
            f"Calculated interval details: household_id={household_id}, first_reading_id={first_reading.id}, "
            f"previous_reading_id={previous_reading.id}, current_reading_id={current_reading.id}, "
            f"consumption_since_last={consumption_since_last}, days_since_last={days_since_last}, "
            f"average_daily_consumption={average_daily_consumption}"
            f", billing_period_cost={billing_period_cost.total_cost if billing_period_cost else 'N/A'}"
            f", consumption_for_total={consumption_since_last}"
            f" (first_reading_kwh={first_reading.reading_kwh}, current_reading_kwh={current_reading.reading_kwh})"
            f" (previous_reading_kwh={previous_reading.reading_kwh if previous_reading else 'N/A'})"
            f" (current_reading_date={current_reading.reading_date}, previous_reading_date={previous_reading.reading_date if previous_reading else 'N/A'})"
            f" (billing_period_start={billing_period.start_date if billing_period else 'N/A'}, billing_period_end={billing_period.end_date if billing_period else 'N/A'})"
            f" (billing_period_cost_calculation_start={first_reading.reading_date}, billing_period_cost_calculation_end={current_reading.reading_date}) "
            f"(billing_period_cost_calculation_billing_period_id={billing_period.id if billing_period else 'N/A'})"
        )
        return IntervalDetails(
            consumption_since_last=consumption_since_last,
            days_since_last=days_since_last,
            average_daily_consumption=average_daily_consumption,
            billing_period_cost=billing_period_cost,
            consumption_for_total=consumption_since_last,
        )

    def _calculate_interval_cost(
        self,
        household_id: int,
        start_date: date,
        end_date: date,
        billing_service: BillingService,
        billing_period: Optional[BillingPeriod],
    ) -> Optional[BillingPeriodCostResponse]:
        """Calculate tariff cost for a single interval, tolerating missing tariff data."""
        try:
            logger.debug(
                f"Calculating interval cost: household_id={household_id}, start_date={start_date}, end_date={end_date}, "
                f"billing_period_id={billing_period.id if billing_period else 'N/A'}"
            )
            cost = billing_service.calculate_cost_for_date_range(
                household_id=household_id,
                start_date=start_date,
                end_date=end_date,
                billing_period_id=billing_period.id if billing_period else None,
            )
            logger.debug(
                f"Calculated interval cost: household_id={household_id}, start_date={start_date}, "
                f"end_date={end_date}, total_cost={cost.total_cost}"
            )
            return cost
        except BillingServiceError as exc:
            logger.warning(
                f"Unable to calculate interval cost: household_id={household_id}, start_date={start_date}, "
                f"end_date={end_date}, billing_period_id={billing_period.id if billing_period else 'N/A'}, reason={exc.message}"
            )
            return None

    def _build_meter_reading_response(
        self,
        reading: MeterReading,
        consumption_since_last: Optional[float],
        days_since_last: Optional[int],
        average_daily_consumption: Optional[float],
        billing_period_cost: Optional[BillingPeriodCostResponse],
    ) -> MeterReadingWithHistoryResponse:
        """Build the API response model for a single meter reading row."""
        logger.debug(
            f"Building meter reading response: reading_id={reading.id}, household_id={reading.household_id}, "
            f"reading_date={reading.reading_date}, reading_kwh={reading.reading_kwh}, is_initial={reading.is_initial}, "
            f"consumption_since_last={consumption_since_last}, days_since_last={days_since_last}, "
            f"average_daily_consumption={average_daily_consumption}, "
            f"billing_period_cost={billing_period_cost.total_cost if billing_period_cost else 'N/A'}"
        )
        return MeterReadingWithHistoryResponse(
            id=reading.id,
            household_id=reading.household_id,
            reading_date=reading.reading_date,
            reading_kwh=float(reading.reading_kwh),
            is_initial=reading.is_initial,
            created_at=reading.created_at,
            consumption_since_last=consumption_since_last,
            days_since_last=days_since_last,
            average_daily_consumption_since_last=average_daily_consumption,
            billing_period_cost=billing_period_cost,
        )

    def _build_dashboard_response(
        self,
        household: Household,
        resolved_query: ResolvedMeterReadingQuery,
        readings: List[MeterReadingWithHistoryResponse],
        total_consumption: float,
    ) -> MeterReadingHistoryDashboardResponse:
        """Assemble the final dashboard response payload."""
        logger.debug(
            f"Building dashboard response: household_id={household.id}, household_name={household.name}, "
            f"billing_period_id={resolved_query.billing_period.id if resolved_query.billing_period else 'N/A'}, "
            f"start_date={resolved_query.start_date}, end_date={resolved_query.end_date}, "
            f"number_of_readings={len(readings)}, total_consumption={total_consumption}"
        )

        return MeterReadingHistoryDashboardResponse(
            household=HouseholdResponse(id=household.id, name=household.name),
            billing_period=self._build_billing_period_response(
                resolved_query.billing_period
            ),
            period=DateRangeResponse(
                start=resolved_query.start_date,
                end=resolved_query.end_date,
            ),
            number_of_readings=len(readings),
            total_consumption_kwh=total_consumption,
            readings=readings,
        )

    def _build_billing_period_response(
        self,
        billing_period: Optional[BillingPeriod],
    ) -> Optional[BillingPeriodInfoResponse]:
        """Convert an optional billing period domain object into its API serializer."""
        if billing_period is None:
            return None

        return BillingPeriodInfoResponse(
            id=billing_period.id,
            start_date=billing_period.start_date,
            end_date=billing_period.end_date,
        )
