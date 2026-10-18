# 11 · Guía paso a paso desde la web (sin terminal, para alguien que nunca usó Databricks)

> **Qué vas a lograr:** el proyecto completo funcionando en tu propio Databricks (datos, tablas, dashboards y los 4
> Genie Agents) usando **sólo el navegador**. No hace falta instalar nada ni saber programar.
>
> **Tiempo:** ~1 hora y media, de la cual ~45 minutos es esperar a que corra el job.
>
> **Sobre las imágenes:** las pantallas de Databricks cambian seguido. Las capturas de `img/ui/` son del proyecto
> NovaMart (mismo workspace, mismos menús) y algunas son *mockups* de pantallas nuevas. Si un botón no está
> exactamente donde dice, buscá el nombre del menú: los nombres cambian menos que los lugares.
>
> **Palabras nuevas:** si alguna no la conocés (workspace, catálogo, job, warehouse...), está en el
> [glosario](15_glosario.md#conceptos-de-la-plataforma).

| paso | qué | tiempo |
|---|---|---|
| 1 | Crear la cuenta | 5 min |
| 2 | Conocer la pantalla | 3 min |
| 3 | Traer el código (Git folder) | 3 min |
| 4 | Crear el catálogo | 2 min |
| 5 | Desplegar el bundle | 3 min |
| 6 | Correr el job principal | ~45 min |
| 7 | Mirar los datos | 10 min |
| 8 | Dashboards | 5 min |
| 9 | Genie Agents | 10 min |
| 10 | Agent mode | 5 min |
| 11 | Opcionales: App, Genie Code, prod, corridas automáticas | — |

---

## 1. Crear la cuenta (Free Edition)

1. Abrí `https://www.databricks.com/learn/free-edition` y hacé clic en **Sign up**.
2. Registrate con tu email (o con Google/Microsoft). No pide tarjeta.
3. Al terminar se abre tu **workspace**. Anotá la dirección del navegador (algo como
   `https://dbc-1234abcd-5678.cloud.databricks.com`): es tu workspace y la vas a necesitar si algún día usás la terminal.

Free Edition trae todo lo que usa el proyecto: Unity Catalog (dónde se guardan y gobiernan las tablas), cómputo
*serverless* (no tenés que crear ni prender servidores), un SQL warehouse (para consultas y dashboards) y Genie.

![Inicio del workspace](img/ui/novamart_01_workspace_bundle.png)

## 2. Conocer la pantalla (lo que vas a usar)

El menú de la izquierda tiene todo. Estos son los que usa la guía:

| menú | para qué |
|---|---|
| **Workspace** | tus carpetas y archivos: acá va a vivir el código |
| **Catalog** | los datos: catálogos → esquemas → tablas |
| **SQL Editor** | escribir y correr consultas SQL |
| **Jobs & Pipelines** | los procesos automáticos (el pipeline del proyecto) |
| **Dashboards** | los tableros |
| **Genie** | los agents a los que se les pregunta en castellano |
| **Compute** | el SQL warehouse y las Apps |

## 3. Traer el código (Git folder)

**Qué es un Git folder:** una carpeta del workspace conectada a un repositorio de GitHub. Trae todo el código del
proyecto y lo podés actualizar con un botón.

1. Menú **Workspace** → abrí tu carpeta de usuario (`Users` → tu email).
2. Arriba a la derecha: **Create → Git folder**.
3. En **Git repository URL** pegá: `https://github.com/MauricioGarcia98/andes-viento-austral`
4. **Git provider:** GitHub. **Branch:** `main`.
5. **Create Git folder**. En unos segundos aparece la carpeta `andes-viento-austral`.

**Cómo verificar:** adentro ves las carpetas `src/`, `notebooks/`, `sql/`, `genie/`, `docs/`... y el archivo
`databricks.yml`, igual que en GitHub.

## 4. Crear el catálogo (paso obligatorio en Free Edition)

**Qué es un catálogo:** el nivel más alto donde se guardan los datos en Unity Catalog. Una tabla se nombra con tres
partes: `catálogo.esquema.tabla` (por ejemplo `andes_viento_dev.gold.dim_park`). El proyecto usa el catálogo
`andes_viento_dev`.

**Por qué a mano:** en Free Edition el proceso de despliegue no puede crear catálogos (falla con
`Metastore storage root URL does not exist`), pero una consulta SQL sí.

1. Menú **SQL Editor**.
2. Arriba a la derecha, en el selector de cómputo, elegí **Serverless Starter Warehouse**.
3. Pegá esto en el editor y apretá **Run** (o Ctrl/Cmd + Enter):
   ```sql
   CREATE CATALOG IF NOT EXISTS andes_viento_dev COMMENT 'Andes Viento Austral (dev)';
   ```
4. Abajo tiene que decir que terminó sin error.

**Cómo verificar:** menú **Catalog** → en la lista aparece `andes_viento_dev` (por ahora vacío).

![SQL Editor](img/ui/novamart_13_sql_editor.png)

## 5. Desplegar el bundle

**Qué es "desplegar":** el archivo `databricks.yml` y la carpeta `resources/` describen todo lo que el proyecto
necesita: 3 jobs, 1 pipeline, 6 dashboards y 1 App. Desplegar es pedirle a Databricks que **cree todo eso** a
partir del código. El target `dev` (desarrollo) agrega `[dev tu_usuario]` al nombre de cada cosa para que no se
mezcle con producción.

1. En el Git folder, abrí el archivo `databricks.yml`.
2. Aparece el panel de **bundles** (ícono de cohete 🚀 o botón **Deployments**, según la versión).
3. Elegí el target **dev** → botón **Deploy**.
4. Esperá ~1-2 minutos hasta que diga que terminó.

**Cómo verificar:** menú **Jobs & Pipelines** → aparecen:
- `[dev tu_usuario] andes-viento-e2e` (el principal)
- `[dev tu_usuario] andes-viento-daily` y `[dev tu_usuario] andes-viento-maintenance` (con el reloj en pausa)
- `[dev tu_usuario] andes-viento-ldp` (el pipeline declarativo)

![Deployments](img/ui/novamart_07_jobs.png)

**Si falla:**
- `CATALOG_DOES_NOT_EXIST` → falta el paso 4.
- `An app with the same name already exists` → ya tenés una App con ese nombre (Free Edition permite una sola):
  borrala en **Compute → Apps**.

> 📌 **Regla de oro:** si cambiás algo del código, **volvé a desplegar antes de correr el job**. El job usa la última
> versión desplegada, no lo que editaste.

## 6. Correr el job principal

**Qué hace:** en 12 pasos genera 3 años y 9 meses de datos de 13 parques (con los problemas de la vida real a
propósito), los ingiere, los limpia, arma el modelo para el negocio, aplica seguridad, prepara la capa para Genie y
al final revisa 10 controles de calidad. Si un control falla, el job termina en rojo.

1. **Jobs & Pipelines** → clic en `[dev tu_usuario] andes-viento-e2e`.
2. Botón **Run now** (arriba a la derecha). No cambies los parámetros.
3. Se abre la corrida. Pestaña **Graph**: cada tarea pasa de gris (pendiente) a azul (corriendo) a verde (terminó bien).
4. Esperá ~45 minutos. Podés cerrar la pestaña: el job sigue corriendo.

**Qué mirar mientras tanto:**
- Las tareas `generate_data`, `silver_reference` y `silver_telemetry` son **for each**: corren lo mismo para varias
  fuentes en paralelo. Clic en una para ver cada iteración.
- `should_generate` es una **condición**: decide si generar datos nuevos o sólo procesar los que ya están.

![Graph del job](img/ui/novamart_09b_run_grafo.png)

**Cómo verificar:** las 12 tareas en verde y arriba dice **Succeeded**.

**Si una tarea queda roja:**
1. Clic en la tarea roja → leé el mensaje de error (pestaña **Output**).
2. Buscalo en la tabla de errores al final de esta guía o en la [bitácora](08_bitacora.md).
3. Cuando esté arreglado: botón **Repair run** (arriba a la derecha). Corre sólo lo que falló y lo que depende de
   eso, no todo de nuevo.

Un mensaje `There are already 5 active runs` no es un error: Free Edition permite 5 corridas a la vez y la tarea
espera su turno sola.

## 7. Mirar los datos

**Recorrer las capas:**
1. Menú **Catalog** → `andes_viento_dev`. Vas a ver los esquemas `bronze` (crudo), `silver` (limpio), `gold`
   (listo para el negocio) y `ops` (auditoría y calidad).
2. Abrí `gold` → `mart_generation_vs_budget` → pestaña **Sample data**: generación real vs. presupuesto por parque y mes.
3. Pestaña **Overview**: cada columna tiene una descripción en castellano. Genie las lee para entender los datos.
4. Pestaña **Lineage**: de qué tablas sale esta (bronze → silver → gold).

![Catalog explorer](img/ui/novamart_02_catalogo.png)

![Linaje](img/ui/novamart_05_lineage.png)

**Comprobar los números** (SQL Editor, warehouse *Serverless Starter Warehouse*):
```sql
-- ¿Hasta qué día hay datos?  → 2026-09-30
SELECT max(reading_date) FROM andes_viento_dev.gold.v_park_daily;

-- La historia principal: ¿cuánto generó Cañadón León contra el presupuesto en julio 2025?  → -18.4
SELECT round(variance_pct * 100, 1) AS desvio_pct
FROM andes_viento_dev.gold.mart_generation_vs_budget
WHERE park_code = 'LEO' AND year_month = '2025-07';

-- ¿Por qué? La cascada oficial (una función certificada)
SELECT * FROM andes_viento_dev.gold.fn_explicar_desvio('LEO', '2025-07');
```
Si te da −18,4 % y la cascada muestra curtailment, hielo y menos viento, todo salió bien.

**Para aprender SQL con estos datos:** abrí `learning/01_sql_select_filtros_orden.sql` en el Git folder y corré las
celdas una por una ([ruta de aprendizaje](../learning/README.md)).

## 8. Dashboards

1. Menú **Dashboards** → `Andes · Dirección · Generación vs presupuesto` (y uno por cada caso de negocio:
   curtailment y baterías, mantenimiento predictivo, limpieza de paneles, cumplimiento PPA, garantía del fabricante).
2. Si pide un warehouse, elegí **Serverless Starter Warehouse**.
3. Para compartirlo: botón **Publish**.

Qué responde cada dashboard: [03 · Casos de negocio](03_casos_de_negocio.md).

![Dashboard](img/ui/mockup_dashboard.svg)

## 9. Genie Agents

**Qué son:** expertos a los que les preguntás en castellano ("¿por qué Cañadón León generó menos en julio?") y que
responden consultando las tablas, con las instrucciones, ejemplos y funciones certificadas de su área. El proyecto
tiene 4: Operación de parques, Mantenimiento predictivo, Comercial PPA y Finanzas y mercado
([12 · Genie](12_genie.md)).

**Crearlos desde un notebook (recomendado, sin terminal):**
1. En el Git folder abrí `notebooks/12_deploy_genie`.
2. Arriba, en el widget **Target**, dejá `dev`.
3. Botón **Run all** (arriba). Tarda menos de un minuto.
4. Al final imprime el link de cada agent.

**Cómo verificar:** menú **Genie** → aparecen `Andes · Operación de parques [dev]`, `Andes · Mantenimiento
predictivo [dev]`, `Andes · Comercial PPA [dev]` y `Andes · Finanzas y mercado [dev]`.

**Probarlo:**
1. Entrá a `Andes · Operación de parques [dev]`.
2. Escribí: *¿Por qué Cañadón León generó menos en julio 2025?*
3. Genie muestra la respuesta, una tabla y el **SQL que usó** (desplegá "Show code"): debería usar
   `fn_explicar_desvio` y mostrar la cascada (presupuesto, efecto del viento, curtailment, hielo...).
4. Más preguntas para probar están en la sección **Sample questions** de cada agent y en
   [genie/agent_mode.md](genie/agent_mode.md) (con la respuesta esperada).

![Genie](img/ui/mockup_genie_agent.svg)

**Para entender cómo está armado un agent**, entrá a uno y mirá sus pestañas: **Data** (tablas y metric views que ve),
**Instructions** (reglas del negocio), **SQL Queries & Functions** (ejemplos y funciones certificadas) y **Benchmarks**
(las preguntas de prueba con su respuesta correcta). Todo eso sale de `genie/src/<agent>.yml`.

> ¿Y si quiero crearlo a mano, para aprender? **Genie → New** → agregá las tablas de la sección `tables` y
> `metric_views` del YAML → en **Instructions** pegá `instructions` → en **SQL Queries & Functions** agregá los
> `examples` y las funciones de `functions` → en **Benchmarks** cargá las preguntas de `benchmarks`. Ojo: cada función
> va **sólo en el agent cuyo YAML la lista** (Genie prefiere usar una función certificada aunque no sirva para la
> pregunta, R16 de la bitácora).

## 10. Agent mode (preguntas de "por qué")

**Qué es:** un modo en el que Genie arma un plan de varios pasos: consulta, mira el resultado, decide la próxima
consulta y al final explica. Sirve para preguntas abiertas que no tienen una tabla con la respuesta.

1. En un Genie Agent, activá **Agent mode** (o usá **Genie One** desde la página de inicio).
2. Pegá una pregunta de [genie/agent_mode.md](genie/agent_mode.md), por ejemplo *¿Por qué el mantenimiento costó 4
   veces más en dólares en 2024 que en 2023?*
3. Mirá el plan y las consultas que va corriendo, y compará la respuesta con la esperada.

## 11. Opcionales

**La App** (un chat propio que usa la API de Genie; no hace falta, Genie ya se usa desde la plataforma):
**Compute → Apps → andes-genie-chat → Start** → abrí la URL. Para que la App pueda leer los agents hay que darle
permisos con `deploy_genie.py --grant-app andes-genie-chat` desde una terminal ([10 · Paso 10](10_despliegue_y_cicd.md#paso-10--dashboards-app-y-genie-code-opcionales)).

**Genie Code** (el asistente que te ayuda a programar): abrí cualquier notebook → ícono del asistente (✨) → preguntá
*"¿cómo agrego una fuente nueva a este proyecto?"*. Para que conozca las convenciones del proyecto, copiá
`.assistant_instructions.md` y la carpeta `.assistant/skills/` a tu carpeta de usuario (o corré
`scripts/install_assistant_files.py` desde una terminal).

**Producción:** repetí los pasos 4 (catálogo `andes_viento`), 5 (target **prod**), 6 (el job sin prefijo
`[dev ...]`) y 9 (widget **Target** = `prod`).

**Corridas automáticas:** el job `andes-viento-daily` agrega un día nuevo de datos cada mañana. Viene pausado: entrá
al job → panel **Schedules & Triggers** → **Resume**. Antes leé [19 · Operación](19_operacion_diaria.md) (cuota de
tablas y mantenimiento).

**Actualizar el código:** en el Git folder, botón con el nombre de la rama → **Pull**. Después volvé a desplegar (paso 5).

---

## Errores típicos y qué hacer

| ves esto | significa | hacé esto |
|---|---|---|
| `Metastore storage root URL does not exist` | se intentó crear el catálogo sin SQL | paso 4 |
| `CATALOG_DOES_NOT_EXIST` | falta el catálogo | paso 4 |
| `There are already 5 active runs (limit: 5)` | tope de corridas simultáneas de Free Edition | nada: espera sola |
| `UNKNOWN_FIELD_EXCEPTION` en los logs de bronze | apareció una columna nueva (está a propósito) | nada: el código reinicia la lectura |
| un dashboard "sin datos" | el job todavía no terminó | esperar a que `quality_gate` esté verde |
| Genie: `INVALID_CERTIFIED_ANSWER_FUNCTION_EXCEPTION ... date` | una función volvió a una versión vieja | volver a desplegar (paso 5) y correr el job |
| Genie: "no tengo acceso a la tabla" | permisos | quien pregunta necesita `USE CATALOG`, `USE SCHEMA` y `SELECT` sobre `gold` |
| un mail "reached 80 % of the 500 Table quota" | cuota de tablas de Free Edition | [19 · La cuota de 500 tablas](19_operacion_diaria.md#la-cuota-de-500-tablas) |
| un cambio "desaparece" después de una corrida | no volviste a desplegar | regla de oro del paso 5 |

¿Querés hacer lo mismo con la terminal? [10 · Replicar desde cero](10_despliegue_y_cicd.md).
