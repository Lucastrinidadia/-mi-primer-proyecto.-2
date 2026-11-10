"""Interfaz de línea de comandos del sistema.

Uso rápido:
  python -m sistema_apuestas analizar --demo
  python -m sistema_apuestas analizar --deporte futbol --bankroll 500
  python -m sistema_apuestas resultado 3 GANADA --cuota-cierre 1.18
  python -m sistema_apuestas rendimiento --por mercado
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from .analisis import analizar_eventos
from .bankroll import REGLAS_ORO, PlanBankroll, validar_dia
from .demo import eventos_demo
from .filtros import Criterios
from .informe import formatear_oportunidad, informe, informe_metricas
from .modelos import Clasificacion, Deporte, Resultado
from .seguimiento import Seguimiento

DB_POR_DEFECTO = "datos/seguimiento.db"
TZ_POR_DEFECTO = "America/Asuncion"  # el usuario apuesta en Apostala (Paraguay)


def _plan(args) -> PlanBankroll | None:
    return PlanBankroll(bankroll=args.bankroll) if args.bankroll else None


def _a_hora_local(oportunidades, tz_nombre: str) -> None:
    """Convierte los horarios de los eventos a la zona pedida (en sitio)."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_nombre)
    except Exception:
        print(f"Zona horaria desconocida '{tz_nombre}'; se mantiene UTC.",
              file=sys.stderr)
        return
    vistos = set()
    for op in oportunidades:
        ev = op.evento if hasattr(op, "evento") else op
        if id(ev) not in vistos:
            ev.inicio = ev.inicio.astimezone(tz)
            vistos.add(id(ev))


def _obtener_eventos(args):
    """Descarga eventos+cuotas según la fuente elegida. Devuelve (eventos, contexto)."""
    from .fuentes import ErrorConfiguracion
    contexto: dict[str, list[str]] = {}
    eventos = []
    if args.fuente == "espn":
        if args.deporte not in ("basquet", "todos"):
            raise ErrorConfiguracion(
                "La fuente 'espn' solo cubre NBA; usa --deporte basquet.")
        from .fuentes_espn import eventos_nba
        eventos, contexto = eventos_nba(args.fecha)
        print("Fuente de referencia: ESPN (NBA). Publica normalmente UNA casa "
              "(DraftKings): sirve como línea justa de referencia, pero el techo "
              "de clasificación es B hasta tener multi-casa (THE_ODDS_API_KEY).\n")
    else:
        from .fuentes import convertir_eventos, obtener_eventos_con_cuotas
        deportes = ([Deporte(args.deporte)] if args.deporte != "todos"
                    else [Deporte.FUTBOL, Deporte.TENIS, Deporte.BASQUET])
        for dep in deportes:
            crudos = obtener_eventos_con_cuotas(dep, region=args.region)
            eventos.extend(convertir_eventos(crudos, dep))
    return eventos, contexto


def cmd_analizar(args) -> int:
    plan = _plan(args)
    criterios = Criterios()

    if args.demo:
        eventos = eventos_demo()
        if args.deporte != "todos":
            eventos = [(e, m) for e, m in eventos if e.deporte.value == args.deporte]
        oportunidades = analizar_eventos(eventos, criterios, plan, es_demo=True)
        print(informe(oportunidades, plan, args.mostrar_descartadas, es_demo=True))
        if args.registrar:
            _registrar_recomendadas(oportunidades, plan, args.db)
        return 0

    from .fuentes import ErrorConfiguracion, ErrorFuente
    try:
        eventos, contexto = _obtener_eventos(args)
    except ErrorConfiguracion as e:
        print(f"CONFIGURACIÓN NECESARIA:\n{e}", file=sys.stderr)
        return 2
    except ErrorFuente as e:
        print(f"Error de la fuente de datos (no se analiza con datos parciales): {e}",
              file=sys.stderr)
        return 3

    if not eventos:
        print("Sin eventos próximos con cuotas en las ligas configuradas. "
              "Recomendación: NO APOSTAR.")
        return 0

    oportunidades = analizar_eventos(eventos, criterios, plan)
    if contexto:
        from .fuentes_espn import enriquecer_con_contexto
        enriquecer_con_contexto(oportunidades, contexto)
    _a_hora_local(oportunidades, args.tz)
    print(informe(oportunidades, plan, args.mostrar_descartadas))

    if args.registrar:
        _registrar_recomendadas(oportunidades, plan, args.db)
    return 0


