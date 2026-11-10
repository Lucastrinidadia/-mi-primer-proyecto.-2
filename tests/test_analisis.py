import unittest

from sistema_apuestas.analisis import analizar_eventos, prob_consenso_mercado
from sistema_apuestas.bankroll import PlanBankroll
from sistema_apuestas.demo import eventos_demo
from sistema_apuestas.modelos import Clasificacion


class TestAnalisis(unittest.TestCase):
    def test_demo_pipeline_completo(self):
        plan = PlanBankroll(bankroll=1000)
        ops = analizar_eventos(eventos_demo(), plan=plan, es_demo=True)
        self.assertEqual(len(ops), 4)
        self.assertTrue(all(o.es_demo for o in ops))

        por_seleccion = {o.seleccion: o for o in ops}

        # El mercado equilibrado de básquet (p~50%) debe quedar DESCARTADO
        basquet = por_seleccion["Menos de 220.5 puntos"]
        self.assertEqual(basquet.clasificacion, Clasificacion.DESCARTADA)

        # "Más de 0.5 goles" con cuota 1.05: descartada por cuota mínima/EV
        mas05 = por_seleccion["Más de 0.5 goles"]
        self.assertEqual(mas05.clasificacion, Clasificacion.DESCARTADA)

        # Debe existir al menos una recomendación A+/A en los datos demo
        recomendadas = [o for o in ops if o.clasificacion in
                        (Clasificacion.A_PLUS, Clasificacion.A)]
        self.assertGreaterEqual(len(recomendadas), 1)
        for o in recomendadas:
            self.assertGreater(o.valor_esperado, 0.0)
            self.assertGreaterEqual(o.prob_estimada, 0.75)
            self.assertGreater(o.stake_unidades, 0.0)
            self.assertLessEqual(o.stake_unidades, 2.0)

        # Orden: las A+/A primero
        clases = [o.clasificacion for o in ops]
        if Clasificacion.A_PLUS in clases and Clasificacion.DESCARTADA in clases:
            self.assertLess(clases.index(Clasificacion.A_PLUS),
                            clases.index(Clasificacion.DESCARTADA))

    def test_consenso_coherente(self):
        eventos = eventos_demo()
        _, mercados = eventos[0]
        prob, n = prob_consenso_mercado(mercados[0])
        self.assertEqual(n, 7)
        self.assertGreater(prob, 0.75)
        self.assertLess(prob, 0.90)

    def test_informe_sin_oportunidades(self):
        from sistema_apuestas.informe import informe
        texto = informe([], plan=None)
        self.assertIn("NO APOSTAR", texto)


if __name__ == "__main__":
    unittest.main()
