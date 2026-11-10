"""Comparación con tu casa local (p. ej. Apostala, Paraguay).

Una casa local que no aparece en los agregadores (como Apostala, único
operador licenciado en Paraguay) no se puede comparar automáticamente.
El flujo correcto es:

1. `comparar`: el sistema calcula la probabilidad justa de referencia y
   te dice la CUOTA MÍNIMA que tu casa debe pagar para que la apuesta
   alcance clase A o A+. Abres tu casa y comparas en un minuto.
2. `evaluar --seleccion ... --cuota X`: clasifica la cuota concreta que
   tu casa te ofrece (EV, clase, stake) y permite registrarla.

Honestidad del método: con referencia de UNA sola casa (ESPN/DraftKings),
el techo de clasificación es B (observación, sin stake). Para emitir A/A+
hace falta consenso multi-casa (THE_ODDS_API_KEY).
"""

from __future__ import annotations

import math
import statistics

from .analisis import prob_consenso_mercado
from .bankroll import PlanBankroll, stake_unidades
from .filtros import Criterios, clasificar, nivel_confianza
from .modelos import (Clasificacion, CuotaCasa, Evento, MercadoEvento,
                      Oportunidad)
from .valor import diferencia_vs_consenso, valor_esperado


def _techo(x: float) -> float:
    """Redondeo hacia arriba a 2 decimales (umbral conservador)."""
    return math.ceil(x * 100.0 - 1e-9) / 100.0


def cuotas_minimas(p: float, criterios: Criterios = Criterios()) -> dict:
    """Cuota justa y cuotas mínimas para clase A / A+ dada la probabilidad.

    min_a / min_a_plus son None cuando la probabilidad no alcanza el umbral
    de ese nivel (este sistema no apuesta por debajo del 75%).
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"Probabilidad inválida: {p}")
    return {
        "justa": 1.0 / p,
        "min_a": _techo((1.0 + criterios.ev_minimo) / p)
                 if p >= criterios.prob_minima else None,
        "min_a_plus": _techo((1.0 + criterios.ev_a_plus) / p)
                      if p >= criterios.prob_a_plus else None,
    }


def candidatos(eventos: list[tuple[Evento, list[MercadoEvento]]],
               criterios: Criterios = Criterios()) -> list[dict]:
    """Todas las selecciones con su probabilidad de referencia y umbrales.

    Devuelve filas ordenadas por probabilidad descendente; las que tienen
    min_a son las únicas que este sistema puede llegar a recomendar.
    """
    filas: list[dict] = []
    for evento, mercados in eventos:
        for m in mercados:
            p, n = prob_consenso_mercado(m)
            if n == 0:
                continue
            filas.append({"evento": evento, "mercado": m, "p": p, "n_ref": n,
                          **cuotas_minimas(p, criterios)})
    filas.sort(key=lambda f: -f["p"])
    return filas


def evaluar_cuota(evento: Evento, m: MercadoEvento, cuota: float, casa: str,
                  criterios: Criterios | None = None,
                  plan: PlanBankroll | None = None) -> Oportunidad:
    """Clasifica la cuota que TU casa ofrece frente a la referencia."""
    if criterios is None:
        # Evaluación de cuota propia: la referencia puede ser 1 sola casa
        # (el techo B por pocas casas sigue aplicándose más abajo).
        criterios = Criterios(min_casas_absoluto=1)
    p, n_ref = prob_consenso_mercado(m)
    if n_ref == 0:
        raise ValueError("Sin cuotas de referencia válidas para este mercado")
    ev = valor_esperado(p, cuota)
    dif = diferencia_vs_consenso(cuota, m.cuotas)
    clasif, motivos = clasificar(p, cuota, ev, n_ref, m.mercado, dif, criterios)
    mediana_ref = statistics.median(c.cuota for c in m.cuotas)

    estadisticas = [
        f"Probabilidad justa de referencia: {p:.1%} "
        f"(consenso sin margen de {n_ref} casa(s) de referencia).",
        f"Cuota justa: {1.0 / p:.2f} | tu cuota en {casa}: {cuota:.2f} "
        f"({dif:+.1f}% sobre la mediana de referencia {mediana_ref:.2f}).",
    ]
    riesgos = list(motivos)
    riesgos.append(f"Cuota introducida a mano: verifícala en {casa} justo antes de apostar.")
    if n_ref < criterios.min_casas:
        riesgos.append(f"Referencia de solo {n_ref} casa(s): techo de clase B "
                       "hasta tener consenso multi-casa (THE_ODDS_API_KEY).")

    op = Oportunidad(
        evento=evento, mercado=m.mercado, seleccion=m.seleccion,
        mejor_cuota=CuotaCasa(casa, cuota), prob_estimada=p,
        prob_implicita=1.0 / cuota, valor_esperado=ev, clasificacion=clasif,
        num_casas=n_ref,
        metodo="Cuota propia vs probabilidad justa de referencia",
        estadisticas=estadisticas, riesgos=riesgos,
        fuentes=[evento.fuente or "referencia de mercado",
                 f"Cuota evaluada: {casa} (introducida por el usuario)"],
        confianza=nivel_confianza(clasif, n_ref))
    if plan and clasif in (Clasificacion.A_PLUS, Clasificacion.A):
        op.stake_unidades = stake_unidades(plan, p, cuota, clasif)
    return op
