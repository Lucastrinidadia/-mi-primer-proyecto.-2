import unittest

from sistema_apuestas.filtros import Criterios, clasificar, nivel_confianza
from sistema_apuestas.modelos import Clasificacion


class TestFiltros(unittest.TestCase):
    def test_ev_negativo_siempre_descartada(self):
        # probabilidad altísima pero cuota sin valor: se DESCARTA (regla clave)
        c, motivos = clasificar(prob_estimada=0.95, cuota=1.03, ev=-0.022,
                                num_casas=8, mercado="total_goles")
        self.assertEqual(c, Clasificacion.DESCARTADA)
        self.assertIn("EV", motivos[0])

    def test_a_plus(self):
        c, _ = clasificar(prob_estimada=0.84, cuota=1.25, ev=0.05,
                          num_casas=7, mercado="doble_oportunidad")
        self.assertEqual(c, Clasificacion.A_PLUS)

    def test_a(self):
        c, _ = clasificar(prob_estimada=0.77, cuota=1.33, ev=0.024,
                          num_casas=5, mercado="ganador")
        self.assertEqual(c, Clasificacion.A)

    def test_b_por_pocas_casas(self):
        c, motivos = clasificar(prob_estimada=0.78, cuota=1.30, ev=0.03,
                                num_casas=3, mercado="ganador")
        self.assertEqual(c, Clasificacion.B)
        self.assertTrue(any("casas" in m for m in motivos))

    def test_b_por_mercado_inestable(self):
        c, _ = clasificar(prob_estimada=0.80, cuota=1.28, ev=0.03,
                          num_casas=6, mercado="tarjetas")
        self.assertEqual(c, Clasificacion.B)

    def test_descartada_prob_baja(self):
        c, _ = clasificar(prob_estimada=0.55, cuota=2.0, ev=0.10,
                          num_casas=8, mercado="ganador")
        self.assertEqual(c, Clasificacion.DESCARTADA)

    def test_descartada_cuota_minima(self):
        c, _ = clasificar(prob_estimada=0.97, cuota=1.05, ev=0.018,
                          num_casas=8, mercado="total_goles")
        self.assertEqual(c, Clasificacion.DESCARTADA)

    def test_descartada_cuota_sospechosa(self):
        # mejor cuota 20% por encima de la mediana: probable error/trampa
        c, motivos = clasificar(prob_estimada=0.80, cuota=1.45, ev=0.16,
                                num_casas=6, mercado="ganador",
                                dif_vs_consenso=20.0)
        self.assertEqual(c, Clasificacion.DESCARTADA)
        self.assertTrue(any("mediana" in m for m in motivos))

    def test_umbral_75(self):
        # p=0.74 con todo lo demás bien: no puede ser A (criterio del sistema)
        c, _ = clasificar(prob_estimada=0.74, cuota=1.40, ev=0.036,
                          num_casas=6, mercado="ganador")
        self.assertEqual(c, Clasificacion.B)

    def test_criterios_personalizados(self):
        laxos = Criterios(prob_minima=0.70)
        c, _ = clasificar(prob_estimada=0.72, cuota=1.42, ev=0.022,
                          num_casas=6, mercado="ganador", criterios=laxos)
        self.assertEqual(c, Clasificacion.A)

    def test_confianza(self):
        self.assertEqual(nivel_confianza(Clasificacion.A_PLUS, 8), "Alta")
        self.assertEqual(nivel_confianza(Clasificacion.DESCARTADA, 8), "Nula")


if __name__ == "__main__":
    unittest.main()
