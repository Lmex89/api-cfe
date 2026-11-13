"""Domain service for consumption calculations - SOLID principles."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from services.business.history_rows import consumption_between

if TYPE_CHECKING:
    from db.uow import TariffConsumptionUnitofWork


class MeterReadingConsumptionCalculator:
    """
    SRP: Single Responsibility Principle
    Sole Purpose: Calculate consumption from meter readings only.
    """

    def __init__(self, uow: "TariffConsumptionUnitofWork"):
        self.uow = uow

    def calculate_total(
        self,
        household_id: int,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """
        Total consumption = final_reading_kwh - initial_reading_kwh
        """
        first_reading = self.uow.meter_reading_repository.get_first_reading_in_range(
            household_id=household_id,
            reading_date_from=start_date,
            reading_date_to=end_date,
        )
        last_reading = self.uow.meter_reading_repository.get_last_reading_in_range(
            household_id=household_id,
            reading_date_from=start_date,
            reading_date_to=end_date,
        )

        if not first_reading or not last_reading:
            return Decimal("0")

        return consumption_between(first_reading, last_reading)
