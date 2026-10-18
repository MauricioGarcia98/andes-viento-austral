# 04 · La plataforma Databricks

## 🎯 Objetivo

Entender las piezas de Databricks que usa el proyecto **tocándolas a mano** antes de automatizarlas: el workspace,
Unity Catalog, el cómputo, los notebooks, los jobs y la CLI. Al final vas a tener creado el catálogo
`andes_viento_dev` (donde vive todo el curso) y la CLI conectada.

## 📚 Conceptos

### El workspace y la cuenta

Una **cuenta** de Databricks tiene uno o más **workspaces** (el sitio web donde trabajás, con una URL propia: el
*host*). Free Edition te da una cuenta con un workspace.

**Límites de Free Edition que condicionan el diseño:**

| límite | consecuencia en el proyecto |
|---|---|
| sólo cómputo serverless (no hay clústeres propios) | no se declaran clústeres en ningún lado |
| cuota diaria de cómputo | se trabaja con `scale_factor = 0.1` (37 turbinas) |
| 5 corridas de jobs a la vez | las tareas en paralelo esperan turno (no es un error) |
| 1 App por workspace | la App vive sólo en el target `dev` |
| 500 tablas por metastore (con las borradas ~7 días) | no recrear lo que no cambió; evitar `full_refresh` |
| el almacenamiento es *Default Storage* | los catálogos se crean por SQL, no por API |

### Unity Catalog: dónde viven los datos

```
metastore (uno por región de la cuenta)
└── catálogo           andes_viento_dev          ← uno por ambiente (dev / prod)
    ├── esquema        bronze, silver, gold, ops, landing
    │   ├── tabla      gold.dim_park              ← "managed": UC decide dónde guardar los archivos
    │   ├── vista      gold.v_park_daily          ← una consulta guardada
    │   ├── metric view gold.mv_generacion        ← métricas oficiales (capítulo 18)
    │   ├── función    gold.fn_explicar_desvio    ← SQL reutilizable (capítulo 18)
    │   └── volumen    landing.raw                ← una carpeta de archivos: /Volumes/andes_viento_dev/landing/raw
    └── information_schema                        ← el catálogo describiéndose a sí mismo (vistas de metadatos)
```

- Una tabla se nombra con **tres partes**: `catálogo.esquema.tabla`.
- **Permisos:** para leer una tabla hace falta `USE CATALOG` sobre el catálogo, `USE SCHEMA` sobre el esquema y
  `SELECT` sobre la tabla. El que la crea es **dueño** (*owner*) y puede todo. En Free Edition vos sos admin.
- **Tablas del sistema** (`system.*`): uso y costos (`system.billing.usage`), auditoría, linaje. Sólo lectura.

### El cómputo

| tipo | para qué | en el proyecto |
|---|---|---|
| **serverless (notebooks y jobs)** | correr Python y SQL; Databricks lo prende y apaga solo | todas las tareas del job |
| **SQL warehouse** | correr SQL para el SQL Editor, dashboards y Genie | *Serverless Starter Warehouse* (ya viene creado) |

### Notebooks

Un documento con celdas. Cada celda es Python por defecto; con `%sql` arriba es SQL; con `%md`, texto. Dentro de un
notebook ya existen:
- `spark`: la sesión de Spark, ya conectada a Unity Catalog.
- `dbutils`: utilidades (archivos, *widgets*, secretos, valores entre tareas).
- `display(df)`: muestra un DataFrame como tabla interactiva.
- `%run ./otro_notebook`: ejecuta otro notebook en el mismo contexto (comparte variables).
- **widgets**: parámetros con nombre (`dbutils.widgets.text("catalog", "andes_viento_dev")`). Cuando un job corre el
  notebook, los parámetros del job llenan los widgets.

### Jobs

Un **job** es un conjunto de **tareas** con dependencias (un grafo). Cada corrida (**run**) guarda el estado y los
logs de cada tarea. Si falla una, se puede **reparar** (volver a correr sólo lo que falló). El job del proyecto tiene
12 tareas, una condición y tres *for each* (capítulo 15).

### Archivos en el workspace

| dónde | qué | ejemplo |
|---|---|---|
| **Workspace** (`/Workspace/Users/<vos>/...`) | código y notebooks | lo que sube el bundle |
| **Git folder** | una carpeta del workspace conectada a GitHub | alternativa web al bundle |
| **Volumen** (`/Volumes/<cat>/<esq>/<vol>/...`) | datos en archivos, gobernados por UC | los archivos crudos de landing |

