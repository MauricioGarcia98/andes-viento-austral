# 10 · Replicar el proyecto desde cero (por terminal)

> **Para quién es esta guía:** para alguien que quiere tener el proyecto completo funcionando en su propio
> workspace de Databricks, usando la terminal. No hace falta saber Databricks: cada paso explica **qué hace**,
> **por qué** se hace, **cómo verificar** que salió bien y **qué hacer si falla**.
>
> ¿Preferís no usar la terminal? Seguí la [guía desde la web](11_guia_desde_la_web.md). Llegás al mismo lugar.
>
> ¿Querés **escribirlo vos** en lugar de desplegar el código terminado? Seguí el curso [construir/](../construir/README.md).
>
> ¿No entendés una palabra? Está en el [glosario](15_glosario.md) (sección "Conceptos de la plataforma").

## El mapa: qué vas a tener al final

```
 Tu computadora                           Tu workspace de Databricks (Free Edition)
 ──────────────                           ─────────────────────────────────────────
 repo clonado ──(databricks bundle deploy)──▶ código + 3 jobs + 1 pipeline + 6 dashboards + 1 app
 tests locales                               catálogo andes_viento_dev
 (Spark + Delta)                               ├── landing  (archivos crudos, un volumen)
                                               ├── bronze   (11 tablas)
 scripts/deploy_genie.py ───────────────────▶  ├── silver   (13 tablas)
                                               ├── gold     (19 tablas + 3 vistas + 7 metric views + 7 funciones)
                                               └── ops      (auditoría, calidad, cuarentena)
                                             4 Genie Agents ("Andes · ...") que responden sobre gold
```

Tiempo total estimado la primera vez: **~2 horas**, de las cuales ~45 minutos es esperar al job y ~90 minutos
(opcional) es la evaluación de Genie.

| paso | qué | tiempo |
|---|---|---|
| 1 | Crear la cuenta de Databricks Free Edition | 5 min |
| 2 | Instalar las herramientas (git, Python, Java, Databricks CLI) | 15 min |
| 3 | Clonar el repo y correr los tests locales (opcional pero recomendado) | 15 min |
| 4 | Conectar la CLI con tu workspace | 5 min |
| 5 | Crear los catálogos | 2 min |
| 6 | Validar y desplegar el bundle | 3 min |
| 7 | Correr el job principal | ~45 min |
| 8 | Verificar los datos | 5 min |
| 9 | Desplegar y probar los Genie Agents | 10 min (+90 de evaluación opcional) |
| 10 | Dashboards, App y Genie Code (opcional) | 10 min |
| 11 | Prod (opcional) | ~50 min |
| 12 | CI/CD con GitHub Actions (opcional) | 15 min |

---

## Paso 1 · Crear la cuenta de Databricks Free Edition

**Qué es:** Databricks es una plataforma en la nube para trabajar con datos. *Free Edition* es la versión gratuita:
no pide tarjeta y trae todo lo que usa este proyecto (Unity Catalog, cómputo *serverless*, un SQL warehouse y Genie).

1. Entrá a `https://www.databricks.com/learn/free-edition` → **Sign up**.
2. Registrate con un email (o tu cuenta de Google/Microsoft).
3. Al terminar te abre tu **workspace**: tu espacio de trabajo. Fijate la URL del navegador, se parece a
   `https://dbc-1234abcd-5678.cloud.databricks.com`. **Anotala: es tu "host"** y la vas a usar en el paso 4.

**Cómo verificar:** en el menú de la izquierda ves *Workspace*, *Catalog*, *Jobs & Pipelines*, *SQL Editor*, *Genie*.

**Límites de Free Edition que importan para este proyecto** (explican varias decisiones):
- **Cuota diaria de cómputo**: por eso usamos `scale_factor = 0.1` (37 turbinas en vez de 380).
- **Máximo 5 corridas de jobs al mismo tiempo**: si ves `There are already 5 active runs`, la tarea espera sola.
- **Una sola App** por workspace: la App vive sólo en el target `dev`.
- **500 tablas por metastore** (contando las borradas en los últimos ~7 días): ver [19 · Operación](19_operacion_diaria.md).
- **Los catálogos no se pueden crear por API**, sólo por SQL: por eso existe el paso 5.

