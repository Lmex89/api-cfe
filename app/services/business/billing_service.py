"""Billing orchestration - composes smaller domain services (composition over inheritance)."""

from datetime import date
from typing import Optional

from common.api.errors.business_error import TariffCalculationError
from db.url_uow import UrlShortenerUnitofWork
from model.dashboard_serializers import (
    ActiveTariffResponse,
    BillingPeriodCostResponse,
    DateRangeResponse,
    HouseholdConsumptionDashboardResponse,
    HouseholdResponse,
    MeterReadingPointResponse,
    MultiplePeriodsSummaryResponse,
)
from services.business import MeterReadingConsumptionCalculator
from services.business.tariff_calculator import RangeBasedTariffCalculator

from starlette import status


class BillingServiceError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BillingService:
    """
    OCP: Open/Closed Principle
    Open for extension (add new calculators), closed for modification (core logic stable).

    Orchestrates consumption + tariff calculations for dashboards.
    """

    def __init__(
        self,
        uow: UrlShortenerUnitofWork,
        consumption_calc: Optional[MeterReadingConsumptionCalculator] = None,
        tariff_calc: Optional[RangeBasedTariffCalculator] = None,
    ):
        self.uow = uow
        self.consumption_calc = consumption_calc or MeterReadingConsumptionCalculator(
            uow
        )
        self.tariff_calc = tariff_calc or RangeBasedTariffCalculator(uow)

    def calculate_billing_period_cost(
        self, billing_period_id: int
    ) -> BillingPeriodCostResponse:
        """Calculate total cost for a billing period (for dashboards)."""
        bp = self.uow.billing_period_repository.get(billing_period_id)
        if not bp:
            raise BillingServiceError(
                "Billing period not found", status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        household = self.uow.household_repository.get(bp.household_id)
        if not household:
            raise BillingServiceError(
                "Household not found", status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        active_tariff = self._get_active_tariff(bp.household_id, bp.start_date)
        if not active_tariff:
            raise BillingServiceError("No active tariff for this period", 422)

        consumption = self.consumption_calc.calculate_total(
            bp.household_id, bp.start_date, bp.end_date
        )
        try:
            cost_result = self.tariff_calc.calculate_cost(
                consumption, active_tariff.tariff_id, bp.start_date
            )
        except TariffCalculationError as exc:
            raise BillingServiceError(exc.message, exc.status_code) from exc

        cost = cost_result.total_cost
        avg_daily = self.consumption_calc.calculate_average_daily(
            bp.household_id, bp.start_date, bp.end_date
        )

        return BillingPeriodCostResponse(
            billing_period_id=billing_period_id,
            household_id=bp.household_id,
            household_name=household.name,
            period_start=bp.start_date,
            period_end=bp.end_date,
            total_consumption_kwh=float(consumption),
            average_daily_kwh=float(avg_daily),
            tariff_code=active_tariff.code,
            total_cost=float(cost),
            cost_per_kwh=float(cost / consumption) if consumption > 0 else 0,
        )

    def get_household_consumption_dashboard(
        self, household_id: int, start_date: date, end_date: date
    ) -> HouseholdConsumptionDashboardResponse:
        """Multi-period consumption dashboard for single household."""
        household = self.uow.household_repository.get(household_id)
        if not household:
            raise BillingServiceError(
                "Household not found", status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        readings_raw = self.consumption_calc.get_readings_in_range(
            household_id, start_date, end_date
        )
        total_consumption = self.consumption_calc.calculate_total(
            household_id, start_date, end_date
        )
        avg_daily = self.consumption_calc.calculate_average_daily(
            household_id, start_date, end_date
        )

        readings = [
            MeterReadingPointResponse(
                date=date.fromisoformat(item["date"]),
                reading_kwh=float(item["reading_kwh"]),
                is_initial=bool(item["is_initial"]),
            )
            for item in readings_raw
        ]

        return HouseholdConsumptionDashboardResponse(
            household=HouseholdResponse(id=household.id, name=household.name),
            period=DateRangeResponse(start=start_date, end=end_date),
            total_consumption_kwh=float(total_consumption),
            average_daily_kwh=float(avg_daily),
            number_of_readings=len(readings),
            readings=readings,
        )

    def get_multiple_periods_summary(
        self, household_id: int, start_date: date, end_date: date
    ) -> MultiplePeriodsSummaryResponse:
        """Comparison across multiple billing periods."""
        household = self.uow.household_repository.get(household_id)
        if not household:
            raise BillingServiceError(
                "Household not found", status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        periods = self.uow.billing_period_repository.list(
            household_id=household_id, limit=1000
        )

        # Filter periods within date range
        periods_in_range = [
            p for p in periods if p.start_date >= start_date and p.end_date <= end_date
        ]

        period_summaries = []
        for period in periods_in_range:
            try:
                summary = self.calculate_billing_period_cost(period.id)
                period_summaries.append(summary)
            except BillingServiceError:
                continue

        total_consumption = sum(p.total_consumption_kwh for p in period_summaries)
        total_cost = sum(p.total_cost for p in period_summaries)

        return MultiplePeriodsSummaryResponse(
            household=HouseholdResponse(id=household.id, name=household.name),
            period_range=DateRangeResponse(start=start_date, end=end_date),
            number_of_periods=len(period_summaries),
            total_consumption_kwh=float(total_consumption),
            total_cost=float(total_cost),
            periods=period_summaries,
        )

    def _get_active_tariff(
        self, household_id: int, effective_date: date
    ) -> Optional[ActiveTariffResponse]:
        """
        LSP: Liskov Substitution Principle
        Extract active tariff lookup to avoid duplicating in calc methods.
        """
        hts = self.uow.household_tariff_repository.list(
            household_id=household_id, limit=1000
        )
        if not hts:
            return None

        for ht in hts:
            if ht.start_date <= effective_date and (
                ht.end_date is None or ht.end_date >= effective_date
            ):
                tariff = self.uow.tariff_repository.get(ht.tariff_id)
                if tariff:
                    return ActiveTariffResponse(
                        tariff_id=ht.tariff_id, code=tariff.code
                    )

        return None
