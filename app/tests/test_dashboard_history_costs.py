"""Meter-reading history: each row carries the cumulative Costo total from the first Lectura."""
from datetime import date
from decimal import Decimal
import unittest

from fakes import FakeUoW
from model.domain.household_model import Household
from model.domain.household_tariff_model import HouseholdTariff
from model.domain.meter_reading_model import MeterReading
from model.domain.tariff_model import Tariff
from model.domain.tariff_range_model import TariffRange
from model.domain.tariff_version_model import TariffVersion
from services.dashboard_service import DashboardService

D = Decimal


class HistoryRowCostTests(unittest.TestCase):
    def test_each_row_prices_cumulative_consumo_from_first_lectura(self):
        uow = FakeUoW()
        uow.household_repository.add(Household(name="Casa"))
        uow.tariff_repository.add(Tariff(code="1C"))
        v = TariffVersion(tariff_id=1, year=2026, month=4)
        uow.tariff_version_repository.add(v)
        # Flat price 2.00 per kWh (single unlimited Rango).
        uow.tariff_range_repository.add(
            TariffRange(tariff_version_id=v.id, range_min=D(0), range_max=None, price_per_kwh=D(2))
        )
        uow.household_tariff_repository.add(
            HouseholdTariff(household_id=1, tariff_id=1, start_date=date(2026, 1, 1))
        )
        for day, kwh, first in [(1, 1000, True), (10, 1050, False), (20, 1150, False)]:
            uow.meter_reading_repository.add(
                MeterReading(household_id=1, reading_date=date(2026, 4, day),
                             reading_kwh=D(kwh), is_initial=first)
            )

        r = DashboardService(uow).get_household_meter_readings_with_history(
            1, start_date=date(2026, 4, 1), end_date=date(2026, 4, 30)
        )

        costs = [row.billing_period_cost.total_cost_witout_taxes for row in r.readings]
        self.assertEqual(costs, [0, 100, 300])
        self.assertAlmostEqual(r.readings[2].billing_period_cost.total_cost, 300 * 1.21)

    def _seed_readings_only(self):
        uow = FakeUoW()
        uow.household_repository.add(Household(name="Casa"))
        for day, kwh, first in [(1, 1000, True), (10, 1050, False)]:
            uow.meter_reading_repository.add(
                MeterReading(household_id=1, reading_date=date(2026, 4, day),
                             reading_kwh=D(kwh), is_initial=first)
            )
        return uow

    def test_row_cost_is_null_when_household_has_no_tariff(self):
        r = DashboardService(self._seed_readings_only()).get_household_meter_readings_with_history(
            1, start_date=date(2026, 4, 1), end_date=date(2026, 4, 30)
        )
        self.assertEqual([row.billing_period_cost for row in r.readings], [None, None])
        self.assertEqual(r.readings[1].consumption_since_last, 50)

    def test_row_cost_is_null_on_any_billing_service_failure(self):
        from unittest.mock import patch
        from services.business.billing_service import BillingServiceError

        with patch(
            "services.dashboard_service.BillingService.calculate_cost_for_date_range",
            side_effect=BillingServiceError("Household not found", 422),
        ):
            r = DashboardService(self._seed_readings_only()).get_household_meter_readings_with_history(
                1, start_date=date(2026, 4, 1), end_date=date(2026, 4, 30)
            )
        self.assertEqual([row.billing_period_cost for row in r.readings], [None, None])


if __name__ == "__main__":
    unittest.main()
