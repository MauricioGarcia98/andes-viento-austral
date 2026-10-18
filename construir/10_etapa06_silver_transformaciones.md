# 10 · Etapa 6 · Silver I: limpiar

## 🎯 Objetivo

Escribir las **transformaciones** que convierten bronze (texto crudo, formatos mezclados, relojes corridos, unidades
equivocadas) en datos **confiables**: tipos correctos, todo en UTC, kW en todos lados, sensores clavados anulados,
valores imposibles marcados. Y las **reglas de calidad** de cada tabla silver. Cada transformación es una función pura
`DataFrame → DataFrame` con su test.

**Archivos:** `src/andes_viento/silver/__init__.py`, `silver/transforms.py`, `silver/rules.py`, `tests/test_transforms.py`.

## 📚 Conceptos

- **La convención de fechas del proyecto** (vale para todo el resto):

| columna | tipo | qué es |
|---|---|---|
| `*_ts`, `ts_utc` | TIMESTAMP | el **instante real**, en UTC |
| `*_local` | TIMESTAMP | la hora de pared argentina (UTC−3), sólo para mostrar |
| `reading_date`, `*_date` | DATE | el **día operativo local** del parque |

  Guardar instantes en UTC evita ambigüedades (en otros países, el cambio de horario hace que una hora local exista
  dos veces). El día local es lo que entiende la gente ("¿cuánto generé el martes?").
- **`try_*`:** `try_to_timestamp`, `try_cast` devuelven NULL si el texto no se puede convertir, en vez de cortar el
  job. Spark 4 viene con **modo ANSI** activado: un `cast` que falla es un error, no un NULL silencioso.
- **Funciones de ventana:** calculan algo mirando las filas vecinas (`lag`, `row_number`) dentro de un grupo
  (`partitionBy`) en un orden (`orderBy`), sin agrupar.
- **Función pura:** su salida depende sólo de su entrada. Se testea con un DataFrame chico armado a mano.

## 🧱 Paso a paso

### 1. Utilidades de fechas y números

```python
TZ = "America/Argentina/Buenos_Aires"
LOCAL_FORMATS = ("yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd'T'HH:mm:ss", "dd/MM/yyyy HH:mm:ss", "dd/MM/yyyy HH:mm",
                 "yyyy-MM-dd HH:mm", "dd/MM/yyyy", "yyyy-MM-dd")

def try_ts(col, *formats):
    c = F.col(col) if isinstance(col, str) else col
    return F.coalesce(*[F.try_to_timestamp(c, F.lit(f)) for f in formats])

def try_date(col, fmt):
    return F.to_date(F.try_to_timestamp(col, F.lit(fmt)))

def local_to_utc(col, formats=LOCAL_FORMATS):
    return F.to_utc_timestamp(try_ts(col, *formats), TZ)

def ar_number(col):
    c = F.col(col) if isinstance(col, str) else col
    return (F.regexp_replace(F.regexp_replace(c, r"\.", ""), ",", ".")).try_cast("double")
```
- `try_ts` prueba **varios formatos** y se queda con el primero que funciona (`coalesce`). Así una columna con fechas
  `dd/MM/yyyy` (CMMS viejo) e ISO (CMMS nuevo) se lee entera.
- `try_date` existe porque `F.try_to_date` **no existe** en la API de Python de PySpark 4 (L2 de la bitácora).
- `.try_cast` es un **método de la columna**, no una función de `F` (L2).
- `ar_number`: primero se sacan los puntos de miles, después la coma decimal pasa a punto: `"45.231,50"` → `45231.5`.
  En ese orden: al revés quedaría `45.231.50`.

### 2. SCADA: tres formatos de fecha

```python
def parse_scada_time(df):
    has_epoch = "ts_epoch_ms" in df.columns
    epoch = F.timestamp_millis(F.col("ts_epoch_ms").cast("long")) if has_epoch else F.lit(None).cast("timestamp")
    iso = F.try_to_timestamp(F.col("ts"), F.lit(ISO_OFFSET))                               # AWS: con offset
    dmy = F.to_utc_timestamp(F.try_to_timestamp(F.col("ts"), F.lit("dd/MM/yyyy HH:mm:ss")), TZ)  # PEI: hora local
    return (df.withColumn("device_ts", F.coalesce(epoch, iso, dmy))
              .withColumn("ts_format", F.when(epoch.isNotNull(), "epoch_ms").when(iso.isNotNull(), "iso_offset")
                          .when(dmy.isNotNull(), "local_dmy"))
              .withColumn("received_ts", F.try_to_timestamp(F.col("received_at"), F.lit(ISO_Z))))
```
`device_ts` es "lo que cree la turbina". `ts_format` queda guardado para auditar. `received_ts` es la hora en que el
concentrador del parque recibió el mensaje, sellada con **GPS** (confiable).

### 3. SCADA: relojes corridos y husos cambiados con un solo método

