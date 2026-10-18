# 05 · Etapa 1 · Cimientos: paquete, configuración y utilidades

## 🎯 Objetivo

Antes de generar un solo dato hay que tener **la caja de herramientas** que todo el resto va a usar:

- un **paquete de Python** instalable (`andes_viento`) con lint y tests;
- **una sola configuración** (`ProjectConfig`) que sabe cómo se llaman las tablas y dónde están los archivos, en
  Databricks y en tu computadora;
- una **sesión de Spark local** con Delta para los tests;
- utilidades de **Delta** (MERGE, sobrescritura parcial), **auditoría** (cuánto tardó cada paso) y **calidad**
  (reglas por fila con cuarentena);
- el **setup** que crea los esquemas y las tablas de operación.

Va primero porque cada etapa siguiente importa algo de acá. Al final: `pytest` corre 1 test en verde.

**Archivos de esta etapa** (`git diff --stat <commit inicial> etapa-01`):
```
.gitignore  LICENSE  pyproject.toml
src/andes_viento/__init__.py   config.py   setup.py
src/andes_viento/utils/__init__.py   spark.py   delta.py   audit.py
src/andes_viento/quality/__init__.py   expectations.py
tests/conftest.py   tests/test_quality.py
```

## 📚 Conceptos

- **dataclass:** una clase de Python que se define sólo con sus campos (`@dataclass`). `frozen=True` la hace
  inmutable: una vez creada no se puede cambiar, sólo copiar con cambios (`dataclasses.replace(cfg, catalog="x")`).
  Así nadie modifica la configuración a mitad de una corrida.
- **MERGE (upsert):** "si la fila existe, actualizala; si no, insertala", en una sola operación atómica de Delta.
- **Idempotente:** correr dos veces da el mismo resultado que correr una. Es la propiedad más importante de un
  pipeline: si algo falla a la mitad, lo volvés a correr sin miedo a duplicar.
- **Context manager (`with ...`):** código que corre "antes" y "después" de un bloque, aunque el bloque falle. Lo
  usamos para medir y registrar cada paso.
- **Fixture de pytest:** algo que pytest prepara y le pasa a los tests (por ejemplo, una sesión de Spark).

## 🧱 Paso a paso

Trabajá en tu repo `mi-andes-viento`, en una rama `etapa-01`, con el venv activado (capítulos 02 y 03).

### 1. `.gitignore` y `LICENSE`

`.gitignore` (qué **no** se sube y por qué):
```
__pycache__/   *.pyc   *.egg-info/      # basura de Python y de la instalación editable
.venv/                                   # el entorno virtual: cada uno crea el suyo
.pytest_cache/   .ruff_cache/            # cachés de las herramientas
.local/   spark-warehouse/   metastore_db/   derby.log    # datos y metastore de Spark local
.databricks/                             # estado local del bundle (capítulo 15)
dist/   build/   node_modules/   docs/diagrams/src/node_modules/
.env                                     # variables de entorno con secretos, si alguna vez usás uno
genie/deployed_*.json                    # IDs de los Genie Agents de TU workspace (capítulo 20)
```
(En el archivo real va un patrón por línea.) `LICENSE`: el texto de la licencia MIT. Sin licencia, legalmente nadie
puede reusar tu código.

### 2. `pyproject.toml`

El bloque `[project]` está explicado en el [capítulo 03](03_python_y_herramientas.md#5-cómo-se-ve-un-pyprojecttoml-lo-escribís-en-la-etapa-1).
Lo nuevo acá es la configuración de las herramientas:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]          # dónde buscar tests
addopts = "-ra -q"             # -q: salida corta; -ra: al final, resumen de lo que no pasó
markers = [
  "integration: corre el pipeline completo landing->gold con Spark local (lento)",
]

