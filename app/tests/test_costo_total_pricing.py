from datetime import date
from decimal import Decimal
import unittest

from model.domain.tariff_range_model import TariffRange
from model.domain.tariff_version_model import TariffVersion
from model.domain.household_model import Household
from model.domain.household_tariff_model import HouseholdTariff
from model.domain.tariff_model import Tariff
from services.business.costo_total import CostoTotal
from services.business.costo_total_catalog import InMemoryTariffCatalog


def _build_calculator():
    april_version = TariffVersion(id=101, tariff_id=1, year=2026, month=4)
    may_version = TariffVersion(id=102, tariff_id=1, year=2026, month=5)
    september_version = TariffVersion(id=103, tariff_id=1, year=2026, month=9)
    october_version = TariffVersion(id=104, tariff_id=1, year=2026, month=10)
    november_version = TariffVersion(id=105, tariff_id=1, year=2026, month=11)

    catalog = InMemoryTariffCatalog()
    catalog.viviendas[1] = Household(name="Casa", id=1)
    catalog.tarifas[1] = Tariff(code="1C", id=1)
    catalog.add_asignacion(
        HouseholdTariff(household_id=1, tariff_id=1, start_date=date(2026, 1, 1))
    )
    for v in (april_version, may_version, september_version, october_version, november_version):
        catalog.add_version(v)

    ranges_by_version = (
        {
            101: [
                TariffRange(
                    tariff_version_id=101,
                    range_min=Decimal("0"),
                    range_max=Decimal("100"),
                    price_per_kwh=Decimal("1.00"),
                ),
                TariffRange(
                    tariff_version_id=101,
                    range_min=Decimal("100"),
                    range_max=Decimal("200"),
                    price_per_kwh=Decimal("2.00"),
                ),
                TariffRange(
                    tariff_version_id=101,
                    range_min=Decimal("200"),
                    range_max=None,
                    price_per_kwh=Decimal("3.00"),
                ),
            ],
            102: [
                TariffRange(
                    tariff_version_id=102,
                    range_min=Decimal("0"),
                    range_max=Decimal("200"),
                    price_per_kwh=Decimal("1.50"),
                ),
                TariffRange(
                    tariff_version_id=102,
                    range_min=Decimal("200"),
                    range_max=Decimal("350"),
                    price_per_kwh=Decimal("2.50"),
                ),
                TariffRange(
                    tariff_version_id=102,
                    range_min=Decimal("350"),
                    range_max=None,
                    price_per_kwh=Decimal("3.50"),
                ),
            ],
            103: [
                TariffRange(
                    tariff_version_id=103,
                    range_min=Decimal("0"),
                    range_max=Decimal("100"),
                    price_per_kwh=Decimal("1.20"),
                ),
                TariffRange(
                    tariff_version_id=103,
                    range_min=Decimal("100"),
                    range_max=Decimal("200"),
                    price_per_kwh=Decimal("2.20"),
                ),
                TariffRange(
                    tariff_version_id=103,
                    range_min=Decimal("200"),
                    range_max=None,
                    price_per_kwh=Decimal("3.20"),
                ),
            ],
            104: [
                TariffRange(
                    tariff_version_id=104,
                    range_min=Decimal("0"),
                    range_max=Decimal("100"),
                    price_per_kwh=Decimal("1.80"),
                ),
                TariffRange(
                    tariff_version_id=104,
                    range_min=Decimal("100"),
                    range_max=Decimal("200"),
                    price_per_kwh=Decimal("2.80"),
                ),
                TariffRange(
                    tariff_version_id=104,
                    range_min=Decimal("200"),
                    range_max=None,
                    price_per_kwh=Decimal("3.80"),
                ),
            ],
            105: [
                TariffRange(
                    tariff_version_id=105,
                    range_min=Decimal("0"),
                    range_max=Decimal("100"),
                    price_per_kwh=Decimal("2.00"),
                ),
                TariffRange(
                    tariff_version_id=105,
                    range_min=Decimal("100"),
                    range_max=Decimal("200"),
                    price_per_kwh=Decimal("3.00"),
                ),
                TariffRange(
                    tariff_version_id=105,
                    range_min=Decimal("200"),
                    range_max=None,
                    price_per_kwh=Decimal("4.00"),
                ),
            ],
        }
    )

    for ranges in ranges_by_version.values():
        for r in ranges:
            catalog.add_rango(r)
    return CostoTotal(catalog)


