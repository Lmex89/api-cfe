from datetime import date
from decimal import Decimal
import unittest

from services.business import cfe_billing_calculator as calc
from services.business.period_utils import (
    first_day_of_month,
    last_day_of_month,
    midpoint_date,
    split_by_month_segments,
)
from services.tariff_version_normalizer import normalize_tariff_versions_history


class PuntoMedioDelPeriodoTest(unittest.TestCase):
    def test_periodo_bimestral_de_60_dias_cae_en_el_dia_30_desde_el_inicio(self):
        self.assertEqual(midpoint_date(date(2024, 1, 1), date(2024, 2, 29)), date(2024, 1, 30))

    def test_periodo_de_un_solo_dia_es_su_propio_punto_medio(self):
        self.assertEqual(midpoint_date(date(2024, 3, 5), date(2024, 3, 5)), date(2024, 3, 5))

    def test_diferencia_impar_redondea_hacia_abajo(self):
        self.assertEqual(midpoint_date(date(2024, 3, 1), date(2024, 3, 4)), date(2024, 3, 2))

    def test_punto_medio_cruza_fin_de_anio(self):
        self.assertEqual(midpoint_date(date(2023, 12, 20), date(2024, 1, 10)), date(2023, 12, 30))

    def test_fin_anterior_al_inicio_es_error(self):
        with self.assertRaises(ValueError):
            midpoint_date(date(2024, 2, 2), date(2024, 2, 1))


class DiasDeMesTest(unittest.TestCase):
    def test_primer_y_ultimo_dia_de_febrero_bisiesto_y_no_bisiesto(self):
        self.assertEqual(first_day_of_month(date(2024, 2, 17)), date(2024, 2, 1))
        self.assertEqual(last_day_of_month(date(2024, 2, 17)), date(2024, 2, 29))
        self.assertEqual(last_day_of_month(date(2023, 2, 1)), date(2023, 2, 28))


class ProrrateoPorMesDelPeriodoTest(unittest.TestCase):
    def test_periodo_dentro_de_un_mes_produce_un_segmento(self):
        (seg,) = split_by_month_segments(date(2024, 4, 10), date(2024, 4, 20))
        self.assertEqual((seg.month, seg.calendar_days, seg.segment_days), (4, 30, 11))
        self.assertEqual(seg.capacity_factor, Decimal("1"))

    def test_periodo_bimestral_completo_produce_dos_segmentos_con_mes_completo(self):
        segs = split_by_month_segments(date(2024, 1, 1), date(2024, 2, 29))
        self.assertEqual([(s.month, s.calendar_days, s.segment_days) for s in segs],
                         [(1, 31, 31), (2, 29, 29)])
        self.assertEqual(segs[1].end_date, date(2024, 2, 29))

    def test_periodo_parcial_en_ambos_extremos(self):
        segs = split_by_month_segments(date(2024, 1, 20), date(2024, 3, 10))
        self.assertEqual([s.segment_days for s in segs], [12, 29, 10])
        self.assertEqual(segs[0].start_date, date(2024, 1, 20))
        self.assertEqual(segs[1].start_date, date(2024, 2, 1))

    def test_periodo_cruza_fin_de_anio(self):
        segs = split_by_month_segments(date(2023, 12, 15), date(2024, 1, 15))
        self.assertEqual([(s.year, s.month, s.segment_days) for s in segs],
                         [(2023, 12, 17), (2024, 1, 15)])

    def test_dias_de_segmentos_suman_dias_inclusivos_del_periodo(self):
        start, end = date(2023, 11, 3), date(2024, 2, 27)
        total = sum(s.segment_days for s in split_by_month_segments(start, end))
        self.assertEqual(total, (end - start).days + 1)

    def test_fin_anterior_al_inicio_es_error(self):
        with self.assertRaises(ValueError):
            split_by_month_segments(date(2024, 2, 2), date(2024, 2, 1))


class NormalizadorDeVersionesDeTarifaTest(unittest.TestCase):
    def test_versiones_por_anio_y_mes_no_requieren_normalizacion_y_no_toca_el_uow(self):
        # ADR 0002: version keyed by year/month; the uow must not be touched.
        self.assertEqual(normalize_tariff_versions_history(object()), 0)


class ConstantesDeReglasTest(unittest.TestCase):
    def test_factor_de_punto_medio_duplica_rangos_mensuales_a_bimestre(self):
        self.assertEqual(calc.MIDPOINT_PERIOD_FACTOR, Decimal("2"))

    def test_verano_es_de_abril_a_septiembre(self):
        summer = [m for m in range(1, 13) if calc.CfeSequentialBillingCalculator._is_summer_month(m)]
        self.assertEqual(summer, [4, 5, 6, 7, 8, 9])


if __name__ == "__main__":
    unittest.main()
