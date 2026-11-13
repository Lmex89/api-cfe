import unittest

from fakes import FakeUoW, make_client
from model.domain.billing_period_model import BillingPeriod
from model.domain.household_model import Household
from datetime import date
from services.business.billing_service import BillingServiceError
from services.dashboard_service import DashboardService
from services.errors import (
    BillingPeriodNotFoundError,
    BillingPeriodOwnershipError,
    HouseholdNotFoundError,
    InvalidFilterError,
)

H = "/api/v1/dashboards/household/1/meter-readings"


def _uow():
    uow = FakeUoW()
    uow.household_repository.add(Household(name="A"))
    uow.household_repository.add(Household(name="B"))
    uow.billing_period_repository.add(
        BillingPeriod(household_id=2, start_date=date(2026, 4, 1), end_date=date(2026, 5, 31))
    )
    return uow


class HistoryDomainErrorsToHttpTest(unittest.TestCase):
    def status(self, path):
        with make_client(_uow()) as client:
            return client.get(path).status_code

    def test_filtro_incompleto_400(self):
        self.assertEqual(self.status(H), 400)

    def test_inicio_posterior_a_fin_400(self):
        self.assertEqual(self.status(H + "?start_date=2026-05-01&end_date=2026-04-01"), 400)

    def test_periodo_de_otra_vivienda_400(self):
        self.assertEqual(self.status(H + "?billing_period_id=1"), 400)

    def test_vivienda_inexistente_404(self):
        self.assertEqual(
            self.status("/api/v1/dashboards/household/9/meter-readings?start_date=2026-04-01&end_date=2026-05-01"),
            404,
        )

    def test_periodo_inexistente_404(self):
        self.assertEqual(self.status(H + "?billing_period_id=99"), 404)


class ServicesRaiseOnlyDomainErrorsTest(unittest.TestCase):
    def history(self, **kw):
        return DashboardService(_uow()).get_household_meter_readings_with_history(**kw)

    def test_errores_de_dominio(self):
        with self.assertRaises(InvalidFilterError):
            self.history(household_id=1)
        with self.assertRaises(HouseholdNotFoundError):
            self.history(household_id=9, start_date=date(2026, 4, 1), end_date=date(2026, 5, 1))
        with self.assertRaises(BillingPeriodNotFoundError):
            self.history(household_id=1, billing_period_id=99)
        with self.assertRaises(BillingPeriodOwnershipError):
            self.history(household_id=1, billing_period_id=1)

    def test_billing_service_error_sin_codigo_http(self):
        self.assertFalse(hasattr(BillingServiceError("x"), "status_code"))


if __name__ == "__main__":
    unittest.main()
