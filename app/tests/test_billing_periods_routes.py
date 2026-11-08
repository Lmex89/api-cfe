import unittest

from fakes import FakeUoW, make_client

URL = "/api/v1/billing-periods"


def periodo(start="2024-01-01", end="2024-02-29", household_id=1):
    return {"household_id": household_id, "start_date": start, "end_date": end}


class CrearPeriodoTest(unittest.TestCase):
    def test_crea_un_periodo_valido_para_una_vivienda(self):
        uow = FakeUoW()
        with make_client(uow) as client:
            response = client.post(URL, json=periodo())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(
            (body["id"], body["household_id"], body["start_date"], body["end_date"]),
            (1, 1, "2024-01-01", "2024-02-29"),
        )
        self.assertTrue(uow.committed)

    def test_rechaza_fechas_con_formato_invalido(self):
        uow = FakeUoW()
        with make_client(uow) as client:
            response = client.post(URL, json=periodo(start="no-es-fecha"))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(uow.billing_period_repository.items, {})

    def test_rechaza_periodo_sin_fecha_final(self):
        with make_client(FakeUoW()) as client:
            response = client.post(URL, json={"household_id": 1, "start_date": "2024-01-01"})
        self.assertEqual(response.status_code, 422)

    def test_rechaza_vivienda_con_id_no_positivo(self):
        with make_client(FakeUoW()) as client:
            response = client.post(URL, json=periodo(household_id=0))
        self.assertEqual(response.status_code, 422)

    def test_requiere_autenticacion(self):
        with make_client(FakeUoW(), user=None) as client:
            response = client.post(URL, json=periodo())
        self.assertEqual(response.status_code, 401)


class PeriodoConsultaActualizaBorraTest(unittest.TestCase):
    def test_obtener_periodo_inexistente_devuelve_404(self):
        with make_client(FakeUoW()) as client:
            self.assertEqual(client.get(f"{URL}/99").status_code, 404)

    def test_actualiza_la_fecha_final_del_periodo(self):
        with make_client(FakeUoW()) as client:
            client.post(URL, json=periodo())
            response = client.put(f"{URL}/1", json={"end_date": "2024-03-01"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["end_date"], "2024-03-01")
        self.assertEqual(response.json()["start_date"], "2024-01-01")

    def test_borra_el_periodo(self):
        uow = FakeUoW()
        with make_client(uow) as client:
            client.post(URL, json=periodo())
            response = client.delete(f"{URL}/1")
        self.assertEqual(response.json(), {"deleted": True})
        self.assertEqual(uow.billing_period_repository.items, {})


class PeriodoValidacionesPendientesTest(unittest.TestCase):
    """Pinea el comportamiento ACTUAL: la API no valida orden de fechas ni traslapes.

    BUG (reportado): deberia rechazar fin < inicio y periodos traslapados
    de la misma vivienda. Si se corrige, invertir estas pruebas a 4xx.
    """

    # BUG (pinned): end < start is accepted.
    def test_acepta_periodo_con_fin_anterior_al_inicio_BUG(self):
        with make_client(FakeUoW()) as client:
            response = client.post(URL, json=periodo(start="2024-03-01", end="2024-01-01"))
        self.assertEqual(response.status_code, 201)

    # BUG (pinned): overlapping Periodos of one household are accepted.
    def test_acepta_periodos_traslapados_en_la_misma_vivienda_BUG(self):
        uow = FakeUoW()
        with make_client(uow) as client:
            first = client.post(URL, json=periodo("2024-01-01", "2024-02-29"))
            second = client.post(URL, json=periodo("2024-02-01", "2024-03-31"))
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertEqual(len(uow.billing_period_repository.items), 2)

    # BUG (pinned): updating end < start is accepted.
    def test_actualizar_fin_anterior_al_inicio_se_acepta_BUG(self):
        with make_client(FakeUoW()) as client:
            client.post(URL, json=periodo())
            response = client.put(f"{URL}/1", json={"end_date": "2023-01-01"})
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
