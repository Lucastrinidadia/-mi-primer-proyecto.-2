import tempfile
import unittest
from datetime import date
from pathlib import Path

from sistema_apuestas.modelos import Resultado
from sistema_apuestas.seguimiento import Seguimiento


class TestSeguimiento(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.seg = Seguimiento(Path(self.dir.name) / "test.db")

    def tearDown(self):
        self.seg.cerrar()
        self.dir.cleanup()

    def _pick(self, **extra) -> int:
        base = dict(fecha_evento="2026-11-11T20:00:00", deporte="futbol",
                    competicion="Liga Test", evento="A vs B",
                    mercado="doble_oportunidad", seleccion="1X",
                    casa="CasaX", cuota=1.25, prob_estimada=0.83, ev=0.04,
                    clasificacion="A+", stake_unidades=1.5)
        base.update(extra)
        return self.seg.registrar(**base)

    def test_ciclo_completo(self):
        pid = self._pick()
        self.assertEqual(len(self.seg.pendientes()), 1)

        self.seg.fijar_cuota_cierre(pid, 1.18)
        self.seg.fijar_resultado(pid, Resultado.GANADA)

        m = self.seg.metricas()
        self.assertEqual(m.total, 1)
        self.assertEqual(m.ganadas, 1)
        self.assertAlmostEqual(m.beneficio_unidades, 1.5 * 0.25)
        self.assertAlmostEqual(m.tasa_acierto, 1.0)
        self.assertAlmostEqual(m.roi, 0.25)
        # CLV: 1.25 vs cierre 1.18 => positivo
        self.assertGreater(m.clv_medio_pct, 0.0)
        self.assertEqual(len(self.seg.pendientes()), 0)

    def test_perdida_y_nula(self):
        p1 = self._pick()
        p2 = self._pick(seleccion="Más de 1.5", mercado="total_goles",
                        stake_unidades=1.0)
        self.seg.fijar_resultado(p1, Resultado.PERDIDA)
        self.seg.fijar_resultado(p2, Resultado.NULA)
        m = self.seg.metricas()
        self.assertEqual((m.perdidas, m.nulas), (1, 1))
        self.assertAlmostEqual(m.beneficio_unidades, -1.5)
        self.assertAlmostEqual(m.tasa_acierto, 0.0)  # nulas no cuentan

    def test_demo_excluida_de_metricas(self):
        self._pick(es_demo=True)
        m = self.seg.metricas()
        self.assertEqual(m.total, 0)
        m_con_demo = self.seg.metricas(incluir_demo=True)
        self.assertEqual(m_con_demo.total, 1)

    def test_desglose_y_filtros(self):
        f = self._pick()
        t = self._pick(deporte="tenis", mercado="ganador", cuota=1.30,
                       stake_unidades=1.0)
        self.seg.fijar_resultado(f, Resultado.GANADA)
        self.seg.fijar_resultado(t, Resultado.PERDIDA)

        por_deporte = self.seg.desglose("deporte")
        self.assertIn("futbol", por_deporte)
        self.assertIn("tenis", por_deporte)
        self.assertEqual(por_deporte["futbol"].ganadas, 1)
        self.assertEqual(por_deporte["tenis"].perdidas, 1)

        por_mercado = self.seg.desglose("mercado")
        self.assertIn("doble_oportunidad", por_mercado)
        with self.assertRaises(ValueError):
            self.seg.desglose("otro_campo")

    def test_limites_diarios(self):
        self._pick(stake_unidades=2.0)
        pid = self._pick(stake_unidades=1.0)
        self.seg.fijar_resultado(pid, Resultado.PERDIDA)
        apostadas, perdidas, n = self.seg.apostado_en_fecha(date.today())
        self.assertAlmostEqual(apostadas, 3.0)
        self.assertAlmostEqual(perdidas, 1.0)
        self.assertEqual(n, 2)

    def test_resultado_pick_inexistente(self):
        with self.assertRaises(KeyError):
            self.seg.fijar_resultado(999, Resultado.GANADA)


if __name__ == "__main__":
    unittest.main()
