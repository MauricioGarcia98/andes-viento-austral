# 11 · Etapa 7 · Silver II: cargar, SCD2 y CDC

## 🎯 Objetivo

Llevar las transformaciones del capítulo 10 a **tablas silver que se actualizan de forma incremental**, cada entidad
con la estrategia que le corresponde: historia completa (SCD2) para los activos y los contratos, último estado para
las órdenes (CDC con bajas), "el definitivo pisa al preliminar" para los precios, e "insertar sólo lo nuevo" para la
telemetría. Todo **idempotente**: correr dos veces el mismo lote no cambia nada.

**Archivos:** `src/andes_viento/silver/scd2.py`, `silver/load.py`, `tests/test_scd2.py`.

## 📚 Conceptos

- **SCD tipo 1 vs. tipo 2** (*Slowly Changing Dimension*):

| | SCD1 | SCD2 |
|---|---|---|
| qué guarda | sólo el valor actual | **todas** las versiones, con desde/hasta |
| ejemplo | el teléfono de una cuadrilla | el número de serie de la multiplicadora de una turbina |
| para qué | "¿cómo es hoy?" | "¿cómo era **en ese momento**?" |

  En SCD2 cada versión tiene `valid_from`, `valid_to` (NULL si es la vigente) e `is_current`. Para saber qué
  multiplicadora tenía la turbina cuando falló hace falta SCD2.
- **`foreachBatch`:** en streaming, en vez de escribir directo a una tabla, se le pasa **cada lote** a una función tuya
  que puede hacer cualquier cosa: limpiar, validar, hacer un MERGE. Es la forma de tener streaming incremental con
  lógica compleja.
- **Hash de fila:** un `sha2` de los atributos concatenados. Si el hash no cambió, la fila no cambió: no hace falta
  comparar columna por columna.

## 🧱 Paso a paso

### 1. `scd2.py`: SCD2 a mano con MERGE (5 casos difíciles)

**`row_hash`**: `sha2` de los atributos que se siguen, con `coalesce(..., "<null>")` para que NULL no rompa la
concatenación (`concat_ws` saltea los NULL: `"a", NULL, "b"` y `"a", "b"` darían el mismo hash).

**`build_versions`, la cadena de versiones dentro del lote:**
```python
def build_versions(updates, keys, tracked, ts_col):
    w = Window.partitionBy(*keys).orderBy(F.col(ts_col))
    return (updates.withColumn(HASH_COL, row_hash([*tracked, "is_deleted"]))
            .dropDuplicates([*keys, ts_col, HASH_COL])                      # reenvíos idénticos
            .withColumn("_prev_hash", F.lag(HASH_COL).over(w))
            .where(F.col("_prev_hash").isNull() | (F.col("_prev_hash") != F.col(HASH_COL)))  # sólo cambios reales
            .drop("_prev_hash"))
```
En la carga histórica, un mismo activo trae **varios cambios en el mismo lote** (alta, renombre, cambio de firmware,
cambio de multiplicadora). Un MERGE ingenuo "por clave" se quedaría con uno solo. Acá se arma la cadena completa y se
descartan las filas que no cambian nada respecto de la anterior.

**`scd2_merge`, contra lo que ya está en la tabla:**
```python
    current = spark.table(target).where("is_current").select(*keys, F.col(HASH_COL).alias("_cur_hash"),
                                                            F.col("valid_from").alias("_cur_from"))
    candidates = (versions.join(current, keys, "left")
        .where(F.col("_cur_from").isNull() | (F.col(ts_col) > F.col("_cur_from")))        # (3) tardíos: se ignoran
        .withColumn("_rn", F.row_number().over(w))
        .where(~((F.col("_rn") == 1) & (F.col(HASH_COL) == F.coalesce(F.col("_cur_hash"), F.lit("")))))  # (2)
        .withColumn("valid_from", F.col(ts_col))
        .withColumn("valid_to", F.lead(ts_col).over(w))                                   # (1) la cadena
        .withColumn("is_current", F.col("valid_to").isNull()))
    to_close = candidates.where(F.col("_cur_hash").isNotNull()).groupBy(*keys).agg(F.min("valid_from").alias("_close_ts"))
    ...
    staged = to_close.unionByName(to_insert, allowMissingColumns=True)
    DeltaTable.forName(spark, target).alias("t").merge(staged.alias("s"), on)
        .whenMatchedUpdate(set={"valid_to": "s._close_ts", "is_current": "false"})       # cerrar la vigente
        .whenNotMatchedInsert(condition=f"s.`_mk_{keys[0]}` IS NULL", values=insert_values)  # insertar las nuevas
        .execute()
```
**El truco de las claves `_mk_`:** un solo MERGE tiene que hacer dos cosas con la misma clave: **cerrar** la versión
vigente e **insertar** las nuevas. Si las dos filas tuvieran la misma clave de cruce, la nueva también "matchearía" con
la vigente y no se insertaría. Por eso se arma un lote con dos tipos de fila: las de cierre traen la clave en
`_mk_asset_id` (matchean y cierran) y las de inserción traen `_mk_asset_id = NULL` (nunca matchean y se insertan).

