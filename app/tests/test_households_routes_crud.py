import unittest

from model.domain.household_model import Household
from main import app
from fakes import FakeUoW, make_client


class ViviendaCrudTest(unittest.TestCase):
    def setUp(self):
        self.uow = FakeUoW()
        # make_client's __exit__ is set on the instance, so `with` never runs it
        # and dependency_overrides leak between tests; reset them here.
        app.dependency_overrides.clear()
        self.addCleanup(app.dependency_overrides.clear)

    def test_crea_una_vivienda(self):
        with make_client(self.uow) as client:
            r = client.post("/api/v1/households", json={"name": "Casa"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["name"], "Casa")
        self.assertEqual(r.json()["id"], 1)
        self.assertTrue(self.uow.committed)
        self.assertEqual(self.uow.household_repository.get(1).name, "Casa")

    def test_obtiene_una_vivienda_por_id(self):
        self.uow.household_repository.add(Household(name="Casa"))
        with make_client(self.uow) as client:
            r = client.get("/api/v1/households/1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "Casa")

    def test_lista_respeta_limit_y_offset(self):
        for n in ("A", "B", "C"):
            self.uow.household_repository.add(Household(name=n))
        with make_client(self.uow) as client:
            r = client.get("/api/v1/households?limit=1&offset=1")
        self.assertEqual([h["name"] for h in r.json()], ["B"])

    def test_actualiza_el_nombre_de_la_vivienda(self):
        self.uow.household_repository.add(Household(name="Casa"))
        with make_client(self.uow) as client:
            r = client.put("/api/v1/households/1", json={"name": "Depto"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "Depto")
        self.assertEqual(self.uow.household_repository.get(1).name, "Depto")

    def test_borra_la_vivienda(self):
        self.uow.household_repository.add(Household(name="Casa"))
        with make_client(self.uow) as client:
            r = client.delete("/api/v1/households/1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"deleted": True})
        self.assertIsNone(self.uow.household_repository.get(1))

    def test_vivienda_inexistente_devuelve_404_en_get_put_delete(self):
        with make_client(self.uow) as client:
            for r in (
                client.get("/api/v1/households/99"),
                client.put("/api/v1/households/99", json={"name": "x"}),
                client.delete("/api/v1/households/99"),
            ):
                self.assertEqual(r.status_code, 404)
                self.assertEqual(r.json()["message"], "Household not found")

    def test_nombre_demasiado_largo_es_rechazado_con_422(self):
        with make_client(self.uow) as client:
            r = client.post("/api/v1/households", json={"name": "x" * 101})
        self.assertEqual(r.status_code, 422)
        self.assertFalse(self.uow.committed)

    def test_actualizar_con_nombre_largo_es_422(self):
        self.uow.household_repository.add(Household(name="Casa"))
        with make_client(self.uow) as client:
            r = client.put("/api/v1/households/1", json={"name": "x" * 101})
        self.assertEqual(r.status_code, 422)

    def test_id_no_numerico_y_paginacion_invalida_son_422(self):
        with make_client(self.uow) as client:
            self.assertEqual(client.get("/api/v1/households/abc").status_code, 422)
            self.assertEqual(client.get("/api/v1/households?limit=0").status_code, 422)
            self.assertEqual(client.get("/api/v1/households?offset=-1").status_code, 422)

    def test_sin_autenticacion_devuelve_401(self):
        with make_client(self.uow, user=None) as client:
            self.assertEqual(client.get("/api/v1/households").status_code, 401)


if __name__ == "__main__":
    unittest.main()
