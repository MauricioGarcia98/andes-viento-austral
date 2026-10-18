# 09 · Etapa 5 · Bronze con Auto Loader

## 🎯 Objetivo

Llevar cada archivo de `landing` a una tabla Delta de **bronze**, de forma **incremental** (cada corrida lee sólo
los archivos nuevos), **sin perder nada** (lo que no encaja va a una columna de rescate) y **sin limpiar nada**
(bronze es "lo que llegó, tal cual llegó"). Tiene que aguantar solo que el SCADA agregue columnas.

**Archivos:** `src/andes_viento/ingestion/__init__.py`, `ingestion/bronze.py`. (Esta etapa no tiene un test propio:
la cubre el test de punta a punta del capítulo 14.)

## 📚 Conceptos

- **Structured Streaming:** Spark lee una carpeta como una tabla que crece. Con un **checkpoint** (una carpeta donde
  anota qué archivos ya procesó) cada corrida sigue donde quedó la anterior.
- **`trigger(availableNow=True)`:** procesar todo lo disponible ahora y terminar. Es "streaming" usado como un batch
  incremental: perfecto para un job diario.
- **Auto Loader (`cloudFiles`):** la versión de Databricks del streaming de archivos. Descubre archivos nuevos de forma
  eficiente, **infiere el esquema**, lo guarda (`schemaLocation`) y lo **evoluciona** cuando aparecen columnas.
- **`_rescued_data`:** una columna donde Auto Loader guarda, como JSON, lo que no pudo encajar en el esquema (un tipo
  inesperado, una columna mal escrita). Así no se pierde nada.
- **Schema hints:** pistas de tipo para columnas que la inferencia adivinaría mal.
- **`_metadata`:** columna oculta con el archivo de origen de cada fila. Se usa para el linaje.

## 🧱 Paso a paso

### 1. Los contratos de las fuentes

```python
CSV_CONTRACTS = {
    "inverter_5min": ["plant", "inverter", "timestamp", "poa_irradiance_wm2", ...],
    "cmms_assets": [...], "cmms_crews": [...], "cammesa_spot_prices": ["FECHA", "HORA", "NODO", "PRECIO_ARS_MWH", "TIPO"],
    "ppa_contracts": [...], "fx_rates": ["FECHA", "MONEDA", "TIPO", "VALOR"], "generation_budget": [...],
}
CSV_LATE_COLUMNS = {"inverter_5min": ["soiling_sensor_pct"]}
SOURCE_FORMATS = {"scada_turbine": "json", "inverter_5min": "csv", ...}
CSV_SEPARATOR = {"cammesa_spot_prices": ";", "fx_rates": ";"}
```
**Por qué todo como `STRING` en los CSV:** en un CSV todo es texto. Si bronze intentara convertir `"45.231,50"` a
número, fallaría o, peor, lo convertiría mal. Bronze guarda el texto y **silver** decide cómo interpretarlo, con
reglas y tests. El contrato fija **los nombres y el orden** de las columnas.

**Los *hints* de JSON:**
```python
JSON_SCHEMA_HINTS = {
    "cmms_work_orders": {
        "parts": "ARRAY<STRUCT<part_code: STRING, description: STRING, qty: BIGINT, unit_cost_usd: DOUBLE>>",
        "water_m3": "DOUBLE", "water_cost_usd": "DOUBLE", "crane_cost_usd": "DOUBLE", ...},
    "scada_turbine": {"setpoint_kw": "DOUBLE", "ts_epoch_ms": "BIGINT"},
    "weather": {"snow_cm": "DOUBLE", "dust_aod": "DOUBLE", "precip_prob_pct": "BIGINT"},
}
```
El JSON tiene tipos, pero la inferencia mira **los primeros archivos**. Si en los primeros días ninguna orden tuvo
repuestos, `parts` se infiere como `ARRAY<STRING>` y después las órdenes con repuestos no se pueden leer (L3 de la
bitácora). Si `setpoint_kw` sólo tuvo valores enteros, se infiere `BIGINT`. El *hint* fija el tipo correcto desde el
principio.

### 2. Leer la carpeta como stream