class CostoTotalPricingTests(unittest.TestCase):
    def test_full_summer_period_uses_midpoint_month_pricing_for_all_days(self):
        calc = _build_calculator()

        result = calc.calculate(Decimal("110"), 1, date(2026, 4, 20), date(2026, 5, 20))

        months = {line.segment_month for line in result.renglones}
        self.assertEqual(months, {5})

        may_tier_1 = next(line for line in result.renglones if line.tier_level == 1)
        self.assertAlmostEqual(float(may_tier_1.price_per_kwh), 1.50, places=6)

    def test_single_segment_doubles_monthly_capacity_for_60day_convention(self):
        # Ranges store MONTHLY limits; the midpoint path doubles them for the
        # ~60-day billing period convention (MIDPOINT_PERIOD_FACTOR=2).
        calc = _build_calculator()

        result = calc.calculate(Decimal("150"), 1, date(2026, 4, 1), date(2026, 4, 30))

        april_tier_1 = next(
            line
            for line in result.renglones
            if line.segment_year == 2026 and line.segment_month == 4 and line.tier_level == 1
        )
        april_tier_2 = next(
            line
            for line in result.renglones
            if line.segment_year == 2026 and line.segment_month == 4 and line.tier_level == 2
        )

        # Tier 1 monthly limit 100 -> doubled capacity 200 kWh for the period.
        self.assertAlmostEqual(float(april_tier_1.kwh_charged), 150.0, places=6)
        self.assertAlmostEqual(float(april_tier_2.kwh_charged), 0.0, places=6)

    def test_midpoint_segment_applies_capacity_factor_2(self):
        calc = _build_calculator()

        segment = calc._midpoint_segment(date(2026, 4, 1), date(2026, 4, 30))

        self.assertEqual(segment.capacity_factor, Decimal("2"))

    def test_month_segments_keep_capacity_factor_1(self):
        from services.business.period_utils import split_by_month_segments

        segments = split_by_month_segments(date(2026, 9, 1), date(2026, 10, 31))

        self.assertEqual([s.month for s in segments], [9, 10])
        for segment in segments:
            self.assertEqual(segment.capacity_factor, Decimal("1"))

    def test_full_non_summer_period_uses_midpoint_month_pricing_for_all_days(self):
        calc = _build_calculator()

        result = calc.calculate(Decimal("90"), 1, date(2026, 10, 20), date(2026, 11, 20))

        months = {line.segment_month for line in result.renglones}
        self.assertEqual(months, {11})

        november_tier_1 = next(line for line in result.renglones if line.tier_level == 1)
        self.assertAlmostEqual(float(november_tier_1.price_per_kwh), 2.00, places=6)

    def test_cross_season_period_uses_proration_segments(self):
        calc = _build_calculator()

        result = calc.calculate(Decimal("250"), 1, date(2026, 9, 1), date(2026, 10, 31))

        months = {line.segment_month for line in result.renglones}
        self.assertEqual(months, {9, 10})

        charged = float(sum(line.kwh_charged for line in result.renglones))
        self.assertAlmostEqual(charged, 250.0, places=6)

    def test_cross_season_minority_under_15_days_uses_midpoint(self):
        calc = _build_calculator()

        result = calc.calculate(Decimal("250"), 1, date(2026, 9, 28), date(2026, 10, 5))

        months = {line.segment_month for line in result.renglones}
        self.assertEqual(len(months), 1)

        charged = float(sum(line.kwh_charged for line in result.renglones))
        self.assertAlmostEqual(charged, 250.0, places=6)


if __name__ == "__main__":
    unittest.main()
