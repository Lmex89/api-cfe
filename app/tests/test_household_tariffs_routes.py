import unittest

from fakes import FakeUoW, make_client

BASE = "/api/v1/household-tariffs"


def _body(**kw):
    return {"household_id": 1, "tariff_id": 1, "start_date": "2024-01-01", **kw}


class AsignacionValidaTest(unittest.TestCase):
    def test_crea_asignacion_vigente_sin_fecha_fin(self):
        uow = FakeUoW()
        with make_client(uow) as client:
            r = client.post(BASE, json=_body())
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()["end_date"])
        self.assertEqual(r.json()["id"], 1)
        self.assertTrue(uow.committed)

    def test_crea_asignacion_con_intervalo_cerrado(self):
        with make_client(FakeUoW()) as client:
            r = client.post(BASE, json=_body(end_date="2024-06-30"))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["end_date"], "2024-06-30")

    def test_obtiene_asignacion_por_id(self):
        with make_client(FakeUoW()) as client:
            client.post(BASE, json=_body())
            r = client.get(f"{BASE}/1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["start_date"], "2024-01-01")

    def test_asignacion_inexistente_responde_404(self):
        with make_client(FakeUoW()) as client:
            self.assertEqual(client.get(f"{BASE}/99").status_code, 404)
            self.assertEqual(client.put(f"{BASE}/99", json={}).status_code, 404)
            self.assertEqual(client.delete(f"{BASE}/99").status_code, 404)

    def test_lista_filtra_por_vivienda_y_tarifa(self):
        with make_client(FakeUoW()) as client:
            client.post(BASE, json=_body(household_id=1, tariff_id=1))
            client.post(BASE, json=_body(household_id=2, tariff_id=1))
            client.post(BASE, json=_body(household_id=2, tariff_id=3))
            by_house = client.get(BASE, params={"household_id": 2}).json()
            both = client.get(BASE, params={"household_id": 2, "tariff_id": 3}).json()
        self.assertEqual([a["id"] for a in by_house], [2, 3])
        self.assertEqual([a["id"] for a in both], [3])

    def test_cierra_vigencia_actualizando_fecha_fin(self):
        with make_client(FakeUoW()) as client:
            client.post(BASE, json=_body())
            r = client.put(f"{BASE}/1", json={"end_date": "2024-12-31"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["end_date"], "2024-12-31")
        self.assertEqual(r.json()["start_date"], "2024-01-01")

    def test_borra_asignacion(self):
        with make_client(FakeUoW()) as client:
            client.post(BASE, json=_body())
            r = client.delete(f"{BASE}/1")
            self.assertEqual(r.json(), {"deleted": True})
            self.assertEqual(client.get(f"{BASE}/1").status_code, 404)


class AsignacionInvalidaTest(unittest.TestCase):
    def test_rechaza_ids_no_positivos_y_fecha_mal_formada(self):
        with make_client(FakeUoW()) as client:
            for bad in (
                _body(household_id=0),
                _body(tariff_id=-1),
                _body(start_date="no-es-fecha"),
            ):
                self.assertEqual(client.post(BASE, json=bad).status_code, 422, bad)

    def test_rechaza_sin_fecha_inicio(self):
        with make_client(FakeUoW()) as client:
            r = client.post(BASE, json={"household_id": 1, "tariff_id": 1})
        self.assertEqual(r.status_code, 422)

    # BUG (pinned): end_date < start_date is accepted (no vigencia validation).
    def test_fecha_fin_anterior_a_inicio_se_acepta_hoy(self):
        with make_client(FakeUoW()) as client:
            r = client.post(BASE, json=_body(end_date="2023-01-01"))
        self.assertEqual(r.status_code, 201)

    # BUG (pinned): overlapping assignments of one household are accepted.
    def test_asignaciones_traslapadas_de_una_vivienda_se_aceptan_hoy(self):
        with make_client(FakeUoW()) as client:
            a = client.post(BASE, json=_body(end_date="2024-12-31"))
            b = client.post(BASE, json=_body(start_date="2024-06-01"))
        self.assertEqual((a.status_code, b.status_code), (201, 201))


if __name__ == "__main__":
    unittest.main()
