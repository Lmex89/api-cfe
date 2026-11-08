import asyncio
import json
import unittest

from fakes import FakeUoW, make_client
from main import app
from model.errors import EntityNotFoundException, http420_error_handler


class ErrorDeNegocioTest(unittest.TestCase):
    def test_vivienda_inexistente_responde_404_con_message_status_details(self):
        with make_client(FakeUoW()) as client:
            r = client.get("/api/v1/households/999")
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertEqual(body["message"], "Household not found")
        self.assertEqual(body["status"], 404)
        self.assertIn("details", body)

    def test_periodo_inexistente_en_dashboard_propaga_status_del_error_de_negocio(self):
        # BUG (pinned): BillingService uses 422 (not 404) for a missing Periodo.
        with make_client(FakeUoW()) as client:
            r = client.get("/api/v1/dashboards/billing-period/999")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(r.json()), {"message", "status", "details"})
        self.assertEqual(r.json()["message"], "Billing period not found")

    def test_dashboard_con_rango_invertido_responde_400(self):
        with make_client(FakeUoW()) as client:
            r = client.get(
                "/api/v1/dashboards/household/1/consumption",
                params={"start_date": "2026-02-01", "end_date": "2026-01-01"},
            )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["status"], 400)

    def test_entidad_no_encontrada_responde_420_con_message_y_data(self):
        resp = asyncio.run(http420_error_handler(None, EntityNotFoundException("falta")))
        self.assertEqual(resp.status_code, 420)
        body = json.loads(resp.body)
        self.assertEqual(body["message"], "falta")
        self.assertEqual(set(body), {"message", "data"})

    def test_handler_420_esta_registrado_en_la_app(self):
        self.assertIs(app.exception_handlers[EntityNotFoundException], http420_error_handler)


class ErrorDeValidacionTest(unittest.TestCase):
    def test_cuerpo_invalido_responde_422_con_message_status_details(self):
        with make_client(FakeUoW()) as client:
            r = client.post("/api/v1/households", json={"name": "x" * 101})
        self.assertEqual(r.status_code, 422)
        body = r.json()
        self.assertEqual(body["message"], "Error en la validación de la petición")
        self.assertEqual(body["status"], 422)
        self.assertIsInstance(body["details"], str)

    def test_parametro_de_query_fuera_de_rango_responde_422(self):
        with make_client(FakeUoW()) as client:
            r = client.get("/api/v1/households", params={"limit": 0})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["status"], 422)

    def test_id_no_numerico_responde_422(self):
        with make_client(FakeUoW()) as client:
            r = client.get("/api/v1/households/abc")
        self.assertEqual(r.status_code, 422)

    def test_sin_token_responde_401_con_formato_consistente(self):
        with make_client(FakeUoW(), user=None) as client:
            r = client.get("/api/v1/households")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["status"], 401)


if __name__ == "__main__":
    unittest.main()
