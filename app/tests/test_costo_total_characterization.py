"""Characterization tests: freeze today's Costo total behaviour (issue #4).

Ranges store monthly limits (100 / 100 / unlimited); the price of tier n in
month m is m * n, so the pricing month is visible in every result.
"""
from datetime import date
from decimal import Decimal
import unittest

from fakes import FakeUoW
from model.domain.billing_period_model import BillingPeriod
from model.domain.household_model import Household
from model.domain.household_tariff_model import HouseholdTariff
from model.domain.meter_reading_model import MeterReading
from model.domain.tariff_model import Tariff
from model.domain.tariff_range_model import TariffRange
from model.domain.tariff_version_model import TariffVersion
from services.business.billing_service import BillingService, BillingServiceError
from services.business.costo_total import NoAsignacionVigente

D = Decimal


def _add_version(uow, tariff_id, year, month):
    v = TariffVersion(tariff_id=tariff_id, year=year, month=month)
    uow.tariff_version_repository.add(v)
    for n, (lo, hi) in enumerate([(0, 100), (100, 200), (200, None)], start=1):
        uow.tariff_range_repository.add(
            TariffRange(
                tariff_version_id=v.id,
                range_min=D(lo),
                range_max=None if hi is None else D(hi),
                price_per_kwh=D(month * n),
            )
        )
    return v


def _world(months=(1, 4, 5, 9, 10, 11, 12)):
    uow = FakeUoW()
    uow.household_repository.add(Household(name="Casa"))
    uow.tariff_repository.add(Tariff(code="1C"))
    for m in months:
        _add_version(uow, 1, 2026, m)
    return uow


def _readings(uow, start, end, kwh, household_id=1):
    uow.meter_reading_repository.add(
        MeterReading(household_id=household_id, reading_date=start, reading_kwh=D(1000), is_initial=True)
    )
    uow.meter_reading_repository.add(
        MeterReading(household_id=household_id, reading_date=end, reading_kwh=D(1000) + D(kwh))
    )


def _assign(uow, tariff_id, start, end=None, household_id=1):
    uow.household_tariff_repository.add(
        HouseholdTariff(household_id=household_id, tariff_id=tariff_id, start_date=start, end_date=end)
    )


def _cost(start, end, kwh, months=(1, 4, 5, 9, 10, 11, 12)):
    uow = _world(months)
    _assign(uow, 1, date(2026, 1, 1))
    _readings(uow, start, end, kwh)
    uow.billing_period_repository.add(BillingPeriod(household_id=1, start_date=start, end_date=end))
    return BillingService(uow).calculate_billing_period_cost(1)