---

## Paso 2 · Instalar las herramientas en tu computadora

| herramienta | para qué la usamos | versión que usamos | cómo verificar |
|---|---|---|---|
| **git** | bajar el código | cualquiera reciente | `git --version` |
| **Python** | tests locales y scripts de Genie | 3.10 o más nueva (probado con 3.11 y 3.13) | `python3 --version` |
| **Java** | Spark local (sólo para los tests) | 17 o más nueva | `java -version` |
| **Databricks CLI** | desplegar y correr cosas en el workspace | ≥ 0.250 (probado con 1.21) | `databricks --version` |

### Instalar la Databricks CLI

- **macOS:** `brew tap databricks/tap && brew install databricks`
- **Linux o macOS sin Homebrew:** `curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh`
- **Windows:** `winget install Databricks.DatabricksCLI` (en PowerShell). Después cerrá y abrí la terminal.

> ⚠️ Hay un paquete viejo de Python que también se llama `databricks-cli` (`pip install databricks-cli`). **No es
> este.** Si `databricks --version` muestra algo como `0.18`, desinstalalo y usá la CLI nueva.

### Java (sólo si vas a correr los tests locales)

- macOS: `brew install openjdk@17` · Ubuntu/Debian: `sudo apt install openjdk-17-jdk` · Windows: instalador de
  *Eclipse Temurin 17* (adoptium.net).

---

## Paso 3 · Clonar el repo y probarlo en tu computadora

**Por qué:** antes de gastar cómputo en la nube, conviene comprobar que el código funciona. Los tests corren el
pipeline completo (generar datos → bronze → silver → gold → quality gate) con Spark y Delta en tu máquina.

```bash
git clone https://github.com/MauricioGarcia98/andes-viento-austral.git
cd andes-viento-austral

python3 -m venv .venv               # un entorno aislado de Python para este proyecto
source .venv/bin/activate           # en Windows: .venv\Scripts\activate
pip install -e ".[dev,genie]"       # instala Spark, Delta, pytest, ruff y el SDK de Databricks (~3 min)

ruff check src tests scripts apps   # estilo y errores comunes   → debe decir "All checks passed!"
pytest -m "not integration"         # 27 tests rápidos (~2 min)  → "27 passed"
pytest -m integration               # el pipeline entero en local (~5-10 min) → "1 passed"
```

**Qué tiene que pasar:** los tres comandos terminan sin errores (`passed`, ninguna línea `FAILED`).

**Si falla:**
- `JAVA_HOME is not set` o `Java gateway process exited` → falta Java 17 (paso 2).
- `pip` falla compilando `pyspark` en Debian/Ubuntu (`install_layout`) → asegurate de estar **dentro del venv**
  (`which python` tiene que apuntar a `.venv`). Es el error L1 de la [bitácora](08_bitacora.md).

Qué prueba cada test y por qué: [18 · Pruebas](18_pruebas.md).

---

## Paso 4 · Conectar la CLI con tu workspace

**Qué es:** la CLI necesita saber a qué workspace hablarle y con qué permisos. El método recomendado es **OAuth**:
se abre el navegador, iniciás sesión y la CLI guarda la credencial en tu computadora (en `~/.databrickscfg`).

```bash
databricks auth login --host https://dbc-1234abcd-5678.cloud.databricks.com   # tu host del paso 1
```

1. Te pregunta un nombre de perfil. **Escribí `DEFAULT`** (así los scripts de Python lo encuentran solos).
2. Se abre el navegador → iniciá sesión → *Allow*.
3. Volvé a la terminal.

**Cómo verificar:**
```bash
databricks current-user me      # muestra tu usuario (tu email) → la conexión funciona
```

**Si le pusiste otro nombre al perfil**, exportá `DATABRICKS_CONFIG_PROFILE=<nombre>` antes de correr los scripts.

> 🔒 **Nunca** pegues un token en un archivo del repo, en un commit ni en un chat. La credencial vive en
> `~/.databrickscfg`, en tu carpeta de usuario (fuera del repo). El `.gitignore` excluye `.env` y `genie/deployed_*.json`.

---

## Paso 5 · Crear los catálogos (una sola vez)

