"""UowTariffCatalog: Asignaciones most recent first, Versión fallback, Rangos."""
from datetime import date
from decimal import Decimal
import unittest

from fakes import FakeUoW
from model.domain.household_tariff_model import HouseholdTariff
from model.domain.tariff_range_model import TariffRange
from model.domain.tariff_version_model import TariffVersion
from services.business.costo_total_catalog import UowTariffCatalog


class UowTariffCatalogTests(unittest.TestCase):
    def setUp(self):
        self.uow = FakeUoW()
        self.catalog = UowTariffCatalog(self.uow)

    def test_asignaciones_are_most_recent_first_and_per_vivienda(self):
        add = self.uow.household_tariff_repository.add
        add(HouseholdTariff(household_id=1, tariff_id=1, start_date=date(2025, 1, 1)))
        add(HouseholdTariff(household_id=2, tariff_id=9, start_date=date(2025, 1, 1)))
        add(HouseholdTariff(household_id=1, tariff_id=2, start_date=date(2026, 1, 1)))
        self.assertEqual([a.tariff_id for a in self.catalog.asignaciones(1)], [2, 1])

    def test_version_falls_back_to_latest_earlier_month(self):
        for month in (1, 3):
            self.uow.tariff_version_repository.add(TariffVersion(tariff_id=1, year=2026, month=month))
        self.assertEqual(self.catalog.version(1, 2026, 3).month, 3)
        self.assertEqual(self.catalog.version(1, 2026, 2).month, 1)
        self.assertIsNone(self.catalog.version(1, 2025, 12))

    def test_rangos_belong_to_their_version(self):
        add = self.uow.tariff_range_repository.add
        add(TariffRange(tariff_version_id=1, range_min=Decimal(0), range_max=None, price_per_kwh=Decimal(1)))
        add(TariffRange(tariff_version_id=2, range_min=Decimal(0), range_max=None, price_per_kwh=Decimal(2)))
        self.assertEqual([r.price_per_kwh for r in self.catalog.rangos(2)], [Decimal(2)])


if __name__ == "__main__":
    unittest.main()
