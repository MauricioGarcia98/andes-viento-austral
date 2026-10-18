# 08 · Etapa 4 · Las 11 fuentes sucias

## 🎯 Objetivo

Convertir la física y los eventos en **los archivos que mandaría cada sistema real**: el SCADA de cada fabricante,
la plataforma de los inversores, el proveedor de clima, el sistema de mantenimiento (CMMS), CAMMESA, Comercial y
Finanzas. Cada uno con **su formato y sus defectos**, porque eso es lo que el pipeline tiene que aprender a resolver.
Al final, `write_source` escribe todo en la zona de aterrizaje (`landing`), una carpeta por día de llegada.

**Archivos:** `src/andes_viento/datagen/generators.py`, `writer.py`, `tests/test_datagen.py`.

## 📚 Conceptos

- **Día del dato vs. día de llegada (`ingest_date`):** una lectura de las 10:00 del lunes puede llegar el martes
  (satélite caído, reenvío). Cada fila sabe cuándo **pasó** y cuándo **llegó**. Los datos tardíos viven en esa
  diferencia y son la causa de muchos errores en los pipelines reales.
- **Broadcast join:** cuando una tabla es chica, Spark le manda una copia entera a cada ejecutor y evita mover la
  tabla grande por la red. Las tablas guía (eventos, clima diario) se unen así a millones de lecturas.
- **`array<struct>` + `filter`:** en vez de unir cada lectura con "el evento activo en ese instante" (un *join por
  rango*, muy caro), se le pega a cada turbina **la lista** de sus eventos y se busca adentro con
  `filter(lista, e -> instante entre e.start y e.end)`.
- **CDC (Change Data Capture):** la fuente no manda "la tabla", manda **los cambios**: `I` (alta), `U` (cambio) y `D`
  (baja), cada uno con su fecha. Silver los aplica en orden (capítulo 11).

## 🧱 Paso a paso

### 1. Las utilidades del principio de `generators.py`

| función | qué hace | por qué |
|---|---|---|
| `_set_utc` | fija la zona horaria de la sesión en UTC | que el texto de las fechas no dependa del workspace |
| `_date_of(epoch)` | día UTC de un *epoch* (`date_from_unix_date`) | rápido y sin zona horaria |
| `_fmt(epoch, patrón)` | *epoch* a texto con un patrón | cada fabricante usa uno |
| `_ar_number` | `1234567.5` → `"1.234.567,50"` | así manda los números CAMMESA (punto de miles, coma decimal) |
| `_array_of_structs` | agrupa filas chicas por clave en `array<struct>` | ver Conceptos |
| `_first_active(items, epoch)` | el primer elemento de la lista activo en ese instante | con `try_element_at`: si no hay ninguno, NULL en vez de error |
| `_maybe_null` | vuelve NULL un valor con probabilidad `p` | sensores que no reportan |
| `_range_partitions` | cuántas particiones usar (~2.000 turbina-días cada una) | ni miles de tareas chicas ni pocas gigantes |
| `HORIZON = 45 días` | el generador "mira" 45 días al futuro | una falla del 20 de agosto ya calienta la multiplicadora en julio |

### 2. El SCADA de turbinas (la fuente grande)

`generate_scada_turbine` es el corazón. En orden:

**a) La grilla de instantes × turbinas.**
```python
    slots = spark.range(t0 // 600, t1 // 600, 1, n_parts).select((F.col("id") * 600).alias("epoch"))
    df = (slots.crossJoin(F.broadcast(tur))
          .where(F.col("epoch") >= F.col("comm_epoch"))     # nada antes de la puesta en marcha
          ...
          .join(F.broadcast(wx), ["park", "date_local"], "left")                      # clima del día
          .join(F.broadcast(events), F.col("asset_id") == F.col("ev_asset"), "left")  # paradas de la turbina
          .join(F.broadcast(curt), ...)   # órdenes de CAMMESA del parque
          .join(F.broadcast(comm), ...)   # cortes de comunicación del parque
          .join(F.broadcast(skew), ...)   # relojes corridos de la turbina
          .join(F.broadcast(stuck), ...)) # sensores clavados de la turbina
```
`spark.range` genera un instante cada 600 s (10 minutos) **en paralelo**; el `crossJoin` con las turbinas da una fila
por turbina e instante. Todas las uniones son *broadcast* con tablas chicas.