def _registrar_recomendadas(oportunidades, plan, ruta_db) -> None:
    seg = Seguimiento(ruta_db)
    hoy = date.today()
    for op in oportunidades:
        if op.clasificacion not in (Clasificacion.A_PLUS, Clasificacion.A):
            continue
        if plan:
            apostadas, perdidas, n = seg.apostado_en_fecha(hoy)
            ok, motivo = validar_dia(plan, apostadas, perdidas, n, op.stake_unidades)
            if not ok:
                print(f"\nNO registrada ({op.seleccion}): {motivo}")
                continue
        pid = seg.registrar(
            fecha_evento=op.evento.inicio.isoformat(),
            deporte=op.evento.deporte.value,
            competicion=op.evento.competicion,
            evento=f"{op.evento.local} vs {op.evento.visitante}",
            mercado=op.mercado, seleccion=op.seleccion,
            casa=op.mejor_cuota.casa, cuota=op.mejor_cuota.cuota,
            prob_estimada=op.prob_estimada, ev=op.valor_esperado,
            clasificacion=op.clasificacion.value,
            stake_unidades=op.stake_unidades, es_demo=op.es_demo)
        print(f"\nPick #{pid} registrado: {op.seleccion} @ {op.mejor_cuota.cuota:.2f} "
              f"({op.stake_unidades:.2f}u). Apunta la cuota de cierre antes del inicio "
              f"con: python -m sistema_apuestas cierre {pid} CUOTA")
    seg.cerrar()


def cmd_comparar(args) -> int:
    """Tabla de cuotas mínimas que tu casa (p. ej. Apostala) debe pagar."""
    from .comparar import candidatos
    from .fuentes import ErrorConfiguracion, ErrorFuente
    try:
        eventos, _ = _obtener_eventos(args)
    except ErrorConfiguracion as e:
        print(f"CONFIGURACIÓN NECESARIA:\n{e}", file=sys.stderr)
        return 2
    except ErrorFuente as e:
        print(f"Error de la fuente de datos: {e}", file=sys.stderr)
        return 3
    if not eventos:
        print("Sin eventos próximos con cuotas de referencia.")
        return 0

    filas = candidatos(eventos)
    if args.equipo:
        filtro = args.equipo.lower()
        filas = [f for f in filas
                 if filtro in f["mercado"].seleccion.lower()
                 or filtro in f["evento"].local.lower()
                 or filtro in f["evento"].visitante.lower()]

    _a_hora_local([f["evento"] for f in filas], args.tz)
    aptos = [f for f in filas if f["min_a"] is not None]
    print(f"Guía para comparar con {args.casa}: cuota mínima que debe pagar "
          "para que la apuesta alcance cada clase.\n")
    if not aptos:
        print("Ningún mercado alcanza el 75% de probabilidad de referencia: "
              "hoy no hay candidatos. NO APOSTAR por descarte no es un error, "
              "es el sistema funcionando.")
    for f in aptos:
        e, m = f["evento"], f["mercado"]
        a_plus = f"{f['min_a_plus']:.2f}" if f["min_a_plus"] else "— (p < 82%)"
        print(f"  {e.inicio.strftime('%d/%m %H:%M')} {e.local} vs {e.visitante} "
              f"[{e.competicion}]\n"
              f"    {m.seleccion}: p justa {f['p']:.1%} | cuota justa {f['justa']:.2f} "
              f"| clase A si paga >= {f['min_a']:.2f} | A+ si >= {a_plus} "
              f"(referencia: {f['n_ref']} casa(s))")
    no_aptos = len(filas) - len(aptos)
    if no_aptos:
        print(f"\n  Mercados bajo el umbral del 75%: {no_aptos} (no aptos para "
              "este sistema, aunque la cuota parezca atractiva).")
    if aptos and any(f["n_ref"] < Criterios().min_casas for f in aptos):
        print("\n  AVISO: la referencia actual es de pocas casas; al evaluar una "
              "cuota concreta el techo será clase B (observación, sin stake) "
              "hasta configurar THE_ODDS_API_KEY (consenso multi-casa).")
    print(f"\n  Siguiente paso: mira esas selecciones en {args.casa} y evalúa la "
          "cuota real, p. ej.:\n  python -m sistema_apuestas evaluar "
          "--seleccion \"<texto>\" --cuota 1.XX --fuente espn")
    return 0