### La CLI y el SDK

- **CLI** (`databricks ...`): para desplegar bundles, correr jobs y llamar a cualquier API (`databricks api get ...`).
- **SDK de Python** (`from databricks.sdk import WorkspaceClient`): lo mismo, desde un script. Los scripts de Genie lo
  usan. Toma las credenciales del mismo lugar que la CLI.

## 🧱 Paso a paso

### 1. Crear la cuenta y recorrer el workspace

`https://www.databricks.com/learn/free-edition` → **Sign up**. Anotá la URL del workspace (tu *host*). Abrí cada menú
de la izquierda una vez: **Workspace, Catalog, SQL Editor, Jobs & Pipelines, Dashboards, Genie, Compute**.

### 2. Crear el catálogo del curso

**SQL Editor** → arriba a la derecha elegí **Serverless Starter Warehouse** → corré:

```sql
CREATE CATALOG IF NOT EXISTS andes_viento_dev COMMENT 'Andes Viento Austral (dev)';
```

**Por qué SQL y no la API:** en Free Edition el almacenamiento es *Default Storage*, y la API que usan los bundles para
crear catálogos falla con `Metastore storage root URL does not exist`. Por SQL funciona. Por eso en el proyecto el
catálogo es un **prerrequisito manual** y el código sólo crea esquemas para adentro
([ADR-007](../docs/adr/ADR-007-catalogo-por-sql.md)).

### 3. Practicar Unity Catalog a mano (y después borrarlo)

```sql
CREATE SCHEMA andes_viento_dev.practica COMMENT 'para probar';
CREATE TABLE andes_viento_dev.practica.parques (codigo STRING, nombre STRING, mw DOUBLE);
INSERT INTO andes_viento_dev.practica.parques VALUES ('LEO','Cañadón León',202.5), ('SUS','Susques Solar',220);
SELECT * FROM andes_viento_dev.practica.parques;

DESCRIBE HISTORY andes_viento_dev.practica.parques;     -- Delta guarda una versión por cada cambio
UPDATE andes_viento_dev.practica.parques SET mw = 205 WHERE codigo = 'LEO';
SELECT * FROM andes_viento_dev.practica.parques VERSION AS OF 1;   -- "time travel": cómo estaba antes

COMMENT ON TABLE andes_viento_dev.practica.parques IS 'Parques de prueba';
ALTER TABLE andes_viento_dev.practica.parques ALTER COLUMN mw COMMENT 'Potencia instalada en MW';

SELECT table_name, comment FROM andes_viento_dev.information_schema.tables WHERE table_schema = 'practica';
```

Mirá la tabla en **Catalog → andes_viento_dev → practica → parques**: pestañas *Overview* (los comentarios),
*Sample data*, *History*, *Lineage*. Genie lee esos comentarios (capítulo 17).

Probá un volumen:
```sql
CREATE VOLUME andes_viento_dev.practica.archivos;
```
**Catalog → practica → archivos → Upload to this volume** → subí un CSV cualquiera. Después:
```sql
SELECT * FROM read_files('/Volumes/andes_viento_dev/practica/archivos/', format => 'csv', header => true);
```

Al final:
```sql
DROP SCHEMA andes_viento_dev.practica CASCADE;
```

### 4. Un notebook con widgets y `%run`

**Workspace → tu carpeta → Create → Notebook** (`config`):
```python
dbutils.widgets.text("catalog", "andes_viento_dev", "Catálogo")
catalog = dbutils.widgets.get("catalog")
print("trabajo en", catalog)
```
Otro notebook (`principal`) en la misma carpeta:
```python
%run ./config
```
```python
display(spark.sql(f"SHOW SCHEMAS IN {catalog}"))
```
Corré `principal`: ves los esquemas. **Así funcionan los notebooks del proyecto:** cada uno hace `%run ./_bootstrap`,
que define los widgets y la configuración (capítulo 15).

### 5. Un job a mano

**Jobs & Pipelines → Create → Job** → tarea `t1` tipo *Notebook* → elegí `principal` → **Create task** → **Run now**.
Mirá la corrida: estado, duración, la salida. En la pestaña **Parameters** del job agregá `catalog = andes_viento_dev`:
llega al widget del notebook. Borrá el job al terminar. En el capítulo 15 este mismo job se escribe como código (YAML).

