from datetime import date
from decimal import Decimal
import unittest

from model.domain.tariff_range_model import TariffRange
from model.domain.tariff_version_model import TariffVersion
from services.business.cfe_billing_calculator import CfeSequentialBillingCalculator


class _FakeTariffVersionRepository:
    def __init__(self, by_period):
        self.by_period = by_period

    def get_by_tariff_and_period_or_latest_before(self, tariff_id, year, month):
        return self.by_period.get((tariff_id, year, month))


class _FakeTariffRangeRepository:
    def __init__(self, by_version):
        self.by_version = by_version

    def list(self, tariff_version_id):
        return self.by_version.get(tariff_version_id, [])


class _FakeUow:
    def __init__(self, version_repo, range_repo):
        self.tariff_version_repository = version_repo
        self.tariff_range_repository = range_repo


def _build_calculator():
    april_version = TariffVersion(id=101, tariff_id=1, year=2026, month=4)
    may_version = TariffVersion(id=102, tariff_id=1, year=2026, month=5)
    september_version = TariffVersion(id=103, tariff_id=1, year=2026, month=9)
    october_version = TariffVersion(id=104, tariff_id=1, year=2026, month=10)
    november_version = TariffVersion(id=105, tariff_id=1, year=2026, month=11)

    version_repo = _FakeTariffVersionRepository(
        {
            (1, 2026, 4): april_version,
            (1, 2026, 5): may_version,
            (1, 2026, 9): september_version,
            (1, 2026, 10): october_version,
            (1, 2026, 11): november_version,
        }
    )

    range_repo = _FakeTariffRangeRepository(
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

    return CfeSequentialBillingCalculator(_FakeUow(version_repo, range_repo))


class CfeSequentialBillingCalculatorTests(unittest.TestCase):
    def test_full_summer_period_uses_midpoint_month_pricing_for_all_days(self):
        calc = _build_calculator()

        result = calc.calculate_cost(
            consumption_kwh=Decimal("110"),
            tariff_id=1,
            start_date=date(2026, 4, 20),
            end_date=date(2026, 5, 20),
        )

        months = {line.segment_month for line in result.tier_lines}
        self.assertEqual(months, {5})

        may_tier_1 = next(line for line in result.tier_lines if line.tier_level == 1)
        self.assertAlmostEqual(may_tier_1.price_per_kwh, 1.50, places=6)

    def test_single_segment_keeps_sequential_behavior(self):
        calc = _build_calculator()

        result = calc.calculate_cost(
            consumption_kwh=Decimal("150"),
            tariff_id=1,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )

        april_tier_1 = next(
            line
            for line in result.tier_lines
            if line.segment_year == 2026 and line.segment_month == 4 and line.tier_level == 1
        )
        april_tier_2 = next(
            line
            for line in result.tier_lines
            if line.segment_year == 2026 and line.segment_month == 4 and line.tier_level == 2
        )

        self.assertAlmostEqual(april_tier_1.kwh_charged, 100.0, places=6)
        self.assertAlmostEqual(april_tier_2.kwh_charged, 50.0, places=6)

    def test_full_non_summer_period_uses_midpoint_month_pricing_for_all_days(self):
        calc = _build_calculator()

        result = calc.calculate_cost(
            consumption_kwh=Decimal("90"),
            tariff_id=1,
            start_date=date(2026, 10, 20),
            end_date=date(2026, 11, 20),
        )

        months = {line.segment_month for line in result.tier_lines}
        self.assertEqual(months, {11})

        november_tier_1 = next(line for line in result.tier_lines if line.tier_level == 1)
        self.assertAlmostEqual(november_tier_1.price_per_kwh, 2.00, places=6)

    def test_cross_season_period_uses_proration_segments(self):
        calc = _build_calculator()

        result = calc.calculate_cost(
            consumption_kwh=Decimal("250"),
            tariff_id=1,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 10, 31),
        )

        months = {line.segment_month for line in result.tier_lines}
        self.assertEqual(months, {9, 10})

        charged = sum(line.kwh_charged for line in result.tier_lines)
        self.assertAlmostEqual(charged, 250.0, places=6)

    def test_cross_season_minority_under_15_days_uses_midpoint(self):
        calc = _build_calculator()

        result = calc.calculate_cost(
            consumption_kwh=Decimal("250"),
            tariff_id=1,
            start_date=date(2026, 9, 28),
            end_date=date(2026, 10, 5),
        )

        months = {line.segment_month for line in result.tier_lines}
        self.assertEqual(len(months), 1)

        charged = sum(line.kwh_charged for line in result.tier_lines)
        self.assertAlmostEqual(charged, 250.0, places=6)


if __name__ == "__main__":
    unittest.main()
