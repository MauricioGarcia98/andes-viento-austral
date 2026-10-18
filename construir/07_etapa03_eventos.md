# 07 · Etapa 3 · Eventos: lo que le pasa a la empresa

## 🎯 Objetivo

La física dice cuánto **podría** generar cada turbina. Esta etapa decide **qué pasó** cada día: si hubo un frente
frío, hielo, una falla, un corte de satélite, un reloj corrido, una orden de CAMMESA de bajar potencia, cuánto valía
el dólar. Son las **tablas guía**: listas chicas que después las fuentes grandes (capítulo 08) consultan para
"ensuciar" y "romper" la telemetría.

También llegan los primeros tests de verdad: que la física en Spark y en Python coincidan y que la historia guionada
esté en los datos.

**Archivos:** `src/andes_viento/datagen/events.py`, `tests/test_physics.py`, `tests/test_events.py`.

## 📚 Conceptos

- **Proceso AR(1) (autorregresivo):** una serie donde cada valor depende del anterior más ruido:
  `x_hoy = 0,75 · x_ayer + ruido`. Es la forma más simple de modelar que "si ayer hizo frío, hoy probablemente
  también". El viento y la temperatura diarios se modelan así.
- **Driver vs. ejecutores:** en Spark, el *driver* es el proceso que coordina; los *ejecutores* procesan las
  particiones. Lo que es chico y secuencial (365 días × 13 parques) se calcula en el driver con Python; lo que es
  enorme y paralelo (millones de lecturas), en los ejecutores con Spark.
- **Prefijo estable:** si generás la historia hasta el 30-09-2026 y después el job diario genera el 01-10-2026, ese
  día tiene que ser **idéntico** al que saldría de regenerar todo hasta el 01-10-2026. Para eso, toda serie arranca
  siempre en `cfg.start_date`, sin importar hasta dónde se pida.
- **`lru_cache`:** memoriza el resultado de una función para los mismos argumentos. La flota y el clima se piden
  muchas veces por corrida; se calculan una.

## 🧱 Paso a paso

Escribí `events.py` en este orden (`git show etapa-03:src/andes_viento/datagen/events.py`):

### 1. Utilidades de fechas

`local_epoch(d, hora)` da los segundos UTC de una fecha y hora **argentinas** (`ART = UTC-3`). Todos los eventos se
guardan como *epoch* UTC: un número sin ambigüedad de zona horaria. `daterange` y `month_starts` recorren días y
meses.

### 2. La flota a la escala pedida

```python
@dataclass(frozen=True)
class Unit:
    asset_id: str      # WTG00001... / INV00001...
    asset_type: str    # WTG | INV
    park: str
    idx: int           # 1..n dentro del parque
    tag: str           # nombre original ("CRV-07")
    new_tag: str | None  # nombre después del renombre ("CRV-WTG007", sólo Cerro Arenales)
    manufacturer: str | None
    rated_kw: float
    dc_kwp: float
    panels: int
    wake: float        # pérdida por estela (algunas turbinas "tapan" a otras)
    commissioning: date

@lru_cache(maxsize=8)
def _fleet(scale_factor: float, seed: int) -> tuple[Unit, ...]:
    cfg = ProjectConfig(scale_factor=scale_factor, seed=seed)
    ...
    for park in R.PARKS:
        n = cfg.units(park.units_real)
        for i in range(1, n + 1):
            rng = prng(seed, "unit", park.code, i)
            ...
    return tuple(units)
```
- El `asset_id` (`WTG00031`) es la **clave estable** de la turbina para siempre. El `tag` (`CRV-07`) es el nombre que
  ve la gente y **cambia** (en Cerro Arenales en jun-2024). Separar "identidad" de "nombre" es la base del SCD2 del
  capítulo 11.
- `wake` es un número al azar fijo por turbina (0,92 a 1,04): unas turbinas están mejor ubicadas que otras.
- Devuelve una **tupla** (inmutable) porque `lru_cache` devuelve el mismo objeto a todos: si fuera una lista, alguien
  podría modificarla y arruinarles los datos a los demás.

`fleet(cfg, "WTG")`, `park_capacity_kw` y `park_units` son consultas sobre la flota.

### 3. El clima diario: dos procesos AR(1) por región

