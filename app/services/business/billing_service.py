"""Billing orchestration - composes smaller domain services (composition over inheritance)."""

from datetime import date
from typing import Optional

from loguru import logger
from common.api.errors.business_error import TariffCalculationError
from db.uow import TariffConsumptionUnitofWork
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
from model.domain.billing_period_model import BillingPeriod


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
        uow: TariffConsumptionUnitofWork,
        consumption_calc: Optional[MeterReadingConsumptionCalculator] = None,
        tariff_calc: Optional[RangeBasedTariffCalculator] = None,
    ):
        self.uow = uow
        self.consumption_calc = consumption_calc or MeterReadingConsumptionCalculator(
            uow
        )
        self.tariff_calc = tariff_calc or RangeBasedTariffCalculator(uow)
        logger.info("BillingService initialized")
        logger.debug(
            f"BillingService dependencies: consumption_calc={type(self.consumption_calc).__name__}, "
            f"tariff_calc={type(self.tariff_calc).__name__}"
        )

    def calculate_billing_period_cost(
        self, billing_period_id: int
    ) -> BillingPeriodCostResponse:
        """Calculate total cost for a billing period (for dashboards)."""
        logger.info(
            f"Calculating billing period cost for billing_period_id={billing_period_id}"
        )
        bp: BillingPeriod = self.uow.billing_period_repository.get(billing_period_id)
        if not bp:
            logger.debug(f"Billing period not found: billing_period_id={billing_period_id}")
            raise BillingServiceError(
                "Billing period not found", status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        household = self.uow.household_repository.get(bp.household_id)
        if not household:
            logger.debug(f"Household not found: household_id={bp.household_id}")
            raise BillingServiceError(
                "Household not found", status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        active_tariff = self._get_active_tariff(bp.household_id, bp.start_date)
        if not active_tariff:
            logger.debug(
                f"No active tariff found for household_id={bp.household_id}, effective_date={bp.start_date}"
            )
            raise BillingServiceError(
                "No active tariff for this period",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

        consumption = self.consumption_calc.calculate_total(
            bp.household_id, bp.start_date, bp.end_date
        )
        try:
            cost_result = self.tariff_calc.calculate_cost(
                consumption, active_tariff.tariff_id, bp.start_date
            )
        except TariffCalculationError as exc:
            logger.debug(
                f"Tariff calculation failed for billing_period_id={billing_period_id}: {exc.message}"
            )
            raise BillingServiceError(exc.message, exc.status_code) from exc

        cost = cost_result.total_cost
        avg_daily = self.consumption_calc.calculate_average_daily(
            bp.household_id, bp.start_date, bp.end_date
        )
        logger.debug(
            f"Billing period metrics: consumption={consumption}, avg_daily={avg_daily}, "
            f"base_cost={cost}, iva={cost_result.iva}, dap={cost_result.dap}"
        )
        logger.info(
            f"Calculated billing period cost for billing_period_id={billing_period_id}, "
            f"total_cost={cost_result.iva + cost + cost_result.dap}"
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
            total_cost_witout_taxes=float(cost),
            iva=float(cost_result.iva),
            total_cost_with_iva=float(cost_result.iva + cost),
            dap=float(cost_result.dap),
            total_cost=float(cost_result.iva + cost + cost_result.dap),
            cost_per_kwh=float(cost / consumption) if consumption > 0 else 0,
        )

    def get_household_consumption_dashboard(
        self, household_id: int, start_date: date, end_date: date
    ) -> HouseholdConsumptionDashboardResponse:
        """Multi-period consumption dashboard for single household."""
        logger.info(
            f"Building household dashboard for household_id={household_id}, start_date={start_date}, end_date={end_date}"
        )
        household = self.uow.household_repository.get(household_id)
        if not household:
            logger.debug(f"Household not found: household_id={household_id}")
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

    def get_multiple_periods_summary(
        self, household_id: int, start_date: date, end_date: date
    ) -> MultiplePeriodsSummaryResponse:
        """Comparison across multiple billing periods."""
        logger.info(
            f"Building periods summary for household_id={household_id}, start_date={start_date}, end_date={end_date}"
        )
        household = self.uow.household_repository.get(household_id)
        if not household:
            logger.debug(f"Household not found: household_id={household_id}")
            raise BillingServiceError(
                "Household not found", status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        periods: list[BillingPeriod] = self.uow.billing_period_repository.list(
            household_id=household_id, limit=1000
        )
        logger.debug(
            f"Fetched periods for summary: household_id={household_id}, total_periods={len(periods)}"
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
                logger.debug(
                    f"Skipping period from summary due to calculation error: billing_period_id={period.id}"
                )
                continue

        total_consumption = sum(p.total_consumption_kwh for p in period_summaries)
        total_cost = sum(p.total_cost for p in period_summaries)
        logger.debug(
            f"Summary totals: household_id={household_id}, periods_in_range={len(periods_in_range)}, "
            f"periods_calculated={len(period_summaries)}, total_consumption={total_consumption}, total_cost={total_cost}"
        )
        logger.info(f"Periods summary generated for household_id={household_id}")

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
            logger.debug(
                f"No household tariffs found: household_id={household_id}, effective_date={effective_date}"
            )
            return None

        for ht in hts:
            if ht.start_date <= effective_date and (
                ht.end_date is None or ht.end_date >= effective_date
            ):
                tariff = self.uow.tariff_repository.get(ht.tariff_id)
                if tariff:
                    logger.debug(
                        f"Active tariff found: household_id={household_id}, tariff_id={ht.tariff_id}, code={tariff.code}"
                    )
                    return ActiveTariffResponse(
                        tariff_id=ht.tariff_id, code=tariff.code
                    )

        logger.debug(
            f"No active tariff matched effective date: household_id={household_id}, effective_date={effective_date}"
        )
        return None
