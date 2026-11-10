"""Modelos de datos del sistema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Deporte(str, Enum):
    FUTBOL = "futbol"
    TENIS = "tenis"
    BASQUET = "basquet"
    OTRO = "otro"


class Clasificacion(str, Enum):
    A_PLUS = "A+"          # Excelente oportunidad con evidencia sólida
    A = "A"                # Buena oportunidad
    B = "B"                # Interesante, pero con incertidumbre
    DESCARTADA = "DESCARTADA"  # Riesgo elevado o falta de valor


class Resultado(str, Enum):
    PENDIENTE = "PENDIENTE"
    GANADA = "GANADA"
    PERDIDA = "PERDIDA"
    NULA = "NULA"  # push / anulada / devuelta


@dataclass(frozen=True)
class CuotaCasa:
    """Cuota ofrecida por una casa de apuestas concreta."""

    casa: str
    cuota: float
    url: str = ""

    @property
    def prob_implicita(self) -> float:
        return 1.0 / self.cuota


@dataclass
class MercadoEvento:
    """Un mercado concreto de un evento con las cuotas de varias casas.

    `cuotas_contrarias` contiene, por casa, las cuotas del resto de
    resultados del mismo mercado (necesarias para quitar el margen).
    """

    seleccion: str                       # p.ej. "1X", "Más de 1.5 goles"
    mercado: str                         # p.ej. "doble_oportunidad", "total_goles"
    cuotas: list[CuotaCasa] = field(default_factory=list)
    # Por casa: lista completa de cuotas del mercado (incluida la selección)
    cuotas_mercado_completo: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class Evento:
    deporte: Deporte
    competicion: str
    local: str
    visitante: str
    inicio: datetime
    id_externo: str = ""
    fuente: str = ""


@dataclass
class Oportunidad:
    """Resultado final del análisis de un mercado de un evento."""

    evento: Evento
    mercado: str
    seleccion: str
    mejor_cuota: CuotaCasa
    prob_estimada: float          # probabilidad "real" estimada por el modelo
    prob_implicita: float         # 1 / mejor_cuota
    valor_esperado: float         # EV por unidad apostada: p*cuota - 1
    clasificacion: Clasificacion
    num_casas: int                # nº de casas usadas en el consenso
    metodo: str                   # cómo se estimó la probabilidad
    estadisticas: list[str] = field(default_factory=list)
    riesgos: list[str] = field(default_factory=list)
    fuentes: list[str] = field(default_factory=list)
    stake_unidades: float = 0.0
    confianza: str = ""           # texto: Alta / Media / Baja
    es_demo: bool = False