```python
WIND_DAY_SIGMA = 0.12

@lru_cache(maxsize=4)
def _park_days(seed, start, end):
    state = {r: {"x": 0.0, "y": 0.0} for r in ("PATAGONIA", "NOA")}
    for d in daterange(start, end):
        regional = {}
        for region, st in state.items():
            rng = prng(seed, "wx", region, d)
            st["x"] = 0.75 * st["x"] + 0.66 * rng.gauss(0, 1)    # viento del día (persistente)
            st["y"] = 0.80 * st["y"] + 0.60 * rng.gauss(0, 1)    # anomalía de temperatura
            regional[region] = (math.exp(WIND_DAY_SIGMA * st["x"] - WIND_DAY_SIGMA ** 2 / 2), 2.5 * st["y"])
        for park in R.PARKS:
            ...   # cada parque: la señal regional + su propio ruido; lluvia, nieve, hielo, nubes, polvo
```
- **Regional primero, después el parque:** un frente afecta a toda la Patagonia; cada parque le suma su variación.
  Así los parques de una región están correlacionados, como en la realidad.
- `exp(σ·x − σ²/2)`: un multiplicador **log-normal** con media 1. Un día ventoso puede ser 1,3 y uno calmo 0,7, pero
  en promedio no cambia el viento medio del parque.
- Por cada parque y día se decide: lluvia (con la probabilidad de su región y mes; en la Puna llueve en verano, el
  "invierno altiplánico"), **nieve** (si llueve con temperatura bajo 1 °C), **ruta cortada** (nieve ≥ 4 cm: las
  cuadrillas no llegan), **hielo en palas** (parques de Santa Cruz o a más de 400 m, de mayo a septiembre, con
  temperatura bajo 0,5 °C), nubes y **tormentas de polvo** (solares, de julio a octubre).
- **La historia guionada se impone acá:** en julio 2025 el viento de Cañadón León no depende del azar
  (`wind_anomaly = 0.98`) y del 3 al 5 de julio hay ola polar (−7 °C extra y precipitación: hielo).

### 4. Suciedad de paneles y limpiezas

`soiling()` recorre cada parque solar día por día: la suciedad sube un poco cada día (más en la estación seca y con
tormentas de polvo), baja con la lluvia (`× 0,25` con más de 4 mm) y vuelve casi a cero con una **limpieza**. La
política histórica de la empresa es limpiar "cada ~75 días" o después de una tormenta fuerte. El caso de negocio 3
muestra que esa política es mala (capítulo 13). Es secuencial (la suciedad de hoy depende de la de ayer): por eso se
calcula en el driver.

### 5. Paradas: preventivo, fallas menores y mayores

```python
def downtime_events(cfg, end):
    wx = park_day_index(cfg, end + timedelta(days=60))
    for u in fleet(cfg):
        for m0 in month_starts(first, end):
            rng = prng(cfg.seed, "dt", u.asset_id, m0)
            if u.asset_type == "WTG":
                # preventivo semestral, en meses alternados según la turbina
                # falla menor (12 % por mes): 45 % se resuelve con un reset remoto; si no, viaje + reparación
                # falla mayor (4,5 % por año): multiplicadora, rodamiento principal o del generador
                # lote defectuoso HTW 2024-2025: 60 % anual de multiplicadoras rotas
            else:
                # inversores: fallas de IGBT, ventilación, aislación
        # historia: la multiplicadora de la turbina 1 de Cañadón León, el 26-07-2025, 21 días
        events.extend(_drop_overlaps(per_unit))
```
**`_major`, la falla mayor**, es donde está la operación real:
```python
    warn_days = R.COMPONENTS[comp][1] + rng.randint(-4, 6)          # días de aviso en las temperaturas
    surprise = forced_days is None and rng.random() < 0.15          # 15 %: falla sin aviso
    wait = rng.uniform(*wait_days) * 24                              # repuesto importado: 12-20 días
    if park.province == "Santa Cruz" and d.month in (6, 7, 8):
        delay = rng.uniform(5, 8) * 24                               # nieve en la ruta + viento: la grúa no iza
    ...
    return _event(..., degrade_start=None if surprise else start - warn_days * 86_400)
```
- `degrade_start`: desde cuándo la turbina **calienta más que sus vecinas**. Es la firma que el modelo predictivo
  puede detectar (capítulo 13). Sin aviso (`surprise`), el modelo no la puede ver, y está bien que no la vea.