```python
def estimate_clock_offset(df):
    delta = F.unix_timestamp("received_ts") - F.unix_timestamp("device_ts")
    stats = (df.withColumn("_delta", delta)
             .withColumn("_recv_date", F.to_date("received_ts"))
             .groupBy("turbine", "_recv_date")
             .agg(F.percentile_approx("_delta", 0.05, 1000).alias("_p05"))
             .withColumn("clock_offset_s", F.when(F.abs(F.col("_p05")) >= 120,
                         (F.round(F.col("_p05") / 60) * 60).cast("long")).otherwise(F.lit(0))))
    return (df ... .join(F.broadcast(stats.drop("_p05")), ["turbine", "_recv_date"], "left")
            .withColumn("tz_corrected", F.abs(F.col("clock_offset_s")) >= 3_000)
            .withColumn("clock_corrected", (F.col("clock_offset_s") != 0) & ~F.col("tz_corrected"))
            .withColumn("ts_utc", F.timestamp_seconds(F.round((device + offset) / 600) * 600)))
```
**La idea** ([ADR-004](../docs/adr/ADR-004-relojes-por-percentil.md)): la demora normal entre que la turbina mide y
el concentrador recibe es de segundos. Por turbina y día, el **percentil 5** de `recepción − hora del equipo` es "la
demora mínima". Si da +7 minutos, el reloj atrasa 7 minutos. Si da −3 horas, el equipo cambió de huso (Pampa del
Castillo desde abr-2024). Se corrige sumando ese desfase y redondeando al bloque de 10 minutos.

**Por qué el percentil 5 y no el promedio ni el mínimo:** el promedio lo arruinan los reenvíos satelitales (que llegan
horas tarde). El mínimo lo arruina un solo valor raro. El percentil 5 es robusto a las dos cosas.

**Por qué ±120 s de umbral:** debajo de 2 minutos es ruido de red; no se corrige.

### 4. SCADA: unidades, imposibles y sensores clavados

**`fix_power_units`:** si el equipo declara la unidad (`power_unit`), se usa. Si no (el firmware viejo de PEI no la
manda), se **infiere**: con viento ≥ 4 m/s, un valor menor que 1,6 veces la potencia nominal **en MW** sólo puede estar
en MW. `unit_converted` queda marcado.

**`null_impossible`:** viento fuera de 0-60 m/s, temperatura de multiplicadora > 200 °C o potencia > 1,3 veces la
nominal → NULL, y el nombre del campo se guarda en `bad_values` para que la regla de calidad lo cuente. No se
descarta la fila: el resto de los sensores sirve.

**`flag_stuck_sensors`:**
```python
def flag_stuck_sensors(df, cols=STUCK_CHECK, run=STUCK_RUN):    # 6 lecturas iguales seguidas = 1 hora
    w = Window.partitionBy("asset_id").orderBy("ts_utc")
    for c in cols:
        same = [F.lag(c, k).over(w) == F.col(c) for k in range(1, run)]   # igual a las 5 anteriores
        ...
```
Un sensor real siempre varía en el último decimal. Seis lecturas **exactamente** iguales (una hora) es un sensor
clavado: se anula desde ahí. Las primeras repeticiones no se anulan (el test lo verifica).

### 5. `clean_scada`: todo junto

Lee los sensores del struct (`_sensor` devuelve NULL si el campo todavía no existe: los sensores del *drift* no están
antes de 2025), une con `asset_tags` para traducir el nombre de la turbina a su `asset_id` estable (los nombres
viejos y nuevos de Cerro Arenales apuntan al mismo id), corrige el reloj, las unidades y los imposibles, y calcula
`reading_date`, `latency_s` y `late_arrival` (más de una hora de demora).

`SCADA_COLUMNS` fija las columnas y el orden de `silver.scada_10min`. La deduplicación (`dedupe_first_arrival`: ante
copias, la **primera** que llegó) se aplica en la carga (capítulo 11).

### 6. Las otras fuentes

| función | lo interesante |
|---|---|
| `clean_inverter` | dos formatos de fecha local; el **bug de MW** se detecta por magnitud (con irradiancia > 150 W/m², una potencia AC < 5 "kW" es imposible: son MW); irradiancia > 1.500 = centinela de error |
| `clean_assets` | tags en mayúsculas, fechas en dos formatos, `op = 'D'` → `is_deleted` |
| `clean_work_orders` | 6 fechas de hitos, todas con `local_to_utc`; columnas opcionales (`opt`) porque los primeros archivos pueden no traerlas; se agrega el `asset_id` |
| `explode_parts` | `posexplode` del array de repuestos: una fila por repuesto, con número de línea y costo |
| `clean_dispatch` | fechas ISO con offset; versiones de cada instrucción |
| `clean_spot_prices` | **la hora 24:** `FECHA + (HORA − 1) horas`: la hora 1 empieza a las 00:00 y la 24 a las 23:00; `version_rank` 2 para `DEFINITIVO` |
| `clean_fx`, `clean_budget`, `clean_contracts` | números argentinos, columnas en castellano a inglés, CUIT sólo con dígitos y guiones, emails en minúsculas |
| `clean_weather` | instantes UTC y el día local del dato |

### 7. `rules.py`: las reglas de cada tabla

