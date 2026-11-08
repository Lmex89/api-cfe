import unittest

from model.domain.household_model import Household
from fakes import FakeUoW, make_client


class ListarViviendasTest(unittest.TestCase):
    def test_lista_las_viviendas_existentes(self):
        uow = FakeUoW()
        uow.household_repository.add(Household(name="Casa"))
        with make_client(uow) as client:
            response = client.get("/api/v1/households")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([h["name"] for h in response.json()], ["Casa"])


if __name__ == "__main__":
    unittest.main()