**b) La física y el estado de cada instante.**
```python
        .withColumn("wind_true", ph.wind_by_park_col(...))
        .withColumn("potential_kw", ph.power_kw_col(F.col("wind_true"), F.col("rated_kw"), F.col("rated_ms")))
        .withColumn("down", _first_active("ev", e))                   # ¿está en una parada?
        .withColumn("degr", ...)                                       # ¿se está degradando antes de una falla?
        .withColumn("progress", ...)                                   # 0 → 1 a medida que se acerca la falla
        .withColumn("setpoint_kw", _first_active("cu", e)["setpoint_kw"])   # ¿hay tope de CAMMESA?
        .withColumn("icing", ...)                                      # ¿hay hielo a esta hora?
    status = (F.when(kind.isin("MAJOR_FAILURE", "MINOR_FAULT"), 1)    # falla
              .when(kind == "PREVENTIVE", 2)                           # mantenimiento
              .when(F.col("icing"), 3)                                 # hielo
              .when(F.col("wind_true") >= ph.CUT_OUT_MS, 6)            # demasiado viento
              .when(F.col("wind_true") < ph.CUT_IN_MS, 5)              # poco viento
              .when(F.col("setpoint_kw").isNotNull() & (F.col("potential_kw") > F.col("setpoint_kw")), 4)  # recortada
              .otherwise(0))                                           # generando normal
```
El **orden** de los `when` es la prioridad: si está rota, no importa que haya hielo. Este código de estado es la base
de la descomposición de pérdidas de gold (capítulo 12): cada 10 minutos perdidos tienen **una** causa.

**c) Lo que miden los sensores.** La potencia es la potencial (con el tope de CAMMESA si lo hay) más un 3 % de ruido;
parada, la turbina **consume** un poco (potencia negativa, como en la realidad). Las temperaturas de la multiplicadora
y los rodamientos dependen de la temperatura ambiente y de la carga, y **suben con `progress²` antes de una falla**:
ésa es la firma que encuentra el modelo predictivo (capítulo 13). La vibración sube con `progress³` (aparece más
tarde, más cerca de la falla).

**d) Lo que se rompe en el camino.**
```python
    df = (df.where(F.col("outage").isNull() | F.col("outage.buffered"))    # corte sin buffer: el dato se PIERDE
          .withColumn("recv_epoch", ...)                                   # cuándo llega (corte con buffer: al reconectar)
          .withColumn("copies", F.when(u("dup") < 0.004, F.array(0, 1)).otherwise(F.array(0)))
          .withColumn("copy", F.explode("copies"))                         # 0,4 %: llega duplicado, hasta 30 h después
          .withColumn("ingest_date", _date_of(F.col("recv_epoch") - ART_S))
          .where(F.col("ingest_date").between(start, end))                 # sólo lo que LLEGA en el rango pedido
          .withColumn("device_epoch", e + F.col("offset_s")))              # la hora que dice el reloj de la turbina
```
- `gen_from = start - 2 días`: para generar lo que **llega** el día D hay que simular también los días anteriores
  (los reenvíos). Por eso el filtro es por `ingest_date`.
- `device_epoch` es la hora del reloj de la turbina, que puede estar corrida (`offset_s`). Silver la corrige con la
  hora de recepción (capítulo 10).

