# 12 · Genie en el centro

> Estado de la familia Genie en octubre 2026: **Genie One** (el chat de toda la empresa en la home), **Genie Agents**
> (ex *Genie spaces*: un experto por dominio, con sus tablas, instrucciones y benchmarks), **Agent mode** (Genie arma un
> plan de varios pasos para preguntas de "por qué") y **Genie Code** (ex Databricks Assistant: te ayuda a construir).
> Los nombres de los productos cambian rápido; los conceptos de abajo, no.

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
| **Andes · Finanzas y mercado** | Comercial | CFO, Riesgo, CEO | `mart_generation_vs_budget`, `mart_curtailment_battery`, `fact_curtailment_hourly`, `fact_maintenance_order`, `dim_park`, `dim_date`, `v_park_price_month`, `mv_curtailment`, `mv_generacion` | `fn_ranking_baterias`, `fn_perdida_curtailment`, `fn_explicar_desvio` | 21 |

Configuración versionada: [`genie/src/*.yml`](../genie/src) (fuente) → [`genie/agents/*.json`](../genie/agents)
(`serialized_space`). Resultados de la evaluación: [genie/resultados_benchmarks.md](genie/resultados_benchmarks.md).

> ⚠️ **Funciones confiables sin parámetros `DATE`.** Si una función certificada tiene un parámetro `DATE`, el deploy
> por API funciona, pero **todas** las preguntas del agent fallan con `INVALID_CERTIFIED_ANSWER_FUNCTION_EXCEPTION ...
> argument type is not supported: date`. Usá `STRING` (`'2025-07-01'`) y convertí con `to_date()` adentro de la
> función. Nos pasó de verdad: ver R11 en la [bitácora](08_bitacora.md).

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
