"""Gestión del bankroll: unidades pequeñas, límites y disciplina.

Reglas fijas del sistema (no configurables a peor):
- Nunca martingala ni progresiones tras pérdida.
- Nunca aumentar el stake para "recuperar".
- Si no hay oportunidades A+ o A: NO APOSTAR.
- Stake por apuesta acotado aunque Kelly sugiera más.
"""

from __future__ import annotations

from dataclasses import dataclass

from .modelos import Clasificacion
from .valor import kelly


@dataclass(frozen=True)
class PlanBankroll:
    bankroll: float                 # dinero total destinado a apostar (asumible perderlo)
    unidad_pct: float = 1.0         # 1 unidad = 1% del bankroll
    kelly_fraccion: float = 0.25    # Kelly fraccional (25%): reduce varianza
    max_unidades_apuesta: float = 2.0
    max_unidades_dia: float = 5.0
    stop_loss_dia: float = 3.0      # unidades perdidas en el día para parar
    max_apuestas_dia: int = 3

    @property
    def valor_unidad(self) -> float:
        return self.bankroll * self.unidad_pct / 100.0


# Tope de unidades por clasificación: la confianza manda sobre Kelly.
TOPE_POR_CLASE = {
    Clasificacion.A_PLUS: 2.0,
    Clasificacion.A: 1.0,
    Clasificacion.B: 0.0,          # las B no se apuestan: solo se observan
    Clasificacion.DESCARTADA: 0.0,
}


def stake_unidades(plan: PlanBankroll, prob: float, cuota: float,
                   clasificacion: Clasificacion) -> float:
    """Unidades a apostar: Kelly fraccional acotado por clase y por plan.

    Devuelve 0 para B y DESCARTADA.
    """
    tope_clase = TOPE_POR_CLASE.get(clasificacion, 0.0)
    if tope_clase <= 0:
        return 0.0
    f = kelly(prob, cuota) * plan.kelly_fraccion       # fracción del bankroll
    unidades = f * 100.0 / plan.unidad_pct             # pasar a unidades
    unidades = min(unidades, tope_clase, plan.max_unidades_apuesta)
    return round(max(unidades, 0.0), 2)


def validar_dia(plan: PlanBankroll, unidades_ya_apostadas: float,
                unidades_perdidas_hoy: float, apuestas_hoy: int,
                stake_nuevo: float) -> tuple[bool, str]:
    """Comprueba los límites diarios antes de registrar una apuesta nueva."""
    if unidades_perdidas_hoy >= plan.stop_loss_dia:
        return False, (f"STOP-LOSS diario alcanzado ({unidades_perdidas_hoy:.1f}u perdidas). "
                       "No se apuesta más hoy. No perseguir pérdidas.")
    if apuestas_hoy >= plan.max_apuestas_dia:
        return False, f"Límite de {plan.max_apuestas_dia} apuestas diarias alcanzado."
    if unidades_ya_apostadas + stake_nuevo > plan.max_unidades_dia:
        return False, (f"Superaría el límite diario de {plan.max_unidades_dia:.1f}u "
                       f"(ya apostadas: {unidades_ya_apostadas:.1f}u).")
    return True, "OK"


REGLAS_ORO = [
    "Apuesta solo dinero que puedas permitirte perder por completo.",
    "1 unidad = 1% del bankroll. Nunca más de 2 unidades por apuesta.",
    "Máximo 3 apuestas y 5 unidades por día; stop-loss diario de 3 unidades.",
    "Nunca aumentes el stake para recuperar pérdidas (nada de martingalas).",
    "Apuestas simples antes que combinadas: las combinadas multiplican el margen de la casa.",
    "Sin oportunidades A+ o A, la jugada correcta es NO APOSTAR.",
    "Evalúa el sistema por EV y ROI a largo plazo (100+ apuestas), no por una racha.",
    "Si apostar deja de ser una decisión fría, para. Ayuda: jugadores anónimos / líneas de juego responsable.",
]
