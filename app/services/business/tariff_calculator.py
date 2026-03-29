"""Tariff cost calculation - handles tiered pricing logic."""

from datetime import date
from decimal import Decimal
from loguru import logger 
from common.api.errors.business_error import TariffCalculationError
from db.uow import TariffConsumptionUnitofWork
from model.dashboard_serializers import (
    ActiveTariffVersionResponse,
    TariffCostCalculationResponse,
)
from starlette import status


class RangeBasedTariffCalculator:
    """
    SRP: Single Responsibility Principle
    Sole Purpose: Calculate cost using tiered tariff ranges.
    """

    def __init__(self, uow: TariffConsumptionUnitofWork):
        self.uow = uow

    def calculate_cost(
        self,
        consumption_kwh: Decimal,
        tariff_id: int,
        effective_date: date,
    ) -> TariffCostCalculationResponse:
        """
        Calculate cost by applying tiered tariff ranges.
        Example:
          - 0-100 kWh: $0.10/kWh
          - 100-300 kWh: $0.15/kWh
          - >300 kWh: $0.20/kWh
        """

        tariff_version = self._get_active_tariff_version(tariff_id, effective_date)
        if not tariff_version:
            raise TariffCalculationError(
                "No active tariff version for this period",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

        ranges = self.uow.tariff_range_repository.list(
            tariff_version_id=tariff_version.id
        )
        if not ranges:
            raise TariffCalculationError(
                "No tariff ranges configured for active tariff version",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

        sorted_ranges = sorted(ranges, key=lambda r: r.range_min)

        total_cost = Decimal("0")
        remaining_kwh = consumption_kwh

        for tariff_range in sorted_ranges:
            if remaining_kwh <= 0:
                break

            # Calculate consumption in this range
            range_max = tariff_range.range_max or Decimal(999999)
            range_size = range_max - tariff_range.range_min
            consumption_in_range = min(remaining_kwh, range_size)

            # Apply price for this range
            range_cost = consumption_in_range * tariff_range.price_per_kwh
            total_cost += range_cost

            remaining_kwh -= consumption_in_range

        iva = total_cost * Decimal("0.16")  # Example IVA calculation (16%)
        dap = total_cost * Decimal("0.05")  # Example DAP calculation (5%)
        logger.info(f"Calculated cost: {total_cost}, IVA: {iva}, DAP: {dap}")

        return TariffCostCalculationResponse(
            total_cost=total_cost,
            tariff_version=tariff_version,
            iva=iva,
            dap=dap,
        )

    def _get_active_tariff_version(
        self, tariff_id: int, effective_date: date
    ) -> ActiveTariffVersionResponse | None:
        """
        DIP: Dependency Inversion Principle
        Find active tariff version without exposing query logic to caller.
        """
        versions = self.uow.tariff_version_repository.list(
            tariff_id=tariff_id, limit=1000
        )
        if not versions:
            return None

        for version in versions:
            if version.start_date <= effective_date:
                if version.end_date is None or version.end_date >= effective_date:
                    return ActiveTariffVersionResponse(
                        id=version.id,
                        tariff_id=version.tariff_id,
                        start_date=version.start_date,
                        end_date=version.end_date,
                    )

        return None