def cmd_evaluar(args) -> int:
    """Evalúa la cuota concreta que ofrece tu casa para una selección."""
    from .comparar import evaluar_cuota
    from .fuentes import ErrorConfiguracion, ErrorFuente
    try:
        eventos, contexto = _obtener_eventos(args)
    except ErrorConfiguracion as e:
        print(f"CONFIGURACIÓN NECESARIA:\n{e}", file=sys.stderr)
        return 2
    except ErrorFuente as e:
        print(f"Error de la fuente de datos: {e}", file=sys.stderr)
        return 3

    filtro = args.seleccion.lower()
    coincidencias = [(e, m) for e, ms in eventos for m in ms
                     if filtro in m.seleccion.lower()
                     and (not args.mercado or m.mercado == args.mercado)]
    if not coincidencias:
        print(f"Ninguna selección coincide con '{args.seleccion}'. "
              "Usa 'comparar' para ver las disponibles.", file=sys.stderr)
        return 1
    if len(coincidencias) > 1:
        print("Hay varias selecciones que coinciden; sé más específico "
              "(o añade --mercado):", file=sys.stderr)
        for e, m in coincidencias[:10]:
            print(f"  - {m.seleccion} [{m.mercado}] ({e.local} vs {e.visitante})",
                  file=sys.stderr)
        return 1

    evento, mercado = coincidencias[0]
    plan = _plan(args)
    op = evaluar_cuota(evento, mercado, args.cuota, args.casa, plan=plan)
    if contexto:
        from .fuentes_espn import enriquecer_con_contexto
        enriquecer_con_contexto([op], contexto)
    _a_hora_local([op], args.tz)
    print(formatear_oportunidad(op, 1))

    if op.clasificacion in (Clasificacion.A_PLUS, Clasificacion.A):
        print(f"\nVEREDICTO: APTA ({op.clasificacion.value}).")
    elif op.clasificacion == Clasificacion.B:
        print("\nVEREDICTO: SOLO OBSERVACIÓN (B). El sistema NO apuesta las B; "
              "sirve para registrarla y medir si tu casa deja valor.")
    else:
        print("\nVEREDICTO: DESCARTADA. No apostar a esta cuota.")

    if args.registrar:
        if op.clasificacion == Clasificacion.DESCARTADA:
            print("No se registra: está DESCARTADA.")
            return 0
        seg = Seguimiento(args.db)
        pid = seg.registrar(
            fecha_evento=op.evento.inicio.isoformat(),
            deporte=op.evento.deporte.value, competicion=op.evento.competicion,
            evento=f"{op.evento.local} vs {op.evento.visitante}",
            mercado=op.mercado, seleccion=op.seleccion, casa=args.casa,
            cuota=args.cuota, prob_estimada=op.prob_estimada,
            ev=op.valor_esperado, clasificacion=op.clasificacion.value,
            stake_unidades=op.stake_unidades,
            notas=f"cuota manual; referencia {op.num_casas} casa(s)")
        seg.cerrar()
        print(f"Pick #{pid} registrado en {args.casa} "
              f"({op.stake_unidades:.2f}u{'; solo observación' if op.stake_unidades == 0 else ''}).")
    return 0


def cmd_resultado(args) -> int:
    seg = Seguimiento(args.db)
    try:
        if args.cuota_cierre:
            seg.fijar_cuota_cierre(args.id, args.cuota_cierre)
        seg.fijar_resultado(args.id, Resultado(args.resultado))
        print(f"Pick #{args.id} actualizado: {args.resultado}.")
        return 0
    except KeyError as e:
        print(e, file=sys.stderr)
        return 1
    finally:
        seg.cerrar()


def cmd_cierre(args) -> int:
    seg = Seguimiento(args.db)
    seg.fijar_cuota_cierre(args.id, args.cuota)
    seg.cerrar()
    print(f"Cuota de cierre {args.cuota:.2f} guardada para el pick #{args.id}. "
          "El CLV se calcula automáticamente en 'rendimiento'.")
    return 0


def cmd_pendientes(args) -> int:
    seg = Seguimiento(args.db)
    filas = seg.pendientes()
    if not filas:
        print("No hay picks pendientes.")
    for f in filas:
        demo = " [DEMO]" if f["es_demo"] else ""
        print(f"#{f['id']}{demo} {f['fecha_evento'][:16]} {f['evento']} | "
              f"{f['seleccion']} @ {f['cuota']:.2f} ({f['casa']}) | "
              f"{f['stake_unidades']:.2f}u [{f['clasificacion']}]")
    seg.cerrar()
    return 0


def cmd_rendimiento(args) -> int:
    seg = Seguimiento(args.db)
    print(informe_metricas("GLOBAL", seg.metricas()))
    if args.por:
        print(f"\nDesglose por {args.por}:")
        for clave, m in sorted(seg.desglose(args.por).items()):
            print("  " + informe_metricas(clave, m))
    print("\nLectura: el CLV positivo sostenido y el ROI con 100+ picks son las "
          "señales fiables; rachas cortas no significan nada. Retira del plan "
          "los mercados con ROI y CLV negativos persistentes.")
    seg.cerrar()
    return 0


