from datetime import date
from decimal import Decimal
import unittest

from fakes import FakeRepository, FakeUoW, make_client
from main import app
from model.domain.billing_period_model import BillingPeriod
from model.domain.household_model import Household
from model.domain.household_tariff_model import HouseholdTariff
from model.domain.meter_reading_model import MeterReading
from model.domain.tariff_model import Tariff
from model.domain.tariff_range_model import TariffRange
from model.domain.tariff_version_model import TariffVersion


class _Readings(FakeRepository):
    def _in_range(self, household_id, reading_date_from, reading_date_to):
        return sorted(
            (
                r for r in self.items.values()
                if r.household_id == household_id
                and reading_date_from <= r.reading_date <= reading_date_to
            ),
            key=lambda r: r.reading_date,
        )

    def get_first_reading_in_range(self, household_id, reading_date_from, reading_date_to):
        found = self._in_range(household_id, reading_date_from, reading_date_to)
        return found[0] if found else None

    def get_last_reading_in_range(self, household_id, reading_date_from, reading_date_to):
        found = self._in_range(household_id, reading_date_from, reading_date_to)
        return found[-1] if found else None

    def list(self, household_id=None, reading_date_from=None, reading_date_to=None, limit=100, offset=0, **_):
        return self._in_range(household_id, reading_date_from, reading_date_to)


class _ByHousehold(FakeRepository):
    def list(self, household_id=None, limit=100, offset=0, **_):
        return [i for i in self.items.values() if i.household_id == household_id]


class _Versions(FakeRepository):
    """Mimics the real repo: exact month, else latest earlier version."""

    def get_by_tariff_and_period_or_latest_before(self, tariff_id, year, month):
        earlier = [
            v for v in self.items.values()
            if v.tariff_id == tariff_id and (v.year, v.month) <= (year, month)
        ]
        return max(earlier, key=lambda v: (v.year, v.month), default=None)


class _Ranges(FakeRepository):
    def list(self, tariff_version_id=None, **_):
        return [r for r in self.items.values() if r.tariff_version_id == tariff_version_id]


def _uow(version_month=1):
    """Vivienda 1 with Tarifa 1D, Periodo Apr-May 2026, Lecturas 1000 -> 1250."""
    uow = FakeUoW()
    uow.meter_reading_repository = _Readings()
    uow.household_tariff_repository = _ByHousehold()
    uow.billing_period_repository = _ByHousehold()
    uow.tariff_version_repository = _Versions()
    uow.tariff_range_repository = _Ranges()

    uow.household_repository.add(Household(name="Casa"))
    uow.tariff_repository.add(Tariff(code="1D"))
    uow.household_tariff_repository.add(
        HouseholdTariff(household_id=1, tariff_id=1, start_date=date(2026, 1, 1))
    )
    uow.billing_period_repository.add(
        BillingPeriod(household_id=1, start_date=date(2026, 4, 1), end_date=date(2026, 5, 31))
    )
    uow.meter_reading_repository.add(
        MeterReading(1, date(2026, 4, 1), Decimal("1000"), is_initial=True)
    )
    uow.meter_reading_repository.add(MeterReading(1, date(2026, 5, 31), Decimal("1250")))
    uow.tariff_version_repository.add(
        TariffVersion(tariff_id=1, year=2026, month=version_month)
    )
    # Monthly limits; the 60-day Periodo doubles them (ADR 0003: escalonado).
    for lo, hi, price in ((0, 100, "1"), (100, 200, "2"), (200, None, "3")):
        uow.tariff_range_repository.add(
            TariffRange(
                tariff_version_id=1,
                range_min=Decimal(lo),
                range_max=None if hi is None else Decimal(hi),
                price_per_kwh=Decimal(price),
            )
        )
    return uow


