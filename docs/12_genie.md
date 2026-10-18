# 12 · Genie en el centro

> Estado de la familia Genie en octubre 2026: **Genie One** (el chat de toda la empresa en la home), **Genie Agents**
> (ex *Genie spaces*: un experto por dominio, con sus tablas, instrucciones y benchmarks), **Agent mode** (Genie arma un
> plan de varios pasos para preguntas de "por qué") y **Genie Code** (ex Databricks Assistant: te ayuda a construir).
> Los nombres de los productos cambian rápido; los conceptos de abajo, no.

## Cómo se usa (desde Databricks, con los datos)

Genie se usa **desde la plataforma**: menú **Genie** del workspace → elegís el agent de tu área → preguntás en
castellano. Genie arma el SQL sobre las tablas gold, metric views y funciones del proyecto, lo corre con **tus
permisos** (si tenés un *row filter* por parque, ves sólo tu parque) y muestra la respuesta, la tabla y el SQL.

1. **Genie** → `Andes · Operación de parques` (en dev lleva el sufijo `[dev]`).
2. Preguntá: *¿Por qué Cañadón León generó menos en julio 2025?*
3. Mirá la respuesta y desplegá **Show code** para ver el SQL: debería usar `fn_explicar_desvio`.
4. Repreguntá en la misma conversación: *¿Y en agosto?* (Genie recuerda el contexto).
5. Si la respuesta está mal, marcala con 👎: queda en **Monitoring** para que el equipo de datos la revise.

