"""Modelos de probabilidad por deporte.

Dos vías complementarias para estimar la probabilidad "real":

1. Consenso de mercado (todas las fuentes): se quita el margen (vig) a las
   cuotas de muchas casas y se promedia. El consenso de un mercado líquido
   es el estimador más fiable disponible sin datos privados; superar la
   mejor cuota frente a ese consenso es la definición clásica de valor.

2. Modelos estadísticos (cuando hay datos): Poisson bivariante simple para
   goles en fútbol, Elo logístico para tenis y diferencial de puntos con
   distribución normal para básquet. Sirven para contrastar el consenso,
   nunca para sustituir datos reales por supuestos.
"""

from __future__ import annotations

import math

MAX_GOLES = 10  # truncamiento de la matriz de Poisson


# ---------------------------------------------------------------------------
# Fútbol: modelo de Poisson
# ---------------------------------------------------------------------------

def poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) para X ~ Poisson(lam)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam**k / math.factorial(k)


def matriz_goles(lam_local: float, lam_visitante: float,
                 max_goles: int = MAX_GOLES) -> list[list[float]]:
    """Matriz P[i][j] = P(local marca i, visitante marca j)."""
    p_local = [poisson_pmf(i, lam_local) for i in range(max_goles + 1)]
    p_visit = [poisson_pmf(j, lam_visitante) for j in range(max_goles + 1)]
    return [[p_local[i] * p_visit[j] for j in range(max_goles + 1)]
            for i in range(max_goles + 1)]


def estimar_lambdas(goles_favor_local: float, goles_contra_local: float,
                    goles_favor_visitante: float, goles_contra_visitante: float,
                    media_liga_local: float = 1.5,
                    media_liga_visitante: float = 1.2) -> tuple[float, float]:
    """Goles esperados de cada equipo a partir de medias por partido.

    Entradas: medias de goles a favor/en contra por partido de cada equipo
    (idealmente de los últimos 5-10 partidos, separando casa/fuera).
    Método clásico fuerza ataque x fuerza defensa x media de la liga.
    """
    ataque_local = goles_favor_local / media_liga_local if media_liga_local else 1.0
    defensa_visitante = goles_contra_visitante / media_liga_local if media_liga_local else 1.0
    ataque_visitante = goles_favor_visitante / media_liga_visitante if media_liga_visitante else 1.0
    defensa_local = goles_contra_local / media_liga_visitante if media_liga_visitante else 1.0

    lam_local = ataque_local * defensa_visitante * media_liga_local
    lam_visitante = ataque_visitante * defensa_local * media_liga_visitante
    return max(lam_local, 0.05), max(lam_visitante, 0.05)


def prob_mercados_futbol(lam_local: float, lam_visitante: float) -> dict[str, float]:
    """Probabilidades de los mercados principales a partir de la matriz de goles."""
    m = matriz_goles(lam_local, lam_visitante)
    n = len(m)
    p1 = sum(m[i][j] for i in range(n) for j in range(n) if i > j)
    px = sum(m[i][i] for i in range(n))
    p2 = sum(m[i][j] for i in range(n) for j in range(n) if i < j)

    def p_total(cond) -> float:
        return sum(m[i][j] for i in range(n) for j in range(n) if cond(i + j))

    probs = {
        "1": p1, "X": px, "2": p2,
        "1X": p1 + px, "X2": px + p2, "12": p1 + p2,  # doble oportunidad
        "mas_0.5": p_total(lambda t: t > 0.5),
        "mas_1.5": p_total(lambda t: t > 1.5),
        "mas_2.5": p_total(lambda t: t > 2.5),
        "menos_2.5": p_total(lambda t: t < 2.5),
        "menos_3.5": p_total(lambda t: t < 3.5),
        "menos_4.5": p_total(lambda t: t < 4.5),
        "ambos_marcan": sum(m[i][j] for i in range(1, n) for j in range(1, n)),
    }
    # Hándicap asiático -1.0 / +1.0 para el local (prob. de ganar sin contar push)
    gana_por_2 = sum(m[i][j] for i in range(n) for j in range(n) if i - j >= 2)
    pierde_o_empata_menos1 = sum(m[i][j] for i in range(n) for j in range(n) if i - j <= 0)
    probs["local_-1.0_gana"] = gana_por_2
    probs["visitante_+1.0_gana"] = pierde_o_empata_menos1
    return probs


# ---------------------------------------------------------------------------
# Tenis: Elo logístico
# ---------------------------------------------------------------------------

def prob_elo(elo_a: float, elo_b: float, escala: float = 400.0) -> float:
    """Probabilidad de que A gane a B según diferencia de Elo (superficie incluida
    si los Elo son específicos de superficie)."""
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / escala))


# ---------------------------------------------------------------------------
# Básquet: diferencial de puntos ~ Normal
# ---------------------------------------------------------------------------

def _cdf_normal(x: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2))))


def prob_basquet_ml(rating_local: float, rating_visitante: float,
                    ventaja_local: float = 2.8, sigma: float = 11.5) -> float:
    """P(gana local) con margen ~ Normal(diferencia de rating + ventaja local, sigma).

    sigma ≈ 11-12 puntos es el valor empírico habitual en NBA.
    """
    mu = rating_local - rating_visitante + ventaja_local
    return 1.0 - _cdf_normal(0.0, mu, sigma)


def prob_basquet_total(total_esperado: float, linea: float,
                       sigma: float = 18.0) -> dict[str, float]:
    """Probabilidad de más/menos puntos que la línea."""
    p_mas = 1.0 - _cdf_normal(linea, total_esperado, sigma)
    return {"mas": p_mas, "menos": 1.0 - p_mas}


# ---------------------------------------------------------------------------
# Consenso de mercado (vale para cualquier deporte)
# ---------------------------------------------------------------------------

def prob_consenso(cuotas_por_casa: dict[str, list[float]],
                  indice_seleccion: int) -> tuple[float, int]:
    """Probabilidad de consenso de una selección a partir de varias casas.

    `cuotas_por_casa`: por casa, las cuotas de TODOS los resultados del
    mercado (p.ej. [c_1, c_X, c_2]). A cada casa se le quita su margen de
    forma proporcional y se promedia la probabilidad de la selección.

    Devuelve (probabilidad media sin margen, nº de casas usadas).
    """
    probs: list[float] = []
    for cuotas in cuotas_por_casa.values():
        if len(cuotas) <= indice_seleccion or any(c <= 1.0 for c in cuotas):
            continue
        implicitas = [1.0 / c for c in cuotas]
        margen = sum(implicitas)
        if margen <= 0:
            continue
        probs.append(implicitas[indice_seleccion] / margen)
    if not probs:
        return 0.0, 0
    # Mediana: más robusta que la media frente a una casa con cuota atípica.
    probs.sort()
    k = len(probs)
    mediana = probs[k // 2] if k % 2 else 0.5 * (probs[k // 2 - 1] + probs[k // 2])
    return mediana, k