[tool.ruff]
line-length = 110
target-version = "py310"
extend-exclude = ["notebooks", "learning", "pipelines", "docs"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM"]
ignore = ["E501"]
```

- **`markers`**: declarar el marker `integration` permite separar los tests lentos (`pytest -m "not integration"`).
  Sin declararlo, pytest avisa que no lo conoce.
- **`extend-exclude` de ruff:** los notebooks usan `spark`, `dbutils` y `display`, que no están definidos en el archivo
  (los inyecta Databricks). ruff los marcaría como error (`F821 undefined name`). Se excluyen; la lógica de verdad
  está en `src/`, que sí se revisa.
- **Reglas:** `E`/`W` estilo, `F` errores reales (imports sin usar, nombres indefinidos), `I` orden de imports, `B`
  bugs típicos (por ejemplo argumentos por defecto mutables), `UP` sintaxis moderna, `SIM` simplificaciones.
  `E501` (línea larga) se ignora porque `line-length` ya lo controla el formateo.

### 3. El paquete: `src/andes_viento/__init__.py`

Vacío. Su existencia convierte la carpeta en un paquete importable. Lo mismo `utils/__init__.py` y
`quality/__init__.py`.

### 4. `config.py`: la única fuente de nombres y rutas

**Bloque 1: las constantes del proyecto.**
```python
LAYERS = ("landing", "bronze", "silver", "gold", "ops")

SOURCES = (
    "scada_turbine",        # telemetría 10 min (JSON gz, con schema drift en 2025)
    "inverter_5min",        # inversores solares 5 min (CSV, con columna nueva en 2025)
    "cmms_assets", "cmms_work_orders", "cmms_crews",
    "cammesa_dispatch", "cammesa_spot_prices",
    "ppa_contracts", "weather", "fx_rates", "generation_budget",
)

SILVER_REFERENCE = ("assets", "crews", "contracts", "fx_rates", "spot_prices", "budget", "dispatch", "weather")
SILVER_TELEMETRY = ("scada", "inverter", "work_orders")

EXPECTED_TABLES = { "bronze": list(SOURCES), "silver": [...], "gold": [...], "ops": [...] }
```
**Por qué acá:** el job, los tests y los scripts recorren estas listas. Si las fuentes estuvieran escritas en cinco
lugares, agregar una fuente obligaría a acordarse de los cinco. `SILVER_REFERENCE` va antes que
`SILVER_TELEMETRY` porque la telemetría necesita las tablas de referencia (los nombres viejos y nuevos de cada
turbina, capítulo 11). `EXPECTED_TABLES` lo usa `scripts/run_local.py` para verificar que se crearon todas.
(Escribí la lista completa: `git show etapa-01:src/andes_viento/config.py`.)

**Bloque 2: ¿estoy en Databricks?**
```python
def is_databricks() -> bool:
    return "DATABRICKS_RUNTIME_VERSION" in os.environ
```
Databricks define esa variable de entorno en todo su cómputo. Con esto el mismo código se comporta distinto donde
hace falta (por ejemplo, liquid clustering sólo existe en Databricks).

**Bloque 3: `ScaleProfile`, los parámetros físicos de la flota real** (inversor de 2,5 MW, panel de 550 Wp, tasa de
fallas). Son "perillas" del generador agrupadas en un solo lugar.

**Bloque 4: `ProjectConfig`, el corazón.**
```python
@dataclass(frozen=True)
class ProjectConfig:
    catalog: str = "andes_viento"
    schema_prefix: str = ""          # en local: "andes_" para no chocar con otras bases
    volume: str = "raw"
    base_path: str | None = None     # override local (por defecto /Volumes/...)
    scale_factor: float = 1.0
    start_date: date = date(2023, 1, 1)
    end_date: date = date(2026, 9, 30)
    seed: int = 2009                 # año de fundación de la empresa
    profile: ScaleProfile = field(default_factory=ScaleProfile)

    def schema(self, layer: str) -> str:
        if layer not in LAYERS:
            raise ValueError(f"Capa desconocida: {layer}. Válidas: {LAYERS}")
        return f"{self.catalog}.{self.schema_prefix}{layer}"

    def table(self, layer: str, name: str) -> str:
        return f"{self.schema(layer)}.{name}"
```
- `cfg.table("gold", "dim_park")` → en Databricks `andes_viento_dev.gold.dim_park`; en local
  `spark_catalog.andes_gold.dim_park`. **Ningún módulo escribe un nombre de tabla a mano**: todos llaman a
  `cfg.table(...)`. Así el mismo código corre en dev, prod y local.
- `schema()` valida la capa: un `cfg.table("gol", ...)` falla al instante con un mensaje claro y no crea un esquema `gol`.
- `seed = 2009`: la semilla de todo el azar. Misma semilla, mismos datos (capítulo 06).
- `field(default_factory=ScaleProfile)`: un default que es un objeto se crea con una fábrica. Con
  `profile = ScaleProfile()` todas las instancias compartirían el mismo objeto (el bug `B` que detecta ruff).

**Bloque 5: rutas de archivos.**
```python
    @property
    def root_path(self) -> str:
        if self.base_path:
            return self.base_path.rstrip("/")
        return f"/Volumes/{self.catalog}/{self.schema_prefix}landing/{self.volume}"

    def landing_path(self, source: str) -> str:   return f"{self.root_path}/landing/{source}"
    def checkpoint_path(self, name: str) -> str:  return f"{self.root_path}/_checkpoints/{name}"
    def schema_location(self, source: str) -> str: return f"{self.root_path}/_schemas/{source}"
```
En Databricks todo vive en un volumen de UC (`/Volumes/andes_viento_dev/landing/raw/...`); en local, en una carpeta
temporal (`base_path`). `_checkpoints` y `_schemas` son la "memoria" de Auto Loader (capítulo 09): qué archivos ya
leyó y qué esquema infirió.

**Bloque 6: escala.**
```python
    def units(self, n_real: int) -> int:
        return max(1, int(round(n_real * self.scale_factor)))
```
Con `scale_factor = 0.1`, un parque de 45 turbinas tiene 4 (o 5). El `max(1, ...)` garantiza que **ningún parque
desaparece** a escala chica: la historia necesita los 13 parques ([ADR-002](../docs/adr/ADR-002-scale-factor-por-flota.md)).

**Bloque 7: dos fábricas de configuración.**
```python
def local_config(base_path: str, scale_factor: float = 0.02, **kwargs) -> ProjectConfig:
    return ProjectConfig(catalog="spark_catalog", schema_prefix="andes_", base_path=base_path,
                         scale_factor=scale_factor, **kwargs)

def config_from_widgets(dbutils) -> ProjectConfig:
    def get(name: str, default: str) -> str:
        try:
            value = dbutils.widgets.get(name)
            return value if value != "" else default
        except Exception:
            return default
    return ProjectConfig(catalog=get("catalog", "andes_viento"), scale_factor=float(get("scale_factor", "0.1")),
                         start_date=date.fromisoformat(get("start_date", "2023-01-01")),
                         end_date=date.fromisoformat(get("end_date", "2026-09-30")))
```
- En local, Spark OSS no tiene Unity Catalog: el "catálogo" es `spark_catalog` y los esquemas llevan el prefijo
  `andes_`.
- En Databricks, los parámetros del job llegan a los widgets del notebook (capítulo 15). El `try/except` y el `""`
  hacen que el notebook también funcione abierto a mano, sin job.

### 5. `utils/spark.py`: Spark local con Delta

```python
def get_spark(app_name: str = "andes_viento") -> SparkSession:
    active = SparkSession.getActiveSession()
    if active is not None:
        return active
    if is_databricks():
        return SparkSession.builder.getOrCreate()
    return build_local_spark(app_name)

def build_local_spark(app_name="andes_viento-local", warehouse_dir=None) -> SparkSession:
    from delta import configure_spark_with_delta_pip
    builder = (SparkSession.builder.appName(app_name).master("local[*]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .config("spark.databricks.delta.properties.defaults.enableChangeDataFeed", "true")
        .config("spark.databricks.delta.schema.autoMerge.enabled", "true")
        .config("spark.sql.streaming.schemaInference", "true"))
    if warehouse_dir:
        builder = (builder.config("spark.sql.warehouse.dir", warehouse_dir)
                   .config("spark.sql.catalogImplementation", "hive")
                   .config("spark.hadoop.javax.jdo.option.ConnectionURL",
                           f"jdbc:derby:;databaseName={warehouse_dir}/metastore_db;create=true"))
    if os.environ.get("ANDES_DELTA_JARS_IN_CLASSPATH") == "1":
        return builder.getOrCreate()
    return configure_spark_with_delta_pip(builder).getOrCreate()
```
| línea | por qué |
|---|---|
| `local[*]` | todos los núcleos de tu máquina |
| `shuffle.partitions = 8` | el default (200) es para clústeres: con datos chicos, 200 particiones = 200 tareas vacías y los tests tardan el triple |
| `session.timeZone = UTC` | **convención del proyecto: todo `*_ts` está en UTC.** Sin esto, Spark usa la zona de tu computadora y las fechas cambian según quién corra el test |
| `ui.enabled = false` | no levantar la interfaz web de Spark en cada test |
| `enableChangeDataFeed` | igual que en Databricks: las tablas guardan qué filas cambiaron |
| `schema.autoMerge` | un MERGE puede agregar columnas nuevas (el *schema drift* del capítulo 09) |
| `streaming.schemaInference` | Spark OSS no infiere el esquema en streaming por defecto; Auto Loader local lo necesita |
| metastore Derby | sin un metastore, las tablas creadas con `saveAsTable` se olvidan al cerrar Spark |
| `ANDES_DELTA_JARS_IN_CLASSPATH` | escape para entornos sin internet (los JARs ya instalados a mano) |

### 6. `utils/delta.py`: operaciones Delta reutilizables

**`create_table_if_not_exists`**: crea la tabla vacía con el esquema de un DataFrame. En Databricks agrega
**liquid clustering** (`clusterBy`, ordenar físicamente los archivos por las columnas por las que más se filtra) y
*deletion vectors* (borrar filas sin reescribir archivos). En local no existen: se saltean con `is_databricks()`.

**`merge_upsert`**:
```python
    cond = " AND ".join(f"t.`{k}` <=> s.`{k}`" for k in keys)
    ...
    if sequence_col:
        seq = f"s.`{sequence_col}` >= t.`{sequence_col}`"
        matched_cond = f"({matched_cond}) AND {seq}" if matched_cond else seq
    target.alias("t").merge(source.alias("s"), cond) \
          .whenMatchedUpdateAll(condition=matched_cond).whenNotMatchedInsertAll().execute()
```
- `<=>` es la **igualdad que tolera NULL** (`NULL <=> NULL` es verdadero; `NULL = NULL` es NULL, o sea "no"). Si una
  clave puede ser nula, con `=` cada corrida insertaría un duplicado.
- `sequence_col`: el registro de la fuente sólo pisa al de la tabla si es **igual o más nuevo**. En CDC los eventos
  llegan desordenados; sin esto, un cambio viejo que llega tarde deshace uno nuevo.

**`overwrite_partitions`**: `mode("overwrite")` + `replaceWhere` = "reemplazá **sólo** las filas que cumplen este
predicado". Es el patrón de los hechos incrementales (capítulo 12): reprocesar los últimos 3 días sin tocar los otros
1.300.

**`merge_cdc`**: como `merge_upsert` pero con **bajas**: si el evento dice `is_deleted`, borra la fila. Las tres
ramas (`whenMatchedDelete`, `whenMatchedUpdateAll`, `whenNotMatchedInsertAll`) se condicionan a que el evento sea más
nuevo y no sea una baja de algo que no existe.

**`optimize`**: compacta archivos chicos. El job de mantenimiento lo usa (capítulo 16).

### 7. `utils/audit.py`: medir y registrar cada paso

```python
@contextmanager
def audited(cfg, spark, step: str, target: str):
    start = time.time()
    result: dict = {"rows_written": None}
    try:
        yield result
    except Exception as exc:
        log_run(cfg, spark, step=step, target=target, status="FAILED",
                duration_s=time.time() - start, error=str(exc)[:4000])
        raise
    log_run(cfg, spark, step=step, target=target, status="SUCCEEDED",
            rows_written=result.get("rows_written"), duration_s=time.time() - start)
```
Se usa así:
```python
with audited(cfg, spark, "bronze", "bronze.*") as res:
    res["rows_written"] = ingest_all(spark, cfg)
```
Cada paso queda en `ops.pipeline_runs` (paso, estado, filas, segundos, error). El `raise` después de registrar es
clave: **se registra la falla y se vuelve a lanzar**, para que el job igual termine en rojo.

`get_watermark` / `set_watermark` guardan "hasta qué fecha procesé" por pipeline en `ops.watermarks` (los hechos
incrementales los usan en el capítulo 12).

### 8. `quality/expectations.py`: reglas por fila

**Bloque 1: la regla.**
```python
@dataclass(frozen=True)
class Rule:
    name: str
    expr: str                    # SQL que tiene que ser VERDADERO para una fila válida
    action: str = "quarantine"   # warn | quarantine | fail

    def __post_init__(self):
        if self.action not in ("warn", "quarantine", "fail"):
            raise ValueError(f"Acción inválida: {self.action}")
```
`__post_init__` valida al crear: un `Rule(..., "quarentine")` mal escrito falla enseguida y no silenciosamente.

**Bloque 2: marcar qué reglas falla cada fila.**
```python
def tag_failures(df, rules):
    checks = [F.when(~F.coalesce(F.expr(r.expr), F.lit(False)), F.lit(r.name)) for r in rules]
    return df.withColumn(DQ_COL, F.filter(F.array(*checks), lambda x: x.isNotNull()))
```
Agrega una columna `_dq_failed_rules` con un array de nombres de reglas incumplidas. **`coalesce(expr, false)` es la
línea más importante:** en SQL, `NULL > 0` no es ni verdadero ni falso, es NULL. Sin el `coalesce`, una fila con el
valor nulo "no fallaría" ninguna regla y pasaría como válida.

**Bloque 3: contar en una pasada.** `summarize` hace **un solo** `agg` con una suma por regla. Diez `filter().count()`
serían diez lecturas completas de millones de filas.

**Bloque 4: `enforce`, todo junto.**
1. marca las fallas y cuenta;
2. escribe una fila por regla en `ops.dq_results` (para el monitoreo y para el gate);
3. si alguna regla `fail` falló, **corta todo** con `DataQualityError`;
4. separa las filas con fallas `quarantine` o `fail` y las guarda en `ops.quarantine` como JSON con el motivo
   (JSON porque cada tabla tiene columnas distintas y la cuarentena es una sola tabla);
5. devuelve las válidas, sin la columna auxiliar.

### 9. `setup.py`: esquemas y tablas de operación

```python
def create_namespace(spark, cfg):
    if is_databricks():
        try:
            spark.sql(f"CREATE CATALOG IF NOT EXISTS {cfg.catalog} ...")
        except Exception as exc:     # Free Edition: el catálogo se crea a mano por SQL
            print(f"No se pudo crear el catálogo ... Se asume que ya existe.")
    for layer in LAYERS:
        if is_databricks():
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS {cfg.schema(layer)} COMMENT '{LAYER_COMMENTS[layer]}'")
        else:
            spark.sql(f"CREATE DATABASE IF NOT EXISTS {cfg.schema(layer)}")
    ensure_ops_tables(spark, cfg)
    if is_databricks():
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {cfg.schema('landing')}.{cfg.volume} ...")
```
- Intenta crear el catálogo pero **no falla si no puede** (Free Edition): el catálogo es un prerrequisito manual.
- Todo es `IF NOT EXISTS`: **idempotente**. El job lo corre en cada ejecución.
- `ensure_ops_tables` crea las 5 tablas de `ops` **antes** de que corran las tareas en paralelo. Si dos tareas del
  *for each* intentaran crear `ops.dq_results` a la vez, una fallaría con `TABLE_ALREADY_EXISTS`.
- `drop_layers` (para un *full refresh*) borra bronze, silver, gold y ops, **no** el volumen con los archivos.

### 10. `tests/conftest.py` y el primer test

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    wh = tmp_path_factory.mktemp("warehouse")
    session = build_local_spark("andes-tests", warehouse_dir=str(wh))
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()

@pytest.fixture()
def cfg(tmp_path, spark):
    prefix = f"t{abs(hash(str(tmp_path))) % 10**8}_"
    c = replace(local_config(str(tmp_path / "volume"), scale_factor=0.02), schema_prefix=prefix)
    from andes_viento.setup import create_namespace
    create_namespace(spark, c)
    return c
```
- **`scope="session"`**: una sola sesión de Spark para todos los tests (arrancarla tarda ~20 s).
- **`cfg` con prefijo único por test**: cada test escribe en sus propios esquemas (`t12345678_bronze`...), así un test
  no ve las tablas de otro.
- `sys.path.insert`: los tests importan el código de `src/` aunque no hayas hecho `pip install -e`.

`tests/test_quality.py` prueba `enforce` con 3 filas: la del `NULL` va a cuarentena, la negativa sólo avisa (`warn`)
y con una regla `fail` se lanza `DataQualityError`.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| un `ProjectConfig` inmutable | variables globales o leer widgets en cada módulo | los módulos dependerían de Databricks (no se podrían testear) y cualquiera podría cambiar un valor a mitad de corrida |
| framework de calidad propio | Great Expectations / DQX | se quería entender el mecanismo (son 100 líneas) y que corra igual en local; en LDP se usan las *expectations* nativas (capítulo 16) |
| auditoría en una tabla Delta | logs de texto | una tabla se consulta con SQL ("¿qué paso tardó más esta semana?") |
| `merge_upsert` con `<=>` | `=` | `=` duplica filas cuando la clave tiene NULL |

## ✅ Probalo

```bash
pip install -e ".[dev]"
ruff check src tests          # All checks passed!
pytest                        # 1 passed
python -c "from andes_viento.config import ProjectConfig as P; print(P(catalog='andes_viento_dev').table('gold','dim_park'))"
# andes_viento_dev.gold.dim_park
```

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `ModuleNotFoundError: andes_viento` | falta `__init__.py` o la instalación editable | revisá `src/andes_viento/__init__.py`; `pip install -e ".[dev]"` |
| `Another instance of Derby may have already booted the database` | quedó otra sesión de Spark abierta con el mismo metastore | cerrá otros Python/pytest; borrá `metastore_db/` |
| `ANALYSIS_EXCEPTION: ... is not a Delta table` | la sesión no tiene la extensión Delta | revisá las dos líneas `config` de Delta |
| `F821 undefined name 'spark'` en ruff | ruff está revisando un notebook | `extend-exclude = ["notebooks", ...]` |
| el test tarda minutos | `shuffle.partitions` en 200 | `.config("spark.sql.shuffle.partitions", "8")` |

## 📍 Punto de control

```bash
git add -A && git commit -m "etapa-01: cimientos" && git push -u origin etapa-01
git diff etapa-01 HEAD --stat        # contra la referencia (remoto "referencia", ver el README del curso)
```

## 🏋️ Ejercicio

1. Agregá a `ProjectConfig` un método `volume_path()` que devuelva `/Volumes/<catálogo>/<prefijo>landing/<volumen>` y un
   test que lo verifique con `catalog="x"`.
2. Escribí un test nuevo para `enforce` donde una regla evalúe NULL (`valor > 0` con valor nulo) y verificá que la
   fila va a cuarentena. Después sacá el `coalesce` de `tag_failures` y mirá cómo el test falla. Volvé a ponerlo.
3. Usá `audited` en un script que cuente hasta un millón con Spark y consultá `ops.pipeline_runs` en local.
