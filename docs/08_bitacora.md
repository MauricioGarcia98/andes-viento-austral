# 08 · Bitácora: los errores reales, explicados en criollo

> Todo lo que salió mal construyendo y desplegando Andes Viento Austral, en orden, con el mensaje real, por qué pasó,
> cómo se arregló y qué aprendimos. Workspace: **Databricks Free Edition**, compute serverless, CLI v1.21,
> `scale_factor = 0.1`. Los errores de NovaMart ya estaban aplicados desde el día 1 (ver más abajo).

## Lo que trajimos aprendido de NovaMart (y por eso NO pasó)

| error en NovaMart | cómo lo evitamos acá |
|---|---|
| `The dependency on an if/else condition ... does not specify an outcome` | `outcome: "true"` / `"false"` en todas las dependencias de `should_generate` |
| `Catalog 'novamart_dev' does not exist` / `Metastore storage root URL does not exist` | catálogo creado por SQL antes del primer deploy (ADR-007) |
| `CF_ADD_NEW_NOT_SUPPORTED` (`.schema()` + `addNewColumns` en CSV) | contrato por `cloudFiles.schemaHints` |
| `UNKNOWN_FIELD_EXCEPTION` agotando los reintentos del job | reinicio del stream en `bronze.py` (los reintentos quedan para infraestructura) |

Resultado: **el primer `bundle deploy` salió limpio** (12 recursos creados) y bronze absorbió el schema drift de HT-OS 5.0
y del sensor de suciedad sin intervención.

---

## Antes de desplegar: lo que encontró la prueba local de punta a punta

<details>
<summary><b>L1 · <code>pip install pyspark</code> falla con <code>AttributeError: install_layout</code></b></summary>

- **Qué pasó:** el `setuptools` del Python del sistema (Debian) no sabe construir el paquete de PySpark.
- **Arreglo:** usar un entorno virtual (`python -m venv .venv`) con `pip`/`setuptools` actualizados.
- **Lección:** nunca instalar dependencias de un proyecto en el Python del sistema.
</details>

<details>
<summary><b>L2 · <code>module 'pyspark.sql.functions' has no attribute 'try_cast'</code> (y <code>try_to_date</code>)</b></summary>

- **Qué pasó:** en SQL existen `try_cast` y `try_to_date`, pero en la API de Python de Spark 4 `try_cast` es un método
  de columna (`col.try_cast("double")`) y `try_to_date` directamente no existe.
- **Arreglo:** `F.col(x).try_cast(...)` y un helper `try_date()` con `to_date(try_to_timestamp(...))`.
- **Lección:** con ANSI activo (default en Spark 4 y serverless) un `CAST` inválido es un ERROR; en silver se usan
  las variantes `try_*` y una regla de calidad que cuenta los NULL.
</details>

<details>
<summary><b>L3 · <code>INVALID_EXTRACT_BASE_FIELD_TYPE ... Can't extract a value from "p"</code></b></summary>

- **Qué pasó:** un lote de órdenes del CMMS traía sólo `parts: []`. Al inferir el esquema del JSON, un array vacío se
  tipa `ARRAY<STRING>` y después `p.part_code` no existe. **Auto Loader haría exactamente lo mismo** si los primeros
  archivos que muestrea no traen repuestos.
- **Arreglo:** `JSON_SCHEMA_HINTS` en bronze (`parts ARRAY<STRUCT<...>>`) y el generador manda `null` en vez de `[]`.
- **Lección:** `schemaHints` no es sólo para CSV: en JSON fijalo para todo lo que la inferencia pueda adivinar mal.
</details>

<details>
<summary><b>L4 · <code>does not support REPLACE TABLE AS SELECT</code> (Spark local)</b></summary>

- **Qué pasó:** en Spark OSS el formato por defecto es Parquet; `CREATE OR REPLACE TABLE ... AS SELECT` sólo funciona con Delta.
- **Arreglo:** `USING DELTA` explícito en los 7 marts (en Databricks no cambia nada).
</details>

<details>
<summary><b>L5 · <code>[INVALID_IDENTIFIER] The unquoted identifier pd-gearbox_c is invalid</code></b></summary>

- **Qué pasó:** `sum(gearbox_c) OVER pd - gearbox_c` con una ventana con nombre (`WINDOW pd AS ...`): el parser leyó
  `pd-gearbox_c` como un identificador con guion.
- **Arreglo:** paréntesis: `(sum(gearbox_c) OVER pd) - gearbox_c`.
- **Ojo:** este arreglo se hizo en local DESPUÉS del primer deploy, y la primera corrida real falló justo en
  `gold_marts` con este error (ver R2). Lección de proceso: **no desplegar hasta que la prueba local de punta a punta pase**.
</details>

