# 19 · Operar el proyecto día a día

> **Para quién:** ya desplegaste el proyecto ([10](10_despliegue_y_cicd.md) u [11](11_guia_desde_la_web.md)) y ahora
> querés mantenerlo vivo: que lleguen datos nuevos, saber si algo se rompió, cambiar algo sin romper nada, cuidar
> la cuota de Free Edition y que Genie siga respondiendo bien.

## Qué corre y cuándo

| job | qué hace | cuándo | estado inicial |
|---|---|---|---|
| `andes-viento-e2e` | el pipeline completo (12 tareas) | a mano, o lo dispara el diario | — |
| `andes-viento-daily` | genera los archivos de **un día nuevo** y dispara el e2e con `generate=false` | todos los días 06:15 (hora argentina) | **pausado** |
| `andes-viento-maintenance` | `OPTIMIZE` + `VACUUM` + `ANALYZE` de silver y gold | domingos 04:00 | **pausado** |
| `andes-viento-ldp` | el pipeline declarativo (para comparar) | a mano | — |

**Activar un schedule:** Jobs & Pipelines → el job → panel derecho **Schedules & Triggers** → **Resume**.
En dev los schedules siempre quedan pausados (es el modo `development` del bundle); actívalos en prod.

**Cómo funciona el día nuevo:** el job diario mira el último día con datos (por ejemplo 2026-09-30), genera el
siguiente (2026-10-01) para las 11 fuentes y corre el e2e. El e2e no regenera la historia: Auto Loader lee sólo los
archivos nuevos y gold recalcula sólo los días afectados (watermarks). Tarda ~12 minutos contra ~45 de la carga
completa.

---

## ¿Está todo bien? (chequeo de 2 minutos)

