"""Cálculo de valor: probabilidad implícita, margen, EV y Kelly."""

from __future__ import annotations

from .modelos import CuotaCasa


def prob_implicita(cuota: float) -> float:
    """Probabilidad implícita de una cuota decimal (incluye el margen de la casa)."""
    if cuota <= 1.0:
        raise ValueError(f"Cuota inválida: {cuota}")
    return 1.0 / cuota


def quitar_margen(cuotas: list[float]) -> list[float]:
    """Quita el margen (vig) de un mercado completo de forma proporcional.

    Devuelve las probabilidades sin margen, que suman 1.
    """
    implicitas = [prob_implicita(c) for c in cuotas]
    total = sum(implicitas)
    return [p / total for p in implicitas]


def margen_casa(cuotas: list[float]) -> float:
    """Margen (overround) de la casa en un mercado: suma de implícitas - 1."""
    return sum(prob_implicita(c) for c in cuotas) - 1.0


def valor_esperado(prob_real: float, cuota: float) -> float:
    """EV por unidad apostada: p * cuota - 1.

    EV > 0  => apuesta con valor matemático.
    EV <= 0 => la cuota no paga lo suficiente para la probabilidad estimada.
    """
    if not 0.0 <= prob_real <= 1.0:
        raise ValueError(f"Probabilidad inválida: {prob_real}")
    return prob_real * cuota - 1.0


def kelly(prob_real: float, cuota: float) -> float:
    """Fracción de Kelly completa: f* = (p*b - q) / b, con b = cuota - 1.

    Devuelve 0 si no hay ventaja. En la práctica se usa una fracción
    (p.ej. 25% de Kelly) para reducir la varianza: ver bankroll.py.
    """
    b = cuota - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - prob_real
    f = (prob_real * b - q) / b
    return max(0.0, f)


def mejor_cuota(cuotas: list[CuotaCasa]) -> CuotaCasa:
    """La mejor cuota disponible entre casas para una misma selección."""
    if not cuotas:
        raise ValueError("No hay cuotas disponibles")
    return max(cuotas, key=lambda c: c.cuota)


def diferencia_vs_consenso(mejor: float, cuotas: list[CuotaCasa]) -> float:
    """Cuánto supera la mejor cuota a la mediana del mercado (en %).

    Una mejor cuota muy por encima del resto puede ser un error de la casa
    (se limita rápido) o una señal de valor; en ambos casos conviene saberlo.
    """
    if not cuotas:
        return 0.0
    valores = sorted(c.cuota for c in cuotas)
    k = len(valores)
    mediana = valores[k // 2] if k % 2 else 0.5 * (valores[k // 2 - 1] + valores[k // 2])
    if mediana <= 0:
        return 0.0
    return (mejor / mediana - 1.0) * 100.0
