# 05 · Arquitectura

```
 FUENTES (11)                    LANDING            BRONZE              SILVER                  GOLD                      CONSUMO
 ─────────────                   ───────            ──────              ──────                  ────                      ───────
 SCADA turbinas (JSON gz) ─┐                                                                   dim_* (7, 2 SCD2)
 Inversores (CSV)          │     UC Volume          Auto Loader         foreachBatch:           fact_turbine_10min ──┐    Metric views (7)
 CMMS activos/órdenes      ├──▶  /Volumes/<cat>/ ─▶ (schemaHints, ─▶   tipar, relojes, ─▶     fact_* (6)            ├──▶ Funciones UC (7)
 CAMMESA despacho/spot     │     landing/raw/       rescued data,       kW/MW, clavados,        mart_* (9, SQL)       │    Genie Agents (4)
 PPA, clima, dólar, ppto  ─┘     <fuente>/          linaje)             reglas + cuarentena,    v_park_daily (OBT)  ──┘    Dashboards AI/BI (6)
                                 ingest_date=…                          SCD2 / CDC / dedupe                                 App (Conversation API)
                                                                              │                       │
                                                       OPS: pipeline_runs · watermarks · dq_results · quarantine · park_access
```

Diagramas: [arquitectura](diagrams/02_arquitectura.svg) · [proceso completo (animado)](animations/proceso_completo.svg) ·
[linaje](diagrams/03_linaje.svg) · [DAG del job](diagrams/08_dag_job.svg).

## Decisiones (ADRs)

| ADR | decisión | estado |
|---|---|---|
| [ADR-001](adr/ADR-001-genie-en-el-centro.md) | El producto es Genie; la capa de datos existe para que responda bien | aceptada |
| [ADR-002](adr/ADR-002-scale-factor-por-flota.md) | `scale_factor` escala la flota, no los días | aceptada |
| [ADR-003](adr/ADR-003-generador-con-fisica.md) | Generador con física continua (viento como función del tiempo) y tablas guía en el driver | aceptada |
| [ADR-004](adr/ADR-004-relojes-por-percentil.md) | Corregir relojes y husos con el percentil 5 de la demora de recepción | aceptada |
| [ADR-005](adr/ADR-005-identidad-de-perdidas.md) | La descomposición de pérdidas vive en el hecho de 10 minutos | aceptada |
| [ADR-006](adr/ADR-006-imperativo-y-declarativo.md) | Pipeline imperativo (Job) como principal y declarativo (LDP) como comparación | aceptada |
| [ADR-007](adr/ADR-007-catalogo-por-sql.md) | El catálogo se crea por SQL antes del primer deploy | aceptada |
| [ADR-008](adr/ADR-008-gobierno-desde-yaml.md) | Gobierno generado desde un diccionario YAML | aceptada |
| [ADR-009](adr/ADR-009-genie-como-codigo.md) | Genie Agents como código (YAML → serialized_space → API) | aceptada |

## Imperativo vs. declarativo (el mismo problema, dos estilos)

| aspecto | Job + notebooks (`src/`) | Lakeflow Declarative Pipelines (`pipelines/*.sql`) |
|---|---|---|
| Ingesta | Auto Loader explícito, reinicio en código ante columnas nuevas | `read_files` en `STREAMING TABLE`; el motor reinicia solo |
| Calidad | `Rule(...)` + `enforce()` → `ops.dq_results`, `ops.quarantine` | `CONSTRAINT ... EXPECT ... ON VIOLATION DROP ROW / FAIL UPDATE` |
| SCD2 | `scd2_merge()`: ~100 líneas | `AUTO CDC ... STORED AS SCD TYPE 2`: 8 líneas |
| Relojes desfasados | percentil por turbina y día de recepción | difícil en streaming declarativo: se omite (y se documenta) |
| Incremental en gold | watermark + `replaceWhere` a mano | vistas materializadas (refresco incremental cuando se puede) |
| Testing local | pytest + Spark/Delta OSS | sólo en Databricks |
| Cuándo elegirlo | lógica compleja, control fino, tests | pipelines estándar, menos código, linaje y calidad "gratis" |