def cmd_reglas(_args) -> int:
    print("Reglas de gestión del bankroll:")
    for r in REGLAS_ORO:
        print(f"  - {r}")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    fuente_defecto = "oddsapi" if os.environ.get("THE_ODDS_API_KEY") else "espn"

    p = argparse.ArgumentParser(
        prog="sistema_apuestas",
        description=("Análisis selectivo de apuestas deportivas por valor (+EV). "
                     "Solo recomienda A+ y A; si no hay valor: NO APOSTAR. "
                     "No apuesta automáticamente ni accede a cuentas."))
    p.add_argument("--db", default=DB_POR_DEFECTO,
                   help="ruta de la base de datos de seguimiento")
    p.add_argument("--tz", default=TZ_POR_DEFECTO,
                   help=f"zona horaria de los informes (por defecto {TZ_POR_DEFECTO})")
    sub = p.add_subparsers(dest="comando", required=True)

    def _opciones_fuente(sp, deporte_defecto="todos"):
        sp.add_argument("--deporte", choices=["futbol", "tenis", "basquet", "todos"],
                        default=deporte_defecto)
        sp.add_argument("--region", default="eu", choices=["eu", "uk", "us", "au"],
                        help="región de casas (fuente oddsapi)")
        sp.add_argument("--fuente", default=fuente_defecto,
                        choices=["oddsapi", "espn"],
                        help="oddsapi = multi-casa (requiere THE_ODDS_API_KEY); "
                             "espn = NBA sin clave (1 casa de referencia). "
                             f"Por defecto: {fuente_defecto}")
        sp.add_argument("--fecha", default=None,
                        help="fecha AAAAMMDD para la fuente espn (por defecto, hoy)")

    a = sub.add_parser("analizar", help="buscar oportunidades de valor")
    _opciones_fuente(a)
    a.add_argument("--demo", action="store_true",
                   help="usar datos FICTICIOS para probar el sistema (no apostar)")
    a.add_argument("--bankroll", type=float, default=None,
                   help="bankroll total para calcular stakes en unidades")
    a.add_argument("--mostrar-descartadas", action="store_true",
                   help="mostrar también los mercados descartados y el porqué")
    a.add_argument("--registrar", action="store_true",
                   help="registrar automáticamente las A+/A en el seguimiento")
    a.set_defaults(func=cmd_analizar)

    co = sub.add_parser(
        "comparar",
        help="cuotas mínimas que tu casa (p. ej. Apostala) debe pagar para A/A+")
    _opciones_fuente(co, deporte_defecto="basquet")
    co.add_argument("--casa", default="Apostala",
                    help="nombre de tu casa de apuestas (por defecto: Apostala)")
    co.add_argument("--equipo", default=None,
                    help="filtrar por equipo o texto de la selección")
    co.set_defaults(func=cmd_comparar)

    ev = sub.add_parser(
        "evaluar", help="clasificar la cuota concreta que te ofrece tu casa")
    _opciones_fuente(ev, deporte_defecto="basquet")
    ev.add_argument("--seleccion", required=True,
                    help="texto de la selección, p. ej. 'Gana New York Knicks'")
    ev.add_argument("--cuota", type=float, required=True,
                    help="cuota decimal que ofrece tu casa")
    ev.add_argument("--casa", default="Apostala",
                    help="nombre de tu casa (por defecto: Apostala)")
    ev.add_argument("--mercado", default=None,
                    choices=["ganador", "handicap", "total_puntos",
                             "doble_oportunidad", "total_goles"],
                    help="desambiguar si varias selecciones coinciden")
    ev.add_argument("--bankroll", type=float, default=None,
                    help="bankroll para calcular el stake si es A/A+")
    ev.add_argument("--registrar", action="store_true",
                    help="registrar el pick (B se registra con stake 0)")
    ev.set_defaults(func=cmd_evaluar)

    r = sub.add_parser("resultado", help="anotar el resultado de un pick")
    r.add_argument("id", type=int)
    r.add_argument("resultado", choices=["GANADA", "PERDIDA", "NULA"])
    r.add_argument("--cuota-cierre", type=float, default=None,
                   help="cuota de cierre para calcular el CLV")
    r.set_defaults(func=cmd_resultado)

    c = sub.add_parser("cierre", help="guardar la cuota de cierre de un pick (CLV)")
    c.add_argument("id", type=int)
    c.add_argument("cuota", type=float)
    c.set_defaults(func=cmd_cierre)

    pe = sub.add_parser("pendientes", help="listar picks sin resultado")
    pe.set_defaults(func=cmd_pendientes)

    m = sub.add_parser("rendimiento", help="métricas: aciertos, ROI, P/L, CLV")
    m.add_argument("--por", choices=["deporte", "mercado"], default=None)
    m.set_defaults(func=cmd_rendimiento)

    g = sub.add_parser("reglas", help="reglas de gestión del bankroll")
    g.set_defaults(func=cmd_reglas)
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    return args.func(args)
