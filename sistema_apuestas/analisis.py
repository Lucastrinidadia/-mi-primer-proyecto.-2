"""Motor de análisis: convierte eventos+cuotas en oportunidades clasificadas.

Metodología (honesta y verificable):
1. Para cada casa se quita su margen al mercado completo.
2. La probabilidad "real" estimada es la MEDIANA de las probabilidades sin
   margen de todas las casas (consenso de mercado). Es el estimador más
   sólido disponible públicamente; no se inventan probabilidades.
3. Hay valor si la MEJOR cuota disponible paga por encima de ese consenso
   (EV > 0). Después, el filtro de riesgo decide A+/A/B/DESCARTADA.
4. Si hay estadísticas externas (football-data.org), se añaden como
   contraste, nunca como sustituto de datos reales.
"""

from __future__ import annotations

import statistics

from .bankroll import PlanBankroll, stake_unidades
from .filtros import Criterios, clasificar, nivel_confianza
from .modelos import Clasificacion, Evento, MercadoEvento, Oportunidad
from .valor import diferencia_vs_consenso, mejor_cuota, valor_esperado


def prob_consenso_mercado(m: MercadoEvento) -> tuple[float, int]:
    """Mediana de la probabilidad sin margen de la selección entre casas."""
    probs: list[float] = []
    for cuota_casa in m.cuotas:
        completo = m.cuotas_mercado_completo.get(cuota_casa.casa)
        if not completo or any(c <= 1.0 for c in completo):
            continue
        margen_total = sum(1.0 / c for c in completo)
        if margen_total <= 0:
            continue
        probs.append((1.0 / cuota_casa.cuota) / margen_total)
    if not probs:
        return 0.0, 0
    return statistics.median(probs), len(probs)


def analizar_mercado(evento: Evento, m: MercadoEvento,
                     criterios: Criterios = Criterios(),
                     plan: PlanBankroll | None = None,
                     es_demo: bool = False) -> Oportunidad | None:
    if not m.cuotas:
        return None
    prob, num_casas = prob_consenso_mercado(m)
    if num_casas == 0:
        return None

    mejor = mejor_cuota(m.cuotas)
    ev = valor_esperado(prob, mejor.cuota)
    dif = diferencia_vs_consenso(mejor.cuota, m.cuotas)
    clasificacion, riesgos = clasificar(
        prob_estimada=prob, cuota=mejor.cuota, ev=ev, num_casas=num_casas,
        mercado=m.mercado, dif_vs_consenso=dif, criterios=criterios)

    margen_medio = statistics.mean(
        sum(1.0 / c for c in completo) - 1.0
        for completo in m.cuotas_mercado_completo.values()
        if completo and all(c > 1.0 for c in completo)) if m.cuotas_mercado_completo else 0.0
    mediana_cuota = statistics.median(c.cuota for c in m.cuotas)

    estadisticas = [
        f"Consenso de {num_casas} casas tras quitar el margen: {prob:.1%} de probabilidad.",
        f"Cuota mediana del mercado: {mediana_cuota:.2f}; mejor cuota: {mejor.cuota:.2f} ({mejor.casa}).",
        f"La mejor cuota supera a la mediana en {dif:+.1f}%.",
        f"Margen medio de las casas en este mercado: {margen_medio:.1%}.",
    ]
    riesgos = list(riesgos)
    riesgos.extend([
        "La probabilidad proviene del consenso de mercado: no incorpora noticias de última hora (lesiones, alineaciones).",
        "Las cuotas se mueven: verifica la cuota en la casa justo antes de apostar.",
    ])

    fuentes = [evento.fuente or "cuotas de casas de apuestas",
               f"Casas comparadas: {', '.join(sorted({c.casa for c in m.cuotas}))}"]

    oportunidad = Oportunidad(
        evento=evento, mercado=m.mercado, seleccion=m.seleccion,
        mejor_cuota=mejor, prob_estimada=prob,
        prob_implicita=1.0 / mejor.cuota, valor_esperado=ev,
        clasificacion=clasificacion, num_casas=num_casas,
        metodo="Consenso de mercado (mediana sin margen de todas las casas)",
        estadisticas=estadisticas, riesgos=riesgos, fuentes=fuentes,
        confianza=nivel_confianza(clasificacion, num_casas),
        es_demo=es_demo,
    )
    if plan and clasificacion in (Clasificacion.A_PLUS, Clasificacion.A):
        oportunidad.stake_unidades = stake_unidades(
            plan, prob, mejor.cuota, clasificacion)
    return oportunidad


def analizar_eventos(eventos: list[tuple[Evento, list[MercadoEvento]]],
                     criterios: Criterios = Criterios(),
                     plan: PlanBankroll | None = None,
                     es_demo: bool = False) -> list[Oportunidad]:
    """Analiza todos los mercados y devuelve las oportunidades ordenadas por EV."""
    resultado: list[Oportunidad] = []
    for evento, mercados in eventos:
        for m in mercados:
            op = analizar_mercado(evento, m, criterios, plan, es_demo)
            if op is not None:
                resultado.append(op)
    resultado.sort(key=lambda o: (o.clasificacion != Clasificacion.A_PLUS,
                                  o.clasificacion != Clasificacion.A,
                                  -o.valor_esperado))
    return resultado