**e) `_scada_payload`: el JSON de cada fabricante.**
```python
    ts = (F.when(mfr == "AWS", F.concat(_fmt(dev - ART_S, "yyyy-MM-dd'T'HH:mm:ss"), F.lit("-03:00")))
          .when(mfr == "PEI", _fmt(F.when(pei_utc, dev).otherwise(dev - ART_S), "dd/MM/yyyy HH:mm:ss")))
    ... F.when(mfr == "HTW", dev * 1000).alias("ts_epoch_ms")            # HTW: milisegundos en otro campo
    active_power = F.when(mfr == "PEI", F.round(power_kw / 1000, 4)).otherwise(F.round(power_kw, 1))   # PEI en MW
    tag = F.when(new_tag existe & fecha >= renombre & no es una de las 2 turbinas con el PLC sin actualizar, new_tag)
           .otherwise(tag)
    sensors = F.struct(sensor("wind_ms", wind, 2), ..., 
                       F.when(drift, ...).alias("ice_detector"),          # sólo HTW con HT-OS 5.0 (desde mar-2025)
                       F.when(drift, ...).alias("oil_particle_count"),
                       F.when(drift, ...).alias("tower_accel_mg"))
```
- Tres formatos de fecha según el fabricante; Pampa del Castillo, desde abr-2024, manda la hora en **UTC** con el
  mismo formato que antes (nadie avisó).
- Valores imposibles a propósito: viento 99,9 (código de error del anemómetro), temperatura 999, picos de 1,5 veces la
  potencia nominal.
- `F.when(drift, ...)` sin `otherwise` da NULL: antes de 2025 esas columnas son nulas y Spark, al escribir JSON,
  **omite** los campos nulos. Para el lector, los campos "aparecen" en marzo 2025: eso es el *schema drift*.
- `msg_id`: un hash de turbina + instante + copia. Dos copias del mismo mensaje tienen ids distintos (como en la
  realidad), así que deduplicar por `msg_id` no alcanza.

### 3. Inversores y clima

`generate_inverter_5min` sigue la misma receta (grilla × flota, broadcast de tablas guía): irradiancia con nubes y
cúmulos, temperatura de módulo, potencia DC con **la suciedad** del día y la pérdida por temperatura, potencia AC con
el tope del inversor. Sus defectos: dos formatos de fecha según el parque, el **bug de MW** en Fiambalá, una
irradiancia de 9999 ocasional, exportes que llegan 1-3 días tarde o se re-exportan, y la columna nueva
`soiling_sensor_pct` desde jun-2025.

`generate_weather` arma dos tipos de registro por parque y hora: lo **observado** (`actual`) y el **pronóstico**
emitido el día anterior al mediodía (`forecast`, con error). El caso de limpieza de paneles usa el pronóstico de
lluvia (si va a llover, no conviene limpiar).

### 4. Las fuentes chicas (en el driver)

Todas siguen el mismo patrón: recorrer una tabla guía en Python, armar filas y `spark.createDataFrame(filas, esquema)`.

| fuente | qué tiene | sus defectos a propósito |
|---|---|---|
| `cmms_assets` (CSV, CDC) | el registro de cada equipo: tag, números de serie, firmware | renombres, cambios de serie al reemplazar componentes, fechas `dd/MM/yyyy` antes de la migración del CMMS (mar-2024) e ISO después, reenvíos idénticos al día siguiente |
| `cmms_crews` (CSV) | las 6 cuadrillas | un cambio de líder en 2025 |
| `cmms_work_orders` (JSON, CDC) | cada orden con sus hitos: `I` abierta → `U` en curso → `U` cerrada con costos y repuestos | la mitad de los resets remotos **no se registra**; órdenes duplicadas por error que se crean y se borran (`D`); fechas en dos formatos |
| `cammesa_dispatch` (JSON) | las órdenes de bajar potencia, con versiones | órdenes corregidas (versión 2 `MODIFICADA`) y emitidas por error (`ANULADA`), duplicados |
| `cammesa_spot_prices` (CSV `;`) | precio horario por nodo | `HORA` 1..24 (la 24 es de 23 a 24), coma decimal, versión `PRELIMINAR` al día siguiente y `DEFINITIVO` el 10 del mes siguiente (a veces distinta) |
| `fx_rates` (CSV `;`) | dólar oficial diario | no hay cotización fines de semana ni feriados (silver tiene que completar el calendario) |
| `generation_budget` (CSV) | presupuesto P50 por parque y mes | columnas en castellano; un re-presupuesto `v2` en julio 2025 |
| `ppa_contracts` (CSV, CDC) | los contratos | indexación de precio cada enero, cambio de contacto, adenda de volumen, rescisión (`U` + `D`), duplicados |