| caso | cómo se resuelve |
|---|---|
| (1) varios cambios en el mismo lote | `lead()` arma la cadena: cada versión termina donde empieza la siguiente |
| (2) reenvío idéntico | si la primera versión del lote tiene el mismo hash que la vigente, se descarta |
| (3) cambio tardío (más viejo que la vigente) | se ignora (`ts > _cur_from`) |
| (4) baja | `is_deleted` es parte del hash: la baja es una versión más |
| (5) re-ejecutar el mismo lote | (2) + (3): no se duplican versiones |

### 2. `load.py`: el patrón de carga incremental

```python
def run_incremental(spark, cfg, bronze_name, checkpoint_name, process_batch):
    if not spark.catalog.tableExists(cfg.table("bronze", bronze_name)):
        print(f"bronze.{bronze_name} no existe todavía: nada que procesar")
        return
    query = (spark.readStream.option("maxFilesPerTrigger", 400).table(cfg.table("bronze", bronze_name))
             .writeStream.foreachBatch(process_batch)
             .option("checkpointLocation", cfg.checkpoint_path(f"silver_{checkpoint_name}"))
             .trigger(availableNow=True).start())
    query.awaitTermination()
```
Lee la tabla **bronze como stream** (sólo lo que se agregó desde la última vez, gracias al checkpoint) y le pasa cada
lote a `process_batch`. Cada entidad define su `batch(df, batch_id)`:

**Activos (SCD2 + tabla de alias):**
```python
    def batch(df, batch_id):
        s = df.sparkSession
        clean = enforce(s, cfg, T.clean_assets(df), rules.ASSETS, target, batch_id)
        scd2_merge(s, clean.drop("_ingested_at"), target, ["asset_id"], T.ASSET_TRACKED, ts_col="updated_at")
        hist = s.table(target)
        tags = (hist.groupBy("asset_tag", "asset_id").agg(...)
                .join(hist.where("is_current").select("asset_id", "asset_type", "park_code", "rated_kw", "dc_kwp"), "asset_id"))
        tags.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(tags_t)
```
`silver.asset_tags` tiene **todos los nombres que tuvo cada equipo** (`CRV-07` y `CRV-WTG007` apuntan a `WTG00031`).
Las dos turbinas de Cerro Arenales que siguieron mandando el nombre viejo después del renombre se resuelven solas. Por
eso la telemetría se carga **después** de los activos: es el segundo *for each* del job (capítulo 15).

`s = df.sparkSession`: dentro de `foreachBatch` se usa la sesión del lote, no la de afuera (en Databricks serverless
pueden ser distintas).

**Las otras estrategias:**

| entidad | estrategia | detalle |
|---|---|---|
| `crews` | último estado + bajas (`merge_cdc`) | `_latest` se queda con el último evento por cuadrilla dentro del lote |
| `contracts` | SCD2 | adendas de precio y volumen: Comercial necesita el precio de cada mes |
| `fx_rates`, `budget` | upsert por clave | sin historia |
| `spot_prices` | upsert con `sequence_col = version_rank` | el `DEFINITIVO` (2) pisa al `PRELIMINAR` (1), **nunca al revés** aunque el preliminar llegue después |
| `dispatch` | upsert con `sequence_col = version` | la versión más alta de cada instrucción (las anuladas quedan con su estado) |
| `weather` | upsert con `sequence_col = issued_ts` | el pronóstico más reciente para cada hora |
| `scada`, `inverter` | **insert-only** | `dedupe_first_arrival` + `MERGE ... WHEN NOT MATCHED INSERT`: un reenvío que llega días después no duplica |
| `work_orders` | CDC con bajas + tabla hija | el último evento de cada orden (ante empate, la baja gana); las duplicadas por error se borran; los repuestos van a `work_order_parts` (se borran y reescriben los de las órdenes del lote) |

