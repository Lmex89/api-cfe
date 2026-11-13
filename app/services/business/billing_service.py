"""Billing orchestration - composes smaller domain services (composition over inheritance)."""

from datetime import date
from decimal import Decimal
from typing import Optional

from loguru import logger
from db.uow import TariffConsumptionUnitofWork
from model.dashboard_serializers import (
    CfeBillingBreakdownResponse,
    CfeTierLineItem,
    BillingPeriodCostResponse,
    DateRangeResponse,
    HouseholdResponse,
    MultiplePeriodsSummaryResponse,
)
from services.business import MeterReadingConsumptionCalculator
from services.business.costo_total import CostoTotal, CostoTotalError
from services.business.costo_total_catalog import UowTariffCatalog

from model.domain.billing_period_model import BillingPeriod


class BillingServiceError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


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
        costo_total: Optional[CostoTotal] = None,
    ):
        self.uow = uow
        self.consumption_calc = consumption_calc or MeterReadingConsumptionCalculator(
            uow
        )
        self.costo_total = costo_total or CostoTotal(UowTariffCatalog(uow))
        logger.info("BillingService initialized")

    def calculate_billing_period_cost(
        self, billing_period_id: int
    ) -> BillingPeriodCostResponse:
        """Calculate total cost for a billing period (for dashboards)."""
        logger.info(
            f"Calculating billing period cost for billing_period_id={billing_period_id}"
        )
        bp: BillingPeriod = self.uow.billing_period_repository.get(billing_period_id)
        if not bp:
            logger.debug(
                f"Billing period not found: billing_period_id={billing_period_id}"
            )
            raise BillingServiceError("Billing period not found")

        # Periodo already read here: its end date is passed as the range end.
        return self._calculate(
            bp.household_id, bp.start_date, bp.end_date, billing_period_id, None
        )

    def calculate_cost_for_date_range(
        self,
        household_id: int,
        start_date: date,
        end_date: date,
        billing_period_id: Optional[int] = None,
    ) -> BillingPeriodCostResponse:
        """Calculate consumption and tariff cost for any household date range."""
        return self._calculate(
            household_id, start_date, end_date, billing_period_id, billing_period_id
        )

    def _calculate(
        self,
        household_id: int,
        start_date: date,
        end_date: date,
        billing_period_id: Optional[int],
        periodo_id: Optional[int],
    ) -> BillingPeriodCostResponse:
        household = self.uow.household_repository.get(household_id)
        if not household:
            raise BillingServiceError("Household not found")
        consumption = self.consumption_calc.calculate_total(
            household_id, start_date, end_date
        )
        try:
            return self.cost_for_consumption(
                household, consumption, start_date, end_date, billing_period_id, periodo_id
            )
        except CostoTotalError as exc:
            raise BillingServiceError(str(exc)) from exc

    def cost_for_consumption(
        self,
        household,
        consumption,
        start_date: date,
        end_date: date,
        billing_period_id: Optional[int],
        periodo_id: Optional[int],
    ) -> BillingPeriodCostResponse:
        """Price an already-computed Consumo (no reading queries). Raises CostoTotalError."""
        household_id = household.id
        d = self.costo_total.calculate(
            consumption, household_id, start_date, end_date, periodo_id
        )
        avg_daily = Decimal(consumption) / Decimal((end_date - start_date).days or 1)
        base_cost, iva, dap = d.costo_base, d.iva, d.dap
        consumption_value = float(consumption)
        cfe_breakdown = CfeBillingBreakdownResponse(
            tier_lines=[
                CfeTierLineItem(
                    segment_year=r.segment_year,
                    segment_month=r.segment_month,
                    tier_level=r.tier_level,
                    tier_name=r.tier_name,
                    days_in_segment=r.days_in_segment,
                    prorated_kwh_capacity=(
                        float(r.prorated_kwh_capacity)
                        if r.prorated_kwh_capacity is not None
                        else None
                    ),
                    kwh_charged=float(r.kwh_charged),
                    price_per_kwh=float(r.price_per_kwh),
                    subtotal=float(r.subtotal),
                )
                for r in d.renglones
            ],
            subtotal_before_taxes=float(base_cost),
            iva=float(iva),
            dap=float(dap),
            total=float(d.costo_total),
        )

        return BillingPeriodCostResponse(
            billing_period_id=billing_period_id,
            household_id=household_id,
            household_name=household.name,
            period_start=start_date,
            period_end=end_date,
            total_consumption_kwh=consumption_value,
            average_daily_kwh=float(avg_daily),
            tariff_code=d.tariff_code,
            total_cost_witout_taxes=float(base_cost),
            iva=float(iva),
            total_cost_with_iva=float(iva + base_cost),
            dap=float(dap),
            total_cost=float(d.costo_total),
            cost_per_kwh=float(d.cost_per_kwh),
            cfe_breakdown=cfe_breakdown,
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
            raise BillingServiceError("Household not found")

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