**Qué es un catálogo:** en Unity Catalog los datos se organizan en tres niveles: **catálogo → esquema → tabla**
(por ejemplo `andes_viento_dev.gold.dim_park`). El proyecto usa un catálogo por ambiente: `andes_viento_dev`
(desarrollo) y `andes_viento` (producción).

**Por qué a mano:** en Free Edition el almacenamiento es *Default Storage* y la API que usa el bundle falla con
`Metastore storage root URL does not exist`. Por SQL sí funciona ([ADR-007](adr/ADR-007-catalogo-por-sql.md)).

**Opción A (más fácil), desde la web:** menú **SQL Editor** → arriba a la derecha elegí el warehouse
*Serverless Starter Warehouse* → pegá y corré (botón *Run* o Ctrl/Cmd + Enter):

```sql
CREATE CATALOG IF NOT EXISTS andes_viento_dev COMMENT 'Andes Viento Austral (dev)';
CREATE CATALOG IF NOT EXISTS andes_viento     COMMENT 'Andes Viento Austral (prod)';
```

**Opción B, desde la terminal:**
```bash
databricks warehouses list            # copiá el ID del "Serverless Starter Warehouse"
databricks api post /api/2.0/sql/statements --json \
  '{"warehouse_id":"<ID>","statement":"CREATE CATALOG IF NOT EXISTS andes_viento_dev","wait_timeout":"50s"}'
```
(Repetilo con `andes_viento` si vas a usar prod.)

**Cómo verificar:** menú **Catalog** → aparece `andes_viento_dev` (vacío, sólo con `default` e `information_schema`).

---

## Paso 6 · Validar y desplegar el bundle

**Qué es un bundle:** el archivo `databricks.yml` y la carpeta `resources/` describen **como código** todo lo que el
proyecto necesita en el workspace: jobs, pipeline, dashboards, App. "Desplegar" sube el código y crea o actualiza
esos recursos para que coincidan con lo que dice el repo.

**Qué es un target:** una variante del despliegue. `dev` (por defecto) usa el catálogo `andes_viento_dev`, agrega el
prefijo `[dev tu_usuario]` a los nombres y pausa los schedules. `prod` usa `andes_viento` y no agrega prefijo.

```bash
databricks bundle validate -t dev     # revisa el YAML sin cambiar nada → "Validation OK!"
databricks bundle deploy   -t dev     # sube y crea los recursos (~1-2 min)
```

**Qué crea `deploy -t dev`** (12 recursos):

| recurso | nombre en el workspace | dónde lo ves |
|---|---|---|
| esquema | `andes_viento_dev.ldp` | Catalog |
| job principal | `[dev tu_usuario] andes-viento-e2e` | Jobs & Pipelines |
| job diario | `[dev tu_usuario] andes-viento-daily` (pausado) | Jobs & Pipelines |
| job de mantenimiento | `[dev tu_usuario] andes-viento-maintenance` (pausado) | Jobs & Pipelines |
| pipeline declarativo | `[dev tu_usuario] andes-viento-ldp` | Jobs & Pipelines |
| 6 dashboards | `Andes · Dirección · ...`, `Andes · Caso 1 · ...` ... | Dashboards |
| App | `andes-genie-chat` | Compute → Apps |

**Cómo verificar:** la salida termina con `Deployment complete!` y en **Jobs & Pipelines** ves los 3 jobs y el pipeline.

**Si falla:**
- `CATALOG_DOES_NOT_EXIST` → no hiciste el paso 5.
- `An app with the same name already exists` → ya tenés una App con ese nombre (Free Edition permite una). Borrala
  desde Compute → Apps o quitá la App de `databricks.yml` (R9 de la bitácora).
- `warehouse ... not found` → tu warehouse no se llama *Serverless Starter Warehouse*. Cambiá el nombre en
  `variables.warehouse_id.lookup` de `databricks.yml`.

> 📌 **Regla de oro:** cada vez que cambies algo del repo (un SQL, un notebook, un YAML), **volvé a hacer
> `bundle deploy` antes de correr un job**. El job usa lo último que desplegaste, no lo último que guardaste en tu
> computadora. Nos pasó de verdad (R13 en la bitácora): un arreglo hecho a mano se deshizo en la corrida siguiente.

