# 10 · Despliegue y CI/CD

## Requisitos

- Workspace de Databricks (sirve **Free Edition**) con Unity Catalog y compute serverless.
- Databricks CLI ≥ 0.250 (`databricks --version`) autenticada: `databricks auth login --host https://<tu-workspace>`
  o las variables `DATABRICKS_HOST` / `DATABRICKS_TOKEN` (nunca las pongas en el repo).
- Python 3.10+ si vas a correr tests o los scripts de Genie.

## Paso 0 · Crear los catálogos (UNA vez, ANTES del primer deploy)

En Free Edition (Default Storage) la API del bundle no puede crear catálogos: falla con
`Metastore storage root URL does not exist`. Se crean por SQL, desde el **SQL Editor** con el *Serverless Starter Warehouse*:

```sql
CREATE CATALOG IF NOT EXISTS andes_viento_dev COMMENT 'Andes Viento Austral (dev)';
CREATE CATALOG IF NOT EXISTS andes_viento     COMMENT 'Andes Viento Austral (prod)';
```

O desde la terminal (reemplazá el `warehouse_id`, lo ves con `databricks warehouses list`):

```bash
databricks api post /api/2.0/sql/statements --json \
  '{"warehouse_id":"<id>","statement":"CREATE CATALOG IF NOT EXISTS andes_viento_dev","wait_timeout":"50s"}'
```

## Paso 1 · Validar y desplegar

```bash
databricks bundle validate -t dev
databricks bundle deploy   -t dev      # 12 recursos: schema ldp, 3 jobs, pipeline, 6 dashboards, app
```

## Paso 2 · Correr el pipeline

```bash
databricks bundle run andes_e2e -t dev            # ~45-60 min a SF 0,1 (Free Edition)
databricks bundle run andes_daily -t dev          # un día nuevo, sólo lo nuevo (~10 min)
databricks bundle run andes_ldp -t dev            # versión declarativa (después del e2e)
```

Si una tarea falla, no corras todo de nuevo:
```bash
databricks jobs repair-run <run_id> --rerun-all-failed-tasks --rerun-dependent-tasks
```

## Paso 3 · Genie Agents y App

```bash
pip install "databricks-sdk>=0.60" pyyaml
python scripts/build_genie.py                                   # YAML -> serialized_space
python scripts/deploy_genie.py --target dev --grant-app andes-genie-chat
python scripts/genie_ask.py "¿Por qué Cañadón León generó menos en julio 2025?"
python scripts/genie_eval.py --target dev                       # benchmarks contra la API
databricks bundle run andes_genie_chat -t dev                   # arranca la App
python scripts/install_assistant_files.py                       # instrucciones + skills de Genie Code
```

## Paso 4 · prod

```bash
databricks bundle deploy -t prod
databricks bundle run andes_e2e -t prod
python scripts/deploy_genie.py --target prod
```
En prod los recursos no llevan prefijo `[dev usuario]` y los schedules quedan como están en el YAML (PAUSED: activalos
cuando quieras que corra solo).

## CI/CD con GitHub Actions

| secreto / variable | dónde | para qué |
|---|---|---|
| `DATABRICKS_HOST` | *Variables* del repo | URL del workspace |
| `DATABRICKS_TOKEN` | *Secrets* del repo y del environment `prod` | token de un service principal (en Free Edition, un PAT) |
| environment `prod` | Settings → Environments | *required reviewers* = deploy manual con aprobación |

Flujo: cada push corre lint + tests + `bundle validate`. El deploy es manual: **Actions → CI/CD → Run workflow** con
`deploy_target = dev | prod` (y opcionalmente los Genie Agents).

## Limpieza

```bash
databricks bundle destroy -t dev     # jobs, pipeline, dashboards, app
```
```sql
DROP CATALOG andes_viento_dev CASCADE;   -- tablas, volumen y funciones
```
Los Genie Agents se borran desde la UI o con `DELETE /api/2.0/genie/spaces/{id}`.