- La duración se arma por partes (viaje + espera del repuesto + demoras de acceso + reparación) porque el caso de la
  garantía (capítulo 13) necesita separar las horas: la **nieve en la ruta es fuerza mayor** y no se le cobra al
  fabricante.
- `forced_days=21`: la historia pide exactamente 21 días de parada; la espera se ajusta para que cierre.

**`_drop_overlaps`**: una turbina no puede estar en dos paradas a la vez. Se ordenan por gravedad (mayor, menor,
preventivo) y se descarta la que se superpone con una más grave. Hay un test para esto.

### 6. Problemas de los datos (no de la turbina)

| función | qué genera | qué tiene que hacer silver después |
|---|---|---|
| `comm_outages` | cortes del enlace: VSAT 2-4 por mes (más largos en invierno), fibra rara vez. El 60 % tiene *buffer*: los datos llegan tarde, todos juntos | aceptar datos tardíos y deduplicar |
| `clock_skews` | 6 % de las turbinas por año tiene el reloj corrido 3-14 minutos durante 10-60 días | detectar y corregir el desfase |
| `stuck_sensors` | 1-2 episodios por turbina y año de un sensor "clavado" en un valor | detectar valores repetidos y anularlos |

Son el trabajo del capítulo 10. Generarlos acá, con fecha y magnitud, permite **testear** que silver los encuentra.

### 7. Curtailment: las órdenes de CAMMESA

```python
    for d in daterange(cfg.start_date, end):
        weekend = d.weekday() >= 5 or d in R.HOLIDAYS_AR
        windy = wx[("CRV", d)]["wind_mult"]
        p = 0.16 * growth.get(d.year, 1.1) * season[d.month] * (1.6 if weekend else 1.0) * windy ** 2
        congested = rng.random() < min(0.85, p)
        for park in R.WIND_PARKS:
            if forced:                                    # mantenimiento de la ET (historia)
                frac, reason = 0.50, "MANTENIMIENTO_ET"
            elif congested and prk.random() < park.curtail_exposure:
                frac = ...; reason = "RESTRICCION_TRANSPORTE"
            elif prk.random() < 0.004:
                reason = "CONTROL_FRECUENCIA"
```
La probabilidad de congestión sube con el **año** (la línea se satura cada vez más), la **estación** (primavera:
mucho viento y poca demanda), los **fines de semana y feriados** (poca demanda) y el **viento al cuadrado** (cuando
sopla, sopla en todos los parques a la vez). Cada parque, si hay congestión, recibe la orden con una probabilidad igual
a su exposición: los de Santa Cruz, al final de la línea, la reciben más.

### 8. Mercado y presupuesto

- `fx_rate(d)`: el dólar oficial, interpolando entre fines de mes; el 13-12-2023 salta de ~366 a ~800 (devaluación).
- `cpi_index` y `labor_rate_ars`: inflación acumulada; la hora de trabajo en pesos la sigue con un mes de rezago.
- `spot_price_usd`: precio horario con forma diaria (pico a las 19-21 h) y estacional (invierno caro). **Si el nodo
  Patagonia está congestionado, el precio se derrumba a 4-15 USD/MWh**: sobra energía y no hay cómo sacarla. Por eso
  el curtailment "vale poco" a precio spot (caso de negocio 1).
- `BUDGET_ASSUMPTIONS` y `expected_unit_kw`: el presupuesto P50 que hace Finanzas, con un **Monte Carlo** usando la
  misma física (1.200 instantes al azar del mes). Así el presupuesto es razonable y el desvío real se explica por
  causas concretas.

### 9. Los tests

`tests/test_physics.py`:
```python
@pytest.mark.parametrize("park", ["LEO", "RAW", "PAM"])
def test_wind_spark_equals_python(spark, park):
    ...   # el mismo instante calculado con wind_ms_col en Spark y con wind_ms_py
        assert row.w == pytest.approx(ph.wind_ms_py(park, row.epoch, 1.1, 0.97, 0.3), rel=1e-9)
```
`parametrize` corre el mismo test para tres parques (uno de cada fabricante). La tolerancia es `1e-9`: tienen que
dar lo mismo, no "parecido". También: la forma de la curva de potencia, el sol (de día > 800 W/m², de noche 0) y que
la Puna tenga heladas y el invierno patagónico sea > 10 °C más frío que el verano.

