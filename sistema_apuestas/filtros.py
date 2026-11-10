"""Filtro de riesgo y clasificación de oportunidades.

Regla principal: ser extremadamente selectivo. Probabilidad alta sin valor
se DESCARTA; valor con probabilidad baja también se descarta aquí (este
sistema prioriza selecciones de alta probabilidad, >= 75%).
"""

from __future__ import annotations

from dataclasses import dataclass

from .modelos import Clasificacion

# Mercados considerados estadísticamente estables (líquidos y de baja varianza)
MERCADOS_ESTABLES = {
    "doble_oportunidad",
    "empate_no_valido",     # draw no bet
    "total_goles",          # más/menos goles
    "handicap_asiatico",
    "handicap",             # spread de puntos (básquet)
    "ganador",              # moneyline / h2h
    "total_puntos",         # básquet
    "total_juegos",         # tenis
}


@dataclass(frozen=True)
class Criterios:
    """Umbrales del filtro. Ajustables, pero con valores por defecto estrictos."""

    prob_minima: float = 0.75        # probabilidad estimada mínima para recomendar
    prob_a_plus: float = 0.82        # umbral de probabilidad para A+
    ev_minimo: float = 0.02          # EV mínimo (2%) para considerar valor real
    ev_a_plus: float = 0.045         # EV mínimo para A+ (4.5%)
    cuota_minima: float = 1.08       # por debajo, el riesgo/beneficio no compensa
    cuota_maxima: float = 1.60       # coherente con prob >= 75% + valor
    min_casas: int = 4               # casas mínimas para un consenso fiable
    min_casas_a_plus: int = 6
    min_casas_absoluto: int = 2      # por debajo, descarte duro (1 al evaluar
                                     # una cuota propia contra una referencia)
    max_dif_vs_consenso: float = 12.0  # % máx. de la mejor cuota sobre la mediana


def clasificar(prob_estimada: float, cuota: float, ev: float,
               num_casas: int, mercado: str,
               dif_vs_consenso: float = 0.0,
               criterios: Criterios = Criterios()) -> tuple[Clasificacion, list[str]]:
    """Clasifica una oportunidad y devuelve (clasificación, motivos/riesgos).

    Orden del filtro: primero eliminatorias duras, después calidad.
    """
    c = criterios
    motivos: list[str] = []

    # --- Eliminatorias duras -------------------------------------------------
    if ev <= 0:
        return Clasificacion.DESCARTADA, ["EV negativo o nulo: la cuota no paga la probabilidad estimada."]
    if prob_estimada < 0.60:
        return Clasificacion.DESCARTADA, [f"Probabilidad estimada ({prob_estimada:.0%}) demasiado baja para este sistema."]
    if cuota < c.cuota_minima:
        return Clasificacion.DESCARTADA, [f"Cuota {cuota:.2f} por debajo del mínimo {c.cuota_minima:.2f}: riesgo/beneficio insuficiente."]
    if num_casas < c.min_casas_absoluto:
        return Clasificacion.DESCARTADA, [
            f"Cuotas de menos de {c.min_casas_absoluto} casas: imposible validar el precio."]
    if dif_vs_consenso > c.max_dif_vs_consenso:
        return Clasificacion.DESCARTADA, [
            f"La mejor cuota supera a la mediana del mercado en {dif_vs_consenso:.1f}%: "
            "probable error de la casa o información que el modelo no tiene."]

    # --- Señales de incertidumbre -------------------------------------------
    inestable = mercado not in MERCADOS_ESTABLES
    if inestable:
        motivos.append(f"Mercado '{mercado}' fuera de la lista de mercados estables.")
    if num_casas < c.min_casas:
        motivos.append(f"Consenso con solo {num_casas} casas (mínimo recomendado: {c.min_casas}).")
    if cuota > c.cuota_maxima:
        motivos.append(f"Cuota {cuota:.2f} alta para una selección de probabilidad {prob_estimada:.0%}: revisar.")
    if ev < c.ev_minimo:
        motivos.append(f"EV {ev:+.1%} por debajo del mínimo {c.ev_minimo:.1%}.")
    if prob_estimada < c.prob_minima:
        motivos.append(f"Probabilidad {prob_estimada:.0%} por debajo del objetivo {c.prob_minima:.0%}.")

    # --- Clasificación -------------------------------------------------------
    cumple_a = (prob_estimada >= c.prob_minima and ev >= c.ev_minimo
                and num_casas >= c.min_casas and not inestable
                and cuota <= c.cuota_maxima)
    cumple_a_plus = (cumple_a and prob_estimada >= c.prob_a_plus
                     and ev >= c.ev_a_plus and num_casas >= c.min_casas_a_plus)

    if cumple_a_plus:
        return Clasificacion.A_PLUS, motivos
    if cumple_a:
        return Clasificacion.A, motivos
    # Interesante pero con incertidumbre: hay valor y probabilidad razonable
    if ev >= c.ev_minimo and prob_estimada >= 0.65:
        return Clasificacion.B, motivos
    return Clasificacion.DESCARTADA, motivos or ["No cumple los criterios mínimos de valor y probabilidad."]


def nivel_confianza(clasificacion: Clasificacion, num_casas: int) -> str:
    if clasificacion == Clasificacion.A_PLUS:
        return "Alta"
    if clasificacion == Clasificacion.A:
        return "Media-alta" if num_casas >= 6 else "Media"
    if clasificacion == Clasificacion.B:
        return "Baja"
    return "Nula"
