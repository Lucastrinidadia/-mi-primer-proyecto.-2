"""Datos DEMO, 100% FICTICIOS, para probar el flujo completo sin claves de API.

IMPORTANTE: equipos, cuotas y fechas son inventados a propósito y se marcan
como DEMO en todo el sistema. Jamás deben usarse para apostar dinero real.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .modelos import CuotaCasa, Deporte, Evento, MercadoEvento

_CASAS = ["Casa Demo 1", "Casa Demo 2", "Casa Demo 3", "Casa Demo 4",
          "Casa Demo 5", "Casa Demo 6", "Casa Demo 7"]


def _mercado(seleccion: str, mercado: str, cuotas_sel: list[float],
             mercados_completos: list[list[float]]) -> MercadoEvento:
    m = MercadoEvento(seleccion=seleccion, mercado=mercado)
    for casa, cuota, completo in zip(_CASAS, cuotas_sel, mercados_completos):
        m.cuotas.append(CuotaCasa(casa, cuota))
        m.cuotas_mercado_completo[casa] = completo
    return m


def eventos_demo() -> list[tuple[Evento, list[MercadoEvento]]]:
    manana = datetime.now(timezone.utc) + timedelta(days=1)

    # Caso 1: favorito claro en doble oportunidad; una casa paga 1.28 cuando
    # el consenso sin margen es ~82.7% -> EV ~ +5.9% => A+.
    ev1 = Evento(Deporte.FUTBOL, "Liga Demo", "Atlético Ficticio",
                 "Deportivo Imaginario", manana, "demo-1", "DATOS DEMO (ficticios)")
    m1 = _mercado(
        "1X (Atlético Ficticio o empate)", "doble_oportunidad",
        [1.17, 1.16, 1.18, 1.17, 1.16, 1.17, 1.28],
        # mercado completo por casa: [1X, 2]
        [[1.17, 5.6], [1.16, 5.7], [1.18, 5.5], [1.17, 5.6],
         [1.16, 5.7], [1.17, 5.6], [1.28, 4.2]],
    )
    # Caso 2: cuota sin valor (favorita pero pagada por debajo del consenso)
    m2 = _mercado(
        "Más de 0.5 goles", "total_goles",
        [1.04, 1.05, 1.05, 1.04, 1.05, 1.04, 1.05],
        [[1.04, 12.0], [1.05, 11.5], [1.05, 11.0], [1.04, 12.5],
         [1.05, 11.0], [1.04, 12.0], [1.05, 11.5]],
    )

    # Caso 3: tenis, favorita sólida (~78%) con una casa pagando 1.33
    # -> EV ~ +4.1% pero probabilidad < 82% => A (no A+).
    ev2 = Evento(Deporte.TENIS, "Torneo Demo", "Jugadora Ejemplo A",
                 "Jugadora Ejemplo B", manana + timedelta(hours=3),
                 "demo-2", "DATOS DEMO (ficticios)")
    m3 = _mercado(
        "Gana Jugadora Ejemplo A", "ganador",
        [1.25, 1.24, 1.26, 1.25, 1.24, 1.26, 1.33],
        [[1.25, 4.5], [1.24, 4.6], [1.26, 4.4], [1.25, 4.5],
         [1.24, 4.6], [1.26, 4.4], [1.33, 3.9]],
    )

    # Caso 4: básquet, mercado de puntos equilibrado -> sin valor, se descarta.
    ev3 = Evento(Deporte.BASQUET, "Liga Demo Básquet", "Ciudad Ficticia",
                 "Pueblo Imaginario", manana + timedelta(hours=6),
                 "demo-3", "DATOS DEMO (ficticios)")
    m4 = _mercado(
        "Menos de 220.5 puntos", "total_puntos",
        [1.90, 1.91, 1.90, 1.89, 1.92, 1.90, 1.91],
        [[1.90, 1.90], [1.91, 1.89], [1.90, 1.90], [1.89, 1.91],
         [1.92, 1.88], [1.90, 1.90], [1.91, 1.89]],
    )

    return [(ev1, [m1, m2]), (ev2, [m3]), (ev3, [m4])]
