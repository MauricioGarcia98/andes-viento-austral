# 19 · Orquestación con Lakeflow Jobs, Asset Bundles y CI/CD

## El job e2e por dentro (`resources/andes_e2e.job.yml`)

```
setup ─▶ should_generate (condition) ─true─▶ generate_data (for_each 11 fuentes, 3 en paralelo)
                    │                                   │
                    └──────────── false ──────┐         │
                                              ▼         ▼
                                     bronze_ingest  (run_if: NONE_FAILED)
                                              │
                              silver_reference (for_each 8, concurrencia 4)
                                              │
                              silver_telemetry (for_each 3: scada, inverter, work_orders)
                                              │
                         gold_dimensions ─▶ gold_facts ─▶ gold_marts ─┬─▶ governance ──┐
                                                                      └─▶ semantic_layer ┴─▶ quality_gate
```

- **condition_task**: `{{job.parameters.generate}} == "true"`. Las dependencias de una condición **tienen que** declarar
  `outcome: "true"` o `"false"` (si no, `INVALID_PARAMETER_VALUE`: error 1 de NovaMart).
- **run_if: NONE_FAILED** en `bronze_ingest`: corre aunque una rama quede "excluded".
- **for_each_task**: el mismo notebook con `{{input}}`; `concurrency` limita el paralelismo (Free Edition tiene topes).
- **Job diario**: genera el día siguiente y llama al e2e con `run_job_task` y `generate=false`.

## Comandos

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run andes_e2e -t dev
databricks bundle run andes_daily -t dev
databricks jobs repair-run <run_id> --rerun-all-failed-tasks --rerun-dependent-tasks
databricks bundle destroy -t dev        # borra jobs, pipeline, dashboards y app (no las tablas)
```

## CI/CD (`.github/workflows/ci.yml`)

| job | cuándo | qué hace |
|---|---|---|
| lint | siempre | `ruff` + JSON válidos de Genie y dashboards |
| unit-tests | siempre | `pytest -m "not integration"` con Spark + Delta local |
| integration-tests | siempre | pipeline completo local sobre 5 semanas |
| bundle-validate | si hay `vars.DATABRICKS_HOST` | `bundle validate -t dev` y `-t prod` |
| deploy | manual (`workflow_dispatch`) | `bundle deploy -t <target>` (+ Genie opcional); `prod` con aprobación del environment |

Secretos: `DATABRICKS_TOKEN` como *secret* del repo/environment; `DATABRICKS_HOST` como *variable*. Nunca en el código.

## Ejercicios

1. Agregá una condición "¿es prod?" que salte la generación cuando `catalog = andes_viento` (prod no se regenera).
2. Agregá `email_notifications.on_failure` al job e2e sólo en el target prod (pista: `targets.prod.resources`).
3. Hacé que el job diario reintente 2 veces `generate_next_day` con 5 minutos de espera.
4. En GitHub: creá el environment `prod` con *required reviewers* y corré el deploy manual.

## Soluciones

1. Una `condition_task` `op: NOT_EQUAL, left: "{{job.parameters.catalog}}", right: "andes_viento"` antes de `should_generate`.
2. ```yaml
   targets:
     prod:
       resources:
         jobs:
           andes_e2e:
             email_notifications: { on_failure: [operaciones-datos@andesviento.com.ar] }
   ```
3. `max_retries: 2` y `min_retry_interval_millis: 300000` en la task.
4. Settings → Environments → New environment `prod` → Required reviewers.
