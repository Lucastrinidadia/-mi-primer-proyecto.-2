import unittest

from sistema_apuestas.modelos import CuotaCasa
from sistema_apuestas.valor import (diferencia_vs_consenso, kelly, margen_casa,
                                    mejor_cuota, prob_implicita, quitar_margen,
                                    valor_esperado)


class TestValor(unittest.TestCase):
    def test_prob_implicita(self):
        self.assertAlmostEqual(prob_implicita(2.0), 0.5)
        self.assertAlmostEqual(prob_implicita(1.25), 0.8)
        with self.assertRaises(ValueError):
            prob_implicita(1.0)

    def test_quitar_margen(self):
        probs = quitar_margen([1.90, 1.90])
        self.assertAlmostEqual(sum(probs), 1.0)
        self.assertAlmostEqual(probs[0], 0.5)
        self.assertGreater(margen_casa([1.90, 1.90]), 0.05)

    def test_ev(self):
        # p=0.80, cuota 1.30 => EV = 0.04
        self.assertAlmostEqual(valor_esperado(0.80, 1.30), 0.04)
        # cuota justa => EV 0
        self.assertAlmostEqual(valor_esperado(0.5, 2.0), 0.0)
        # sin valor => EV negativo
        self.assertLess(valor_esperado(0.75, 1.30), 0.0)
        with self.assertRaises(ValueError):
            valor_esperado(1.2, 2.0)

    def test_kelly(self):
        self.assertEqual(kelly(0.5, 2.0), 0.0)          # sin ventaja
        self.assertEqual(kelly(0.4, 1.5), 0.0)          # ventaja negativa -> 0
        f = kelly(0.80, 1.30)                            # con ventaja
        self.assertAlmostEqual(f, (0.8 * 0.3 - 0.2) / 0.3)
        self.assertGreater(f, 0.0)

    def test_mejor_cuota_y_diferencia(self):
        cuotas = [CuotaCasa("a", 1.20), CuotaCasa("b", 1.25), CuotaCasa("c", 1.22)]
        mejor = mejor_cuota(cuotas)
        self.assertEqual(mejor.casa, "b")
        dif = diferencia_vs_consenso(mejor.cuota, cuotas)
        self.assertGreater(dif, 0.0)
        self.assertLess(dif, 5.0)
        with self.assertRaises(ValueError):
            mejor_cuota([])


if __name__ == "__main__":
    unittest.main()