<details>
<summary><b>L6 · Quality gate: <code>toda medición tiene turbina (FK a dim_turbine): 540</code></b></summary>

- **Qué pasó:** la primera versión SCD2 de cada turbina arrancaba a la hora de la carga inicial del CMMS (09:00);
  las mediciones de la madrugada de ese día no encontraban versión vigente en el join point-in-time.
- **Arreglo:** la versión 1 vale "desde siempre" (`1900-01-01`), práctica estándar de Kimball.
- **Lección:** por eso existe el quality gate: el pipeline no falló, pero el dato estaba mal.
</details>

<details>
<summary><b>L7 · Calibración de negocio: todos los PPA "CUMPLEN" siempre</b></summary>

- **Qué pasó:** los volúmenes comprometidos eran 15-45 % de la generación esperada: imposible quedarse corto.
- **Arreglo:** 50-75 % de la P50 (lo típico en un PPA real) y la adenda +20 % del data center.
- **Lección:** los datos sintéticos también se validan con criterio de negocio, no sólo técnico.
</details>

<details>
<summary><b>L8 · Test de integración: la foto inicial del CMMS salía con el firmware viejo</b></summary>

- **Qué pasó:** si la historia arranca después de un cambio (ej. desde jun-2025, el firmware HT-OS 5.0 es de marzo), el
  generador descartaba los cambios anteriores en vez de aplicarlos a la foto inicial.
- **Arreglo:** los cambios previos a la primera carga se "pliegan" en el registro `I` (activos y contratos).
</details>

---

## En Databricks

<details open>
<summary><b>R1 · <code>There are already 5 active runs (limit: 5)</code></b></summary>

- **Qué pasó:** apenas se lanzó la primera corrida, quedó `PENDING` con ese mensaje aunque no había otras corridas activas.
- **Qué hicimos:** nada: a los pocos segundos arrancó sola. Free Edition limita la concurrencia (corridas y tareas
  simultáneas); por eso los `for_each` tienen `concurrency` 3-4.
</details>

<details open>
<summary><b>R2 · <code>gold_marts</code>: <code>[INVALID_IDENTIFIER] ... pd-gearbox_c</code></b></summary>

- **Qué pasó:** el mismo error L5. El bundle se desplegó con el código anterior al arreglo local.
- **Arreglo:** redeploy + nueva corrida. Las tareas anteriores habían salido bien: bronze 505 s, silver 129 + 115 s.
</details>

<details open>
<summary><b>R3 · Regenerar los archivos no sirve: Auto Loader no los vuelve a leer</b></summary>

- **Qué pasó:** para la segunda corrida había que regenerar `ppa_contracts` (L7). Pero el generador sobrescribe los
  archivos en la misma ruta, y Auto Loader, con `cloudFiles.allowOverwrites=false` (default), **ignora un archivo
  ya procesado aunque cambie su contenido**.
- **Arreglo:** `full_refresh=true` en el job: `00_setup` borra bronze/silver/gold/ops, los checkpoints y los
  esquemas inferidos de Auto Loader antes de empezar.
  ```bash
  databricks bundle run andes_e2e -t dev --params full_refresh=true
  ```
- **Lección:** en un lakehouse real los archivos de landing son **inmutables**; si una fuente reenvía, reenvía archivos nuevos.
</details>