**El "plegado" de la foto inicial** (en `cmms_assets` y `ppa_contracts`):
```python
        # la foto inicial del CMMS ya trae los cambios anteriores a su fecha: se "pliegan" en el registro I
        for when, delta, op in sorted(changes[1:], key=lambda c: c[0]):
            if when <= first:
                state = {**state, **delta}
```
Si la historia arranca después de un cambio (por ejemplo, el firmware nuevo), el primer registro `I` tiene que venir
**ya con** ese cambio. Faltaba en la primera versión y el test de integración lo encontró (L8 de la bitácora).

**El registro de fuentes:**
```python
SOURCES = {
    "scada_turbine": (generate_scada_turbine, "json", {"compression": "gzip"}),
    "inverter_5min": (generate_inverter_5min, "csv", {"header": "true"}),
    ...
    "cammesa_spot_prices": (generate_cammesa_spot_prices, "csv", {"header": "true", "sep": ";"}),
}
SCHEMA_DRIFT_CSV = {"inverter_5min": R.SCHEMA_DRIFT_INVERTER}
```
Un diccionario `nombre → (función, formato, opciones)`. El *writer* y el job recorren esto: agregar una fuente es
agregar una función y una línea.

### 5. `writer.py`: escribir en landing

```python
BIG_SOURCES = {"scada_turbine", "inverter_5min", "weather"}

def _write(df, path, fmt, options, mode, big):
    df = df.repartition("ingest_date") if big else df.coalesce(1)
    writer = (df.write.format(fmt)
              .mode("overwrite" if mode in ("full", "incremental") else "append")
              .partitionBy("ingest_date")
              .option("maxRecordsPerFile", 1_000_000))
    if mode == "incremental":
        writer = writer.option("partitionOverwriteMode", "dynamic")
    ...
```
- `partitionBy("ingest_date")` crea `landing/<fuente>/ingest_date=2025-07-15/part-...`: **una carpeta por día de
  llegada**, como una fuente real que deja archivos cada día.
- `repartition("ingest_date")` en las grandes: **un archivo por día** (y no 200 archivitos por día). Miles de archivos
  chicos son el enemigo número uno de Auto Loader. `coalesce(1)` en las chicas: un solo archivo.
- `partitionOverwriteMode = dynamic` en modo incremental: reemplaza **sólo** las carpetas de los días que se
  generaron. Regenerar el 01-10-2026 no borra el resto de la historia.

`write_source` agrega dos detalles: las fuentes chicas sin filas no escriben nada (un día sin cambios de cuadrillas
no genera un archivo vacío) y el **drift del CSV**: como un CSV no tiene esquema, la columna nueva sólo puede
"aparecer" si los archivos anteriores a la fecha se escriben **sin** esa columna. Por eso se escribe en dos tandas.

`generate_all` genera todas las fuentes para un rango, en modo `full` (historia completa) o `incremental` (un día).

### 6. El test

`tests/test_datagen.py`: el SCADA es **determinístico** (dos corridas, mismo resultado, con `exceptAll`); tiene la
suciedad esperada (los tres formatos de fecha, PEI en MW, duplicados, nulos); los sensores nuevos aparecen sólo con
HT-OS 5.0; el inversor tiene el bug de MW y la columna nueva; y las fuentes chicas tienen sus formatos (coma decimal,
hora 24, operaciones `I` y `U`).

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| `array<struct>` + `filter` | join por rango (`epoch BETWEEN start AND end`) | un join por rango sobre millones de filas es carísimo; el array por turbina es chico y viaja por broadcast |
| particionar landing por día de llegada | por día del dato | las fuentes reales dejan archivos cuando **llegan**; los datos tardíos tienen que estar en carpetas posteriores |
| un archivo por día | dejar que Spark escriba los que quiera | el problema de los archivos chicos: Auto Loader y cualquier lector se vuelven lentos |
| defectos con probabilidades bajas (0,4 %, 0,02 %) | muchos defectos | la suciedad realista es **rara**: lo difícil es encontrarla en millones de filas buenas |
| cada fuente con su formato | un formato común | el trabajo de integración de verdad es unificar formatos distintos |

