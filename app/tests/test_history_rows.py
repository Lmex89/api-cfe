from datetime import date
from decimal import Decimal
import unittest

from model.domain.meter_reading_model import MeterReading
from services.business.history_rows import build_history_rows


def lectura(d, kwh):
    return MeterReading(household_id=1, reading_date=d, reading_kwh=Decimal(kwh))


class HistorialDeLecturasTest(unittest.TestCase):
    def test_lista_vacia_da_sin_filas_y_consumo_cero(self):
        self.assertEqual(build_history_rows([]), ([], 0.0))

    def test_una_lectura_da_fila_vacia_y_consumo_cero(self):
        rows, total = build_history_rows([lectura(date(2026, 1, 1), "100")])
        self.assertEqual(total, 0.0)
        r = rows[0]
        self.assertIsNone(r.consumption_since_last)
        self.assertIsNone(r.days_since_last)
        self.assertIsNone(r.average_daily_consumption)
        self.assertEqual(r.cumulative_consumption, 0.0)

    def test_intervalos_de_distinta_duracion_suman_el_total(self):
        rows, total = build_history_rows([
            lectura(date(2026, 1, 1), "100"),
            lectura(date(2026, 1, 11), "150"),
            lectura(date(2026, 1, 13), "160"),
        ])
        self.assertEqual([r.consumption_since_last for r in rows], [None, 50.0, 10.0])
        self.assertEqual([r.days_since_last for r in rows], [None, 10, 2])
        self.assertEqual([r.average_daily_consumption for r in rows], [None, 5.0, 5.0])
        self.assertEqual([r.cumulative_consumption for r in rows], [0.0, 50.0, 60.0])
        self.assertEqual(total, 60.0)

    def test_dias_cero_no_trae_promedio(self):
        rows, _ = build_history_rows([
            lectura(date(2026, 1, 1), "100"),
            lectura(date(2026, 1, 1), "103"),
        ])
        self.assertEqual(rows[1].consumption_since_last, 3.0)
        self.assertEqual(rows[1].days_since_last, 0)
        self.assertIsNone(rows[1].average_daily_consumption)


if __name__ == "__main__":
    unittest.main()