---

## Paso 7 · Correr el job principal

**Qué hace el job `andes-viento-e2e`:** 12 tareas en orden. Genera 3 años y 9 meses de datos sucios de 11 fuentes,
los ingiere, limpia, modela, gobierna, arma la capa semántica y al final verifica 10 invariantes de calidad.

```
setup → should_generate ─(sí)→ generate_data (11 fuentes en paralelo de a 3)
                         └(no)──────────────┐
                                            ▼
        bronze_ingest → silver_reference (8) → silver_telemetry (3) → gold_dimensions → gold_facts → gold_marts
                                                                                                    ├→ governance ─┐
                                                                                                    └→ semantic ───┴→ quality_gate
```

```bash
databricks bundle run andes_e2e -t dev
```

El comando muestra un **Run URL** y espera a que termine (~45 minutos). Podés cerrar la terminal: el job sigue
corriendo en Databricks. Si no querés esperar, agregá `--no-wait`.

**Cómo seguirlo:** abrí el Run URL (o **Jobs & Pipelines → andes-viento-e2e → Runs**) y mirá el grafo: cada tarea
pasa de gris (pendiente) a azul (corriendo) a verde (terminó bien).

**Tiempos reales** (Free Edition, `scale_factor = 0.1`):

| tarea | qué hace | seg |
|---|---|---:|
| `setup` | crea esquemas, volumen y tablas de `ops` | 36 |
| `should_generate` | ¿generar datos? (parámetro `generate`) | 1 |
| `generate_data` | escribe ~3 GB de archivos sucios en `landing` | 654 |
| `bronze_ingest` | Auto Loader: archivos → 11 tablas bronze | 494 |
| `silver_reference` | 8 entidades chicas: activos (SCD2), contratos, precios... | 822 |
| `silver_telemetry` | SCADA, inversores y órdenes de trabajo | 114 |
| `gold_dimensions` | 7 dimensiones (2 con historia SCD2) | 63 |
| `gold_facts` | 5 hechos con pérdidas por causa | 74 |
| `gold_marts` | 9 archivos SQL con los casos de negocio | 57 |
| `governance` | comentarios, PK/FK, tags, máscaras, filtros por parque | 207 |
| `semantic_layer` | 7 metric views + 7 funciones para Genie | 26 |
| `quality_gate` | 10 invariantes: si alguna falla, el job falla | 18 |

**Parámetros útiles** (se pasan con `--params`):

| parámetro | default | para qué |
|---|---|---|
| `generate` | `true` | `false` = no regenerar datos, sólo procesar lo que hay en landing |
| `full_refresh` | `false` | `true` = borrar todo y empezar de cero. ⚠️ Ver la advertencia de abajo |
| `scale_factor` | `0.1` | tamaño de la flota (0.1 = 37 turbinas) |
| `end_date` | `2026-09-30` | último día a generar |

> ⚠️ **No uses `full_refresh=true` sin necesidad.** Borra y recrea ~58 tablas, y en Free Edition las borradas
> siguen contando en la cuota de 500 tablas durante ~7 días (R14 en la bitácora).

**Si una tarea falla** (queda roja): hacé clic en ella, leé el error, arreglá el código, `bundle deploy` y después
**reparala** en lugar de correr todo de nuevo (sólo corre lo que falló y lo que depende de eso):
```bash
databricks jobs repair-run <run_id> --rerun-all-failed-tasks --rerun-dependent-tasks
```
El `<run_id>` es el número al final del Run URL. Si ya reparaste una vez, agregá `--latest-repair-id <id>`.

---

## Paso 8 · Verificar los datos

Abrí el **SQL Editor** y corré estas consultas. Si dan estos números (con `scale_factor = 0.1`), todo salió bien:

