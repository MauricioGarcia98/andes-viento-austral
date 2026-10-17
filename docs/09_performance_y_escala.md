# 09 · Performance y escala

## Volúmenes por scale_factor (2023-01 → 2026-09)

| | SF 0,1 (Free Edition) | SF 1 (flota real) | SF 10 (hipotético) |
|---|---|---|---|
| turbinas / inversores | 37 / 23 | 380 / 220 | 3.800 / 2.200 |
| filas SCADA (10 min) | ~7 M | ~70 M | ~700 M |
| filas inversores (5 min, de día) | ~5 M | ~50 M | ~500 M |
| landing (sin comprimir / gzip) | ~3 GB / ~0,4 GB | ~30 GB / ~4 GB | ~300 GB / ~40 GB |
| `fact_turbine_10min` | ~7 M | ~70 M | ~700 M |

Los tiempos reales de cada tarea a SF 0,1 están en la [bitácora](08_bitacora.md) y en `ops.pipeline_runs`.

## Decisiones de performance (y su porqué)

| decisión | dónde | por qué |
|---|---|---|
| Generador sin UDFs de Python | `datagen/physics.py` | las UDFs serializan fila por fila entre JVM y Python: 10-50x más lentas |
| Tablas guía chicas por **broadcast** | `generators.py` (`_array_of_structs`) | un `array<struct>` por turbina/parque evita joins por rango sobre millones de filas |
| Un archivo por día y fuente en landing | `writer.py` (`repartition("ingest_date")`) | miles de archivos chicos matan a Auto Loader y a cualquier lector |
| `maxFilesPerTrigger` | bronze / silver | lotes acotados: memoria estable en `foreachBatch` |
| **Liquid clustering** `(reading_date, park_code)` | hechos de silver y gold | casi toda consulta filtra por fecha y parque; reemplaza particionado + ZORDER |
| MERGE con la fecha en la condición | `_insert_only` | permite *file pruning* en el destino (no escanea toda la tabla) |
| Incremental por `reading_date` con watermark | `gold/facts.py` | el job diario recalcula 1-3 días, no 1.369 |
| Pre-agregar | `fact_inverter_hourly`, marts | nadie mira un inversor cada 5 min: 12x menos filas |
| Agregar ANTES de ventanas | `mart_turbine_health` | ordenar 1 fila por turbina-día y no 144 |
| `OPTIMIZE` + `VACUUM` + `ANALYZE` semanal | job de mantenimiento | compacta archivos chicos de los MERGE incrementales; estadísticas para el optimizador |

## Cómo escalar a SF 1 y SF 10

1. **Compute**: serverless escala solo; en un workspace pago el job puede usar un *serverless budget policy* o
   performance mode. En Free Edition, SF 0,1 es el máximo razonable (cuotas diarias de cómputo).
2. **Generador**: `_range_partitions` crece con días × turbinas (~2.000 turbina-días por partición).
3. **Bronze**: subir `maxFilesPerTrigger` (los archivos son más grandes); considerar `cloudFiles.useNotifications` con
   storage propio.
4. **Silver SCADA**: es la tarea más pesada. El percentil del reloj agrupa por turbina y día de recepción (escala
   lineal). La ventana de sensores clavados particiona por turbina (bien distribuida).
5. **Gold**: `fact_turbine_10min` usa una ventana por `(park_code, ts_utc)` para el viento del parque: con 3.800
   turbinas sigue siendo chica por partición.
6. **Skew**: Cerro Arenales tiene más turbinas; AQE separa particiones sesgadas en los joins.

## Cómo medir

- **Query profile** (SQL Editor / notebook): archivos leídos vs. podados, *spill*, tiempo por operador.
- `DESCRIBE DETAIL <tabla>`: cantidad y tamaño de archivos.
- `ops.pipeline_runs`: duración por paso y por corrida (comparar SF 0,1 vs. 1).
- `system.billing.usage`: DBUs por job (desafío final 10).
