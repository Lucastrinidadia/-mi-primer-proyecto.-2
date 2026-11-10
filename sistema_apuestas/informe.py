"""Informes en el formato de 10 puntos pedido por el sistema."""

from __future__ import annotations

from .bankroll import REGLAS_ORO, PlanBankroll
from .modelos import Clasificacion, Oportunidad

AVISO_DEMO = ("⚠️  MODO DEMO: todos los equipos, cuotas y fechas son FICTICIOS. "
              "Sirven solo para ver cómo funciona el sistema. NO APOSTAR.")

AVISO_RESPONSABLE = (
    "Apostar conlleva riesgo real de pérdida. Ninguna probabilidad, por alta que sea, "
    "garantiza el resultado. Apuesta solo si es legal en tu jurisdicción, eres mayor de "
    "edad y puedes permitirte perder lo apostado.")


def _linea(n: int, titulo: str, valor: str) -> str:
    return f"  {n:>2}. {titulo}: {valor}"


def formatear_oportunidad(op: Oportunidad, indice: int) -> str:
    e = op.evento
    lineas = [
        f"\n{'='*74}",
        f"[{op.clasificacion.value}] Oportunidad #{indice}"
        + ("   ⚠️ DEMO (datos ficticios)" if op.es_demo else ""),
        "=" * 74,
        _linea(1, "Partido y competición",
               f"{e.local} vs {e.visitante} — {e.competicion} ({e.deporte.value})"),
        _linea(2, "Fecha y horario", e.inicio.strftime("%d/%m/%Y %H:%M UTC")),
        _linea(3, "Mercado recomendado", f"{op.seleccion} [{op.mercado}]"),
        _linea(4, "Cuota disponible",
               f"{op.mejor_cuota.cuota:.2f} en {op.mejor_cuota.casa}"),
        _linea(5, "Probabilidad estimada", f"{op.prob_estimada:.1%} ({op.metodo})"),
        _linea(6, "Probabilidad implícita de la cuota", f"{op.prob_implicita:.1%}"),
        _linea(7, "Valor esperado (EV)", f"{op.valor_esperado:+.2%} por unidad apostada"),
        _linea(8, "Estadísticas que respaldan la selección", ""),
    ]
    lineas += [f"      - {s}" for s in op.estadisticas]
    lineas.append(_linea(9, "Riesgos específicos", ""))
    lineas += [f"      - {r}" for r in op.riesgos]
    lineas.append(_linea(10, "Nivel de confianza", op.confianza))
    if op.stake_unidades > 0:
        lineas.append(f"\n  Stake sugerido: {op.stake_unidades:.2f} unidades "
                      "(Kelly fraccional 25%, con tope por clasificación).")
    if op.fuentes:
        lineas.append("  Fuentes: " + " | ".join(op.fuentes))
    return "\n".join(lineas)


def informe(oportunidades: list[Oportunidad], plan: PlanBankroll | None = None,
            mostrar_descartadas: bool = False, es_demo: bool = False) -> str:
    """Informe completo: solo A+ y A como recomendaciones; el resto, resumen."""
    partes: list[str] = []
    if es_demo:
        partes.append(AVISO_DEMO)

    recomendadas = [o for o in oportunidades
                    if o.clasificacion in (Clasificacion.A_PLUS, Clasificacion.A)]
    observacion = [o for o in oportunidades if o.clasificacion == Clasificacion.B]
    descartadas = [o for o in oportunidades
                   if o.clasificacion == Clasificacion.DESCARTADA]

    partes.append(f"\nMercados analizados: {len(oportunidades)} | "
                  f"A+/A: {len(recomendadas)} | B (solo observación): {len(observacion)} | "
                  f"Descartados: {len(descartadas)}")

    if not recomendadas:
        partes.append(
            "\n>>> RECOMENDACIÓN: NO APOSTAR HOY <<<\n"
            "Ningún mercado analizado alcanza la clasificación A o A+.\n"
            "No apostar también es una decisión ganadora: protege el bankroll\n"
            "y espera a que el valor aparezca. No fuerces pronósticos.")
    else:
        partes.append("\nRECOMENDACIONES (solo A+ y A):")
        for i, op in enumerate(recomendadas, 1):
            partes.append(formatear_oportunidad(op, i))

    if observacion:
        partes.append("\nEn observación (B, NO apostar):")
        for o in observacion:
            partes.append(f"  - {o.evento.local} vs {o.evento.visitante}: {o.seleccion} "
                          f"@ {o.mejor_cuota.cuota:.2f} | p={o.prob_estimada:.0%} "
                          f"EV={o.valor_esperado:+.1%} | motivo: "
                          + (o.riesgos[0] if o.riesgos else "incertidumbre"))

    if mostrar_descartadas and descartadas:
        partes.append("\nDescartadas (transparencia del filtro):")
        for o in descartadas:
            partes.append(f"  - {o.evento.local} vs {o.evento.visitante}: {o.seleccion} "
                          f"@ {o.mejor_cuota.cuota:.2f} | p={o.prob_estimada:.0%} "
                          f"EV={o.valor_esperado:+.1%} | "
                          + (o.riesgos[0] if o.riesgos else ""))

    if plan:
        partes.append(f"\nPlan de bankroll: {plan.bankroll:.2f} | 1 unidad = "
                      f"{plan.valor_unidad:.2f} ({plan.unidad_pct:.1f}%) | "
                      f"máx {plan.max_unidades_apuesta:.0f}u/apuesta, "
                      f"{plan.max_unidades_dia:.0f}u/día, "
                      f"stop-loss diario {plan.stop_loss_dia:.0f}u.")

    partes.append("\nReglas de oro:")
    partes += [f"  - {r}" for r in REGLAS_ORO]
    partes.append("\n" + AVISO_RESPONSABLE)
    return "\n".join(partes)


def informe_metricas(titulo: str, m) -> str:
    acierto = f"{m.tasa_acierto:.1%}" if m.tasa_acierto is not None else "—"
    roi = f"{m.roi:+.1%}" if m.roi is not None else "—"
    clv = f"{m.clv_medio_pct:+.2f}%" if m.clv_medio_pct is not None else "— (registra cuotas de cierre)"
    return (f"{titulo}: {m.total} picks ({m.resueltas} resueltos) | "
            f"Aciertos: {m.ganadas}G/{m.perdidas}P/{m.nulas}N ({acierto}) | "
            f"P/L: {m.beneficio_unidades:+.2f}u | ROI: {roi} | CLV medio: {clv}")
