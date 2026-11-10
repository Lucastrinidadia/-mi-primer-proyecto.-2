import math
import unittest

from sistema_apuestas.probabilidad import (
    estimar_lambdas, matriz_goles, poisson_pmf, prob_basquet_ml,
    prob_basquet_total, prob_consenso, prob_elo, prob_mercados_futbol)


class TestPoisson(unittest.TestCase):
    def test_pmf_suma_1(self):
        total = sum(poisson_pmf(k, 1.6) for k in range(60))
        self.assertAlmostEqual(total, 1.0, places=10)

    def test_matriz_suma_1(self):
        m = matriz_goles(1.5, 1.1)
        self.assertAlmostEqual(sum(sum(f) for f in m), 1.0, places=4)

    def test_mercados_consistentes(self):
        p = prob_mercados_futbol(1.8, 0.9)
        self.assertAlmostEqual(p["1"] + p["X"] + p["2"], 1.0, places=4)
        self.assertAlmostEqual(p["1X"], p["1"] + p["X"], places=10)
        self.assertAlmostEqual(p["X2"], p["X"] + p["2"], places=10)
        # más goles esperados del local => p(1) > p(2)
        self.assertGreater(p["1"], p["2"])
        # jerarquía de totales
        self.assertGreater(p["mas_0.5"], p["mas_1.5"])
        self.assertGreater(p["mas_1.5"], p["mas_2.5"])
        self.assertGreater(p["menos_4.5"], p["menos_3.5"])
        # mas_0.5 = 1 - P(0-0); places=4 por el truncamiento de la matriz
        self.assertAlmostEqual(p["mas_0.5"],
                               1.0 - poisson_pmf(0, 1.8) * poisson_pmf(0, 0.9),
                               places=4)

    def test_lambdas_equipo_fuerte(self):
        lam_l, lam_v = estimar_lambdas(2.4, 0.6, 0.9, 1.8,
                                       media_liga_local=1.5,
                                       media_liga_visitante=1.2)
        self.assertGreater(lam_l, lam_v)
        self.assertGreater(lam_l, 1.5)


class TestOtrosDeportes(unittest.TestCase):
    def test_elo_simetria(self):
        self.assertAlmostEqual(prob_elo(1800, 1800), 0.5)
        self.assertAlmostEqual(prob_elo(1900, 1700) + prob_elo(1700, 1900), 1.0)
        self.assertGreater(prob_elo(2000, 1700), 0.75)

    def test_basquet_ml(self):
        # equipos iguales: el local gana algo más del 50% por ventaja de cancha
        p = prob_basquet_ml(0, 0)
        self.assertGreater(p, 0.5)
        self.assertLess(p, 0.65)
        self.assertGreater(prob_basquet_ml(8, 0), prob_basquet_ml(0, 0))

    def test_basquet_total(self):
        p = prob_basquet_total(225.0, 220.5)
        self.assertAlmostEqual(p["mas"] + p["menos"], 1.0, places=10)
        self.assertGreater(p["mas"], 0.5)


class TestConsenso(unittest.TestCase):
    def test_consenso_quita_margen(self):
        # 3 casas con el mismo mercado 1X2 con margen
        cuotas = {
            "c1": [1.50, 4.20, 6.50],
            "c2": [1.48, 4.30, 6.80],
            "c3": [1.52, 4.10, 6.40],
        }
        p, n = prob_consenso(cuotas, 0)
        self.assertEqual(n, 3)
        # sin margen, p del favorito debe ser menor que la implícita bruta (1/1.48)
        self.assertLess(p, 1 / 1.48)
        self.assertGreater(p, 0.55)

    def test_consenso_sin_datos(self):
        p, n = prob_consenso({}, 0)
        self.assertEqual((p, n), (0.0, 0))
        p, n = prob_consenso({"c1": [1.0, 2.0]}, 0)  # cuota inválida
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
