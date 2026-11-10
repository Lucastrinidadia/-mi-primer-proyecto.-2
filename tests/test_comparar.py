import unittest
from datetime import datetime, timedelta, timezone

from sistema_apuestas.bankroll import PlanBankroll
from sistema_apuestas.comparar import candidatos, cuotas_minimas, evaluar_cuota
from sistema_apuestas.demo import eventos_demo
from sistema_apuestas.modelos import (Clasificacion, CuotaCasa, Deporte,
                                      Evento, MercadoEvento)


def _mercado_una_casa(c_sel: float, c_otro: float) -> MercadoEvento:
    m = MercadoEvento(seleccion="Gana Local", mercado="ganador")
    m.cuotas.append(CuotaCasa("Referencia", c_sel))
    m.cuotas_mercado_completo["Referencia"] = [c_sel, c_otro]
    return m


def _evento() -> Evento:
    return Evento(Deporte.BASQUET, "NBA", "Local", "Visitante",
                  datetime.now(timezone.utc) + timedelta(hours=6),
                  fuente="test")


class TestCuotasMinimas(unittest.TestCase):
    def test_umbral_a_y_a_plus(self):
        u = cuotas_minimas(0.886)
        self.assertAlmostEqual(u["justa"], 1 / 0.886, places=4)
        self.assertAlmostEqual(u["min_a"], 1.16)        # ceil(1.02/0.886)
        self.assertAlmostEqual(u["min_a_plus"], 1.18)   # ceil(1.045/0.886)

    def test_sin_a_plus_bajo_82(self):
        u = cuotas_minimas(0.77)
        self.assertAlmostEqual(u["min_a"], 1.33)
        self.assertIsNone(u["min_a_plus"])

    def test_sin_candidato_bajo_75(self):
        u = cuotas_minimas(0.60)
        self.assertIsNone(u["min_a"])
        self.assertIsNone(u["min_a_plus"])
        with self.assertRaises(ValueError):
            cuotas_minimas(0.0)


class TestEvaluarCuota(unittest.TestCase):
    def test_referencia_una_casa_techo_b(self):
        # Referencia DK 1.08/8.40 -> p justa ~88.6%; mi casa paga 1.17 -> EV>0
        m = _mercado_una_casa(1.08, 8.40)
        op = evaluar_cuota(_evento(), m, cuota=1.17, casa="Apostala")
        self.assertGreater(op.valor_esperado, 0.03)
        self.assertEqual(op.clasificacion, Clasificacion.B)  # techo B con 1 ref
        self.assertEqual(op.mejor_cuota.casa, "Apostala")
        self.assertTrue(any("techo de clase B" in r for r in op.riesgos))

    def test_cuota_sin_valor_descartada(self):
        m = _mercado_una_casa(1.08, 8.40)
        op = evaluar_cuota(_evento(), m, cuota=1.10, casa="Apostala")
        self.assertLess(op.valor_esperado, 0.0)
        self.assertEqual(op.clasificacion, Clasificacion.DESCARTADA)

    def test_referencia_multicasa_puede_dar_a_plus(self):
        # El mercado demo 1X tiene 7 casas de referencia con p ~82.7%
        eventos = eventos_demo()
        evento, mercados = eventos[0]
        plan = PlanBankroll(bankroll=1000)
        op = evaluar_cuota(evento, mercados[0], cuota=1.30, casa="Apostala",
                           plan=plan)
        self.assertEqual(op.clasificacion, Clasificacion.A_PLUS)
        self.assertGreater(op.stake_unidades, 0.0)
        self.assertLessEqual(op.stake_unidades, 2.0)

    def test_cuota_demasiado_alejada_descartada(self):
        eventos = eventos_demo()
        evento, mercados = eventos[0]
        # 1.40 está >12% sobre la mediana de referencia 1.17 -> sospechosa
        op = evaluar_cuota(evento, mercados[0], cuota=1.40, casa="Apostala")
        self.assertEqual(op.clasificacion, Clasificacion.DESCARTADA)


class TestCandidatos(unittest.TestCase):
    def test_orden_y_umbrales(self):
        filas = candidatos(eventos_demo())
        self.assertGreater(len(filas), 0)
        probs = [f["p"] for f in filas]
        self.assertEqual(probs, sorted(probs, reverse=True))
        # El 'Más de 0.5 goles' demo (p ~92%) debe traer umbrales A y A+
        primera = filas[0]
        self.assertGreater(primera["p"], 0.90)
        self.assertIsNotNone(primera["min_a"])
        self.assertIsNotNone(primera["min_a_plus"])
        # Y el total de básquet (p ~50%) no debe ser candidato
        ultima = filas[-1]
        self.assertLess(ultima["p"], 0.60)
        self.assertIsNone(ultima["min_a"])


if __name__ == "__main__":
    unittest.main()
