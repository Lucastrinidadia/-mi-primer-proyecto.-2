"""Fuente NBA sin clave: API pública de ESPN.

Aporta datos REALES y verificables: partidos, cuotas (normalmente un solo
operador, DraftKings), récords total/casa/fuera y partes de lesiones.

Limitación honesta: al publicar UNA sola casa, no permite validar valor
frente al mercado (el filtro del sistema exige >= 2 casas y descartará
todo). Sirve para ver el mercado y el contexto; para detectar valor real
se necesita comparación multi-casa (THE_ODDS_API_KEY en fuentes.py).
"""

from __future__ import annotations

from datetime import datetime, timezone

import requests

from .modelos import CuotaCasa, Deporte, Evento, MercadoEvento, Oportunidad
from .fuentes import ErrorFuente

URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
URL_ODDS = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/"
            "events/{eid}/competitions/{eid}/odds?limit=50")
URL_LESIONES = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"


def _get_json(url: str, params: dict | None = None) -> dict:
    r = requests.get(url, params=params, timeout=30)
    if not r.ok:
        raise ErrorFuente(f"ESPN {r.status_code} en {url.split('?')[0]}")
    return r.json()


def _decimal(nodo: dict | None, *claves: str) -> float | None:
    """Navega nodo[c1][c2]...['decimal'] devolviendo None si falta algo."""
    actual = nodo
    for c in claves:
        if not isinstance(actual, dict) or c not in actual:
            return None
        actual = actual[c]
    if isinstance(actual, dict):
        actual = actual.get("decimal")
    try:
        v = float(actual)
        return v if v > 1.0 else None
    except (TypeError, ValueError):
        return None


def _mercado_dos_lados(nombre_mercado: str, sel_a: str, cuota_a: float,
                       sel_b: str, cuota_b: float, casa: str) -> list[MercadoEvento]:
    """Crea los dos lados de un mercado de dos resultados con una casa."""
    lados = []
    for sel, cuota in ((sel_a, cuota_a), (sel_b, cuota_b)):
        m = MercadoEvento(seleccion=sel, mercado=nombre_mercado)
        m.cuotas.append(CuotaCasa(casa, cuota))
        m.cuotas_mercado_completo[casa] = [cuota_a, cuota_b]
        lados.append(m)
    return lados


def mercados_evento_nba(event_id: str, local: str, visitante: str) -> list[MercadoEvento]:
    datos = _get_json(URL_ODDS.format(eid=event_id))
    mercados: list[MercadoEvento] = []
    for item in datos.get("items", []):
        casa = item.get("provider", {}).get("name", "?") + " (vía ESPN)"
        home, away = item.get("homeTeamOdds", {}), item.get("awayTeamOdds", {})

        # Ganador (moneyline)
        ml_local = _decimal(home, "current", "moneyLine")
        ml_visit = _decimal(away, "current", "moneyLine")
        if ml_local and ml_visit:
            mercados += _mercado_dos_lados(
                "ganador", f"Gana {local}", ml_local,
                f"Gana {visitante}", ml_visit, casa)

        # Hándicap (spread)
        linea = item.get("spread")
        sp_local = _decimal(home, "current", "spread")
        sp_visit = _decimal(away, "current", "spread")
        if linea is not None and sp_local and sp_visit:
            mercados += _mercado_dos_lados(
                "handicap", f"{local} {linea:+g}", sp_local,
                f"{visitante} {-linea:+g}", sp_visit, casa)

        # Total de puntos
        total = item.get("overUnder")
        c_mas = _decimal(item, "current", "over")
        c_menos = _decimal(item, "current", "under")
        if total is not None and c_mas and c_menos:
            mercados += _mercado_dos_lados(
                "total_puntos", f"Más de {total} puntos", c_mas,
                f"Menos de {total} puntos", c_menos, casa)
    return mercados


def _records(competidor: dict) -> str:
    recs = {r.get("type"): r.get("summary") for r in competidor.get("records", [])}
    partes = [recs.get("total", "?")]
    if recs.get("home"):
        partes.append(f"{recs['home']} en casa")
    if recs.get("road"):
        partes.append(f"{recs['road']} fuera")
    return ", ".join(partes)


