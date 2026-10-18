# 03 · Python, entornos, lint y tests

## 🎯 Objetivo

Tener en tu computadora un entorno donde puedas correr **Spark y Delta Lake localmente**, con un linter y un
framework de tests. Es lo que permite probar casi todo el proyecto **antes** de gastar un minuto de cómputo en la
nube: el 60 % de los errores del proyecto original se encontró acá (L1-L8 de la bitácora).

## 📚 Conceptos

| concepto | qué es | por qué lo usamos |
|---|---|---|
| **Python** | el lenguaje del generador, la limpieza (silver) y los scripts | es el lenguaje de PySpark y del SDK de Databricks |
| **entorno virtual (venv)** | una carpeta (`.venv/`) con su propio Python y sus propias librerías | cada proyecto con sus versiones, sin pisar otros proyectos ni el Python del sistema |
| **pip** | el instalador de librerías | |
| **`pyproject.toml`** | el archivo que describe el paquete: nombre, dependencias y configuración de las herramientas | el estándar actual (reemplaza a `setup.py` + `requirements.txt`) |
| **paquete** | una carpeta con `__init__.py` que se puede importar (`import andes_viento`) | la lógica vive en un paquete testeable, no en notebooks |
| **PySpark** | Spark para Python: procesa datos en paralelo | el mismo motor que usa Databricks |
| **Delta Lake (`delta-spark`)** | el formato de tablas con transacciones, MERGE e historia | el formato de todas las tablas de Databricks |
| **Java (JDK)** | Spark está escrito en Scala y corre sobre la máquina virtual de Java | PySpark arranca un proceso Java por detrás |
| **ruff** | un *linter*: revisa el código sin ejecutarlo | atrapa imports sin usar, variables mal escritas y estilo inconsistente |
| **pytest** | el framework de tests | cada problema de datos tiene su test |

## 🧱 Paso a paso

### 1. Instalar Python 3.10 o más nuevo

- macOS: `brew install python@3.11` · Ubuntu 22.04+: ya viene (`sudo apt install python3-venv python3-pip`) ·
  Windows: python.org → instalador → marcá **Add python.exe to PATH**.
- Verificá: `python3 --version` (en Windows, `python --version`).

**Por qué 3.10+:** el código usa sintaxis moderna (`str | None` en lugar de `Optional[str]`) y PySpark 4 lo exige.

### 2. Instalar Java 17

- macOS: `brew install openjdk@17` y seguí las instrucciones que imprime para el `PATH`.
- Ubuntu: `sudo apt install openjdk-17-jdk`.
- Windows: *Eclipse Temurin 17* desde adoptium.net (marcá **Set JAVA_HOME**).
- Verificá: `java -version` → `17.x` o más nuevo.

### 3. Crear el entorno virtual (en tu repo `mi-andes-viento`)

```bash
cd mi-andes-viento
python3 -m venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
which python                       # tiene que terminar en mi-andes-viento/.venv/bin/python
python -m pip install --upgrade pip
```

**Qué cambia al activar:** `python` y `pip` pasan a ser los de `.venv`. El prompt muestra `(.venv)`. Cada vez que
abras una terminal nueva hay que volver a activarlo.

### 4. Probar Spark y Delta sin el proyecto todavía

```bash
pip install "pyspark==4.0.1" "delta-spark==4.0.0" pytest ruff pyyaml
python - <<'EOF'
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession
b = (SparkSession.builder.master("local[2]").appName("prueba")
     .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
     .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"))
spark = configure_spark_with_delta_pip(b).getOrCreate()
spark.range(5).write.format("delta").mode("overwrite").save("/tmp/prueba_delta")
print(spark.read.format("delta").load("/tmp/prueba_delta").count())   # → 5
EOF
```

**Qué hace cada parte:**
- `master("local[2]")`: Spark en tu máquina con 2 hilos. En Databricks el *master* es un clúster (o serverless).
- Las dos líneas `config(...)` activan Delta: la extensión agrega el SQL de Delta (`MERGE`, `OPTIMIZE`...) y el
  catálogo hace que `CREATE TABLE` cree tablas Delta.
- `configure_spark_with_delta_pip`: le agrega al Spark los JARs (librerías Java) de Delta. La primera vez los descarga
  (~1 minuto).

**Por qué versiones fijas (`==`):** cada versión de `delta-spark` funciona con una versión exacta de Spark (Delta
4.0 ↔ Spark 4.0). Con `>=` un día se instala un Spark nuevo que no es compatible y todo falla sin que hayas cambiado
nada.