### 6. Instalar y conectar la CLI

- macOS: `brew tap databricks/tap && brew install databricks`
- Linux o macOS sin Homebrew: `curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh`
- Windows: `winget install Databricks.DatabricksCLI`

```bash
databricks --version                                   # ≥ 0.250 (el proyecto se probó con 1.21)
databricks auth login --host https://<tu-workspace>     # perfil: DEFAULT · se abre el navegador
databricks current-user me                              # tu usuario
databricks catalogs list                                # aparece andes_viento_dev
databricks warehouses list                              # el Serverless Starter Warehouse y su ID
```

**Cómo funciona la autenticación:** `auth login` usa **OAuth**: iniciás sesión en el navegador y la CLI guarda una
credencial que se renueva sola en `~/.databrickscfg` (y una caché en `~/.databricks/`). No hay que copiar tokens. El
SDK de Python lee el mismo archivo. Para GitHub Actions sí hace falta un token (capítulo 22), porque no hay navegador.

**Por qué el perfil se llama `DEFAULT`:** la CLI y el SDK usan ese perfil si no les decís otro. Con otro nombre,
exportá `DATABRICKS_CONFIG_PROFILE=<nombre>` o pasá `-p <nombre>`.

### 7. Llamar a una API cualquiera

```bash
databricks api get /api/2.1/unity-catalog/schemas --json '{"catalog_name": "andes_viento_dev"}'
```
Todo lo que hace la interfaz web es una llamada a la API REST. `databricks api` sirve para lo que no tiene un comando
propio (por ejemplo, los Genie Agents).

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| un catálogo por ambiente (`andes_viento_dev`, `andes_viento`) | un catálogo con esquemas `dev_gold`, `prod_gold` | los permisos se dan por catálogo; mezclar dev y prod en uno facilita romper prod por error |
| tablas *managed* | tablas *external* con una ruta propia | en Free Edition no hay storage propio; managed es más simple y UC maneja el ciclo de vida |
| serverless | clústeres | en Free Edition no hay clústeres; en un workspace pago, serverless arranca en segundos y no hay que mantener versiones |
| OAuth para la CLI | un token personal (PAT) | OAuth no deja una contraseña larga guardada en texto plano para siempre |

## ✅ Probalo

- `databricks catalogs list` muestra `andes_viento_dev`.
- En el SQL Editor, `SHOW SCHEMAS IN andes_viento_dev` muestra `default` e `information_schema` (el esquema
  `practica` ya lo borraste).

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `Metastore storage root URL does not exist` | creaste el catálogo por API o desde la interfaz de Catalog | creálo con SQL (paso 2) |
| `PERMISSION_DENIED` | estás en otro workspace o con otro usuario | `databricks current-user me` |
| la consulta tarda en arrancar | el warehouse estaba apagado (se apaga solo para ahorrar) | esperá ~10 s: se prende solo |
| `Error: cannot configure default credentials` | la CLI no tiene perfil | `databricks auth login --host ...` |
| `databricks: command not found` | no está en el `PATH` | reabrí la terminal; en Linux puede quedar en `/usr/local/bin` |
| la CLI dice versión `0.18` | es el paquete viejo de Python `databricks-cli` | `pip uninstall databricks-cli` e instalá la nueva |

## 📍 Punto de control

Catálogo `andes_viento_dev` vacío, CLI conectada (`databricks current-user me` funciona) y un rato de práctica con
tablas, volúmenes, notebooks y jobs a mano.

## 🏋️ Ejercicio

1. Creá un esquema `prueba`, una tabla con 3 filas y otorgá `SELECT` a `account users`
   (`GRANT SELECT ON TABLE ... TO \`account users\``). Mirá la pestaña *Permissions*.
2. Con `SHOW TABLES DROPPED IN andes_viento_dev.prueba`, después de borrar la tabla, verificá que sigue en
   retención. Recuperala con `UNDROP TABLE`.
3. Consultá cuánto cómputo usaste hoy:
   `SELECT usage_date, sum(usage_quantity) FROM system.billing.usage GROUP BY 1 ORDER BY 1 DESC`.
4. Borrá todo lo que creaste.
