# 15 · Etapa 11 · Asset Bundle, notebooks y el job principal

## 🎯 Objetivo

Llevar el pipeline a Databricks **como código**: un Asset Bundle que describe el job de 12 tareas, notebooks delgados
que llaman al paquete y el primer despliegue real. Al final de esta etapa el pipeline completo corre en tu workspace,
con las tareas en paralelo donde se puede.

**Archivos:** `databricks.yml`, `resources/andes_schemas.yml`, `resources/andes_e2e.job.yml`, `notebooks/_bootstrap.py`
y `notebooks/00_setup.py` a `09_quality_gate.py`.

## 📚 Conceptos

- **Asset Bundle (DAB):** una carpeta con `databricks.yml` que describe recursos del workspace (jobs, pipelines,
  dashboards, Apps, esquemas) **en YAML**. `databricks bundle deploy` sube los archivos y crea o actualiza los recursos
  para que coincidan con el YAML. Es *infraestructura como código*: lo que no está en git no existe.
- **Target:** una variante del despliegue (`dev`, `prod`), con sus propias variables.
- **`mode: development`:** prefija los recursos con `[dev tu_usuario]`, pausa los schedules y deja que cada persona
  tenga su copia sin pisar la de otros.
- **Tipos de tarea que usa el job:**

| tipo | qué hace | en el job |
|---|---|---|
| `notebook_task` | corre un notebook | casi todas |
| `condition_task` | evalúa una condición y elige una rama (`outcome: "true"` / `"false"`) | `should_generate` |
| `for_each_task` | corre la misma tarea para cada valor de una lista, con concurrencia | `generate_data`, `silver_reference`, `silver_telemetry` |

- **`run_if`:** cuándo corre una tarea según el estado de sus dependencias. `NONE_FAILED` = "si ninguna falló"
  (aunque alguna haya quedado *excluida* por la condición).

## 🧱 Paso a paso

### 1. `databricks.yml`

```yaml
bundle:
  name: andes-viento-austral

include:
  - resources/*.yml                 # cada recurso en su archivo

variables:
  catalog:
    default: andes_viento_dev
  scale_factor:
    default: "0.1"
  start_date: { default: "2023-01-01" }
  end_date:   { default: "2026-09-30" }
  warehouse_id:
    lookup:
      warehouse: Serverless Starter Warehouse     # busca el ID por nombre: no hay que copiarlo a mano

targets:
  dev:
    mode: development
    default: true
    variables:
      catalog: andes_viento_dev
  prod:
    mode: production
    workspace:
      root_path: /Workspace/Users/${workspace.current_user.userName}/.bundle/${bundle.name}/${bundle.target}
    variables:
      catalog: andes_viento
      scale_factor: "0.1"
```
- Las **variables** se usan en los recursos como `${var.catalog}`. Cambiar de ambiente = cambiar de target.
- `lookup` resuelve el ID del warehouse por su nombre en cada workspace (los IDs cambian; los nombres no).
- **El catálogo no se declara:** en Free Edition la API no puede crearlo (capítulo 04).
- En `prod`, `root_path` es una carpeta de tu usuario: en una empresa sería un *service principal* desplegando desde
  CI (capítulo 22), pero Free Edition tiene un solo usuario. `/Workspace/Shared` daría permiso de escritura a todos y el
  `validate` lo advierte.
- (La App se agrega en la etapa 17.)

### 2. `resources/andes_schemas.yml`

Declara sólo el esquema `ldp` (para el pipeline declarativo del capítulo 16): un pipeline necesita que su esquema
exista **antes** de crearse. Las capas medallion las crea el notebook `00_setup` en cada corrida.

### 3. Los notebooks delgados

**`_bootstrap.py`** (lo corren todos con `%run ./_bootstrap`):
```python
_src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)
spark.conf.set("spark.sql.session.timeZone", "UTC")
dbutils.widgets.text("catalog", "andes_viento_dev", "Catálogo UC")
dbutils.widgets.text("scale_factor", "0.1", "Scale factor")
dbutils.widgets.text("start_date", "2023-01-01", "Fecha inicio")
dbutils.widgets.text("end_date", "2026-09-30", "Fecha fin")
from andes_viento.config import config_from_widgets
cfg = config_from_widgets(dbutils)
```
- Agrega `../src` al `sys.path`: el bundle sube la carpeta `src/` al lado de `notebooks/`, y así el notebook importa
  **el mismo paquete que testeaste**. No hay que construir ni instalar un *wheel*.