### 5. Cómo se ve un `pyproject.toml` (lo escribís en la etapa 1)

```toml
[build-system]                     # cómo se construye el paquete
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "andes_viento"              # el nombre del paquete
requires-python = ">=3.10"
dependencies = []                  # dependencias OBLIGATORIAS: ninguna (en Databricks Spark ya viene)

[project.optional-dependencies]   # grupos que se instalan sólo si se piden
dev   = ["pyspark==4.0.1", "delta-spark==4.0.0", "pytest>=8", "ruff>=0.6", "pyyaml>=6"]
genie = ["databricks-sdk>=0.60"]

[tool.setuptools.packages.find]
where = ["src"]                    # el código está en src/ (ver "Por qué")
```

Se instala con `pip install -e ".[dev,genie]"`:
- **`-e` (editable):** en vez de copiar el código al entorno, instala un "acceso directo" a tu carpeta `src/`. Editás
  un archivo y el cambio se ve sin reinstalar.
- **`.[dev,genie]`:** el paquete de esta carpeta (`.`) más los grupos `dev` y `genie`.
- **`dependencies = []`:** en Databricks no se instala nada: Spark, Delta y el SDK ya vienen en el runtime. Si
  pusieras `pyspark` como dependencia obligatoria, en Databricks se instalaría encima del que viene y podría romperlo.

### 6. ruff y pytest

```bash
ruff check src tests          # revisar
ruff check src tests --fix    # arreglar solo lo que se puede arreglar solo (por ejemplo ordenar imports)
pytest                        # correr todos los tests
pytest -m "not integration"   # sólo los rápidos (marker "integration" = los lentos)
pytest tests/test_x.py -k nombre -x -vv   # uno solo; -x: parar en el primer error; -vv: más detalle
```

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| layout `src/` (`src/andes_viento/...`) | el paquete en la raíz | con `src/` los tests importan el paquete **instalado**, igual que en producción; en la raíz, Python podría importar por accidente archivos sueltos |
| `venv` | conda, poetry, uv | `venv` viene con Python y alcanza; las otras sirven, pero son una herramienta más para aprender |
| la lógica en un paquete | todo en notebooks | un notebook no se puede testear con pytest ni revisar bien en un PR |
| ruff | flake8 + isort + black | ruff hace lo de los tres, en una sola herramienta y mucho más rápido |
| tests con Spark local | sólo probar en Databricks | cada prueba en la nube cuesta minutos y cuota; en local, segundos |

## ✅ Probalo

```bash
python -c "import pyspark, delta; print(pyspark.__version__)"    # 4.0.1
ruff --version && pytest --version
```
Y el script del paso 4 imprime `5`.

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `AttributeError: install_layout` al instalar pyspark (Debian/Ubuntu) | estás usando el `pip` del sistema, no el del venv | activá el venv (`which python` → `.venv`). Error L1 de la bitácora |
| `JAVA_GATEWAY_EXITED` / `Java gateway process exited before sending its port number` | no hay Java o es viejo | paso 2; `echo $JAVA_HOME` |
| `UnsupportedClassVersionError` | Java 8 u 11 | Java 17+ |
| se queda colgado descargando JARs | proxy o red corporativa | probá desde otra red; los JARs se cachean en `~/.ivy2` |
| `ModuleNotFoundError: andes_viento` | no hiciste `pip install -e` o no activaste el venv | `pip install -e ".[dev]"` |
| `python: command not found` (macOS/Linux) | el comando es `python3` | usá `python3` para crear el venv; adentro, `python` ya existe |

## 📍 Punto de control

Un `.venv` en `mi-andes-viento` donde Spark local escribe y lee una tabla Delta.

## 🏋️ Ejercicio

En una carpeta de práctica (no en tu repo):
1. Escribí `suma.py` con `def ratio(a, b): return a / b if b else None`.
2. Escribí `test_suma.py` con dos tests: uno normal y uno con `b = 0`.
3. Corré `pytest` y después `ruff check .`. Agregá un `import os` que no uses y mirá qué dice ruff.
4. Con Spark local, creá un DataFrame con una columna `fecha` como texto `"15/07/2025"` y convertila a fecha
   (pista: `to_date(col, "dd/MM/yyyy")`). En el capítulo 10 vas a hacer esto con tres formatos mezclados.