`tests/test_events.py`: la flota a escala 1 (380 turbinas, 220 inversores, 1,2 M paneles); el **prefijo estable** del
clima; que la historia exista (la falla del 26-07-2025 dura 21 días, 11 órdenes `MANTENIMIENTO_ET` en Cañadón León);
que no haya paradas superpuestas; y la devaluación.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| tablas guía en el driver | todo en Spark | lo secuencial (clima, suciedad) no se paraleliza y son pocas filas: Python es más simple y claro |
| la historia "forzada" | dejar que salga sola del azar | con azar puro, julio 2025 podría no ser especial y el caso de Agent mode no existiría |
| duraciones por partes (viaje, espera, demora, reparación) | una duración total | la garantía necesita separar la fuerza mayor; Mantenimiento quiere saber cuánto es espera de repuesto |
| precio spot con nodo desacoplado | un precio único nacional | sin eso, el caso de baterías da una respuesta equivocada (que conviene invertir) |
| presupuesto con la misma física | un número fijo por parque | el desvío no tendría causas: sería ruido |

## ✅ Probalo

```bash
pytest tests/test_physics.py tests/test_events.py    # 11 passed
pytest                                               # 12 passed (con el de calidad)
```
Y a mano:
```bash
python - <<'EOF'
from datetime import date, datetime, timedelta, timezone
from andes_viento.config import ProjectConfig
from andes_viento.datagen import events as E
cfg = ProjectConfig(scale_factor=0.1)
print(len(E.fleet(cfg, "WTG")), "turbinas a SF 0,1")
art = timezone(timedelta(hours=-3))
leo = [e for e in E.downtime_events(cfg, date(2025, 8, 31))
       if e["park"] == "LEO" and datetime.fromtimestamp(e["start"], art).date() == date(2025, 7, 26)]
print([(e["asset_id"], e["component"], round((e["end"] - e["start"]) / 86400)) for e in leo])
print(E.fx_rate(date(2023, 12, 12)), "→", E.fx_rate(date(2023, 12, 13)))
EOF
```
Tiene que dar `37 turbinas a SF 0,1`, `[('WTG00034', 'GEARBOX', 21)]` (la multiplicadora guionada: 21 días) y
`372.6 → 800.0` (la devaluación).

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `test_wind_spark_equals_python` falla por poco | las dos fórmulas difieren en algo (un factor, el mes local vs. UTC) | compará `wind_ms_py` y `wind_ms_col` término por término |
| `test_weather_series_is_prefix_stable` falla | la serie no arranca siempre en `start_date` o usa estado global | `_park_days(seed, start, end)` con `start` fijo; el estado dentro de la función |
| `test_no_overlapping_downtime` falla | faltó `_drop_overlaps` o el orden por gravedad | revisá `rank` y la condición de solapamiento |
| tarda mucho | `lru_cache` no aplica porque pasás objetos distintos cada vez | la caché es por `(scale_factor, seed)` y `(seed, start, end)`: valores simples |
| `TypeError: unhashable type` en `lru_cache` | pasaste un `dict` o una lista como argumento | los argumentos de una función cacheada tienen que ser inmutables |

## 📍 Punto de control

```bash
git commit -am "etapa-03: eventos" && git diff etapa-03 HEAD --stat
```

## 🏋️ Ejercicio

1. Contá cuántas órdenes de curtailment recibe cada parque por año
   (`E.curtailment_instructions(cfg, date(2025, 12, 31))`). ¿Crece año a año? ¿Santa Cruz recibe más que Chubut?
2. Agregá a `STORY` una "ola de calor" en la Puna en enero 2026 (+6 °C) y escribí un test que la verifique en
   `park_days`.
3. Calculá con `expected_unit_kw` el factor de capacidad esperado de una turbina de Cañadón León en julio y en
   noviembre. ¿Cuál es mayor y por qué?