```python
def read_landing_stream(spark, cfg, name):
    fmt = SOURCE_FORMATS[name]
    path = cfg.landing_path(name)
    if is_databricks():
        reader = (spark.readStream.format("cloudFiles")
                  .option("cloudFiles.format", fmt)
                  .option("cloudFiles.schemaLocation", cfg.schema_location(name))
                  .option("cloudFiles.inferColumnTypes", "true")
                  .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
                  .option("cloudFiles.partitionColumns", "ingest_date")
                  .option("cloudFiles.maxFilesPerTrigger", 500)
                  .option("rescuedDataColumn", "_rescued_data"))
        if fmt == "csv":
            reader = (reader.option("cloudFiles.inferColumnTypes", "false")
                      .option("cloudFiles.schemaHints", csv_schema_hints(name)))
        elif json_schema_hints(name):
            reader = reader.option("cloudFiles.schemaHints", json_schema_hints(name))
    else:
        reader = spark.readStream.format(fmt).option("maxFilesPerTrigger", 500)
        ...
```
| opción | qué hace |
|---|---|
| `schemaLocation` | dónde Auto Loader guarda el esquema inferido y su historia |
| `inferColumnTypes` | inferir tipos (en JSON); en CSV se apaga: todo texto |
| `schemaEvolutionMode = addNewColumns` | si aparece una columna nueva, agregarla al esquema |
| `partitionColumns = ingest_date` | leer `ingest_date` del nombre de la carpeta (`ingest_date=2025-07-15`) |
| `maxFilesPerTrigger = 500` | procesar en lotes de hasta 500 archivos: memoria estable aunque haya meses acumulados |
| `rescuedDataColumn` | la columna de rescate |

**En local** no hay Auto Loader: se usa el *file source* de Spark OSS, que tiene la misma semántica (checkpoint +
`availableNow`) pero necesita el esquema de antemano (`csv_schema` para CSV y `_json_schema_local` para JSON, que lo
infiere de lo que hay y le aplica los mismos *hints*). Por eso el código tiene dos ramas: así se puede probar todo en
tu computadora.

### 3. Linaje

```python
def add_lineage(df):
    return (df.withColumn("_source_file", F.col("_metadata.file_path"))
              .withColumn("_file_modification_time", F.col("_metadata.file_modification_time"))
              .withColumn("_ingested_at", F.current_timestamp()))
```
Cada fila de bronze sabe **de qué archivo vino** y cuándo se cargó. Cuando un número no cierra en gold, se puede
rastrear hasta el archivo exacto que lo trajo.

### 4. Escribir y reiniciar ante columnas nuevas

```python
_SCHEMA_EVOLUTION_RESTARTS = 3

def ingest_source(spark, cfg, name) -> int:
    target = cfg.table("bronze", name)
    before = spark.table(target).count() if spark.catalog.tableExists(target) else 0
    for attempt in range(_SCHEMA_EVOLUTION_RESTARTS + 1):
        stream = read_landing_stream(...)   # (en local, JSON con esquema inferido)
        query = (add_lineage(stream).writeStream.format("delta")
                 .option("checkpointLocation", cfg.checkpoint_path(f"bronze_{name}"))
                 .option("mergeSchema", "true")
                 .trigger(availableNow=True)
                 .toTable(target))
        try:
            query.awaitTermination()
            break
        except Exception as exc:
            if "UNKNOWN_FIELD_EXCEPTION" not in str(exc) or attempt == _SCHEMA_EVOLUTION_RESTARTS:
                raise
            print(f"{name}: columnas nuevas detectadas, reiniciando el stream ({attempt + 1})")
    return spark.table(target).count() - before
```
**Lo que pasa cuando aparece una columna** (marzo 2025, firmware HT-OS 5.0): Auto Loader la detecta, **guarda el
esquema ampliado** y **detiene el stream** con `UNKNOWN_FIELD_EXCEPTION`. Es el comportamiento documentado: el
stream no puede cambiar de esquema en el aire. Al reiniciarlo, arranca con el esquema nuevo. Por eso el código lo
reinicia hasta 3 veces (una por cada tanda de columnas nuevas). `mergeSchema` deja que la tabla Delta agregue la
columna.

