"""Dashboard service with meter-reading history business logic."""

from datetime import date
from typing import List, Optional

from loguru import logger

from common.model.rest import (
    MeterReadingFilters,
    ResolvedMeterReadingQuery,
)
from db.uow import TariffConsumptionUnitofWork
from model.dashboard_serializers import (
    BillingPeriodCostResponse,
    BillingPeriodInfoResponse,
    DateRangeResponse,
    HouseholdConsumptionDashboardResponse,
    HouseholdResponse,
    MeterReadingPointResponse,
    MeterReadingHistoryDashboardResponse,
    MeterReadingWithHistoryResponse,
)
from model.domain.billing_period_model import BillingPeriod
from model.domain.household_model import Household
from model.domain.meter_reading_model import MeterReading
from decimal import Decimal

from services.business.billing_service import BillingService, BillingServiceError
from services.business.costo_total import CostoTotal, CostoTotalError
from services.business.costo_total_catalog import CachedTariffCatalog, UowTariffCatalog
from services.business import MeterReadingConsumptionCalculator
from services.errors import (
    BillingPeriodNotFoundError,
    BillingPeriodOwnershipError,
    HouseholdNotFoundError,
    InvalidFilterError,
)
from services.business.history_rows import build_history_rows


class DashboardService:
    """Service layer for dashboard meter-reading history use-cases."""

    def __init__(self, uow_factory=TariffConsumptionUnitofWork) -> None:
        self._uow_factory = uow_factory

    def get_household_consumption_dashboard(
        self, household_id: int, start_date: date, end_date: date
    ) -> HouseholdConsumptionDashboardResponse:
        """Multi-period consumption dashboard for single household."""
        with self._uow_factory() as uow:
            return self._consumption_dashboard(uow, household_id, start_date, end_date)

    def _consumption_dashboard(self, uow, household_id, start_date, end_date):
        logger.info(
            f"Building household dashboard for household_id={household_id}, start_date={start_date}, end_date={end_date}"
        )
        household = uow.household_repository.get(household_id)
        if not household:
            logger.debug(f"Household not found: household_id={household_id}")
            raise BillingServiceError("Household not found")

        domain_readings = uow.meter_reading_repository.list(
            household_id=household_id,
            reading_date_from=start_date,
            reading_date_to=end_date,
            limit=1000,
        )
        rows, _ = build_history_rows(domain_readings)
        # last cumulative == last - first, as the previous first/last query gave
        total_consumption = rows[-1].cumulative_consumption if rows else 0.0
        avg_daily = total_consumption / ((end_date - start_date).days or 1)

        readings = [
            MeterReadingPointResponse(
                date=row.reading.reading_date,
                reading_kwh=float(row.reading.reading_kwh),
                is_initial=bool(row.reading.is_initial),
            )
            for row in rows
        ]
        logger.debug(
            f"Dashboard metrics: household_id={household_id}, readings={len(readings)}, "
            f"total_consumption={total_consumption}, avg_daily={avg_daily}"
        )
        logger.info(f"Household dashboard generated for household_id={household_id}")

        return HouseholdConsumptionDashboardResponse(
            household=HouseholdResponse(id=household.id, name=household.name),
            period=DateRangeResponse(start=start_date, end=end_date),
            total_consumption_kwh=float(total_consumption),
            average_daily_kwh=float(avg_daily),
            number_of_readings=len(readings),
            readings=readings,
        )

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
                    household=household,
                    uow=uow,
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
            raise InvalidFilterError("Either billing_period_id or both start_date and end_date must be provided")

        if (
            filters.start_date is not None
            and filters.end_date is not None
            and filters.start_date > filters.end_date
        ):
            logger.debug(
                f"Invalid meter reading filters: start_date={filters.start_date} "
                f"is after end_date={filters.end_date}"
            )
            raise InvalidFilterError("start_date must be before end_date")

    def _get_household_or_404(
        self, uow: TariffConsumptionUnitofWork, household_id: int
    ) -> Household:
        """Load a household or raise a domain error."""
        household = uow.household_repository.get(household_id)
        if not household:
            logger.debug(
                f"Household not found for dashboard lookup: household_id={household_id}"
            )
            raise HouseholdNotFoundError("Household not found")
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
            raise BillingPeriodOwnershipError("Billing period does not belong to this household")

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
        """Load a billing period or raise a domain error."""
        billing_period = uow.billing_period_repository.get(billing_period_id)
        if not billing_period:
            logger.debug(
                f"Billing period not found for dashboard lookup: billing_period_id={billing_period_id}"
            )
            raise BillingPeriodNotFoundError("Billing period not found")
        logger.debug(f"Resolved billing period: billing_period_id={billing_period_id}")
        return billing_period

    def _build_meter_reading_history(
        self,
        readings: List[MeterReading],
        household: Household,
        uow: TariffConsumptionUnitofWork,
        resolved_query: ResolvedMeterReadingQuery,
    ) -> tuple[List[MeterReadingWithHistoryResponse], float]:
        """Transform raw readings into dashboard rows and aggregate consumption."""
        household_id = household.id
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

        rows, total_consumption = build_history_rows(readings)
        billing = BillingService(
            uow, costo_total=CostoTotal(CachedTariffCatalog(UowTariffCatalog(uow)))
        )
        responses = [
            self._build_meter_reading_response(
                reading=row.reading,
                consumption_since_last=row.consumption_since_last,
                days_since_last=row.days_since_last,
                average_daily_consumption=row.average_daily_consumption,
                billing_period_cost=self._calculate_interval_cost(
                    billing,
                    household,
                    row.cumulative_consumption,
                    readings[0].reading_date,
                    row.reading.reading_date,
                    resolved_query.billing_period,
                ),
            )
            for row in rows
        ]
        return responses, total_consumption

    def _calculate_interval_cost(
        self,
        billing: BillingService,
        household: Household,
        consumption: float,
        start_date: date,
        end_date: date,
        billing_period: Optional[BillingPeriod],
    ) -> Optional[BillingPeriodCostResponse]:
        """Price one row from its cumulative Consumo; null (and a warning) if not priceable."""
        bp_id = billing_period.id if billing_period else None
        try:
            return billing.cost_for_consumption(
                household, Decimal(str(consumption)), start_date, end_date, bp_id, bp_id
            )
        except CostoTotalError as exc:
            logger.warning(
                f"Unable to calculate interval cost: household_id={household.id}, start_date={start_date}, "
                f"end_date={end_date}, billing_period_id={bp_id}, reason={exc}"
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