class CostoTotalPeriodCombinationsTests(unittest.TestCase):
    def assertTotals(self, r, base):
        base = float(base)
        self.assertAlmostEqual(r.total_cost_witout_taxes, base, places=6)
        self.assertAlmostEqual(r.iva, base * 0.16, places=6)
        self.assertAlmostEqual(r.dap, base * 0.05, places=6)
        self.assertAlmostEqual(r.total_cost, base * 1.21, places=6)

    def test_full_summer_period_prices_with_midpoint_month_and_doubled_capacity(self):
        # Midpoint 2026-05-01 -> May prices (5/10/15), caps 200/200/inf.
        r = _cost(date(2026, 4, 1), date(2026, 5, 31), 250)
        self.assertEqual(r.total_consumption_kwh, 250)
        self.assertEqual({l.segment_month for l in r.cfe_breakdown.tier_lines}, {5})
        self.assertTotals(r, 200 * 5 + 50 * 10)

    def test_full_non_summer_period_prices_with_midpoint_month_and_doubled_capacity(self):
        # Midpoint 2026-12-01 -> December prices (12/24/36).
        r = _cost(date(2026, 11, 1), date(2026, 12, 31), 250)
        self.assertEqual({l.segment_month for l in r.cfe_breakdown.tier_lines}, {12})
        self.assertTotals(r, 200 * 12 + 50 * 24)

    def test_season_crossing_with_15_or_more_minority_days_prorates_by_month(self):
        # Sep (30 d) + Oct (31 d); consumption split by days, tiers filled per month.
        r = _cost(date(2026, 9, 1), date(2026, 10, 31), 250)
        sep_kwh = 250 * 30 / 61
        oct_kwh = 250 - sep_kwh
        sep = 100 * 9 + (sep_kwh - 100) * 18
        octo = 100 * 10 + (oct_kwh - 100) * 20
        self.assertEqual({l.segment_month for l in r.cfe_breakdown.tier_lines}, {9, 10})
        self.assertTotals(r, sep + octo)

    def test_season_crossing_with_fewer_than_15_minority_days_uses_midpoint(self):
        # Sep 20-30 (11 d) vs Oct 1-5 (5 d): midpoint 2026-09-27 -> Sep prices, caps doubled.
        r = _cost(date(2026, 9, 20), date(2026, 10, 5), 250)
        self.assertEqual({l.segment_month for l in r.cfe_breakdown.tier_lines}, {9})
        self.assertTotals(r, 200 * 9 + 50 * 18)

    def test_consumo_cero_costs_nothing_and_has_zero_cost_per_kwh(self):
        r = _cost(date(2026, 4, 1), date(2026, 5, 31), 0)
        self.assertEqual(r.total_consumption_kwh, 0)
        self.assertTotals(r, 0)
        self.assertEqual(r.cost_per_kwh, 0)


class AsignacionSelectionTests(unittest.TestCase):
    def _service(self):
        uow = _world()
        uow.tariff_repository.add(Tariff(code="1D"))  # id 2
        for m in (4, 5):
            _add_version(uow, 2, 2026, m)
        return uow, BillingService(uow)

    def code(self, svc, d):
        try:
            return svc.costo_total.calculate(Decimal(0), 1, d, d).tariff_code
        except NoAsignacionVigente:
            return None

    def test_start_and_end_dates_are_inclusive(self):
        uow, svc = self._service()
        _assign(uow, 1, date(2026, 4, 10), date(2026, 4, 20))
        self.assertEqual(self.code(svc, date(2026, 4, 10)), "1C")
        self.assertEqual(self.code(svc, date(2026, 4, 20)), "1C")
        self.assertIsNone(self.code(svc, date(2026, 4, 9)))
        self.assertIsNone(self.code(svc, date(2026, 4, 21)))

    def test_null_end_date_means_current(self):
        uow, svc = self._service()
        _assign(uow, 1, date(2026, 4, 1))
        self.assertEqual(self.code(svc, date(2026, 5, 1)), "1C")

    def test_overlap_picks_most_recent_start(self):
        uow, svc = self._service()
        _assign(uow, 1, date(2026, 4, 1))  # added in ascending start order, like the repo
        _assign(uow, 2, date(2026, 4, 15))
        self.assertEqual(self.code(svc, date(2026, 4, 20)), "1D")
        self.assertEqual(self.code(svc, date(2026, 4, 10)), "1C")

    def test_no_current_assignment_returns_none(self):
        uow, svc = self._service()
        _assign(uow, 1, date(2026, 1, 1), date(2026, 3, 31))
        self.assertIsNone(self.code(svc, date(2026, 4, 5)))

    def test_no_assignments_returns_none(self):
        _, svc = self._service()
        self.assertIsNone(self.code(svc, date(2026, 4, 5)))

    def test_tariff_without_version_is_skipped_for_older_assignment(self):
        uow = _world()
        uow.tariff_repository.add(Tariff(code="1D"))  # id 2, no versions at all
        _assign(uow, 1, date(2026, 4, 1))
        _assign(uow, 2, date(2026, 4, 15))
        self.assertEqual(self.code(BillingService(uow), date(2026, 4, 20)), "1C")

    def test_only_assignment_without_version_gives_none(self):
        uow = _world()
        uow.tariff_repository.add(Tariff(code="1D"))
        _assign(uow, 2, date(2026, 4, 1))
        self.assertIsNone(self.code(BillingService(uow), date(2026, 4, 20)))

    def test_cost_without_active_assignment_is_422(self):
        uow = _world()
        _readings(uow, date(2026, 4, 1), date(2026, 5, 31), 100)
        uow.billing_period_repository.add(BillingPeriod(1, date(2026, 4, 1), date(2026, 5, 31)))
        with self.assertRaises(BillingServiceError) as cm:
            BillingService(uow).calculate_billing_period_cost(1)
        self.assertEqual(cm.exception.message, "No active tariff for this period")
        self.assertEqual(cm.exception.status_code, 422)