1. **Jobs & Pipelines → andes-viento-e2e → Runs:** la última corrida en verde.
2. **El quality gate** es la última tarea: si está verde, los 10 controles de calidad pasaron
   ([18 · Pruebas](18_pruebas.md#5-quality-gate-el-último-control-antes-de-publicar)).
3. **¿Hasta qué día hay datos?**
   ```sql
   SELECT max(reading_date) FROM andes_viento_dev.gold.v_park_daily;
   ```
4. **¿Cuánto tardó cada paso?** (cada notebook registra su corrida en `ops.pipeline_runs`)
   ```sql
   SELECT step, target, status, rows_written, round(duration_s) AS seg, error
   FROM andes_viento_dev.ops.pipeline_runs ORDER BY finished_at DESC LIMIT 20;
   ```
5. **¿Cuánta suciedad detectó la calidad?**
   ```sql
   SELECT table_name, rule, action, sum(failed_rows) FROM andes_viento_dev.ops.dq_results GROUP BY ALL ORDER BY 4 DESC;
   ```

**Alertas por mail:** en `resources/andes_e2e.job.yml` hay una línea comentada `email_notifications`. Descomentala con
tu email y hacé `bundle deploy` para recibir un mail cuando el job falle.

---

## Cuando algo falla

1. **Abrí la corrida roja** → clic en la tarea roja → pestaña **Output** o **Logs**: ahí está el error.
2. **Buscá el error** en el índice de [10 · Problemas típicos](10_despliegue_y_cicd.md#problemas-típicos-índice-rápido)
   y en la [bitácora](08_bitacora.md).
3. **Arreglá el código** en tu computadora → `ruff check . && pytest -q` → `databricks bundle deploy -t dev`.
4. **Repará la corrida** (corre sólo lo que falló y lo que depende de eso, no todo):
   ```bash
   databricks jobs repair-run <run_id> --rerun-all-failed-tasks --rerun-dependent-tasks
   ```
   Desde la web: botón **Repair run** arriba a la derecha de la corrida.
5. **Anotalo** en la bitácora (qué pasó, cómo lo encontraste, arreglo, lección). Es la documentación más útil.

**Fallas que se resuelven solas** (no hagas nada): `There are already 5 active runs` (espera turno) y
`UNKNOWN_FIELD_EXCEPTION` en bronze (el código reinicia el stream ante una columna nueva).

---

## Cambiar algo sin romper nada (el circuito)

```
 editar en tu compu ─▶ ruff + pytest ─▶ bundle deploy ─▶ correr / reparar el job ─▶ verificar ─▶ commit + push
                                                              │
                         si tocaste genie/src/*.yml ─▶ build_genie ─▶ deploy_genie ─▶ genie_eval (del agent)
```

| si cambiaste... | después hacé |
|---|---|
| un SQL de `sql/marts/` | `bundle deploy` → reparar desde `gold_marts` |
| una metric view o función (`sql/semantic/`) | `bundle deploy` → reparar desde `semantic_layer` → **preguntarle algo a Genie** |
| el diccionario de gobierno | `python scripts/build_governance.py` → `bundle deploy` → reparar `governance` |
| código Python de `src/` | `pytest` → `bundle deploy` → reparar desde la tarea que lo usa |
| un Genie Agent (`genie/src/*.yml`) | `build_genie.py` → `deploy_genie.py --target dev` → `genie_eval.py --only <agent>` |
| un dashboard | `python scripts/build_dashboards.py` → `bundle deploy` |

> 📌 **La regla de oro:** el job usa lo que **desplegaste**, no lo que guardaste. Si aplicás un arreglo a mano en el
> SQL Editor y no desplegás, la próxima corrida lo pisa (R13 en la bitácora).

---

## La cuota de 500 tablas

**Qué es:** Free Edition permite hasta **500 tablas por metastore** (todo tu workspace, sumando catálogos). Cuentan
tablas, vistas y metric views, **y también las borradas en los últimos ~7 días** (mientras se pueden recuperar con
`UNDROP`). Databricks manda un mail al 80 % y al 85 %.

**Cuánto usa este proyecto:** ~58 objetos por ambiente (dev o prod) + ~27 si corrés el pipeline LDP (13 tablas
propias + 14 internas de materialización).

**Cómo medir:**
```sql
-- tablas vivas por catálogo (sin samples ni system)
SELECT table_catalog, count(*) FROM system.information_schema.tables
WHERE table_catalog NOT IN ('samples','system') AND table_schema <> 'information_schema'
GROUP BY 1;

-- las borradas que todavía cuentan (una consulta por esquema)
SHOW TABLES DROPPED IN andes_viento_dev.gold;
```

**Qué consume cuota sin que te des cuenta:**
- **`full_refresh=true`**: borra y recrea ~58 tablas → +58 "fantasmas" por 7 días.
- **Borrar un catálogo**: sus tablas siguen contando ~7 días.
- **Recrear vistas en cada corrida**: cada `CREATE OR REPLACE VIEW` deja la versión vieja como borrada. El proyecto
  ya lo evita: guarda una huella de cada vista en `ops.sql_fingerprints` y sólo la recrea si cambió (R14).

**Qué hacer si se acerca al límite:**
1. No uses `full_refresh` y no borres y recrees cosas en esos días.
2. Borrá lo que no uses: catálogos de proyectos viejos, el esquema del LDP de dev
   (`DROP SCHEMA andes_viento_dev.dev_<usuario>_ldp CASCADE`), o el ambiente prod si sólo estás aprendiendo.
3. Esperá: las borradas dejan de contar solas a los ~7 días.

Si llegás a 500, crear una tabla nueva falla; lo que ya existe sigue funcionando.

---

## Cómo cuidar a Genie

- **Después de cualquier cambio en `sql/semantic/` o en un YAML de agent, hacele una pregunta** (`genie_ask.py` o
  desde la UI). Los errores de configuración de Genie no aparecen al desplegar, sólo al preguntar (R11).
- **Cuando alguien diga "Genie respondió mal"**: abrí el agent → **Monitoring** (o el historial de la conversación)
  → mirá el SQL que generó. Después agregá esa pregunta como **benchmark** con su SQL correcto, arreglá la causa
  (casi siempre un comentario, una metric view o una función, no las instrucciones) y corré `genie_eval.py --only`.
  El paso a paso está en la skill `andes-genie-agent-authoring`.
- **Una vez por mes** (o después de cambios grandes) corré la evaluación completa y compará con el 98,8 % de
  referencia. Una o dos diferencias son normales (Genie no es determinístico); fallos repetidos en el mismo tema no.

---

## Mantenimiento y costos

- **Job de mantenimiento** (semanal): compacta los archivos chicos que dejan los MERGE incrementales y actualiza las
  estadísticas del optimizador. Sin él, las consultas se van haciendo más lentas con las semanas.
- **Cuánto cómputo se usa** (DBUs por job):
  ```sql
  SELECT usage_metadata.job_id, sum(usage_quantity) AS dbus
  FROM system.billing.usage WHERE usage_date >= current_date() - 30 GROUP BY 1 ORDER BY 2 DESC;
  ```
  La fila sin `job_id` es el uso del SQL warehouse (consultas, dashboards y Genie). En Free Edition no pagás, pero hay
  una cuota diaria: si se agota, el cómputo se frena hasta el día siguiente.
- **Tokens:** si creaste un token para GitHub Actions, rotalo cada tanto (Settings → Developer → Access tokens).

---

## Apagar o borrar

| querés... | hacé |
|---|---|
| que no corra más solo | pausá los schedules (Schedules & Triggers → Pause) |
| liberar cuota sin perder el código | `DROP CATALOG andes_viento CASCADE` (prod) o el esquema LDP |
| borrar todo | `databricks bundle destroy -t dev` + `DROP CATALOG andes_viento_dev CASCADE` + borrar los agents desde Genie |

Detalle en [10 · Borrar todo](10_despliegue_y_cicd.md#borrar-todo).
