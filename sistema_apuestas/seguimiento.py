"""Registro de pronósticos y medición de resultados (SQLite).

Mide lo que importa a largo plazo: aciertos, ROI, P/L, rendimiento por
deporte y por mercado, y CLV (cuota tomada vs cuota de cierre). Un CLV
positivo sostenido es el mejor indicador temprano de que el método gana.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path

from .modelos import Resultado

ESQUEMA = """
CREATE TABLE IF NOT EXISTS picks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creado TEXT NOT NULL,
    fecha_evento TEXT NOT NULL,
    deporte TEXT NOT NULL,
    competicion TEXT NOT NULL,
    evento TEXT NOT NULL,
    mercado TEXT NOT NULL,
    seleccion TEXT NOT NULL,
    casa TEXT NOT NULL,
    cuota REAL NOT NULL,
    cuota_cierre REAL,
    prob_estimada REAL NOT NULL,
    ev REAL NOT NULL,
    clasificacion TEXT NOT NULL,
    stake_unidades REAL NOT NULL,
    resultado TEXT NOT NULL DEFAULT 'PENDIENTE',
    beneficio_unidades REAL,
    es_demo INTEGER NOT NULL DEFAULT 0,
    notas TEXT DEFAULT ''
);
"""


@dataclass
class Metricas:
    total: int = 0
    resueltas: int = 0
    ganadas: int = 0
    perdidas: int = 0
    nulas: int = 0
    unidades_apostadas: float = 0.0
    beneficio_unidades: float = 0.0
    clv_medio_pct: float | None = None

    @property
    def tasa_acierto(self) -> float | None:
        decididas = self.ganadas + self.perdidas
        return self.ganadas / decididas if decididas else None

    @property
    def roi(self) -> float | None:
        return (self.beneficio_unidades / self.unidades_apostadas
                if self.unidades_apostadas else None)


class Seguimiento:
    def __init__(self, ruta_db: str | Path = "datos/seguimiento.db"):
        self.ruta = Path(ruta_db)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.ruta)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        self.con.commit()

    # ------------------------------------------------------------------ alta
    def registrar(self, *, fecha_evento: str, deporte: str, competicion: str,
                  evento: str, mercado: str, seleccion: str, casa: str,
                  cuota: float, prob_estimada: float, ev: float,
                  clasificacion: str, stake_unidades: float,
                  es_demo: bool = False, notas: str = "") -> int:
        cur = self.con.execute(
            """INSERT INTO picks (creado, fecha_evento, deporte, competicion,
                   evento, mercado, seleccion, casa, cuota, prob_estimada, ev,
                   clasificacion, stake_unidades, es_demo, notas)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now().isoformat(timespec="seconds"), fecha_evento,
             deporte, competicion, evento, mercado, seleccion, casa, cuota,
             prob_estimada, ev, clasificacion, stake_unidades,
             int(es_demo), notas))
        self.con.commit()
        return int(cur.lastrowid)

    # ------------------------------------------------------- cierre y resultado
    def fijar_cuota_cierre(self, pick_id: int, cuota_cierre: float) -> None:
        self.con.execute("UPDATE picks SET cuota_cierre=? WHERE id=?",
                         (cuota_cierre, pick_id))
        self.con.commit()

    def fijar_resultado(self, pick_id: int, resultado: Resultado) -> None:
        fila = self.con.execute(
            "SELECT cuota, stake_unidades FROM picks WHERE id=?",
            (pick_id,)).fetchone()
        if fila is None:
            raise KeyError(f"No existe el pick {pick_id}")
        stake = fila["stake_unidades"]
        if resultado == Resultado.GANADA:
            beneficio = stake * (fila["cuota"] - 1.0)
        elif resultado == Resultado.PERDIDA:
            beneficio = -stake
        elif resultado == Resultado.NULA:
            beneficio = 0.0
        else:
            beneficio = None
        self.con.execute(
            "UPDATE picks SET resultado=?, beneficio_unidades=? WHERE id=?",
            (resultado.value, beneficio, pick_id))
        self.con.commit()

    # ------------------------------------------------------------- consultas
    def pendientes(self) -> list[sqlite3.Row]:
        return list(self.con.execute(
            "SELECT * FROM picks WHERE resultado='PENDIENTE' ORDER BY fecha_evento"))

    def apostado_en_fecha(self, dia: date) -> tuple[float, float, int]:
        """(unidades apostadas, unidades perdidas, nº apuestas) de un día."""
        filas = list(self.con.execute(
            "SELECT stake_unidades, beneficio_unidades FROM picks "
            "WHERE date(creado)=? AND es_demo=0", (dia.isoformat(),)))
        apostadas = sum(f["stake_unidades"] for f in filas)
        perdidas = -sum(f["beneficio_unidades"] or 0.0 for f in filas
                        if (f["beneficio_unidades"] or 0.0) < 0)
        return apostadas, perdidas, len(filas)

    def metricas(self, *, deporte: str | None = None,
                 mercado: str | None = None,
                 incluir_demo: bool = False) -> Metricas:
        sql = "SELECT * FROM picks WHERE 1=1"
        args: list = []
        if not incluir_demo:
            sql += " AND es_demo=0"
        if deporte:
            sql += " AND deporte=?"
            args.append(deporte)
        if mercado:
            sql += " AND mercado=?"
            args.append(mercado)
        filas = list(self.con.execute(sql, args))

        m = Metricas(total=len(filas))
        clvs: list[float] = []
        for f in filas:
            if f["resultado"] != Resultado.PENDIENTE.value:
                m.resueltas += 1
                m.unidades_apostadas += f["stake_unidades"]
                m.beneficio_unidades += f["beneficio_unidades"] or 0.0
                if f["resultado"] == Resultado.GANADA.value:
                    m.ganadas += 1
                elif f["resultado"] == Resultado.PERDIDA.value:
                    m.perdidas += 1
                elif f["resultado"] == Resultado.NULA.value:
                    m.nulas += 1
            if f["cuota_cierre"]:
                clvs.append((f["cuota"] / f["cuota_cierre"] - 1.0) * 100.0)
        if clvs:
            m.clv_medio_pct = sum(clvs) / len(clvs)
        return m

    def desglose(self, campo: str) -> dict[str, Metricas]:
        """Métricas agrupadas por 'deporte' o por 'mercado'."""
        if campo not in ("deporte", "mercado"):
            raise ValueError("campo debe ser 'deporte' o 'mercado'")
        valores = [f[0] for f in self.con.execute(
            f"SELECT DISTINCT {campo} FROM picks WHERE es_demo=0")]
        return {v: self.metricas(**{campo: v}) for v in valores}

    def cerrar(self) -> None:
        self.con.close()
