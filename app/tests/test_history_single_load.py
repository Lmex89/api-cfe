"""History loads Household/Periodo/Lecturas once; per-row cost reuses the cumulative Consumo."""
from collections import Counter
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
from services.business.billing_service import BillingService
from services.dashboard_service import DashboardService
from services.errors import (
    BillingPeriodNotFoundError, BillingPeriodOwnershipError,
    HouseholdNotFoundError, InvalidFilterError,
)

D = Decimal


def seed(n_readings=4, tariff=True):
    uow = FakeUoW()
    uow.household_repository.add(Household(name="Casa"))
    uow.household_repository.add(Household(name="Otra"))
    uow.billing_period_repository.add(BillingPeriod(household_id=1, start_date=date(2026, 4, 1), end_date=date(2026, 5, 31)))
    uow.billing_period_repository.add(BillingPeriod(household_id=2, start_date=date(2026, 4, 1), end_date=date(2026, 5, 31)))
    if tariff:
        uow.tariff_repository.add(Tariff(code="1C"))
        for month in (4, 5):
            v = TariffVersion(tariff_id=1, year=2026, month=month)
            uow.tariff_version_repository.add(v)
            uow.tariff_range_repository.add(TariffRange(tariff_version_id=v.id, range_min=D(0), range_max=D(100), price_per_kwh=D("1.5")))
            uow.tariff_range_repository.add(TariffRange(tariff_version_id=v.id, range_min=D(100), range_max=None, price_per_kwh=D("3")))
        uow.household_tariff_repository.add(HouseholdTariff(household_id=1, tariff_id=1, start_date=date(2026, 1, 1)))
    for i in range(n_readings):
        uow.meter_reading_repository.add(MeterReading(
            household_id=1, reading_date=date(2026, 4, 1).fromordinal(date(2026, 4, 1).toordinal() + 7 * i),
            reading_kwh=D(1000 + 60 * i * i), is_initial=(i == 0)))
    return uow


def count_calls(uow):
    calls = Counter()
    for name in vars(uow):
        repo = getattr(uow, name)
        if not name.endswith("_repository"):
            continue
        for meth in ("get", "list", "get_by_billing_period_and_date_range",
                     "get_first_reading_in_range", "get_last_reading_in_range",
                     "get_by_tariff_and_period_or_latest_before"):
            orig = getattr(repo, meth, None)
            if orig is None:
                continue
            def wrap(*a, _o=orig, _k=f"{name}.{meth}", **kw):
                calls[_k] += 1
                return _o(*a, **kw)
            setattr(repo, meth, wrap)
    return calls


class CharacterizationTests(unittest.TestCase):
    """Rows and totals are pinned by hand; each row's cost equals the legacy per-row path
    (Consumo re-read from first/last Lectura, then priced), as origin/main computed it."""

    def _legacy_costs(self, uow, readings, bp_id):
        svc = BillingService(uow)
        return [
            svc.calculate_cost_for_date_range(1, readings[0].reading_date, r.reading_date, bp_id)
            for r in readings
        ]

    def _check(self, bp_id, **filters):
        uow = seed()
        readings = uow.meter_reading_repository.get_by_billing_period_and_date_range(1, date(2026, 4, 1), date(2026, 5, 31))
        legacy = self._legacy_costs(uow, readings, bp_id)
        r = DashboardService(uow).get_household_meter_readings_with_history(1, **filters)
        self.assertEqual([x.billing_period_cost for x in r.readings], legacy)
        self.assertGreater(legacy[-1].total_cost, 0)
        # seed: 1000, 1060, 1240, 1540 kWh, one week apart
        self.assertEqual([x.consumption_since_last for x in r.readings], [None, 60, 180, 300])
        self.assertEqual([x.days_since_last for x in r.readings], [None, 7, 7, 7])
        self.assertEqual(
            [x.average_daily_consumption_since_last for x in r.readings],
            [None, 60 / 7, 180 / 7, 300 / 7],
        )
        self.assertEqual((r.number_of_readings, r.total_consumption_kwh), (4, 540))

    def test_filtro_por_periodo_coincide_con_el_legado(self):
        self._check(1, billing_period_id=1)

    def test_filtro_por_fechas_coincide_con_el_legado(self):
        self._check(None, start_date=date(2026, 4, 1), end_date=date(2026, 5, 31))


class QueryCountTests(unittest.TestCase):
    def _calls(self, n):
        uow = seed(n)
        calls = count_calls(uow)
        DashboardService(uow).get_household_meter_readings_with_history(1, billing_period_id=1)
        return calls

    def test_lecturas_no_crecen_con_el_numero_de_lecturas(self):
        self.assertEqual(self._calls(3), self._calls(8))


class FilterAndErrorTests(unittest.TestCase):
    def setUp(self):
        self.uow = seed()
        self.svc = DashboardService(self.uow)

    def hist(self, **kw):
        return self.svc.get_household_meter_readings_with_history(1, **kw)

    def test_fechas_explicitas_sustituyen_cada_fecha_del_periodo(self):
        r = self.hist(billing_period_id=1, start_date=date(2026, 4, 8))
        self.assertEqual((r.period.start, r.period.end), (date(2026, 4, 8), date(2026, 5, 31)))
        self.assertEqual(r.billing_period.id, 1)
        self.assertEqual(r.number_of_readings, 3)

    def test_solo_fechas_no_trae_periodo(self):
        r = self.hist(start_date=date(2026, 4, 1), end_date=date(2026, 4, 10))
        self.assertIsNone(r.billing_period)
        self.assertEqual(r.number_of_readings, 2)

    def test_periodo_de_otra_vivienda(self):
        with self.assertRaises(BillingPeriodOwnershipError):
            self.hist(billing_period_id=2)

    def test_filtro_incompleto(self):
        with self.assertRaises(InvalidFilterError):
            self.hist(start_date=date(2026, 4, 1))

    def test_inicio_posterior_al_fin(self):
        with self.assertRaises(InvalidFilterError):
            self.hist(start_date=date(2026, 5, 1), end_date=date(2026, 4, 1))

    def test_vivienda_y_periodo_inexistentes(self):
        with self.assertRaises(HouseholdNotFoundError):
            self.svc.get_household_meter_readings_with_history(99, billing_period_id=1)
        with self.assertRaises(BillingPeriodNotFoundError):
            self.hist(billing_period_id=99)

    def test_vivienda_sin_tarifa_da_costo_nulo_en_todas_las_filas(self):
        svc = DashboardService(seed(tariff=False))
        r = svc.get_household_meter_readings_with_history(1, billing_period_id=1)
        self.assertEqual([x.billing_period_cost for x in r.readings], [None] * 4)
        self.assertEqual(r.readings[1].consumption_since_last, 60)

    def test_fila_sin_asignacion_tiene_costo_nulo_y_las_demas_se_costean(self):
        # Fecha efectiva = midpoint(first, row): Apr 1, 4, 8, 11. Asignación from Apr 6.
        self.uow.household_tariff_repository.items[1].start_date = date(2026, 4, 6)
        r = self.hist(start_date=date(2026, 4, 1), end_date=date(2026, 4, 30))
        costs = [x.billing_period_cost for x in r.readings]
        self.assertEqual(costs[:2], [None, None])
        self.assertTrue(all(c is not None for c in costs[2:]))


if __name__ == "__main__":
    unittest.main()
