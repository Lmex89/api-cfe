import unittest

from fakes import FakeRepository, FakeUoW, make_client

BASE = "/api/v1/household-tariffs"


class _FilteringRepo(FakeRepository):
    """FakeRepository.list ignores filters; the real one filters by household/tariff."""

    def list(self, limit=100, offset=0, household_id=None, tariff_id=None, **_):
        rows = [
            i for i in self.items.values()
            if (household_id is None or i.household_id == household_id)
            and (tariff_id is None or i.tariff_id == tariff_id)
        ]
        return rows[offset : offset + limit]


def _uow():
    uow = FakeUoW()
    uow.household_tariff_repository = _FilteringRepo()
    return uow


def _body(**kw):
    return {"household_id": 1, "tariff_id": 1, "start_date": "2024-01-01", **kw}


class AsignacionValidaTest(unittest.TestCase):
    def test_crea_asignacion_vigente_sin_fecha_fin(self):
        uow = _uow()
        with make_client(uow) as client:
            r = client.post(BASE, json=_body())
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()["end_date"])
        self.assertEqual(r.json()["id"], 1)
        self.assertTrue(uow.committed)

    def test_crea_asignacion_con_intervalo_cerrado(self):
        with make_client(_uow()) as client:
            r = client.post(BASE, json=_body(end_date="2024-06-30"))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["end_date"], "2024-06-30")

    def test_obtiene_asignacion_por_id(self):
        with make_client(_uow()) as client:
            client.post(BASE, json=_body())
            r = client.get(f"{BASE}/1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["start_date"], "2024-01-01")

    def test_asignacion_inexistente_responde_404(self):
        with make_client(_uow()) as client:
            self.assertEqual(client.get(f"{BASE}/99").status_code, 404)
            self.assertEqual(client.put(f"{BASE}/99", json={}).status_code, 404)
            self.assertEqual(client.delete(f"{BASE}/99").status_code, 404)

    def test_lista_filtra_por_vivienda_y_tarifa(self):
        with make_client(_uow()) as client:
            client.post(BASE, json=_body(household_id=1, tariff_id=1))
            client.post(BASE, json=_body(household_id=2, tariff_id=1))
            client.post(BASE, json=_body(household_id=2, tariff_id=3))
            by_house = client.get(BASE, params={"household_id": 2}).json()
            both = client.get(BASE, params={"household_id": 2, "tariff_id": 3}).json()
        self.assertEqual([a["id"] for a in by_house], [2, 3])
        self.assertEqual([a["id"] for a in both], [3])

    def test_cierra_vigencia_actualizando_fecha_fin(self):
        with make_client(_uow()) as client:
            client.post(BASE, json=_body())
            r = client.put(f"{BASE}/1", json={"end_date": "2024-12-31"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["end_date"], "2024-12-31")
        self.assertEqual(r.json()["start_date"], "2024-01-01")

    def test_borra_asignacion(self):
        with make_client(_uow()) as client:
            client.post(BASE, json=_body())
            r = client.delete(f"{BASE}/1")
            self.assertEqual(r.json(), {"deleted": True})
            self.assertEqual(client.get(f"{BASE}/1").status_code, 404)


class AsignacionInvalidaTest(unittest.TestCase):
    def test_rechaza_ids_no_positivos_y_fecha_mal_formada(self):
        with make_client(_uow()) as client:
            for bad in (
                _body(household_id=0),
                _body(tariff_id=-1),
                _body(start_date="no-es-fecha"),
            ):
                self.assertEqual(client.post(BASE, json=bad).status_code, 422, bad)

    def test_rechaza_sin_fecha_inicio(self):
        with make_client(_uow()) as client:
            r = client.post(BASE, json={"household_id": 1, "tariff_id": 1})
        self.assertEqual(r.status_code, 422)

    # BUG (pinned): the API does not validate vigencia. These document current
    # behavior; if validation is added, flip the expected status to 4xx.
    def test_fecha_fin_anterior_a_inicio_se_acepta_hoy(self):
        with make_client(_uow()) as client:
            r = client.post(BASE, json=_body(end_date="2023-01-01"))
        self.assertEqual(r.status_code, 201)

    def test_asignaciones_traslapadas_de_una_vivienda_se_aceptan_hoy(self):
        with make_client(_uow()) as client:
            a = client.post(BASE, json=_body(end_date="2024-12-31"))
            b = client.post(BASE, json=_body(start_date="2024-06-01"))
        self.assertEqual((a.status_code, b.status_code), (201, 201))


if __name__ == "__main__":
    unittest.main()