**`_insert_only`:**
```python
def _insert_only(spark, df, target, keys, cluster_by, comment=None):
    create_table_if_not_exists(spark, target, df, cluster_by=cluster_by, comment=comment)
    cond = " AND ".join(f"t.`{k}` = s.`{k}`" for k in keys)
    DeltaTable.forName(spark, target).alias("t").merge(df.alias("s"), cond).whenNotMatchedInsertAll().execute()
```
La clave incluye `reading_date`: así el MERGE puede **podar archivos** (*file pruning*) y no lee los 7 millones de
filas de la tabla para cada lote, sólo los de las fechas del lote.

**El registro:** `LOADERS` (nombre → función), `REFERENCE_ENTITIES` y `TELEMETRY_ENTITIES` (el orden de los dos *for
each*) y `load_all` para correr todo en orden en local.

### 3. El test

`tests/test_scd2.py`: una turbina con alta, renombre y cambio de firmware **en el mismo lote**, más un reenvío idéntico
y un cambio tardío. Verifica que quedan exactamente las versiones esperadas, una sola vigente, y que re-ejecutar no
agrega nada.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| SCD2 a mano | `AUTO CDC ... STORED AS SCD TYPE 2` (LDP) | se quería entender el mecanismo; el capítulo 16 hace lo mismo en 8 líneas con LDP para comparar |
| un MERGE con claves `_mk_` | dos operaciones (UPDATE + INSERT) | dos operaciones no son atómicas: si falla entre las dos, queda una versión cerrada sin la nueva |
| streaming desde bronze | leer bronze entero cada vez | cada corrida reprocesaría 7 millones de filas para agregar 10 mil |
| insert-only para la telemetría | upsert | una lectura no "cambia": si llega dos veces, la primera es la buena |
| la telemetría después de los activos | todo en paralelo | sin `asset_tags`, las lecturas con el nombre viejo quedarían sin turbina (y a cuarentena) |

## ✅ Probalo

```bash
pytest tests/test_scd2.py -v     # 1 passed
pytest -m "not integration"      # 25 passed
```
Y con los datos de los capítulos 08 y 09 (ya están en bronze):
```bash
python - <<'EOF'
from andes_viento.config import local_config
from andes_viento.utils.spark import build_local_spark
from andes_viento.silver.load import load_all
spark = build_local_spark(warehouse_dir="/tmp/andes_wh")
cfg = local_config("/tmp/andes_landing", scale_factor=0.02)
load_all(spark, cfg, ["fx_rates", "spot_prices", "weather"])
spark.sql("SELECT node, hour_local, cammesa_hour, price_ars_mwh, price_type FROM spark_catalog.andes_silver.spot_prices ORDER BY hour_ts LIMIT 3").show()
spark.sql("SELECT * FROM spark_catalog.andes_ops.dq_results ORDER BY checked_at DESC LIMIT 5").show(truncate=40)
EOF
```
Las entidades que necesitan activos (SCADA, inversores, órdenes) recién se pueden cargar con la historia desde el
principio: lo hace el test de integración del capítulo 14.

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE` | dos filas del lote con la misma clave matchean la misma fila destino | deduplicá antes del MERGE (`_latest`, `dropDuplicates`) |
| SCD2 con dos versiones vigentes | la versión vigente no se cerró en el mismo MERGE | revisá las filas `to_close` y la condición `t.is_current = true` |
| 540 claves huérfanas en gold | la primera versión SCD2 empieza en el primer dato, no "desde siempre" | gold arma la primera versión desde 1900 (L6, capítulo 12) |
| la telemetría va toda a cuarentena (`turbina_conocida`) | se cargó antes que los activos | orden: referencia → telemetría |
| `foreachBatch` falla con una sesión cerrada | usaste el `spark` de afuera | `s = df.sparkSession` |

## 📍 Punto de control

```bash
git commit -am "etapa-07: silver, carga incremental, SCD2 y CDC" && git diff etapa-07 HEAD --stat
```

## 🏋️ Ejercicio

1. Con `silver.assets_history`, escribí la consulta "¿qué número de serie de multiplicadora tenía `WTG00034` el
   20-07-2025?" (pista: `valid_from <= fecha AND (valid_to IS NULL OR valid_to > fecha)`).
2. Agregá a `test_scd2.py` un caso de **baja** (`op = 'D'`) y verificá que la versión vigente se cierra y queda una
   versión con `is_deleted = true`.
3. Hacé que los precios spot guarden también la diferencia entre el preliminar y el definitivo (pista: una columna
   más en el upsert).