## ✅ Probalo

```bash
pytest tests/test_datagen.py           # 5 passed (~1 min)
pytest -m "not integration"            # 17 passed
python - <<'EOF'
from datetime import date
from andes_viento.config import local_config
from andes_viento.utils.spark import build_local_spark
from andes_viento.datagen.writer import generate_all
spark = build_local_spark()
cfg = local_config("/tmp/andes_landing", scale_factor=0.02)
generate_all(spark, cfg, date(2025, 7, 1), date(2025, 7, 3))
EOF
ls /tmp/andes_landing/landing/                       # 7 carpetas (ver abajo por qué no 11)
ls /tmp/andes_landing/landing/scada_turbine/          # ingest_date=2025-07-01 ... 03
zcat /tmp/andes_landing/landing/scada_turbine/ingest_date=2025-07-02/*.json.gz | head -2
head -3 /tmp/andes_landing/landing/cammesa_spot_prices/ingest_date=2025-07-02/*.csv
```
Aparecen **7 de las 11 fuentes**: `cmms_assets`, `cmms_crews`, `ppa_contracts` y `cammesa_dispatch` sólo mandan un
archivo cuando hay un cambio (un alta, una adenda, una orden de CAMMESA), y en esos 3 días de julio no hubo. Si generás
desde `cfg.start_date` (el 01-01-2023) aparecen las 11. En el JSON del SCADA vas a ver que el mismo día de llegada
trae lecturas de días anteriores (reenvíos) y formatos de fecha distintos según el sitio; en el CSV de CAMMESA, `;` y
coma decimal (`74.772,10`).

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `[INVALID_EXTRACT_BASE_FIELD_TYPE] Can't extract a value from "p"` al leer órdenes | un array vacío `[]` se infirió como `ARRAY<STRING>` | las órdenes sin repuestos llevan `parts = None`, no `[]` (L3; en bronze se agrega un *schema hint*) |
| `AttributeError: module 'pyspark.sql.functions' has no attribute 'try_cast'` | en PySpark 4, `try_cast` es un método de columna | `col.try_cast("double")` (L2) |
| el SCADA no tiene datos el primer día | `gen_from` no retrocede o el filtro por `ingest_date` es por fecha del dato | `gen_from = start - 2 días` y filtrar por `ingest_date` |
| miles de archivos en landing | falta `repartition("ingest_date")` | ver `_write` |
| los datos cambian entre corridas | quedó un `F.rand()` o un `random` sin semilla | todo con `uniform(..., salt=...)` y `prng(...)` |
| OOM (sin memoria) en local | un `scale_factor` o un rango de fechas muy grandes | SF 0,02 y pocas semanas en local |

## 📍 Punto de control

```bash
git commit -am "etapa-04: las 11 fuentes sucias" && git diff etapa-04 HEAD --stat
```

## 🏋️ Ejercicio

1. Agregá una fuente nueva `scada_met_mast`: una torre meteorológica por parque eólico que mide viento cada 10 minutos
   (pista: copiá la grilla de `generate_weather` con `spark.range` cada 600 s). Registrala en `SOURCES` y verificá que
   `generate_all` crea su carpeta.
2. Agregá un defecto: el 0,1 % de los mensajes de AWS llega con el viento en km/h. ¿Cómo lo detectarías en silver?
3. Cambiá `maxRecordsPerFile` a 1.000 y mirá cuántos archivos genera un día. ¿Por qué eso sería un problema en producción?