class PeriodoEndOverrideTests(unittest.TestCase):
    def _uow(self):
        uow = _world()
        uow.tariff_repository.add(Tariff(code="1D"))  # id 2
        for m in (4, 5):
            _add_version(uow, 2, 2026, m)
        _assign(uow, 1, date(2026, 4, 1), date(2026, 4, 30))
        _assign(uow, 2, date(2026, 5, 1))
        _readings(uow, date(2026, 4, 1), date(2026, 4, 10), 50)
        uow.billing_period_repository.add(BillingPeriod(1, date(2026, 4, 1), date(2026, 5, 31)))
        return uow

    def test_with_billing_period_effective_date_uses_period_end(self):
        # midpoint(04-01, period end 05-31) = 05-01 -> assignment 1D, May prices.
        r = BillingService(self._uow()).calculate_cost_for_date_range(
            1, date(2026, 4, 1), date(2026, 4, 10), billing_period_id=1
        )
        self.assertEqual(r.tariff_code, "1D")
        self.assertEqual({l.segment_month for l in r.cfe_breakdown.tier_lines}, {5})
        self.assertAlmostEqual(r.total_cost_witout_taxes, 50 * 5, places=6)

    def test_without_billing_period_effective_date_uses_range_end(self):
        # midpoint(04-01, 04-10) = 04-05 -> assignment 1C, April prices.
        r = BillingService(self._uow()).calculate_cost_for_date_range(
            1, date(2026, 4, 1), date(2026, 4, 10)
        )
        self.assertEqual(r.tariff_code, "1C")
        self.assertEqual({l.segment_month for l in r.cfe_breakdown.tier_lines}, {4})
        self.assertAlmostEqual(r.total_cost_witout_taxes, 50 * 4, places=6)


class MissingVersionOrRangosTests(unittest.TestCase):
    def test_missing_version_for_every_month_gives_no_active_tariff_422(self):
        uow = _world(months=())
        _assign(uow, 1, date(2026, 1, 1))
        _readings(uow, date(2026, 4, 1), date(2026, 5, 31), 100)
        uow.billing_period_repository.add(BillingPeriod(1, date(2026, 4, 1), date(2026, 5, 31)))
        with self.assertRaises(BillingServiceError) as cm:
            BillingService(uow).calculate_billing_period_cost(1)
        self.assertEqual(cm.exception.message, "No active tariff for this period")

    def test_missing_earlier_version_falls_back_silently_to_latest_before(self):
        # Only April is fed; a May-priced period uses April's version.
        r = _cost(date(2026, 4, 1), date(2026, 5, 31), 100, months=(4,))
        self.assertAlmostEqual(r.total_cost_witout_taxes, 100 * 4, places=6)

    def test_version_without_rangos_is_422(self):
        uow = _world(months=())
        uow.tariff_version_repository.add(TariffVersion(tariff_id=1, year=2026, month=5))
        _assign(uow, 1, date(2026, 1, 1))
        _readings(uow, date(2026, 4, 1), date(2026, 5, 31), 100)
        uow.billing_period_repository.add(BillingPeriod(1, date(2026, 4, 1), date(2026, 5, 31)))
        with self.assertRaises(BillingServiceError) as cm:
            BillingService(uow).calculate_billing_period_cost(1)
        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("No tariff ranges configured", cm.exception.message)


if __name__ == "__main__":
    unittest.main()