Para crear o actualizar los agents: notebook `notebooks/12_deploy_genie` (sin terminal,
[11 · paso 9](11_guia_desde_la_web.md#9-genie-agents)) o `python scripts/deploy_genie.py`
([10 · paso 9](10_despliegue_y_cicd.md#paso-9--desplegar-y-probar-los-genie-agents)). Las APIs de abajo son para
integrar Genie en otras herramientas (la App, un bot); no hacen falta para usarlo.

## La pirámide: por qué Genie responde bien (o mal)

```
                 ▲  Agent mode / Genie One  (preguntas abiertas, "por qué")
                ▲▲▲ Genie Agents            (instrucciones cortas, ejemplos SQL, benchmarks)
              ▲▲▲▲▲ Funciones de UC          (respuestas certificadas = trusted assets)
            ▲▲▲▲▲▲▲ Metric views             (métricas oficiales con sinónimos)
          ▲▲▲▲▲▲▲▲▲ Comentarios + PK/FK      (cada columna explicada en el idioma del negocio)
        ▲▲▲▲▲▲▲▲▲▲▲ Gold bien modelado       (grano claro, identidad de pérdidas, tabla ancha por parque y día)
```

Si Genie se equivoca, el arreglo casi nunca está arriba (en las instrucciones): suele estar abajo (un comentario, una
métrica que no existe, un grano confuso). La skill `andes-genie-agent-authoring` tiene el orden para diagnosticar.

## Los 4 Genie Agents

| agent | dominio | usuarios | tablas + metric views | funciones (trusted) | benchmarks |
|---|---|---|---|---|---|
| **Andes · Operación de parques** | Operación | Gerente de Operaciones, 13 jefes de parque | `v_park_daily`, `mart_generation_vs_budget`, `mart_panel_cleaning`, `fact_curtailment_hourly`, `dim_park`, `dim_weather`, `dim_date`, `mv_generacion`, `mv_limpieza` | `fn_explicar_desvio`, `fn_recomendacion_limpieza`, `fn_perdida_curtailment` | 22 |
| **Andes · Mantenimiento predictivo** | Operación | Jefe de Mantenimiento, Confiabilidad | `mart_turbine_health`, `fact_maintenance_order`, `fact_availability_daily`, `mart_warranty_claims`, `dim_turbine`, `dim_park`, `dim_crew`, `mv_mantenimiento`, `mv_salud_turbinas`, `mv_disponibilidad` | `fn_turbinas_en_riesgo`, `fn_reclamos_garantia` | 22 |
| **Andes · Comercial PPA** | Comercial | Gerente y analista comercial | `fact_ppa_settlement`, `mart_ppa_forecast`, `dim_contract`, `v_contract_park_month`, `dim_park`, `mv_ppa` | `fn_proyeccion_ppa` | 21 |
| **Andes · Finanzas y mercado** | Comercial | CFO, Riesgo, CEO | `mart_generation_vs_budget`, `mart_curtailment_battery`, `fact_curtailment_hourly`, `fact_maintenance_order`, `dim_park`, `dim_date`, `v_park_price_month`, `mv_curtailment`, `mv_generacion` | `fn_ranking_baterias`, `fn_perdida_curtailment` | 21 |

Configuración versionada: [`genie/src/*.yml`](../genie/src) (fuente) → [`genie/agents/*.json`](../genie/agents)
(`serialized_space`). Resultados de la evaluación: [genie/resultados_benchmarks.md](genie/resultados_benchmarks.md) — **85/86 (98,8 %)** en la
ronda final; recorrido 0 % → 74 % → 91 % → 93 % → 98,8 % (ver R11-R16 en la [bitácora](08_bitacora.md)).

> ⚠️ **Funciones confiables sin parámetros `DATE`.** Si una función certificada tiene un parámetro `DATE`, el deploy
> por API funciona, pero **todas** las preguntas del agent fallan con `INVALID_CERTIFIED_ANSWER_FUNCTION_EXCEPTION ...
> argument type is not supported: date`. Usá `STRING` (`'2025-07-01'`) y convertí con `to_date()` adentro de la
> función. Nos pasó de verdad: ver R11 en la [bitácora](08_bitacora.md).

## Lo que aprendimos midiendo (R11-R16 de la bitácora)

La evaluación de las 86 preguntas pasó de 0 % a 98,8 % ([18 · Pruebas](18_pruebas.md#6-evaluación-de-genie)).
Lo que explica cada salto, como reglas para tu próximo agent:

| regla | por qué | error real |
|---|---|---|
| Nunca parámetros `DATE`/`TIMESTAMP` en una función certificada: usá `STRING 'yyyy-MM-dd'` + `to_date()` | Genie rechaza el agent entero, pero recién al preguntar | R11 |
| Programá las funciones a la defensiva: `NULL`, `''`, `'NULL'` y `'TODOS'` = todos | los parámetros los llena un LLM: puede mandar el texto `'NULL'` | R12 |
| Después de cada deploy, hacé al menos una pregunta | los errores de configuración no aparecen al desplegar | R11, R13 |
| `bundle deploy` antes de correr el job | si no, el job recrea la versión vieja de las funciones | R13 |
| Una función certificada va sólo en el agent cuyas preguntas encajan con sus parámetros | Genie la prefiere aunque no sirva (usaba "desvío de un parque y un mes" para "toda la empresa") | R16 |
| Las dimensiones de las metric views, por **nombre** (y el código aparte) | la gente dice "Susques", no "SUS" | ronda 1 |
| Si dos tablas pueden responder lo mismo, decí cuál en las instrucciones | "viento medio" estaba en las turbinas y en la estación meteorológica | ronda 3 |
| Ejemplos SQL para los patrones difíciles (totales de la empresa, supuestos del presupuesto) | los ejemplos pesan más que las instrucciones | ronda 6 |
| Benchmarks con respuesta única y en el mismo formato que respondería una persona | un benchmark mal escrito también "falla" | ronda 7 |

## Cómo mejorar un agent (el circuito)

1. **Juntá las preguntas que salieron mal** (Monitoring, quejas, `genie_eval.py`).
2. **Mirá el SQL que generó Genie** (`docs/genie/resultados_benchmarks_dev.json` o "Show code").
3. **Buscá la causa de abajo hacia arriba** en la pirámide: ¿falta un comentario?, ¿una métrica?, ¿una función?,
   ¿un ejemplo? Recién al final, una instrucción.
4. **Agregá la pregunta como benchmark** con su SQL correcto en `genie/src/<agent>.yml`.
5. `build_genie.py` → `deploy_genie.py --target dev` → `genie_eval.py --target dev --only <agent>`.
6. Si mejoró sin romper otras, commit. La skill `andes-genie-agent-authoring` tiene este mismo orden para Genie Code.

## Anatomía de un `serialized_space` (version 2)

```json
{
  "version": 2,
  "config": { "sample_questions": [{ "id": "<32 hex>", "question": ["¿...?"] }] },
  "data_sources": { "tables": [{ "identifier": "andes_viento_dev.gold.v_park_daily" }] },
  "instructions": {
    "text_instructions": [{ "id": "...", "content": ["línea 1\n", "línea 2"] }],
    "example_question_sqls": [{ "id": "...", "question": ["..."], "sql": ["SELECT ...\n", "FROM ..."] }],
    "sql_functions": [{ "id": "...", "identifier": "andes_viento_dev.gold.fn_explicar_desvio" }]
  },
  "benchmarks": { "questions": [{ "id": "...", "question": ["..."],
                                  "answer": [{ "format": "SQL", "content": ["SELECT ..."] }] }] }
}
```

Lo verificamos contra la API real: creamos un space mínimo, lo exportamos con
`GET /api/2.0/genie/spaces/{id}?include_serialized_space=true` y la API devolvió `"version": 2` con esta estructura.
Las metric views se agregan como tablas (`data_sources.tables`).

## Las APIs que usa el proyecto

| para qué | endpoint | script |
|---|---|---|
| crear un agent | `POST /api/2.0/genie/spaces` (`title`, `warehouse_id`, `serialized_space`) | `deploy_genie.py` |
| actualizarlo | `PATCH /api/2.0/genie/spaces/{id}` | `deploy_genie.py` |
| exportarlo | `GET /api/2.0/genie/spaces/{id}?include_serialized_space=true` | `deploy_genie.py --export` |
| preguntar | `POST .../spaces/{id}/start-conversation` → `GET .../messages/{mid}` (polling) | `genie_ask.py`, App |
| repreguntar | `POST .../conversations/{cid}/messages` | `genie_ask.py --follow` |
| traer filas | `GET .../messages/{mid}/attachments/{aid}/query-result` | `GenieClient` |
| permisos | `PATCH /api/2.0/permissions/genie/{id}` | `deploy_genie.py --grant-app` |

## Buenas prácticas que aplicamos (y por qué)

1. **Instrucciones cortas** (6-8 líneas): reglas que no están en los datos ("hoy" = último día con datos; parques por
   nombre o código; unidades). Lo demás va en comentarios y funciones.
2. **"Hoy" no es `current_date()`**: los datos terminan el 30/09/2026. Sin esa regla, "¿cuánto generé ayer?" da vacío.
3. **Funciones que aceptan nombre o código** (`'Cañadón León'` o `'LEO'`): Genie pasa lo que dijo el usuario.
4. **Benchmarks con respuesta única** (un número, un nombre): se evalúan solos con `genie_eval.py`.
5. **Sinónimos en las metric views** ("recorte", "limitación de red", "multa del fabricante").
6. **Datos sensibles enmascarados** en UC: Genie respeta máscaras y row filters del usuario que pregunta.
7. **Un agent por audiencia**, no uno gigante: menos tablas = menos confusión.

## Agent mode

Preguntas de "por qué" con la respuesta que debería encontrar: [genie/agent_mode.md](genie/agent_mode.md).

## Genie Code (para construir)

- [`.assistant_instructions.md`](../.assistant_instructions.md): convenciones del proyecto (fechas, unidades, capas).
- Skills: [`andes-medallion-conventions`](../.assistant/skills/andes-medallion-conventions/SKILL.md) y
  [`andes-genie-agent-authoring`](../.assistant/skills/andes-genie-agent-authoring/SKILL.md).
- `python scripts/install_assistant_files.py` las copia a tu carpeta del workspace.
