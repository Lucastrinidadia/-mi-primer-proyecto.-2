# Sistema de análisis de apuestas deportivas por valor (+EV)

Sistema **extremadamente selectivo** de análisis de apuestas deportivas. Su objetivo no es
apostar todos los días: es encontrar las pocas oportunidades con **valor matemático
verificable** y descartar todo lo demás. Si no hay valor, la recomendación es **NO APOSTAR**.

> ⚠️ **Aviso**: apostar conlleva riesgo real de pérdida. Ninguna probabilidad, por alta que
> sea, garantiza un resultado, y ningún sistema asegura ganancias. Usa solo dinero que puedas
> permitirte perder, verifica que apostar sea legal en tu jurisdicción y busca ayuda
> profesional si el juego deja de ser una decisión fría. Este software **no apuesta
> automáticamente ni accede a cuentas de casas de apuestas**: solo analiza y recomienda.

## Qué hace

1. **Análisis deportivo** — Fútbol (7 ligas principales), tenis (ATP/WTA) y básquet
   (NBA/Euroliga), ampliable editando `fuentes.py`.
2. **Búsqueda de cuotas** — Compara cuotas reales de múltiples casas (The Odds API),
   calcula probabilidad implícita, quita el margen (vig) y detecta la mejor cuota.
3. **Probabilidad estimada honesta** — La probabilidad "real" se estima con la **mediana del
   consenso de mercado sin margen** (el estimador público más sólido que existe), contrastable
   con modelos estadísticos incluidos: Poisson para goles, Elo para tenis, Normal para básquet.
4. **Filtro de riesgo** — Clasifica cada mercado en `A+ / A / B / DESCARTADA` con umbrales
   estrictos. **Solo A+ y A son recomendaciones**; probabilidad alta sin valor se descarta.
5. **Gestión del bankroll** — Unidades del 1%, Kelly fraccional (25%) con topes, límites
   diarios, stop-loss y prohibición explícita de martingalas.
6. **Seguimiento y mejora continua** — Base de datos SQLite con aciertos, ROI, P/L,
   rendimiento por deporte y por mercado, y **CLV** (cuota tomada vs cuota de cierre).

## Instalación

```bash
pip install -r requirements.txt            # solo 'requests'
```

Datos reales (el sistema **nunca inventa cuotas ni estadísticas**):

```bash
export THE_ODDS_API_KEY=tu_clave           # gratis en https://the-odds-api.com (cuotas)
export FOOTBALL_DATA_API_KEY=tu_clave      # opcional, https://www.football-data.org (stats fútbol)
```

## Uso

```bash
# Ver el sistema funcionando con datos FICTICIOS claramente marcados (sin claves):
python -m sistema_apuestas analizar --demo --bankroll 1000 --mostrar-descartadas

# Análisis real (requiere THE_ODDS_API_KEY):
python -m sistema_apuestas analizar --deporte futbol --bankroll 500
python -m sistema_apuestas analizar --deporte todos --region eu --registrar

# Seguimiento:
python -m sistema_apuestas pendientes
python -m sistema_apuestas cierre 3 1.22            # cuota de cierre -> CLV
python -m sistema_apuestas resultado 3 GANADA
python -m sistema_apuestas rendimiento --por mercado
python -m sistema_apuestas reglas
```

### Formato de cada recomendación (10 puntos)

Partido y competición · fecha y hora · mercado recomendado · cuota y casa · probabilidad
estimada · probabilidad implícita · valor esperado (EV) · estadísticas que la respaldan ·
riesgos específicos · nivel de confianza. Más fuentes verificables y stake sugerido en unidades.

## Metodología (sin humo)

- **Probabilidad implícita**: `1 / cuota`. Incluye el margen de la casa.
- **Quitar el margen**: las implícitas de un mercado se normalizan para que sumen 1.
- **Consenso**: mediana de esas probabilidades entre todas las casas (robusta frente a
  cuotas atípicas). Con menos de 4 casas la confianza baja; con menos de 2, se descarta.
- **Valor esperado**: `EV = p × cuota − 1`. Solo hay recomendación si `EV > 0` **y** la
  probabilidad estimada supera el 75% (sistema orientado a alta probabilidad).
- **Clasificación**:

  | Clase | Condiciones principales |
  |---|---|
  | `A+` | p ≥ 82%, EV ≥ 4.5%, ≥ 6 casas, mercado estable |
  | `A`  | p ≥ 75%, EV ≥ 2%, ≥ 4 casas, mercado estable, cuota ≤ 1.60 |
  | `B`  | hay valor pero con incertidumbre (pocas casas, mercado inestable, p < 75%). **No se apuesta**: solo observación |
  | `DESCARTADA` | EV ≤ 0, p < 60%, cuota < 1.08, o mejor cuota sospechosamente alejada del mercado (> 12% sobre la mediana) |

- **Protecciones extra**: nunca eventos ya empezados; una cuota muy por encima del resto del
  mercado se trata como posible error de la casa y se descarta; las combinadas no se
  recomiendan (multiplican el margen).
- **Mercados estables priorizados**: doble oportunidad, empate no válido (DNB), totales de
  goles (más 0.5/1.5, menos 4.5…), hándicap asiático, ganador, totales de puntos/juegos.
  El módulo `probabilidad.py` calcula además todos esos mercados desde un modelo Poisson
  cuando dispones de medias de goles reales (p. ej. vía football-data.org).

## Gestión del dinero (reglas fijas)

- 1 unidad = **1% del bankroll**. Máximo **2u por apuesta** (A+), 1u (A), 0u (B/descartadas).
- Stake por **Kelly fraccional al 25%**, siempre acotado por los topes anteriores.
- Máximo **3 apuestas/día**, **5u/día**, **stop-loss diario de 3u** (se aplica al registrar).
- **Prohibido** perseguir pérdidas, subir stakes para recuperar y cualquier martingala.
- Sin oportunidades A+/A: **NO APOSTAR** es la recomendación oficial del sistema.

## Mejora continua

Cada pick registrado guarda cuota, probabilidad estimada, EV, clasificación y stake. Con
`rendimiento` obtienes: % de aciertos, ROI real, P/L en unidades, desglose por deporte y por
mercado, y **CLV medio** (si tu cuota supera sistemáticamente a la de cierre, el método tiene
ventaja real; es la señal más fiable antes que cualquier racha). Retira de tu plan los
mercados con ROI y CLV negativos persistentes. Evalúa con 100+ picks, nunca con 10.

## Estructura

```
sistema_apuestas/
  modelos.py       # dataclasses: eventos, cuotas, oportunidades, clasificaciones
  probabilidad.py  # Poisson (fútbol), Elo (tenis), Normal (básquet), consenso sin margen
  valor.py         # prob. implícita, margen, EV, Kelly, mejor cuota
  filtros.py       # filtro de riesgo y clasificación A+/A/B/DESCARTADA
  bankroll.py      # unidades, Kelly fraccional, límites diarios, reglas de oro
  analisis.py      # motor: eventos + cuotas -> oportunidades clasificadas
  fuentes.py       # The Odds API y football-data.org (datos reales, nunca inventados)
  seguimiento.py   # SQLite: picks, resultados, ROI, CLV, desgloses
  informe.py       # informe en el formato de 10 puntos
  demo.py          # datos FICTICIOS marcados como DEMO para probar el flujo
  cli.py           # interfaz de línea de comandos
tests/             # 42 tests unitarios de toda la matemática y el flujo
```

Los tests se ejecutan con `python -m unittest discover -s tests`.