def lesiones_nba(equipos: set[str]) -> dict[str, list[str]]:
    """Jugadores Out / Day-To-Day por equipo (solo los equipos pedidos)."""
    try:
        datos = _get_json(URL_LESIONES)
    except ErrorFuente:
        return {}
    resultado: dict[str, list[str]] = {}
    for t in datos.get("injuries", []):
        nombre = t.get("displayName", "")
        if nombre not in equipos:
            continue
        for les in t.get("injuries", []):
            estado = les.get("status", "")
            if estado not in ("Out", "Day-To-Day"):
                continue
            jugador = les.get("athlete", {}).get("displayName", "?")
            detalle = les.get("details", {}).get("type", "")
            resultado.setdefault(nombre, []).append(
                f"{jugador} ({estado}{', ' + detalle if detalle else ''})")
    return resultado


def eventos_nba(fecha: str | None = None
                ) -> tuple[list[tuple[Evento, list[MercadoEvento]]], dict[str, list[str]]]:
    """Partidos NBA próximos con cuotas + contexto real (récords y lesiones).

    `fecha`: AAAAMMDD opcional. Devuelve (eventos, contexto) donde contexto
    mapea "local|visitante" -> líneas de estadísticas/riesgos verificables.
    """
    params = {"dates": fecha} if fecha else None
    tablero = _get_json(URL_SCOREBOARD, params=params)
    eventos: list[tuple[Evento, list[MercadoEvento]]] = []
    contexto: dict[str, list[str]] = {}
    equipos: set[str] = set()
    pendientes: list[tuple[Evento, str, dict, dict]] = []

    for ev in tablero.get("events", []):
        comp = ev.get("competitions", [{}])[0]
        estado = comp.get("status", {}).get("type", {}).get("name", "")
        if estado != "STATUS_SCHEDULED":
            continue  # nunca analizar partidos empezados o acabados
        try:
            inicio = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if inicio < datetime.now(timezone.utc):
            continue
        competidores = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        c_local, c_visit = competidores.get("home", {}), competidores.get("away", {})
        local = c_local.get("team", {}).get("displayName", "?")
        visitante = c_visit.get("team", {}).get("displayName", "?")
        evento = Evento(Deporte.BASQUET, "NBA", local, visitante, inicio,
                        id_externo=ev.get("id", ""),
                        fuente="ESPN API (cuotas de DraftKings)")
        equipos.update((local, visitante))
        pendientes.append((evento, ev.get("id", ""), c_local, c_visit))

    partes_lesiones = lesiones_nba(equipos)

    for evento, eid, c_local, c_visit in pendientes:
        mercados = mercados_evento_nba(eid, evento.local, evento.visitante)
        if not mercados:
            continue
        clave = f"{evento.local}|{evento.visitante}"
        lineas = [
            f"Récord {evento.local}: {_records(c_local)} (fuente: ESPN).",
            f"Récord {evento.visitante}: {_records(c_visit)} (fuente: ESPN).",
        ]
        for equipo in (evento.local, evento.visitante):
            bajas = partes_lesiones.get(equipo)
            if bajas:
                lineas.append(f"Bajas/duda {equipo}: {'; '.join(bajas[:4])}"
                              + (" …" if len(bajas) > 4 else "")
                              + " (parte de lesiones ESPN).")
        contexto[clave] = lineas
        eventos.append((evento, mercados))
    return eventos, contexto


def enriquecer_con_contexto(oportunidades: list[Oportunidad],
                            contexto: dict[str, list[str]]) -> None:
    """Añade récords y lesiones reales a las estadísticas/riesgos del informe."""
    for op in oportunidades:
        lineas = contexto.get(f"{op.evento.local}|{op.evento.visitante}", [])
        for linea in lineas:
            # Las bajas van al final de riesgos para no desplazar el motivo
            # del filtro, que debe seguir siendo el primero del informe.
            if linea.startswith("Bajas"):
                op.riesgos.append(linea)
            else:
                op.estadisticas.append(linea)
