"""Costo total module through the in-memory tariff catalog.

Ranges store monthly limits (100 / 100 / unlimited); the price of tier n in
month m is m * n, so the pricing month is visible in every result.
"""
from datetime import date
from decimal import Decimal
import unittest

from model.domain.billing_period_model import BillingPeriod
from model.domain.household_model import Household
from model.domain.household_tariff_model import HouseholdTariff
from model.domain.tariff_model import Tariff
from model.domain.tariff_range_model import TariffRange
from model.domain.tariff_version_model import TariffVersion
from services.business.costo_total import (
    CostoTotal, NoAsignacionVigente, PeriodoNotFound, RangosNotFound,
    VersionNotFound, ViviendaNotFound,
)
from services.business.costo_total_catalog import InMemoryTariffCatalog

D = Decimal
ALL = (1, 4, 5, 9, 10, 11, 12)


def _version(cat, tariff_id, month, vid, with_ranges=True):
    cat.add_version(TariffVersion(id=vid, tariff_id=tariff_id, year=2026, month=month))
    if with_ranges:
        for n, (lo, hi) in enumerate([(0, 100), (100, 200), (200, None)], start=1):
            cat.add_rango(TariffRange(
                tariff_version_id=vid, range_min=D(lo),
                range_max=None if hi is None else D(hi), price_per_kwh=D(month * n),
            ))


def _catalog(months=ALL, assign=True):
    cat = InMemoryTariffCatalog()
    cat.viviendas[1] = Household(name="Casa", id=1)
    cat.tarifas[1] = Tariff(code="1C", id=1)
    for m in months:
        _version(cat, 1, m, 100 + m)
    if assign:
        cat.add_asignacion(HouseholdTariff(household_id=1, tariff_id=1, start_date=date(2026, 1, 1)))
    return cat


def _calc(start, end, kwh, **kw):
    return CostoTotal(_catalog(**kw)).calculate(D(kwh), 1, start, end)


class PeriodCombinationsTests(unittest.TestCase):
    def assertTotals(self, r, base):
        base = D(str(base))
        self.assertAlmostEqual(r.costo_base, base, places=6)
        self.assertAlmostEqual(r.iva, base * D("0.16"), places=6)
        self.assertAlmostEqual(r.dap, base * D("0.05"), places=6)
        self.assertAlmostEqual(r.costo_total, base * D("1.21"), places=6)

    def months(self, r):
        return {l.segment_month for l in r.renglones}

    def test_full_summer_uses_midpoint_month_and_doubled_capacity(self):
        r = _calc(date(2026, 4, 1), date(2026, 5, 31), 250)
        self.assertEqual(self.months(r), {5})
        self.assertEqual(r.tariff_code, "1C")
        self.assertTotals(r, 200 * 5 + 50 * 10)

    def test_full_non_summer_uses_midpoint_month(self):
        r = _calc(date(2026, 11, 1), date(2026, 12, 31), 250)
        self.assertEqual(self.months(r), {12})
        self.assertTotals(r, 200 * 12 + 50 * 24)

    def test_season_crossing_with_15_or_more_minority_days_prorates_by_month(self):
        r = _calc(date(2026, 9, 1), date(2026, 10, 31), 250)
        sep_kwh = D(250) * 30 / 61
        oct_kwh = 250 - sep_kwh
        self.assertEqual(self.months(r), {9, 10})
        self.assertTotals(r, 100 * 9 + (sep_kwh - 100) * 18 + 100 * 10 + (oct_kwh - 100) * 20)
        self.assertEqual(sum(l.kwh_charged for l in r.renglones), 250)

    def test_season_crossing_with_fewer_than_15_minority_days_uses_midpoint(self):
        r = _calc(date(2026, 9, 20), date(2026, 10, 5), 250)
        self.assertEqual(self.months(r), {9})
        self.assertTotals(r, 200 * 9 + 50 * 18)

    def test_consumo_cero_has_zero_cost_per_kwh(self):
        r = _calc(date(2026, 4, 1), date(2026, 5, 31), 0)
        self.assertEqual(r.costo_total, 0)
        self.assertEqual(r.cost_per_kwh, 0)

    def test_cost_per_kwh_is_base_over_consumo(self):
        r = _calc(date(2026, 4, 1), date(2026, 5, 31), 250)
        self.assertEqual(r.cost_per_kwh, r.costo_base / 250)

    def test_decimals_are_not_rounded(self):
        r = _calc(date(2026, 9, 1), date(2026, 10, 31), 250)
        self.assertIsInstance(r.costo_base, Decimal)
        self.assertEqual(r.costo_base, sum(l.subtotal for l in r.renglones))
        self.assertEqual(r.iva, r.costo_base * D("0.16"))

    def test_tier_names_and_capacity(self):
        r = _calc(date(2026, 4, 1), date(2026, 5, 31), 250)
        self.assertEqual([l.tier_name for l in r.renglones], ["Básico", "Intermedio", "Excedente"])
        self.assertIsNone(r.renglones[-1].prorated_kwh_capacity)

    def test_missing_earlier_version_falls_back_to_latest_before(self):
        r = _calc(date(2026, 4, 1), date(2026, 5, 31), 100, months=(4,))
        self.assertTotals(r, 100 * 4)


