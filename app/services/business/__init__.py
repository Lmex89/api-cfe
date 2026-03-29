"""Domain service for consumption calculations - SOLID principles."""

from datetime import date
from decimal import Decimal
from typing import Dict, List

from db.url_uow import UrlShortenerUnitofWork


class MeterReadingConsumptionCalculator:
    """
    SRP: Single Responsibility Principle
    Sole Purpose: Calculate consumption from meter readings only.
    """

    def __init__(self, uow: UrlShortenerUnitofWork):
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
        readings = self.uow.meter_reading_repository.list(
            household_id=household_id,
            reading_date_from=start_date,
            reading_date_to=end_date,
            limit=1000,
        )

        if not readings or len(readings) < 2:
            return Decimal("0")

        sorted_readings = sorted(readings, key=lambda r: r.reading_date)
        first_reading = sorted_readings[0].reading_kwh
        last_reading = sorted_readings[-1].reading_kwh

        return last_reading - first_reading

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