- Fija UTC (la convención del proyecto) y define los widgets comunes. Los **parámetros del job llenan los widgets**.

**Cada notebook hace una cosa**, por ejemplo `03_silver_entity.py`:
```python
%run ./_bootstrap
dbutils.widgets.text("entity", "scada", "Entidad")
entity = dbutils.widgets.get("entity")
from andes_viento.silver.load import LOADERS
from andes_viento.utils.audit import audited
with audited(cfg, spark, f"silver_{entity}", f"silver.{entity}"):
    LOADERS[entity](spark, cfg)
```

| notebook | llama a | parámetro propio |
|---|---|---|
| `00_setup` | `create_namespace` (+ reset si `full_refresh`) | `full_refresh` |
| `01_generate_source` | `write_source` | `source`, `mode` |
| `02_bronze_ingest` | `ingest_all` | — |
| `03_silver_entity` | `LOADERS[entity]` | `entity` |
| `04_gold_dimensions` | `load_dimensions` | — |
| `05_gold_facts` | `load_facts` | `full_refresh` |
| `06_gold_marts` | `build_marts` | — |
| `07_governance` | `run_sql_folder("governance")` | — (el SQL llega en la etapa 13) |
| `08_semantic_layer` | `run_sql_folder("semantic")` | — (el SQL llega en la etapa 14) |
| `09_quality_gate` | `run_quality_gate` | — |

**El reset de `00_setup`:** con `full_refresh=true` borra las capas **y** los checkpoints y esquemas de Auto Loader.
Sin eso, regenerar landing no sirve: Auto Loader **ignora archivos sobrescritos** en la misma ruta (R3 de la bitácora).

### 4. `resources/andes_e2e.job.yml`: el job

```yaml
resources:
  jobs:
    andes_e2e:
      name: andes-viento-e2e
      max_concurrent_runs: 1
      timeout_seconds: 14400
      parameters:
        - { name: catalog,      default: "${var.catalog}" }
        - { name: scale_factor, default: "${var.scale_factor}" }
        - { name: start_date,   default: "${var.start_date}" }
        - { name: end_date,     default: "${var.end_date}" }
        - { name: generate,     default: "true" }
        - { name: full_refresh, default: "false" }
      tasks:
        - task_key: setup
          notebook_task: { notebook_path: ../notebooks/00_setup.py }

        - task_key: should_generate
          depends_on: [{ task_key: setup }]
          condition_task: { op: EQUAL_TO, left: "{{job.parameters.generate}}", right: "true" }

        - task_key: generate_data
          depends_on: [{ task_key: should_generate, outcome: "true" }]
          for_each_task:
            inputs: '["scada_turbine","inverter_5min","weather","cmms_assets", ...]'
            concurrency: 3
            task:
              task_key: generate_source
              notebook_task:
                notebook_path: ../notebooks/01_generate_source.py
                base_parameters: { source: "{{input}}", mode: full }

        - task_key: bronze_ingest
          depends_on:
            - task_key: generate_data
            - task_key: should_generate
              outcome: "false"
          run_if: NONE_FAILED
          max_retries: 1
          min_retry_interval_millis: 30000
          notebook_task: { notebook_path: ../notebooks/02_bronze_ingest.py }

        - task_key: silver_reference    # for_each de 8 entidades, concurrencia 4
        - task_key: silver_telemetry    # for_each de 3, depende de silver_reference
        - task_key: gold_dimensions
        - task_key: gold_facts          # base_parameters: full_refresh
        - task_key: gold_marts
        - task_key: governance          # depende de gold_marts
        - task_key: semantic_layer      # depende de gold_marts (en paralelo con governance)
        - task_key: quality_gate        # depende de governance y semantic_layer
```
(Escribí el archivo completo leyendo `git show etapa-11:resources/andes_e2e.job.yml`.)

**Las decisiones del grafo:**

