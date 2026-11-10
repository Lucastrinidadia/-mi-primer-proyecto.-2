"""Fuentes de datos reales. Este módulo NUNCA inventa datos.

- Cuotas de muchas casas: The Odds API (https://the-odds-api.com)
  Clave gratuita en https://the-odds-api.com -> variable THE_ODDS_API_KEY.
- Estadísticas de fútbol: football-data.org (https://www.football-data.org)
  Clave gratuita -> variable FOOTBALL_DATA_API_KEY (opcional, enriquece el análisis).

Sin clave configurada, el sistema lo dice claramente y no analiza: antes
que fabricar números, prefiere no recomendar nada.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

from .modelos import CuotaCasa, Deporte, Evento, MercadoEvento


class ErrorConfiguracion(RuntimeError):
    pass


class ErrorFuente(RuntimeError):
    pass


# Claves de deporte de The Odds API que cubre el sistema por defecto
DEPORTES_ODDS_API: dict[Deporte, list[str]] = {
    Deporte.FUTBOL: [
        "soccer_spain_la_liga", "soccer_epl", "soccer_italy_serie_a",
        "soccer_germany_bundesliga", "soccer_france_ligue_one",
        "soccer_argentina_primera_division", "soccer_uefa_champs_league",
    ],
    Deporte.TENIS: ["tennis_atp", "tennis_wta"],
    Deporte.BASQUET: ["basketball_nba", "basketball_euroleague"],
}

URL_ODDS_API = "https://api.the-odds-api.com/v4"


def _clave_odds_api() -> str:
    clave = os.environ.get("THE_ODDS_API_KEY", "").strip()
    if not clave:
        raise ErrorConfiguracion(
            "Falta THE_ODDS_API_KEY. Consigue una clave gratuita en "
            "https://the-odds-api.com y expórtala:\n"
            "  export THE_ODDS_API_KEY=tu_clave\n"
            "El sistema no inventa cuotas: sin datos reales no hay análisis. "
            "Para ver el flujo completo con datos FICTICIOS usa --demo.")
    return clave


def obtener_eventos_con_cuotas(deporte: Deporte, region: str = "eu",
                               mercados: str = "h2h,totals") -> list[dict]:
    """Descarga eventos próximos con cuotas de múltiples casas.

    Devuelve la respuesta cruda de The Odds API (lista de eventos).
    """
    clave = _clave_odds_api()
    eventos: list[dict] = []
    for sport_key in DEPORTES_ODDS_API.get(deporte, []):
        r = requests.get(
            f"{URL_ODDS_API}/sports/{sport_key}/odds",
            params={"apiKey": clave, "regions": region, "markets": mercados,
                    "oddsFormat": "decimal", "dateFormat": "iso"},
            timeout=30)
        if r.status_code == 401:
            raise ErrorConfiguracion("THE_ODDS_API_KEY no válida (401).")
        if r.status_code == 422:
            continue  # liga sin eventos próximos o mercado no disponible
        if not r.ok:
            raise ErrorFuente(f"The Odds API {r.status_code} en {sport_key}: {r.text[:200]}")
        for ev in r.json():
            ev["_sport_key"] = sport_key
            eventos.append(ev)
    return eventos


def convertir_eventos(crudos: list[dict], deporte: Deporte) -> list[tuple[Evento, list[MercadoEvento]]]:
    """Convierte la respuesta de The Odds API a los modelos del sistema.

    Para cada evento construye los mercados con las cuotas de todas las
    casas, conservando el mercado completo por casa (para quitar el margen).
    """
    resultado: list[tuple[Evento, list[MercadoEvento]]] = []
    for ev in crudos:
        try:
            inicio = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if inicio < datetime.now(timezone.utc):
            continue  # nunca recomendar eventos ya empezados
        evento = Evento(
            deporte=deporte,
            competicion=ev.get("sport_title", ev.get("_sport_key", "")),
            local=ev.get("home_team", ""),
            visitante=ev.get("away_team", ""),
            inicio=inicio,
            id_externo=ev.get("id", ""),
            fuente="The Odds API (agregador de casas)",
        )

        mercados: dict[tuple[str, str], MercadoEvento] = {}
        for casa in ev.get("bookmakers", []):
            nombre_casa = casa.get("title", casa.get("key", "?"))
            for mkt in casa.get("markets", []):
                outcomes = mkt.get("outcomes", [])
                if mkt.get("key") == "h2h":
                    cuotas_completas = [o.get("price", 0) for o in outcomes]
                    if any(c <= 1.0 for c in cuotas_completas):
                        continue
                    for o in outcomes:
                        nombre = o.get("name", "")
                        sel = ("Gana " + nombre) if nombre != "Draw" else "Empate"
                        clave_m = ("ganador", sel)
                        m = mercados.setdefault(clave_m, MercadoEvento(
                            seleccion=sel, mercado="ganador"))
                        m.cuotas.append(CuotaCasa(nombre_casa, o["price"]))
                        m.cuotas_mercado_completo[nombre_casa] = cuotas_completas
                elif mkt.get("key") == "totals":
                    for o in outcomes:
                        punto = o.get("point")
                        if punto is None or o.get("price", 0) <= 1.0:
                            continue
                        lado = "Más de" if o.get("name") == "Over" else "Menos de"
                        unidad = "goles" if deporte == Deporte.FUTBOL else "puntos"
                        sel = f"{lado} {punto} {unidad}"
                        mercado_nombre = ("total_goles" if deporte == Deporte.FUTBOL
                                          else "total_puntos")
                        clave_m = (f"{mercado_nombre}_{punto}", sel)
                        pareja = [x.get("price", 0) for x in outcomes
                                  if x.get("point") == punto]
                        if len(pareja) != 2 or any(c <= 1.0 for c in pareja):
                            continue
                        m = mercados.setdefault(clave_m, MercadoEvento(
                            seleccion=sel, mercado=mercado_nombre))
                        m.cuotas.append(CuotaCasa(nombre_casa, o["price"]))
                        m.cuotas_mercado_completo[nombre_casa] = pareja
        if mercados:
            resultado.append((evento, list(mercados.values())))
    return resultado


# ---------------------------------------------------------------------------
# football-data.org: estadísticas para contrastar el consenso (opcional)
# ---------------------------------------------------------------------------

URL_FOOTBALL_DATA = "https://api.football-data.org/v4"


def forma_reciente_futbol(nombre_equipo: str, limite: int = 10) -> dict | None:
    """Últimos partidos de un equipo vía football-data.org (si hay clave).

    Devuelve dict con goles a favor/en contra por partido y racha, o None si
    no hay clave o el equipo no se encuentra. Nunca estima sin datos.
    """
    clave = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
    if not clave:
        return None
    cab = {"X-Auth-Token": clave}
    r = requests.get(f"{URL_FOOTBALL_DATA}/teams",
                     params={"name": nombre_equipo}, headers=cab, timeout=30)
    if not r.ok:
        return None
    equipos = r.json().get("teams", [])
    if not equipos:
        return None
    equipo_id = equipos[0]["id"]
    r = requests.get(f"{URL_FOOTBALL_DATA}/teams/{equipo_id}/matches",
                     params={"status": "FINISHED", "limit": limite},
                     headers=cab, timeout=30)
    if not r.ok:
        return None
    partidos = r.json().get("matches", [])
    if not partidos:
        return None
    gf = gc = victorias = 0
    for p in partidos:
        marcador = p.get("score", {}).get("fullTime", {})
        es_local = p.get("homeTeam", {}).get("id") == equipo_id
        goles_propios = marcador.get("home" if es_local else "away") or 0
        goles_rival = marcador.get("away" if es_local else "home") or 0
        gf += goles_propios
        gc += goles_rival
        if goles_propios > goles_rival:
            victorias += 1
    n = len(partidos)
    return {
        "partidos": n,
        "goles_favor_pp": gf / n,
        "goles_contra_pp": gc / n,
        "victorias": victorias,
        "fuente": f"football-data.org (últimos {n} partidos)",
    }