**Por qué en el código y no con los reintentos del job:** el job tiene `max_retries: 1` en esta tarea, pero eso es
para fallas de **infraestructura** (una máquina que se cae). Si el reinicio por columnas nuevas dependiera de los
reintentos del job, con tres cambios de esquema se agotarían y el job fallaría. Es el error de NovaMart que ya se
traía aprendido.

`ingest_all` recorre las 11 fuentes; si una carpeta todavía no existe (una fuente que no mandó nada), devuelve 0 en
vez de fallar.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| bronze sin limpiar | limpiar al ingerir | si la limpieza tiene un error, perdiste el dato original; con bronze crudo, se reprocesa |
| CSV como texto + *schema hints* | `.schema(...)` con tipos | con `addNewColumns`, Auto Loader **no admite** `.schema()` en CSV: falla con `CF_ADD_NEW_NOT_SUPPORTED` (lección de NovaMart) |
| `availableNow` | streaming continuo | no hace falta latencia de segundos; un batch incremental es más barato y simple |
| reinicio en código | reintentos del job | los reintentos son para infraestructura y se agotan |
| `_rescued_data` | descartar lo que no encaja | se perdería información sin que nadie se entere |

## ✅ Probalo

Con los archivos que generaste en el capítulo 08:
```bash
python - <<'EOF'
from andes_viento.config import local_config
from andes_viento.setup import create_namespace
from andes_viento.utils.spark import build_local_spark
from andes_viento.ingestion.bronze import ingest_all
spark = build_local_spark(warehouse_dir="/tmp/andes_wh")
cfg = local_config("/tmp/andes_landing", scale_factor=0.02)
create_namespace(spark, cfg)
print(ingest_all(spark, cfg))            # filas nuevas por fuente
print(ingest_all(spark, cfg))            # segunda vez: todo en 0 (incremental)
spark.sql("SELECT site, turbine, ts, ts_epoch_ms, _source_file FROM spark_catalog.andes_bronze.scada_turbine LIMIT 5").show(truncate=60)
EOF
```
La primera corrida da miles de filas por fuente; **la segunda, todo en 0**: el checkpoint recuerda qué leyó.

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `CF_ADD_NEW_NOT_SUPPORTED` | `.schema()` + `addNewColumns` en CSV | el contrato va como `cloudFiles.schemaHints` |
| el job falla con `UNKNOWN_FIELD_EXCEPTION` | no se reinicia el stream en código | el bucle de `ingest_source` |
| regeneraste landing y bronze no ve los cambios | Auto Loader **ignora archivos sobrescritos** en la misma ruta | para empezar de cero, borrá el checkpoint y el esquema (`_checkpoints`, `_schemas`); en el job, el parámetro `full_refresh` lo hace (R3) |
| `INVALID_EXTRACT_BASE_FIELD_TYPE` al leer `parts` | se infirió `ARRAY<STRING>` | el *hint* de `parts` |
| la segunda corrida duplica filas | el checkpoint no es el mismo (cambió la ruta) | `cfg.checkpoint_path(f"bronze_{name}")` fijo por fuente |
| `PATH_NOT_FOUND` | la fuente no tiene archivos todavía | `ingest_all` lo tolera; si es otra fuente, revisá `landing_path` |

## 📍 Punto de control

```bash
git commit -am "etapa-05: bronze con Auto Loader" && git diff etapa-05 HEAD --stat
```

## 🏋️ Ejercicio

1. En local, generá landing del 25-02-2025 al 05-03-2025 (cruza el *drift* del SCADA del 01-03) e ingerí. ¿Aparecen
   `ice_detector` y las otras dos columnas en `bronze.scada_turbine`? ¿Qué valor tienen antes del 1 de marzo?
2. Agregá a mano un archivo JSON con una línea rota (`{"site": "LEO", "turbine": `) en una carpeta de landing y volvé
   a ingerir. Buscá la fila en `_rescued_data`.
3. ¿Qué pasaría si `maxFilesPerTrigger` fuera 1 con 1.300 días de archivos? Probalo con una fuente chica y medí.
