"""Domain service for consumption calculations - SOLID principles."""

from datetime import date
from decimal import Decimal
from typing import Dict, List

from db.uow import TariffConsumptionUnitofWork


class MeterReadingConsumptionCalculator:
    """
    SRP: Single Responsibility Principle
    Sole Purpose: Calculate consumption from meter readings only.
    """

    def __init__(self, uow: TariffConsumptionUnitofWork):
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

        if first_reading.id == last_reading.id:
            return Decimal("0")

        return last_reading.reading_kwh - first_reading.reading_kwh

    def calculate_average_daily(
        self,
        household_id: int,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """Average daily consumption = total_consumption / days."""
        total = self.calculate_total(household_id, start_date, end_date)
        days = (end_date - start_date).days or 1
        return total / Decimal(days) if days > 0 else Decimal("0")

    def get_readings_in_range(
        self,
        household_id: int,
        start_date: date,
        end_date: date,
    ) -> List[Dict]:
        """Get all readings for visualization/audit."""
        readings = self.uow.meter_reading_repository.list(
            household_id=household_id,
            reading_date_from=start_date,
            reading_date_to=end_date,
            limit=1000,
        )
        return [
            {
                "date": str(r.reading_date),
                "reading_kwh": float(r.reading_kwh),
                "is_initial": r.is_initial,
            }
            for r in readings
        ]
