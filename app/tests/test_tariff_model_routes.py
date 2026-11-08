import unittest

from fakes import FakeUoW, make_client


class TarifaRoutesTest(unittest.TestCase):
    def setUp(self):
        self.uow = FakeUoW()

    def test_crear_tarifa_devuelve_201_y_confirma(self):
        with make_client(self.uow) as c:
            r = c.post("/api/v1/tariffs", json={"code": "1C", "description": "Cálida"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["code"], "1C")
        self.assertTrue(self.uow.committed)

    def test_crear_tarifa_con_codigo_duplicado_da_409(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariffs", json={"code": "1C"})
            r = c.post("/api/v1/tariffs", json={"code": "1C"})
        self.assertEqual(r.status_code, 409)

    def test_crear_tarifa_sin_codigo_o_codigo_largo_es_invalido(self):
        with make_client(self.uow) as c:
            for body in ({}, {"code": ""}, {"code": "x" * 11}):
                self.assertIn(c.post("/api/v1/tariffs", json=body).status_code, (400, 422))

    def test_obtener_tarifa_inexistente_da_404(self):
        with make_client(self.uow) as c:
            self.assertEqual(c.get("/api/v1/tariffs/99").status_code, 404)

    def test_listar_y_obtener_tarifa(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariffs", json={"code": "1C"})
            self.assertEqual(len(c.get("/api/v1/tariffs").json()), 1)
            self.assertEqual(c.get("/api/v1/tariffs/1").json()["code"], "1C")

    def test_actualizar_tarifa_cambia_descripcion(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariffs", json={"code": "1C"})
            r = c.put("/api/v1/tariffs/1", json={"description": "nueva"})
        self.assertEqual(r.json()["description"], "nueva")

    def test_actualizar_tarifa_con_codigo_de_otra_da_409(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariffs", json={"code": "1C"})
            c.post("/api/v1/tariffs", json={"code": "1D"})
            r = c.put("/api/v1/tariffs/2", json={"code": "1C"})
        self.assertEqual(r.status_code, 409)

    def test_actualizar_o_borrar_tarifa_inexistente_da_404(self):
        with make_client(self.uow) as c:
            self.assertEqual(c.put("/api/v1/tariffs/9", json={"code": "Z"}).status_code, 404)
            self.assertEqual(c.delete("/api/v1/tariffs/9").status_code, 404)

    def test_borrar_tarifa(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariffs", json={"code": "1C"})
            r = c.delete("/api/v1/tariffs/1")
            self.assertEqual(r.json(), {"deleted": True})
            self.assertEqual(c.get("/api/v1/tariffs/1").status_code, 404)


class VersionDeTarifaRoutesTest(unittest.TestCase):
    def setUp(self):
        self.uow = FakeUoW()
        self.body = {"tariff_id": 1, "year": 2025, "month": 3}

    def test_crear_version_devuelve_201(self):
        with make_client(self.uow) as c:
            r = c.post("/api/v1/tariff-versions", json=self.body)
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.json()["year"], r.json()["month"]), (2025, 3))

    def test_crear_version_duplicada_para_tarifa_anio_mes_da_409(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariff-versions", json=self.body)
            r = c.post("/api/v1/tariff-versions", json=self.body)
        self.assertEqual(r.status_code, 409)

    def test_crear_version_con_mes_o_anio_fuera_de_rango_es_invalido(self):
        with make_client(self.uow) as c:
            for patch in ({"month": 0}, {"month": 13}, {"year": 1899}, {"year": 3001}, {"tariff_id": 0}):
                r = c.post("/api/v1/tariff-versions", json={**self.body, **patch})
                self.assertIn(r.status_code, (400, 422), patch)

    def test_listar_versiones_filtra_por_tarifa(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariff-versions", json=self.body)
            c.post("/api/v1/tariff-versions", json={**self.body, "tariff_id": 2})
            r = c.get("/api/v1/tariff-versions", params={"tariff_id": 2})
        self.assertEqual([v["tariff_id"] for v in r.json()], [2])

    def test_listar_con_limite_invalido_es_invalido(self):
        with make_client(self.uow) as c:
            r = c.get("/api/v1/tariff-versions", params={"limit": 0})
        self.assertIn(r.status_code, (400, 422))

    def test_obtener_version_inexistente_da_404(self):
        with make_client(self.uow) as c:
            self.assertEqual(c.get("/api/v1/tariff-versions/9").status_code, 404)

    def test_actualizar_version_a_periodo_ocupado_da_409(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariff-versions", json=self.body)
            c.post("/api/v1/tariff-versions", json={**self.body, "month": 4})
            r = c.put("/api/v1/tariff-versions/2", json={"month": 3})
        self.assertEqual(r.status_code, 409)

    def test_actualizar_version_mes_invalido_es_invalido(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariff-versions", json=self.body)
            r = c.put("/api/v1/tariff-versions/1", json={"month": 13})
        self.assertIn(r.status_code, (400, 422))

    def test_actualizar_version_a_periodo_libre(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariff-versions", json=self.body)
            r = c.put("/api/v1/tariff-versions/1", json={"month": 5})
        self.assertEqual(r.json()["month"], 5)

    def test_actualizar_y_borrar_version_inexistente_da_404(self):
        with make_client(self.uow) as c:
            self.assertEqual(c.put("/api/v1/tariff-versions/9", json={"month": 1}).status_code, 404)
            self.assertEqual(c.delete("/api/v1/tariff-versions/9").status_code, 404)

    def test_borrar_version(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariff-versions", json=self.body)
            self.assertEqual(c.delete("/api/v1/tariff-versions/1").json(), {"deleted": True})
            self.assertEqual(c.get("/api/v1/tariff-versions/1").status_code, 404)


class RangoRoutesTest(unittest.TestCase):
    def setUp(self):
        self.uow = FakeUoW()
        self.body = {"tariff_version_id": 1, "range_min": "0", "range_max": "75", "price_per_kwh": "0.9"}

    def test_crear_rango_devuelve_201(self):
        with make_client(self.uow) as c:
            r = c.post("/api/v1/tariff-ranges", json=self.body)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(float(r.json()["price_per_kwh"]), 0.9)

    def test_crear_rango_ultimo_sin_tope(self):
        with make_client(self.uow) as c:
            body = {**self.body, "range_min": "75"}
            del body["range_max"]
            r = c.post("/api/v1/tariff-ranges", json=body)
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()["range_max"])

    def test_crear_rango_con_precio_cero_o_version_invalida_es_invalido(self):
        with make_client(self.uow) as c:
            for patch in ({"price_per_kwh": "0"}, {"price_per_kwh": "-1"}, {"tariff_version_id": 0}):
                r = c.post("/api/v1/tariff-ranges", json={**self.body, **patch})
                self.assertIn(r.status_code, (400, 422), patch)

    def test_listar_rangos_filtra_por_version(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariff-ranges", json=self.body)
            c.post("/api/v1/tariff-ranges", json={**self.body, "tariff_version_id": 2})
            r = c.get("/api/v1/tariff-ranges", params={"tariff_version_id": 2})
        self.assertEqual([x["tariff_version_id"] for x in r.json()], [2])

    def test_obtener_actualizar_borrar_rango_inexistente_da_404(self):
        with make_client(self.uow) as c:
            self.assertEqual(c.get("/api/v1/tariff-ranges/9").status_code, 404)
            self.assertEqual(c.put("/api/v1/tariff-ranges/9", json={"range_max": "1"}).status_code, 404)
            self.assertEqual(c.delete("/api/v1/tariff-ranges/9").status_code, 404)

    def test_actualizar_rango_cambia_precio(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariff-ranges", json=self.body)
            r = c.put("/api/v1/tariff-ranges/1", json={"price_per_kwh": "1.2"})
        self.assertEqual(float(r.json()["price_per_kwh"]), 1.2)

    def test_borrar_rango(self):
        with make_client(self.uow) as c:
            c.post("/api/v1/tariff-ranges", json=self.body)
            self.assertEqual(c.delete("/api/v1/tariff-ranges/1").json(), {"deleted": True})
            self.assertEqual(c.get("/api/v1/tariff-ranges/1").status_code, 404)


class AutenticacionTest(unittest.TestCase):
    def test_rutas_del_modelo_de_tarifas_sin_token_dan_401(self):
        with make_client(FakeUoW(), user=None) as c:
            for p in ("tariffs", "tariff-versions", "tariff-ranges"):
                self.assertEqual(c.get(f"/api/v1/{p}").status_code, 401, p)


if __name__ == "__main__":
    unittest.main()
