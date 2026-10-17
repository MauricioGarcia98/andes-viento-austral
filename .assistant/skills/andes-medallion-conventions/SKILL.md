---
name: andes-medallion-conventions
description: Cómo agregar o modificar una fuente, entidad silver o tabla gold en el lakehouse de Andes Viento Austral respetando las convenciones (Auto Loader, reglas de calidad, SCD2, diccionario, tests). Usar cuando pidan "agregar una fuente", "nueva tabla", "nueva columna" o "nueva regla de calidad".
---

# Agregar una fuente o tabla en Andes Viento Austral

Seguí SIEMPRE este orden. Cada paso tiene un archivo dueño.

## 1. Landing (si es una fuente nueva)
- Generador en `src/andes_viento/datagen/generators.py` → registrarlo en `SOURCES` (formato y opciones).
- Debe devolver `ingest_date` = día en que el ARCHIVO llega (no el día del dato).
- Suciedad realista: duplicados, nulos, formatos de fecha del sistema origen, datos tardíos.

## 2. Bronze
- `ingestion/bronze.py`: agregar a `SOURCE_FORMATS`.
- CSV → contrato en `CSV_CONTRACTS` (va por `cloudFiles.schemaHints`, nunca `.schema()`).
- JSON → si la inferencia puede equivocarse (arrays vacíos, números que a veces son null) → `JSON_SCHEMA_HINTS`.
- No limpiar nada: bronze es "lo que llegó, tal cual llegó" + linaje.

## 3. Silver
- Transformación pura en `silver/transforms.py` (`clean_<entidad>`), con `try_cast`/`try_to_timestamp`.
- Reglas en `silver/rules.py` (`Rule(nombre, expr_sql_verdadera, acción)`).
- Loader en `silver/load.py` registrado en `LOADERS` y en `REFERENCE_ENTITIES` o `TELEMETRY_ENTITIES`
  (telemetría = depende de `silver.asset_tags`). Agregar la entidad al `for_each` del job en `resources/andes_e2e.job.yml`.
- Estrategia: SCD2 (`scd2_merge`) si importa la historia; CDC con bajas (`merge_cdc`); insert-only si es un evento.

## 4. Gold
- Dimensión → `gold/dimensions.py` (`DIMENSIONS`), con fila `-1` "desconocido".
- Hecho → `gold/facts.py` (`FACTS`), incremental por `reading_date` con watermark y `replaceWhere`.
- Mart → `sql/marts/NN_nombre.sql` (`CREATE OR REPLACE TABLE ${gold}...`), documentando la regla de negocio arriba.

## 5. Gobierno y semántica
- Entrada en `governance/data_dictionary.yml` (comentario pensado para Genie, PK/FK, tags `pii`).
- `python scripts/build_governance.py` (regenera `sql/governance/*.sql` y el diccionario en docs).
- Si es una métrica oficial → metric view en `sql/semantic/01_metric_views.sql` (sin `;` dentro de `$$`).

## 6. Tests y CI
- Unit test de la transformación en `tests/test_transforms.py`; si cambia el grano, chequeo en `quality/gate.py`.
- `ruff check src tests scripts` y `pytest -m "not integration"`.

## Errores que ya nos pasaron (ver docs/07_bitacora.md)
- `CF_ADD_NEW_NOT_SUPPORTED`: `.schema()` + `addNewColumns` en CSV.
- `UNKNOWN_FIELD_EXCEPTION`: columna nueva → se reinicia el stream en código.
- `ARRAY<STRING>` inferido para un array vacío → `JSON_SCHEMA_HINTS`.