| detalle | por qué |
|---|---|
| **parámetros del job** (`{{job.parameters.x}}`) | los heredan todas las tareas como widgets; un solo lugar para cambiar el catálogo o la escala |
| `should_generate` + `outcome` | el job diario reusa este mismo job con `generate=false`: no regenera la historia, sólo procesa lo que llegó |
| `outcome: "true"` en `generate_data` | sin `outcome`, el bundle falla con *"The dependency on an if/else condition ... does not specify an outcome"* (lección de NovaMart) |
| `bronze_ingest` depende de **las dos ramas** + `run_if: NONE_FAILED` | si se generó, espera a `generate_data`; si no, `generate_data` queda *excluded* y bronze corre igual por la rama `false` |
| `for_each` con `concurrency` 3 / 4 / 3 | paralelismo acotado: Free Edition permite 5 corridas a la vez |
| referencia antes que telemetría | la telemetría necesita `silver.asset_tags` (capítulo 11) |
| `max_retries: 1` sólo en bronze | los reintentos son para infraestructura; las columnas nuevas se manejan en código (capítulo 09) |
| `governance` ∥ `semantic_layer` | no dependen entre sí: corren a la vez y ahorran ~30 segundos |
| `max_concurrent_runs: 1` | dos corridas a la vez escribirían las mismas tablas |
| `timeout_seconds: 14400` | si algo se cuelga, a las 4 horas se corta (y no consume la cuota del día) |
| sin `clusters` | serverless: Databricks pone el cómputo |

### 5. El primer despliegue

```bash
databricks bundle validate -t dev       # revisa el YAML contra el workspace → "Validation OK!"
databricks bundle deploy   -t dev       # sube archivos y crea el job y el esquema ldp
databricks bundle run andes_e2e -t dev  # ~45 min; muestra el Run URL
```
Mirá la corrida en **Jobs & Pipelines → [dev tu_usuario] andes-viento-e2e → Runs → Graph**. Las tareas *for each*
muestran cada iteración. Los tiempos reales de cada tarea están en
[docs/10](../docs/10_despliegue_y_cicd.md#paso-7--correr-el-job-principal).

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| bundle | crear el job a mano en la interfaz | no se versiona, no se revisa en un PR, no se reproduce en prod |
| notebooks delgados + paquete | la lógica en los notebooks | no se puede testear con pytest; el código se duplicaría entre notebooks |
| `sys.path` a `src/` | construir un *wheel* | un paso más (y una versión más que mantener) sin beneficio para este proyecto |
| un job con condición | dos jobs (completo y diario) duplicados | dos definiciones que se desincronizan; acá el diario **reusa** este job (capítulo 16) |
| `for_each` | 11 tareas escritas a mano | agregar una fuente sería agregar una tarea; con `for_each`, un valor a la lista |

## ✅ Probalo

- `bundle validate` → `Validation OK!`
- La corrida termina con las 12 tareas en verde (en esta etapa `governance` y `semantic_layer` no hacen nada todavía:
  sus carpetas de SQL llegan en las etapas 13 y 14).
- En el SQL Editor:
  ```sql
  SELECT round(variance_pct * 100, 1) FROM andes_viento_dev.gold.mart_generation_vs_budget
  WHERE park_code = 'LEO' AND year_month = '2025-07';         -- -18.4
  ```

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `Catalog 'andes_viento_dev' does not exist` | falta el paso del capítulo 04 | `CREATE CATALOG` por SQL |
| `does not specify an outcome` | dependencia de una condición sin `outcome` | `outcome: "true"` / `"false"` |
| `There are already 5 active runs (limit: 5)` | tope de Free Edition (los *for each* cuentan) | nada: esperan turno (R1) |
| `ModuleNotFoundError: andes_viento` en un notebook | el `sys.path` no apunta a `src` | el notebook tiene que estar en `notebooks/` y `src/` al lado |
| un arreglo no se ve en la corrida | no hiciste `bundle deploy` después de cambiar el código | la regla de oro (R13) |
| `CROSS_CATALOG_SCHEMA_REFERENCE_NOT_SUPPORTED` con `SHOW VIEWS IN cat.schema` | serverless no lo admite | consultá `information_schema` (R6) |
| una tarea falla | — | arreglá, `bundle deploy`, **Repair run** (corre sólo lo que falló y lo que depende) |

## 📍 Punto de control

```bash
git add -A && git commit -m "etapa-11: bundle, notebooks y job e2e" && git push
git diff etapa-11 HEAD --stat
```
En `etapa-11`, `databricks.yml` todavía no tiene la App (llega en la etapa 17).

## 🏋️ Ejercicio

1. Corré el job con `--params generate=false`. Mirá en el grafo que `generate_data` queda **Excluded** y `bronze_ingest`
   corre igual.
2. Agregá `email_notifications: { on_failure: [tu@email.com] }` al job, desplegá y forzá una falla (por ejemplo, un
   catálogo que no existe como parámetro). ¿Te llega el mail?
3. Cambiá la concurrencia de `silver_reference` a 8. ¿Termina antes? ¿Por qué no tanto? (pista: R1 y el tope de 5).
