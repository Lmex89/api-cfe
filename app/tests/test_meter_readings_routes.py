import unittest
from datetime import date
from decimal import Decimal

from fakes import FakeUoW, make_client
from services.business import MeterReadingConsumptionCalculator


def body(day, kwh, initial=False, household_id=1):
    return {"household_id": household_id, "reading_date": f"2026-01-{day:02d}",
            "reading_kwh": kwh, "is_initial": initial}


class LecturaRoutesTest(unittest.TestCase):
    def post(self, client, *a, **k):
        return client.post("/api/v1/meter-readings", json=body(*a, **k))

    def test_crea_lectura_inicial(self):
        uow = FakeUoW()
        with make_client(uow) as client:
            r = self.post(client, 1, "100.5", initial=True)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["is_initial"])
        self.assertEqual(r.json()["id"], 1)
        self.assertTrue(uow.committed)

    def test_lectura_duplicada_misma_vivienda_y_fecha_es_409(self):
        with make_client(FakeUoW()) as client:
            self.post(client, 1, "100")
            r = self.post(client, 1, "110")
        self.assertEqual(r.status_code, 409)

    def test_lectura_en_cero_o_negativa_es_422(self):
        with make_client(FakeUoW()) as client:
            self.assertEqual(self.post(client, 1, "0").status_code, 422)
            self.assertEqual(self.post(client, 1, "-5").status_code, 422)

    def test_lectura_inexistente_es_404(self):
        with make_client(FakeUoW()) as client:
            self.assertEqual(client.get("/api/v1/meter-readings/99").status_code, 404)
            self.assertEqual(client.delete("/api/v1/meter-readings/99").status_code, 404)

    def test_actualiza_y_borra_lectura(self):
        with make_client(FakeUoW()) as client:
            self.post(client, 1, "100")
            r = client.put("/api/v1/meter-readings/1", json={"reading_kwh": "120"})
            self.assertEqual(Decimal(str(r.json()["reading_kwh"])), Decimal("120"))
            self.assertEqual(client.delete("/api/v1/meter-readings/1").json(), {"deleted": True})
            self.assertEqual(client.get("/api/v1/meter-readings/1").status_code, 404)

    def test_actualizar_fecha_a_una_ya_ocupada_es_409(self):
        with make_client(FakeUoW()) as client:
            self.post(client, 1, "100")
            self.post(client, 2, "110")
            r = client.put("/api/v1/meter-readings/2", json={"reading_date": "2026-01-01"})
        self.assertEqual(r.status_code, 409)

    def test_lista_filtra_por_vivienda_y_rango_de_fechas(self):
        with make_client(FakeUoW()) as client:
            self.post(client, 1, "100")
            self.post(client, 10, "150")
            self.post(client, 5, "10", household_id=2)
            r = client.get("/api/v1/meter-readings?household_id=1&reading_date_from=2026-01-05")
        self.assertEqual([x["reading_date"] for x in r.json()], ["2026-01-10"])

    def test_lista_con_periodo_inexistente_es_404(self):
        with make_client(FakeUoW()) as client:
            r = client.get("/api/v1/meter-readings?billing_period_id=7")
        self.assertEqual(r.status_code, 404)


class LecturaDecrecienteYConsumoTest(unittest.TestCase):
    def consumo(self, uow):
        return MeterReadingConsumptionCalculator(uow).calculate_total(
            1, date(2026, 1, 1), date(2026, 1, 31))

    def test_consumo_es_ultima_menos_primera_lectura(self):
        uow = FakeUoW()
        with make_client(uow) as client:
            client.post("/api/v1/meter-readings", json=body(1, "100", True))
            client.post("/api/v1/meter-readings", json=body(15, "160"))
            client.post("/api/v1/meter-readings", json=body(30, "250"))
        self.assertEqual(self.consumo(uow), Decimal("150"))

    def test_una_sola_lectura_no_genera_consumo(self):
        uow = FakeUoW()
        with make_client(uow) as client:
            client.post("/api/v1/meter-readings", json=body(1, "100", True))
        self.assertEqual(self.consumo(uow), Decimal("0"))

    def test_lectura_decreciente_se_acepta_y_produce_consumo_negativo(self):
        # BUG (pinned): decreasing readings are accepted and yield negative Consumo.
        uow = FakeUoW()
        with make_client(uow) as client:
            client.post("/api/v1/meter-readings", json=body(1, "200", True))
            r = client.post("/api/v1/meter-readings", json=body(20, "150"))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.consumo(uow), Decimal("-50"))


if __name__ == "__main__":
    unittest.main()
