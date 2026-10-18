# 20 · Etapa 16 · Genie como código

## 🎯 Objetivo

Crear los **4 Genie Agents** (uno por área) **como código**: cada uno definido en un YAML legible, convertido al
formato que entiende la API (`serialized_space`), desplegado con un script y **medido** con una evaluación automática
de 86 preguntas de prueba. Es el producto final del proyecto: las áreas le preguntan a Genie
([ADR-001](../docs/adr/ADR-001-genie-en-el-centro.md)).

**Archivos:** `genie/src/*.yml`, `genie/agents/*.json` (generados), `scripts/build_genie.py`,
`scripts/deploy_genie.py`, `scripts/genie_ask.py`, `scripts/genie_eval.py`, `src/andes_viento/genie/conversation.py`,
`notebooks/12_deploy_genie.py`.

## 📚 Conceptos

- **Genie Agent** (ex *Genie space*): un experto conversacional sobre un conjunto de datos. Tiene:

| parte | qué es | en este proyecto |
|---|---|---|
| **datos** | las tablas y metric views que puede consultar | 6-10 por agent, todas de gold |
| **instrucciones** | reglas del negocio que no están en los datos | "'hoy' es el último día con datos" |
| **ejemplos SQL** | pregunta + SQL correcto, para los patrones difíciles | 5-11 por agent |
| **funciones** | respuestas certificadas (capítulo 18) | 1-3 por agent |
| **preguntas de muestra** | lo que ve el usuario al entrar | 4 por agent |
| **benchmarks** | preguntas de prueba con su respuesta correcta | 21-22 por agent |

- **Un agent por audiencia**, no uno gigante: menos tablas = menos confusión. Operación y Mantenimiento (dominio
  Operación); Comercial PPA y Finanzas y mercado (dominio Comercial).
- **`serialized_space`:** la configuración completa de un agent en JSON (versión 2). Se puede exportar e importar por
  API. Versionarlo en git permite revisar cambios en un PR y tener el mismo agent en dev y prod
  ([ADR-009](../docs/adr/ADR-009-genie-como-codigo.md)).
- **Conversation API:** hacerle preguntas a un agent desde un programa: se inicia una conversación, se espera
  (*polling*) a que Genie termine y se leen el texto, el SQL y las filas.

## 🧱 Paso a paso

### 1. El YAML de un agent (`genie/src/01_operacion_parques.yml`)

```yaml
title: "Andes · Operación de parques"
domain: Operación
description: >-
  Para jefes de parque y la Gerencia de Operaciones: generación diaria, pérdidas por causa ...
users: "Martín Quiroga (Gerente de Operaciones) y los 13 jefes de parque"
tables: [gold.v_park_daily, gold.mart_generation_vs_budget, gold.mart_panel_cleaning, gold.fact_curtailment_hourly,
         gold.dim_park, gold.dim_weather, gold.dim_date]
metric_views: [gold.mv_generacion, gold.mv_limpieza]
functions: [gold.fn_explicar_desvio, gold.fn_recomendacion_limpieza, gold.fn_perdida_curtailment]
instructions: |
  Sos el asistente de Operación de Andes Viento Austral (9 parques eólicos en Chubut y Santa Cruz, 4 solares ...).
  - "Hoy" es el último día con datos: max(reading_date) de gold.v_park_daily. Nunca uses current_date().
  - Los usuarios nombran los parques por nombre ("Cañadón León", "Susques"): filtrá por park_name con ILIKE o por park_code.
  - Energía siempre en MWh con 1 decimal. Curtailment = recorte = limitación de red = orden de CAMMESA.
  - Para "¿por qué generó menos?" usá la función fn_explicar_desvio(parque, 'yyyy-MM'): es la cascada oficial.
  ...
sample_questions:
  - "¿Por qué Cañadón León generó menos en julio 2025?"
examples:
  - question: "Generación vs presupuesto del último mes por parque"
    sql: |
      SELECT park_name, round(actual_mwh, 1) AS real_mwh, ... FROM ${catalog}.gold.mart_generation_vs_budget
      WHERE month_start = (SELECT max(month_start) FROM ${catalog}.gold.mart_generation_vs_budget)
benchmarks:
  - q: "¿Cuál fue el desvío contra presupuesto de Cañadón León en julio 2025?"
    sql: "SELECT round(variance_pct * 100, 1) FROM ${catalog}.gold.mart_generation_vs_budget WHERE park_code = 'LEO' AND year_month = '2025-07'"
```
**Cómo escribir cada parte:**
- **Instrucciones cortas**, sólo lo que **no está en los datos**: qué es "hoy" (los datos terminan el 30-09-2026; sin
  esta regla, "¿cuánto generé ayer?" da vacío), cómo nombra la gente las cosas, unidades, qué función usar para qué.
  Si una regla se puede poner como comentario de una columna, va ahí (capítulo 17).
