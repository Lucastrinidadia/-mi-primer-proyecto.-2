import unittest

from sistema_apuestas.bankroll import PlanBankroll, stake_unidades, validar_dia
from sistema_apuestas.modelos import Clasificacion


class TestBankroll(unittest.TestCase):
    def setUp(self):
        self.plan = PlanBankroll(bankroll=1000.0)

    def test_valor_unidad(self):
        self.assertAlmostEqual(self.plan.valor_unidad, 10.0)

    def test_stake_cero_para_b_y_descartada(self):
        self.assertEqual(stake_unidades(self.plan, 0.8, 1.3, Clasificacion.B), 0.0)
        self.assertEqual(stake_unidades(self.plan, 0.8, 1.3, Clasificacion.DESCARTADA), 0.0)

    def test_stake_acotado(self):
        # ventaja enorme: Kelly pediría mucho, el sistema corta en 2u (A+)
        s = stake_unidades(self.plan, 0.90, 1.30, Clasificacion.A_PLUS)
        self.assertLessEqual(s, 2.0)
        self.assertGreater(s, 0.0)
        # A se corta en 1 unidad
        s_a = stake_unidades(self.plan, 0.90, 1.30, Clasificacion.A)
        self.assertLessEqual(s_a, 1.0)

    def test_stake_sin_ventaja_es_cero(self):
        self.assertEqual(stake_unidades(self.plan, 0.70, 1.30, Clasificacion.A), 0.0)

    def test_stop_loss_diario(self):
        ok, motivo = validar_dia(self.plan, unidades_ya_apostadas=2.0,
                                 unidades_perdidas_hoy=3.0, apuestas_hoy=2,
                                 stake_nuevo=1.0)
        self.assertFalse(ok)
        self.assertIn("STOP-LOSS", motivo)

    def test_limite_apuestas_dia(self):
        ok, _ = validar_dia(self.plan, 2.0, 0.0, 3, 1.0)
        self.assertFalse(ok)

    def test_limite_unidades_dia(self):
        ok, _ = validar_dia(self.plan, 4.5, 0.0, 2, 1.0)
        self.assertFalse(ok)

    def test_dia_ok(self):
        ok, motivo = validar_dia(self.plan, 1.0, 0.5, 1, 1.0)
        self.assertTrue(ok)
        self.assertEqual(motivo, "OK")


if __name__ == "__main__":
    unittest.main()
