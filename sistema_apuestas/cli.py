"""Interfaz de línea de comandos del sistema.

Uso rápido:
  python -m sistema_apuestas analizar --demo
  python -m sistema_apuestas analizar --deporte futbol --bankroll 500
  python -m sistema_apuestas resultado 3 GANADA --cuota-cierre 1.18
  python -m sistema_apuestas rendimiento --por mercado
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from .analisis import analizar_eventos
from .bankroll import REGLAS_ORO, PlanBankroll, validar_dia
from .demo import eventos_demo
from .filtros import Criterios
from .informe import informe, informe_metricas
from .modelos import Clasificacion, Deporte, Resultado
from .seguimiento import Seguimiento

DB_POR_DEFECTO = "datos/seguimiento.db"


def _plan(args) -> PlanBankroll | None:
    return PlanBankroll(bankroll=args.bankroll) if args.bankroll else None


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
    contexto: dict[str, list[str]] = {}
    eventos = []
    try:
        if args.fuente == "espn":
            if args.deporte not in ("basquet", "todos"):
                print("La fuente 'espn' solo cubre NBA (--deporte basquet).",
                      file=sys.stderr)
                return 2
            from .fuentes_espn import eventos_nba
            eventos, contexto = eventos_nba(args.fecha)
            print("Fuente: ESPN (NBA). Normalmente publica UNA sola casa, por lo "
                  "que el filtro no puede validar valor y descartará los mercados; "
                  "para comparación multi-casa configura THE_ODDS_API_KEY.\n")
        else:
            from .fuentes import convertir_eventos, obtener_eventos_con_cuotas
            deportes = ([Deporte(args.deporte)] if args.deporte != "todos"
                        else [Deporte.FUTBOL, Deporte.TENIS, Deporte.BASQUET])
            for dep in deportes:
                crudos = obtener_eventos_con_cuotas(dep, region=args.region)
                eventos.extend(convertir_eventos(crudos, dep))
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
    p = argparse.ArgumentParser(
        prog="sistema_apuestas",
        description=("Análisis selectivo de apuestas deportivas por valor (+EV). "
                     "Solo recomienda A+ y A; si no hay valor: NO APOSTAR. "
                     "No apuesta automáticamente ni accede a cuentas."))
    p.add_argument("--db", default=DB_POR_DEFECTO,
                   help="ruta de la base de datos de seguimiento")
    sub = p.add_subparsers(dest="comando", required=True)

    a = sub.add_parser("analizar", help="buscar oportunidades de valor")
    a.add_argument("--deporte", choices=["futbol", "tenis", "basquet", "todos"],
                   default="todos")
    a.add_argument("--region", default="eu", choices=["eu", "uk", "us", "au"],
                   help="región de casas de apuestas a comparar")
    a.add_argument("--fuente", default="oddsapi", choices=["oddsapi", "espn"],
                   help="oddsapi = multi-casa (requiere clave); espn = NBA sin clave (1 casa)")
    a.add_argument("--fecha", default=None,
                   help="fecha AAAAMMDD para la fuente espn (por defecto, hoy)")
    a.add_argument("--demo", action="store_true",
                   help="usar datos FICTICIOS para probar el sistema (no apostar)")
    a.add_argument("--bankroll", type=float, default=None,
                   help="bankroll total para calcular stakes en unidades")
    a.add_argument("--mostrar-descartadas", action="store_true",
                   help="mostrar también los mercados descartados y el porqué")
    a.add_argument("--registrar", action="store_true",
                   help="registrar automáticamente las A+/A en el seguimiento")
    a.set_defaults(func=cmd_analizar)

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