```sql
-- 1) ¿Hay datos en todas las capas?
SELECT table_schema, count(*) AS tablas
FROM andes_viento_dev.information_schema.tables
WHERE table_schema IN ('bronze','silver','gold','ops') GROUP BY 1;
-- bronze 11 · silver 13 · gold 29 (tablas + vistas + metric views) · ops 6

-- 2) ¿Hasta qué día hay datos?
SELECT max(reading_date) FROM andes_viento_dev.gold.v_park_daily;           -- 2026-09-30

-- 3) La historia principal: Cañadón León en julio 2025
SELECT round(variance_pct * 100, 1) AS desvio_pct
FROM andes_viento_dev.gold.mart_generation_vs_budget
WHERE park_code = 'LEO' AND year_month = '2025-07';                         -- -18.4

-- 4) La cascada que lo explica
SELECT * FROM andes_viento_dev.gold.fn_explicar_desvio('LEO', '2025-07');
```

El resto de los números de negocio esperados está en el [README](../README.md#-resultados-reales-del-deploy) y en
[genie/agent_mode.md](genie/agent_mode.md).

---

## Paso 9 · Desplegar y probar los Genie Agents

**Qué es un Genie Agent:** un "experto" al que le preguntás en lenguaje natural y responde con SQL sobre las tablas
que le diste, siguiendo las instrucciones, los ejemplos y las funciones certificadas que tiene. El proyecto tiene 4,
definidos como código en `genie/src/*.yml` ([12 · Genie](12_genie.md)).

**Por qué no están en el bundle:** los bundles todavía no despliegan Genie Agents, así que lo hace un script con la
API de Genie.

```bash
# (con el venv activado del paso 3)
python scripts/build_genie.py                 # YAML → genie/agents/*.json (formato serialized_space)
python scripts/deploy_genie.py --target dev   # crea o actualiza los 4 agents en tu workspace
```

> Sin terminal: abrí `notebooks/12_deploy_genie` en el workspace → *Run all* (hace lo mismo).

`deploy_genie.py` hace tres cosas: (1) revisa que ninguna función certificada tenga parámetros `DATE` (Genie los
rechaza, R11), (2) crea el agent si no existe o lo actualiza si ya existe (busca por título) y (3) guarda los IDs en
`genie/deployed_dev.json` (ese archivo no se sube a git).

**Cómo verificar:** menú **Genie** → aparecen `Andes · Operación de parques [dev]`, `Andes · Mantenimiento
predictivo [dev]`, `Andes · Comercial PPA [dev]` y `Andes · Finanzas y mercado [dev]`. Entrá a uno y preguntá
*"¿Por qué Cañadón León generó menos en julio 2025?"*.

**Desde la terminal** (usa la Conversation API, la misma que usaría una App):
```bash
python scripts/genie_ask.py --target dev --agent 01_operacion_parques "¿Por qué Cañadón León generó menos en julio 2025?"
```

**Evaluación completa (opcional, ~90 min):** le hace a Genie las 86 preguntas de prueba y compara cada respuesta
con el resultado de un SQL esperado. Escribe `docs/genie/resultados_benchmarks.md`.
```bash
python scripts/genie_eval.py --target dev
```
Resultado de referencia: **85/86 (98,8 %)**. Cómo funciona y cómo leerla: [18 · Pruebas](18_pruebas.md#6-evaluación-de-genie).

---

## Paso 10 · Dashboards, App y Genie Code (opcionales)

**Dashboards:** ya los creó el `bundle deploy`. Menú **Dashboards** → `Andes · Dirección · Generación vs presupuesto`
(y los 5 de cada caso). Si piden warehouse, elegí *Serverless Starter Warehouse*. Botón **Publish** para compartirlos.

**App** (un chat propio que usa la Conversation API; es opcional, porque Genie ya se usa desde la plataforma):
```bash
python scripts/deploy_genie.py --target dev --grant-app andes-genie-chat   # le da permiso a la App sobre los agents
databricks bundle run andes_genie_chat -t dev                               # arranca la App (~3 min)
```
Después: **Compute → Apps → andes-genie-chat** → abrí la URL.

**Genie Code** (el asistente que ayuda a construir dentro del workspace):
```bash
python scripts/install_assistant_files.py   # copia .assistant_instructions.md y las 2 skills a tu carpeta
```

---

## Paso 11 · Producción (opcional)

Es lo mismo con el target `prod` (catálogo `andes_viento`, sin prefijo en los nombres):
```bash
databricks bundle validate -t prod
databricks bundle deploy   -t prod
databricks bundle run andes_e2e -t prod          # ~45 min
python scripts/deploy_genie.py --target prod      # agents sin el sufijo [dev]
```

> En una empresa real, prod lo despliega un *service principal* desde CI/CD y nadie toca prod a mano. En Free
> Edition hay un solo usuario, así que es tu propio usuario.

**Activar las corridas automáticas:** los jobs `daily` (todos los días 06:15, hora argentina) y `maintenance`
(domingos 04:00) se crean **pausados**. Para activarlos: **Jobs & Pipelines → el job → Schedules & Triggers →
Resume**. Cómo operarlos: [19 · Operación](19_operacion_diaria.md).

---

## Paso 12 · CI/CD con GitHub Actions (opcional)

**Qué es:** cada vez que subís código a GitHub, GitHub Actions corre automáticamente el archivo
`.github/workflows/ci.yml`. Así nadie rompe el proyecto sin enterarse.

| job de CI | cuándo corre | qué hace |
|---|---|---|
| `lint` | en cada push y PR | `ruff` + verifica que los JSON de Genie y dashboards estén bien formados |
| `unit-tests` | después de `lint` | `pytest -m "not integration"` con Java 17 |
| `integration-tests` | después de los unitarios | el pipeline completo en local |
| `bundle-validate` | si configuraste `DATABRICKS_HOST` | `bundle validate` de dev y prod contra tu workspace |
| `deploy` | sólo a mano (*Run workflow*) | `bundle deploy` al target elegido y, si querés, los Genie Agents |

**Configuración (una vez), en GitHub → tu repo → Settings:**

1. **Crear un token en Databricks:** ícono de tu usuario (arriba a la derecha) → *Settings* → *Developer* →
   *Access tokens* → *Generate new token* → copialo (se muestra una sola vez).
2. **Secrets and variables → Actions → Variables → New variable:** `DATABRICKS_HOST` = tu host del paso 1.
3. **Secrets and variables → Actions → Secrets → New secret:** `DATABRICKS_TOKEN` = el token.
4. **Environments → New environment** `prod` → *Required reviewers* = vos. Así el deploy a prod pide aprobación.
   Creá también un environment `dev` (sin reviewers).

**Cómo desplegar desde GitHub:** pestaña **Actions → CI/CD → Run workflow** → `deploy_target` = `dev` o `prod` →
marcá `deploy_genie` si querés actualizar los agents.

---

## Problemas típicos (índice rápido)

| ves esto | significa | hacé esto |
|---|---|---|
| `Metastore storage root URL does not exist` | quisiste crear el catálogo por API | paso 5 por SQL |
| `CATALOG_DOES_NOT_EXIST` | falta el catálogo | paso 5 |
| `There are already 5 active runs (limit: 5)` | tope de Free Edition | nada: la tarea espera sola |
| `UNKNOWN_FIELD_EXCEPTION` en los logs de bronze | apareció una columna nueva (es a propósito) | nada: el código reinicia el stream |
| Genie: `INVALID_CERTIFIED_ANSWER_FUNCTION_EXCEPTION ... date` | una función certificada volvió a tener `DATE` | `bundle deploy` + correr `semantic_layer` (R11, R13) |
| un arreglo "desaparece" después de una corrida | no hiciste `bundle deploy` | regla de oro del paso 6 |
| mail "reached 80 % of the 500 Table quota" | cuota de tablas (incluye borradas) | [19 · Operación](19_operacion_diaria.md#la-cuota-de-500-tablas) |
| un dashboard "sin datos" | el job no terminó | esperar al `quality_gate` verde |
| la CLI no encuentra el workspace | perfil distinto de `DEFAULT` | `export DATABRICKS_CONFIG_PROFILE=<perfil>` |

Todos los errores reales del proyecto, con causa y arreglo: [08 · Bitácora](08_bitacora.md).

## Borrar todo

```bash
databricks bundle destroy -t dev     # borra jobs, pipeline, dashboards y App (pide confirmación)
```
```sql
DROP CATALOG andes_viento_dev CASCADE;   -- tablas, volumen, vistas y funciones
```
Los Genie Agents se borran desde **Genie** (menú ⋮ → *Delete*) o con `DELETE /api/2.0/genie/spaces/{id}`.
Recordá que lo borrado sigue contando en la cuota de tablas unos ~7 días.