class AsignacionTests(unittest.TestCase):
    def _cat(self):
        cat = _catalog(assign=False)
        cat.tarifas[2] = Tariff(code="1D", id=2)
        for m in (4, 5):
            _version(cat, 2, m, 200 + m)
        return cat

    def code(self, cat, d, end=None):
        return CostoTotal(cat).calculate(D(10), 1, d, end or d).tariff_code

    def assign(self, cat, tid, start, end=None):
        cat.add_asignacion(HouseholdTariff(household_id=1, tariff_id=tid, start_date=start, end_date=end))

    def test_start_and_end_inclusive_and_null_end_is_current(self):
        cat = self._cat()
        self.assign(cat, 1, date(2026, 4, 10), date(2026, 4, 20))
        self.assertEqual(self.code(cat, date(2026, 4, 10)), "1C")
        self.assertEqual(self.code(cat, date(2026, 4, 20)), "1C")
        for d in (date(2026, 4, 9), date(2026, 4, 21)):
            with self.assertRaises(NoAsignacionVigente):
                self.code(cat, d)
        self.assign(cat, 2, date(2026, 5, 1))
        self.assertEqual(self.code(cat, date(2026, 5, 20)), "1D")

    def test_overlap_picks_most_recent(self):
        cat = self._cat()
        self.assign(cat, 1, date(2026, 4, 1))
        self.assign(cat, 2, date(2026, 4, 15))
        self.assertEqual(self.code(cat, date(2026, 4, 20)), "1D")
        self.assertEqual(self.code(cat, date(2026, 4, 10)), "1C")

    def test_tariff_without_version_is_skipped(self):
        cat = _catalog(assign=False)
        cat.tarifas[2] = Tariff(code="1D", id=2)
        self.assign(cat, 1, date(2026, 4, 1))
        self.assign(cat, 2, date(2026, 4, 15))
        self.assertEqual(self.code(cat, date(2026, 4, 20)), "1C")

    def test_no_assignment_is_domain_error(self):
        with self.assertRaises(NoAsignacionVigente):
            CostoTotal(_catalog(assign=False)).calculate(D(1), 1, date(2026, 4, 1), date(2026, 5, 31))

    def test_periodo_end_overrides_effective_date(self):
        cat = self._cat()
        self.assign(cat, 1, date(2026, 4, 1), date(2026, 4, 30))
        self.assign(cat, 2, date(2026, 5, 1))
        cat.periodos[1] = BillingPeriod(1, date(2026, 4, 1), date(2026, 5, 31), id=1)
        ct = CostoTotal(cat)
        r = ct.calculate(D(50), 1, date(2026, 4, 1), date(2026, 4, 10), periodo_id=1)
        self.assertEqual(r.tariff_code, "1D")
        self.assertEqual({l.segment_month for l in r.renglones}, {5})
        self.assertEqual(r.costo_base, 250)
        r = ct.calculate(D(50), 1, date(2026, 4, 1), date(2026, 4, 10))
        self.assertEqual((r.tariff_code, r.costo_base), ("1C", 200))


class DomainErrorTests(unittest.TestCase):
    def test_missing_vivienda(self):
        with self.assertRaises(ViviendaNotFound):
            CostoTotal(_catalog()).calculate(D(1), 9, date(2026, 4, 1), date(2026, 5, 31))

    def test_missing_periodo(self):
        with self.assertRaises(PeriodoNotFound):
            CostoTotal(_catalog()).calculate(D(1), 1, date(2026, 4, 1), date(2026, 5, 31), periodo_id=9)

    def test_no_version_at_all_means_no_asignacion_vigente(self):
        with self.assertRaises(NoAsignacionVigente):
            _calc(date(2026, 4, 1), date(2026, 5, 31), 1, months=())

    def test_segment_without_version(self):
        # Midpoint (Oct 1) has a version; the September segment has none at or before it.
        cat = _catalog(months=())
        _version(cat, 1, 10, 110)
        with self.assertRaises(VersionNotFound):
            CostoTotal(cat).calculate(D(1), 1, date(2026, 9, 1), date(2026, 10, 31))

    def test_version_without_rangos(self):
        cat = _catalog(months=())
        _version(cat, 1, 5, 105, with_ranges=False)
        with self.assertRaises(RangosNotFound):
            CostoTotal(cat).calculate(D(1), 1, date(2026, 4, 1), date(2026, 5, 31))


class PeriodoReadOnceTests(unittest.TestCase):
    def test_a_periodo_is_read_once_per_calculation(self):
        cat = _catalog()
        cat.periodos[7] = BillingPeriod(1, date(2026, 4, 1), date(2026, 5, 31))
        reads = []
        original = cat.periodo
        cat.periodo = lambda pid: (reads.append(pid), original(pid))[1]
        CostoTotal(cat).calculate(D(100), 1, date(2026, 4, 1), date(2026, 4, 10), 7)
        self.assertEqual(reads, [7])


if __name__ == "__main__":
    unittest.main()