- **Ejemplos** para los patrones difíciles (totales de la empresa, metric views con `MEASURE`), no para lo obvio.
- **Funciones**, sólo en el agent cuyas preguntas encajan con sus parámetros: Genie prefiere una función certificada
  **aunque no sirva** (Finanzas usaba "desvío de un parque y un mes" para "toda la empresa", R16).
- **Benchmarks con respuesta única** (un número, un nombre), con el SQL **esperado**. No un valor fijo: los datos
  cambian con el job diario y el SQL calcula la respuesta correcta al momento de evaluar.
- `${catalog}` es un marcador: el deploy lo reemplaza por el catálogo del target.

(Escribí los 4 YAML con `git show etapa-16:genie/src/<archivo>`. Son el resultado de 7 rondas de mejora; en
[docs/12](../docs/12_genie.md#lo-que-aprendimos-midiendo-r11-r16-de-la-bitácora) está el porqué de cada regla.)

### 2. `build_genie.py`: YAML → `serialized_space`

```python
def _id(*parts):
    return hashlib.md5("|".join(parts).encode()).hexdigest()

def build_space(spec, slug):
    space = {
        "version": 2,
        "config": {"sample_questions": [{"id": _id(slug, "sq", q), "question": [q]} for q in ...]},
        "data_sources": {"tables": [{"identifier": _fq(t)} for t in sorted(tables + metric_views)]},
        "instructions": {
            "text_instructions": [{"id": _id(slug, "ti"), "content": _lines(spec["instructions"])}],
            "example_question_sqls": [{"id": ..., "question": [...], "sql": _lines(e["sql"])} for e in ...],
            "sql_functions": [{"id": ..., "identifier": _fq(f)} for f in sorted(functions)],
        },
        "benchmarks": {"questions": [{"id": ..., "question": [b["q"]],
                                      "answer": [{"format": "SQL", "content": _lines(b["sql"])}]} for b in ...]},
    }
    for section, key in (...):                         # la API exige cada lista ordenada por id
        space[section][key].sort(key=lambda x: x["id"])
    return space
```
- **IDs estables** (`md5` del contenido): reconstruir sin cambios da el mismo JSON, y el diff en git muestra sólo lo
  que de verdad cambió.
- **Las listas ordenadas por id:** la API rechaza el JSON si no (*"example_question_sqls must be sorted by id"*, R8).
- Las metric views van en `data_sources.tables`, como cualquier tabla.
- `assert n >= 20`: cada agent con al menos 20 benchmarks.

### 3. `deploy_genie.py`: crear o actualizar

```python
def deploy(target, only, warehouse_name, catalog):
    w = WorkspaceClient()
    wh = find_warehouse(w, warehouse_name)
    existing = list_spaces(w)                                    # título -> space_id
    for path in sorted((ROOT / "genie" / "agents").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        title, description, space = render(doc, catalog or CATALOGS[target], target)   # ${catalog} y "[dev]"
        check_functions(w, space)                                # ¿algún parámetro DATE? -> corta acá
        body = {"title": title, "description": description, "warehouse_id": wh, "serialized_space": space}
        if title in existing:
            w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{existing[title]}", body=body)
        else:
            sid = w.api_client.do("POST", "/api/2.0/genie/spaces", body=body)["space_id"]
    # guarda los IDs en genie/deployed_<target>.json (sin pisar los agents que no se tocaron)
```
- **Idempotente por título:** si el agent existe, lo actualiza (PATCH); si no, lo crea (POST). En dev el título lleva
  ` [dev]`.
- **`check_functions` antes de desplegar:** revisa con la API de Unity Catalog que ninguna función certificada tenga
  parámetros `DATE`/`TIMESTAMP`. El deploy de un agent con una función así **funciona**, pero después **todas** las
  preguntas fallan (R11). Este chequeo se agregó cuando el job diario recreó una función vieja y Finanzas pasó a 0/21
  (R13).
- `genie/deployed_<target>.json` está en `.gitignore`: son IDs de **tu** workspace.
- `--export <space_id>` imprime el `serialized_space` de un agent (para ver qué cambió alguien desde la interfaz);
  `--grant-app` da permisos a la App (capítulo 21).

**`notebooks/12_deploy_genie.py`** hace lo mismo desde el workspace (para quien no usa terminal): agrega `../scripts`
al `sys.path` e importa `deploy_genie`. Dentro de Databricks, `WorkspaceClient()` se autentica solo.

### 4. La Conversation API: `conversation.py` y `genie_ask.py`

```python
class GenieClient:
    def ask(self, question, conversation_id=None) -> GenieAnswer:
        if conversation_id:
            msg = self.api.do("POST", f"{self._base()}/conversations/{conversation_id}/messages", body={"content": question})
        else:
            resp = self.api.do("POST", f"{self._base()}/start-conversation", body={"content": question})
        return self._wait(conv, mid)

    def _wait(self, conv, mid):
        deadline, delay = time.time() + self.timeout_s, 1.0
        while True:
            msg = self.api.do("GET", f"{self._base()}/conversations/{conv}/messages/{mid}")
            if msg.get("status") in TERMINAL or time.time() > deadline:
                break
            time.sleep(delay)
            delay = min(delay * 1.5, 5.0)                 # backoff: no martillar la API
        ...  # texto, SQL generado y filas (GET .../attachments/{aid}/query-result)
```
Genie tarda de segundos a un minuto: se consulta el estado con esperas crecientes hasta `COMPLETED`, `FAILED` o
`CANCELLED`. `genie_ask.py` es la versión de consola (con `--follow` para repreguntar en la misma conversación).

### 5. `genie_eval.py`: medir

Para cada benchmark: corre el SQL esperado en el warehouse, le hace la misma pregunta a Genie y compara (números con
1 % de tolerancia, porcentajes como `-18.4` o `-0.184`, textos sin acentos ni mayúsculas, etiquetas booleanas
ignoradas). Escribe `docs/genie/resultados_benchmarks.md` y un JSON con el SQL que generó Genie. El detalle del
comparador y el recorrido real de 0 % a 98,8 % están en
[docs/18 · Pruebas](../docs/18_pruebas.md#6-evaluación-de-genie).

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| YAML → JSON con un script | editar el `serialized_space` a mano | el JSON es ilegible (listas de líneas, ids); el YAML se lee y se revisa |
| deploy por API | crear los agents en la interfaz | no se versiona; dev y prod divergen |
| 4 agents | 1 agent con todo | con 30 tablas Genie elige peor |
| benchmarks con SQL esperado | evaluar a ojo | "anda bien" es una opinión; 85/86 es un dato |
| chequeo de `DATE` en el deploy | confiar | el error es silencioso hasta la primera pregunta |

## ✅ Probalo

```bash
pip install -e ".[dev,genie]"
python scripts/build_genie.py                 # 4 líneas: ejemplos, funciones y benchmarks por agent
python scripts/deploy_genie.py --target dev   # 4 líneas "creado ..." (la segunda vez, "actualizado ...")
python scripts/genie_ask.py --target dev --agent 01_operacion_parques "¿Por qué Cañadón León generó menos en julio 2025?"
python scripts/genie_eval.py --target dev --only 01_operacion_parques    # ~25 min para 22 preguntas
```
En la interfaz: **Genie → Andes · Operación de parques [dev]** → pestañas *Data*, *Instructions*, *SQL Queries &
Functions* y *Benchmarks*. Desde *Benchmarks* también se pueden correr las pruebas a mano.

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `Invalid export proto: ... must be sorted by id` | listas sin ordenar | el `sort` de `build_space` (R8) |
| todas las preguntas: `INVALID_CERTIFIED_ANSWER_FUNCTION_EXCEPTION ... date` | una función con parámetro `DATE` | `STRING` + `to_date()`; `bundle deploy` y recrear la función (R11, R13) |
| Genie devuelve tabla vacía en una función | pasó `'NULL'` como texto | funciones tolerantes (R12) |
| Genie usa una función para algo que no le corresponde | la función está en un agent que no la necesita | sacala de ese agent (R16) |
| un benchmark "falla" con una respuesta correcta | el SQL esperado devuelve códigos y Genie nombres (o al revés) | corregí el SQL esperado |
| `deployed_dev.json` perdió agents | un `--only` viejo lo sobrescribía | el script ahora mezcla con lo que había |
| `PERMISSION_DENIED` al preguntar | el usuario no tiene `SELECT` sobre gold o `CAN USE` sobre el warehouse | permisos en UC y en el warehouse |

## 📍 Punto de control

```bash
git commit -am "etapa-16: Genie como código" && git diff etapa-16 HEAD --stat
```

## 🏋️ Ejercicio

1. Creá un quinto agent "HSE" (agua de limpieza, horas de trabajo en altura, rutas cortadas) con 20 benchmarks.
   Construilo, desplegalo y evaluálo.
2. Elegí un benchmark que Genie responda bien, borrá la instrucción que lo explica y volvé a evaluar. ¿Sigue bien?
   ¿Por qué? (pista: los comentarios de las columnas).
3. Usá `genie_ask.py --follow` para hacer una conversación de 3 preguntas encadenadas ("¿y en agosto?", "¿y en San
   Julián?"). ¿Mantiene el contexto?