class DashboardPeriodoTest(unittest.TestCase):
    # make_client's patched instance __exit__ is never called by `with`, so
    # dependency_overrides leak between tests (fakes.py bug); reset them here.
    def setUp(self):
        app.dependency_overrides.clear()
        self.addCleanup(app.dependency_overrides.clear)

    def get(self, path, uow=None, **kw):
        with make_client(uow or _uow(), **kw) as client:
            return client.get(path)

    def test_costo_total_es_costo_base_mas_iva_16_y_dap_5(self):
        body = self.get("/api/v1/dashboards/billing-period/1").json()
        # 250 kWh escalonado: 200*1 + 50*2 = 300 base
        self.assertEqual(body["total_consumption_kwh"], 250)
        self.assertAlmostEqual(body["total_cost_witout_taxes"], 300)
        self.assertAlmostEqual(body["iva"], 48)
        self.assertAlmostEqual(body["dap"], 15)
        self.assertAlmostEqual(body["total_cost"], 363)
        self.assertAlmostEqual(body["total_cost_with_iva"], 348)
        self.assertEqual(body["tariff_code"], "1D")

    def test_consumo_promedio_diario_divide_entre_dias_del_periodo(self):
        body = self.get("/api/v1/dashboards/billing-period/1").json()
        self.assertAlmostEqual(body["average_daily_kwh"], 250 / 60, places=4)

    def test_desglose_por_rango_llena_cada_rango_antes_del_siguiente(self):
        lines = self.get("/api/v1/dashboards/billing-period/1").json()["cfe_breakdown"]["tier_lines"]
        charged = [round(line["kwh_charged"]) for line in lines]
        self.assertEqual(charged[:2], [200, 50])
        self.assertEqual(sum(charged), 250)

    def test_mes_de_tarifa_faltante_usa_la_ultima_version_anterior(self):
        # Only a January Versión de tarifa exists; Apr/May fall back to it.
        response = self.get("/api/v1/dashboards/billing-period/1", _uow(version_month=1))
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.json()["total_cost"], 363)

    def test_sin_version_de_tarifa_anterior_responde_422(self):
        response = self.get("/api/v1/dashboards/billing-period/1", _uow(version_month=12))
        self.assertEqual(response.status_code, 422)

    def test_periodo_inexistente_responde_422(self):
        self.assertEqual(self.get("/api/v1/dashboards/billing-period/99").status_code, 422)

    def test_vivienda_sin_asignacion_responde_422(self):
        uow = _uow()
        uow.household_tariff_repository.items.clear()
        self.assertEqual(self.get("/api/v1/dashboards/billing-period/1", uow).status_code, 422)

    def test_sin_token_responde_401(self):
        self.assertEqual(self.get("/api/v1/dashboards/billing-period/1", user=None).status_code, 401)


class DashboardViviendaTest(unittest.TestCase):
    def get(self, path, uow=None):
        with make_client(uow or _uow()) as client:
            return client.get(path)

    def test_consumo_de_la_vivienda_incluye_total_promedio_y_lecturas(self):
        body = self.get(
            "/api/v1/dashboards/household/1/consumption?start_date=2026-04-01&end_date=2026-05-31"
        ).json()
        self.assertEqual(body["household"], {"id": 1, "name": "Casa"})
        self.assertEqual(body["total_consumption_kwh"], 250)
        self.assertAlmostEqual(body["average_daily_kwh"], 250 / 60, places=4)
        self.assertEqual(body["number_of_readings"], 2)
        self.assertEqual([r["reading_kwh"] for r in body["readings"]], [1000, 1250])
        self.assertTrue(body["readings"][0]["is_initial"])

    def test_rango_con_inicio_posterior_al_fin_responde_400(self):
        r = self.get("/api/v1/dashboards/household/1/consumption?start_date=2026-05-31&end_date=2026-04-01")
        self.assertEqual(r.status_code, 400)

    def test_vivienda_inexistente_responde_422(self):
        r = self.get("/api/v1/dashboards/household/9/consumption?start_date=2026-04-01&end_date=2026-05-31")
        self.assertEqual(r.status_code, 422)

    def test_resumen_suma_consumo_y_costo_total_de_los_periodos(self):
        body = self.get(
            "/api/v1/dashboards/household/1/billing-summary?start_date=2026-04-01&end_date=2026-05-31"
        ).json()
        self.assertEqual(body["number_of_periods"], 1)
        self.assertEqual(body["total_consumption_kwh"], 250)
        self.assertAlmostEqual(body["total_cost"], 363)

    def test_resumen_omite_periodos_fuera_del_rango(self):
        body = self.get(
            "/api/v1/dashboards/household/1/billing-summary?start_date=2026-06-01&end_date=2026-07-31"
        ).json()
        self.assertEqual(body["number_of_periods"], 0)
        self.assertEqual(body["total_cost"], 0)


if __name__ == "__main__":
    unittest.main()