```python
SCADA = [
    Rule("turbina_conocida", "asset_id IS NOT NULL"),                       # quarantine (default)
    Rule("fecha_parseable", "ts_utc IS NOT NULL"),
    Rule("no_viene_del_futuro", "ts_utc <= received_ts + INTERVAL 1 HOUR"),
    Rule("potencia_informada", "power_kw IS NOT NULL", "warn"),
    Rule("valores_fisicamente_posibles", "size(bad_values) = 0", "warn"),
    Rule("sensores_sin_clavarse", "size(stuck_sensors) = 0", "warn"),
    Rule("reloj_sincronizado", "NOT clock_corrected", "warn"),
    Rule("huso_horario_correcto", "NOT tz_corrected", "warn"),
    Rule("llego_a_tiempo", "NOT late_arrival", "warn"),
]
...
ASSETS = [Rule("id_presente", "asset_id IS NOT NULL", "fail"), ...]
FX = [Rule("fecha_valida", "fx_date IS NOT NULL"), Rule("dolar_positivo", "ars_per_usd > 0", "fail")]
```
**Cómo elegir la acción:**

| acción | cuándo | ejemplo |
|---|---|---|
| `fail` | el dato **nunca** debería existir y seguir sería peor que parar | un activo sin id, un dólar negativo |
| `quarantine` | la fila no sirve, pero el resto sí | una lectura sin turbina conocida |
| `warn` | la fila sirve (ya se corrigió o le falta algo menor), pero hay que contarlo | un reloj corregido, un dato tardío |

Las `warn` son las que después muestran **cuánta suciedad se encontró** (capítulo 18 de docs: 526.200 husos
corregidos, 208.900 conversiones de MW).

### 8. Los tests

`tests/test_transforms.py` tiene **un test por problema real**, con un DataFrame chico armado a mano:
`"45.231,50"` y la hora 24; los tres formatos de fecha dando el mismo instante UTC; el cambio de huso; el reloj
corrido 7 minutos y el reenvío de 6 horas; el sensor clavado; la deduplicación; el bug de MW del inversor.

Ejemplo, el del reloj:
```python
def test_clock_skew_and_late_resend(spark):
    ...   # 6 lecturas de una turbina con el reloj 7 minutos atrasado y un reenvío de 6 h antes
    assert out[-1].clock_corrected and out[-1].clock_offset_s == 420
    assert out[-1].ts_utc == datetime(2025, 7, 15, 14, 50)
    assert out[0].late_arrival
```

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| todo en UTC + día local aparte | guardar en hora local | ambigüedad: si la fuente cambia de huso (o hay horario de verano) los instantes se pisan |
| percentil 5 de la demora | confiar en el reloj del equipo | ~6 % de las turbinas por año tiene el reloj corrido: la potencia quedaría en el bloque equivocado |
| inferir MW por magnitud | confiar en la etiqueta de la columna | la columna dice "kW" y el valor está en MW (el bug de Fiambalá) |
| anular el valor imposible y no la fila | descartar la fila | se perderían los otros 9 sensores, que están bien |
| funciones puras | todo en un `clean()` gigante | no se podría testear cada problema por separado |

## ✅ Probalo

```bash
pytest tests/test_transforms.py -v      # 7 passed
pytest -m "not integration"             # 24 passed
```

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `[CAST_INVALID_INPUT] The value '45.231,50' of the type "STRING" cannot be cast to "DOUBLE"` | modo ANSI + `cast` | `try_cast` (y `ar_number` antes) |
| `module 'pyspark.sql.functions' has no attribute 'try_cast'` | es un método de columna | `F.col(x).try_cast("double")` |
| las horas salen corridas 3 h | la sesión no está en UTC o falta `to_utc_timestamp` | `spark.sql.session.timeZone = UTC` y revisá `local_to_utc` |
| la hora 24 da el día siguiente a las 00:00 | sumaste `HORA` en vez de `HORA − 1` | `make_interval(hours=hour - 1)` |
| `[FIELD_NOT_FOUND] sensors.ice_detector` | leés un campo del *drift* antes de que exista | `_sensor()` verifica que el campo esté en el esquema |
| el test del sensor clavado anula de más | la condición no exige las `run − 1` lecturas anteriores | revisá el `lag(c, k)` para `k = 1..5` |

## 📍 Punto de control

```bash
git commit -am "etapa-06: silver, transformaciones y reglas" && git diff etapa-06 HEAD --stat
```
(En `etapa-06`, `test_transforms.py` todavía no tiene los dos tests del separador de SQL: llegan en la etapa 9.)

## 🏋️ Ejercicio

1. Escribí `clean_met_mast` para la fuente del ejercicio del capítulo 08 y un test con 3 filas.
2. Agregá un formato de fecha nuevo (`yyyyMMddHHmm`) a `LOCAL_FORMATS` y un test que lo use. ¿Qué riesgo tiene
   agregar formatos sin cuidado? (pista: `dd/MM` vs. `MM/dd`).
3. Cambiá el percentil 5 por el promedio en `estimate_clock_offset` y corré `test_clock_skew_and_late_resend`. ¿Por
   qué falla?