<details open>
<summary><b>R4 · <code>governance</code>: <code>[PARSE_SYNTAX_ERROR] Syntax error at or near '''</code></b></summary>

- **Qué pasó:** 5 comentarios del diccionario tenían `;` adentro ("...(m/s); null si estaba clavado") y el runner
  separaba sentencias por cualquier `;`, incluso dentro de un string.
- **Cómo lo encontramos:** corriendo `sql/governance/01_comments.sql` sentencia por sentencia contra el warehouse
  (`143/153 OK`, los 10 que fallaban eran las mitades de los 5 comentarios).
- **Arreglo:** `split_statements` ahora respeta `'...'`, `"..."`, `` `...` ``, bloques `$$...$$` y comentarios `--`
  (con test). Después: **148/148 COMMENT, 70/70 PK/FK, 26/26 tags, 14/14 máscaras y row filters OK**.
</details>

<details open>
<summary><b>R5 · Metric views: <code>Can't extract a value from "parque.park_name"... got "STRING"</code></b></summary>

- **Qué pasó:** en `mv_curtailment` y `mv_mantenimiento` el join se llamaba `parque` y había una **dimensión
  "Parque"**. Los nombres no distinguen mayúsculas: `parque.park_name` se resolvió como "el campo park_name de la
  dimensión Parque" (que es un string).
- **Cómo lo encontramos:** una metric view mínima con el join llamado `dp` funcionó a la primera.
- **Arreglo:** join `park`. Las 7 metric views (con `version: 1.1`, `synonyms` y `joins`) y las 7 funciones quedaron OK.
</details>

<details open>
<summary><b>R6 · <code>[CROSS_CATALOG_SCHEMA_REFERENCE_NOT_SUPPORTED] ... andes_viento_dev.gold</code></b></summary>

- **Qué pasó:** las vistas y funciones se crearon bien, pero la última celda del notebook hacía
  `SHOW VIEWS IN andes_viento_dev.gold`. En serverless ese comando no acepta `catálogo.esquema` si no es el catálogo actual.
- **Arreglo:** consultar `andes_viento_dev.information_schema.tables` / `routines`.
- **Lección:** una tarea puede fallar en la parte "decorativa" (mostrar resultados) después de hacer bien el trabajo:
  leé el error completo antes de re-ejecutar.
</details>

<details open>
<summary><b>R7 · Quality gate: <code>disponibilidad contractual entre 0 y 1 (1)</code></b></summary>

- **Qué pasó:** una turbina-día dio **−0,0002**: 16,67 h de falla + 7,33 h sin dato = 24,00 h, pero calculado con
  horas ya redondeadas a 2 decimales.
- **Arreglo:** acotar a [0, 1] en `fact_availability_daily`. Para no reprocesar todo, se corrigió la fila con un
  `UPDATE` (funciona como admin aunque la tabla tenga row filter) y se reparó sólo el gate.
- **Lección:** el gate es la última barrera antes de que Genie muestre un número imposible.
</details>

<details open>
<summary><b>R8 · Genie API: <code>Invalid export proto: instructions.example_question_sqls must be sorted by id</code></b></summary>

- **Qué pasó:** la API valida que cada lista del `serialized_space` esté ordenada por `id`.
- **Arreglo:** `build_genie.py` ordena todas las listas (`sample_questions`, `text_instructions`, `example_question_sqls`,
  `sql_functions`, `benchmarks.questions`). Los 4 agents se crearon y el export confirmó tablas, metric views,
  funciones, ejemplos y benchmarks.
</details>

<details open>
<summary><b>R9 · <code>bundle deploy -t prod</code>: <code>An app with the same name already exists</code></b></summary>

- **Qué pasó:** el nombre de una App es único en el workspace; el modo `development` NO le agrega prefijo como a los
  jobs. Además Free Edition permite una sola App.
- **Arreglo:** la App se declara sólo en `targets.dev.resources` (`databricks.yml`). Prod: 11 recursos OK.
</details>

<details open>
<summary><b>R10 · Calibración con datos reales: la flota era "demasiado sana"</b></summary>

- **Qué pasó:** con los datos reales de la primera corrida completa, ningún parque bajaba del 97 % de
  disponibilidad (el caso 5 quedaba sin reclamos) y Cañadón León daba −15,4 % en julio 2025 (guionado para ~−18 %).
- **Arreglo de negocio:** se agregó a la historia un **lote defectuoso de multiplicadoras de Hanse Turbinen Werke**
  (mar-2024 → dic-2025), algo que pasa en la industria; el tope de red de julio 2025 pasó de 60 % a 50 %.
- **Lección:** los números del "por qué" se documentan con lo que dio la corrida real, no con lo que se esperaba.
</details>

<details open>
<summary><b>R11 · Genie: <code>INVALID_CERTIFIED_ANSWER_FUNCTION_EXCEPTION ... argument type is not supported: date</code></b></summary>

- **Qué pasó:** la primera evaluación de benchmarks dio **0 aciertos**. No era el comparador: Genie rechazaba la
  configuración COMPLETA del agent porque `fn_perdida_curtailment` tenía parámetros `DATE`, y las funciones confiables
  (*certified answers*) no los admiten. El deploy por API no falla: el error aparece recién al preguntar.
- **Cómo lo encontramos:** una pregunta suelta con `scripts/genie_ask.py` mostró el error completo.
- **Arreglo:** parámetros `STRING 'yyyy-MM-dd'` y `to_date()` adentro. La misma pregunta volvió con 350,0 MWh (exacto).
- **Lección:** después de desplegar un agent, **hacele una pregunta** antes de dar el deploy por bueno (lo hace `genie_eval.py`).
</details>

## Tiempos reales por tarea

<!-- TIEMPOS -->

## Cómo reparar sin correr todo de nuevo

```bash
databricks jobs repair-run <run_id> --rerun-all-failed-tasks --rerun-dependent-tasks
# si ya hubo una reparación, la CLI pide la última:
databricks jobs repair-run <run_id> --rerun-all-failed-tasks --latest-repair-id <repair_id>
```
Para depurar SQL, ejecutá el archivo sentencia por sentencia contra el warehouse (Statement Execution API) en vez de
re-correr el job: encontrar R4 y R5 tomó minutos, no corridas de 45.
