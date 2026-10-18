# 18 · Cómo se prueba el proyecto (y cómo lo probamos de verdad)

> **Idea central:** un número equivocado en Genie es peor que no tener número. Por eso el proyecto se prueba en
> **siete capas**, de la más barata (segundos, en tu computadora) a la más cara (una hora y media contra Genie).
> Cada capa atrapa errores que las anteriores no ven.

```
                          ┌────────────────────────────────────────┐
  7. Verificación manual  │ números de negocio, dashboards, Genie   │  a ojo, con consultas guardadas
                          ├────────────────────────────────────────┤
  6. Evaluación de Genie  │ 86 preguntas vs. SQL esperado           │  ~90 min · scripts/genie_eval.py
                          ├────────────────────────────────────────┤
  5. Quality gate         │ 10 invariantes al final del job         │  18 s · si falla, el job falla
                          ├────────────────────────────────────────┤
  4. Reglas de calidad    │ warn / quarantine / fail fila por fila  │  dentro de silver (y expectations del LDP)
                          ├────────────────────────────────────────┤
  3. CI (GitHub Actions)  │ lint + unit + integración + validate    │  ~10 min en cada push
                          ├────────────────────────────────────────┤
  2. Test de integración  │ el pipeline entero en Spark local       │  ~5-10 min · pytest -m integration
                          ├────────────────────────────────────────┤
  1. Lint + unitarios     │ estilo + 27 tests de piezas             │  ~2 min · ruff + pytest
                          └────────────────────────────────────────┘
```

Regla práctica: **cuanto más abajo atrapás un error, más barato es**. Un test unitario que falla cuesta 2 minutos;
el mismo error descubierto por Genie en producción cuesta la confianza de un gerente.

---

## 1. Lint y tests unitarios

**Qué son:**
- **Lint (`ruff`)**: revisa el estilo y errores comunes (variables sin usar, imports rotos) sin ejecutar nada.
- **Test unitario**: un pedacito de código (una función) con un dato de entrada chico armado a mano y la salida
  esperada escrita en el test. Si alguien cambia la función y rompe el comportamiento, el test falla.

**Cómo correrlos** (con el entorno del [paso 3 de la guía](10_despliegue_y_cicd.md#paso-3--clonar-el-repo-y-probarlo-en-tu-computadora)):
```bash
ruff check src tests scripts apps
pytest -m "not integration"         # 27 tests, ~2 min
pytest tests/test_transforms.py -k clock   # uno solo (los que tienen "clock" en el nombre)
```

**Cómo funcionan por dentro:** `tests/conftest.py` crea **una sola** sesión de Spark local con Delta para todos los
tests (crearla tarda ~20 s) y le da a cada test esquemas con un prefijo único, así no se pisan entre sí.

**Qué protege cada test** (cada problema real de los datos tiene el suyo):

| archivo | test | qué verifica | por qué importa |
|---|---|---|---|
| `test_physics.py` | `test_power_curve_shape` | la curva de potencia: 0 bajo 3 m/s, nominal desde ~12,5, 0 sobre 25 (corte) | la física es la base de "cuánto se pudo generar" |
| | `test_wind_spark_equals_python` (×3 parques) | el viento calculado en Spark y en Python dan **exactamente** lo mismo | la física existe dos veces (generador distribuido y Monte Carlo del presupuesto) |
| | `test_solar_spark_equals_python` | ídem para la irradiancia solar; hay sol al mediodía y 0 de noche | |
| | `test_puna_is_cold_and_patagonia_winter_is_cold` | helada en la Puna en julio; invierno patagónico > 10 °C más frío | el hielo en palas depende de esto |
| `test_events.py` | `test_fleet_scales_and_totals` | SF 1 = 380 turbinas, 220 inversores, 1,2 M paneles; a cualquier escala todo parque existe | el `scale_factor` no puede hacer desaparecer un parque |
| | `test_weather_series_is_prefix_stable` | el clima del día D es idéntico si generás hasta D o hasta D+100 | el job diario agrega días sin cambiar el pasado |
| | `test_story_failure_and_grid_maintenance_exist` | la multiplicadora de LEO-01 rompe el 26-07-2025 y para 21 días; hay 11 órdenes `MANTENIMIENTO_ET` | la historia de Agent mode tiene que estar en los datos |
| | `test_no_overlapping_downtime` | una turbina no puede estar en dos paradas a la vez | si no, las horas de falla se duplican |
| | `test_fx_devaluation_and_inflation` | el dólar salta de < 400 a > 790 el 13-12-2023; inflación acumulada | los costos en pesos tienen que comportarse como en la Argentina |
| `test_datagen.py` | `test_scada_is_deterministic` | dos corridas con la misma semilla dan los mismos datos | reproducible = depurable |
| | `test_scada_has_realistic_dirt` | 3 formatos de fecha, potencia en MW en un fabricante, duplicados, nulos | la suciedad que silver tiene que limpiar |
| | `test_scada_schema_drift_only_after_firmware` | los 3 sensores nuevos aparecen sólo con firmware HT-OS 5.0 | el *schema drift* tiene que ser realista |
| | `test_inverter_late_and_unit_bug` | el bug de MW en Fiambalá y la columna `soiling_sensor_pct` | |
| | `test_small_sources_formats` | precios con coma decimal, hora CAMMESA 1..24, CDC con operaciones I y U | formatos argentinos |
| `test_transforms.py` | `test_ar_number_and_cammesa_hour` | `"45.231,50"` → 45231.5; la "hora 24" es de 23 a 24 local | dos clásicos de los datos argentinos |
| | `test_three_timestamp_formats_and_units` | los 3 formatos de fecha terminan en el mismo instante UTC; MW → kW | |
| | `test_timezone_switch_is_detected` | un parque que cambió de huso horario se corrige | |
| | `test_clock_skew_and_late_resend` | un reloj corrido 7 minutos se detecta y corrige; un reenvío tardío se marca | el percentil de la demora ([ADR-004](adr/ADR-004-relojes-por-percentil.md)) |
| | `test_stuck_sensor` | un sensor que repite el mismo valor se anula, pero no las primeras repeticiones | |
| | `test_dedupe_first_arrival` | ante duplicados se queda la primera llegada | |
| | `test_inverter_mw_bug` | el bug de unidades del inversor se corrige | |
| | `test_split_statements_respects_strings_and_dollar_blocks` | el separador de SQL no corta en un `;` dentro de un texto o de un bloque `$$` | error real R4 |
| | `test_view_name_and_fingerprint` | la huella de las vistas ignora espacios y detecta cambios | error real R14 (cuota de tablas) |
| `test_scd2.py` | `test_scd2_history_resends_and_late_changes` | historia SCD2 correcta con reenvíos y cambios que llegan tarde; una sola versión vigente | la historia de las turbinas |
| `test_quality.py` | `test_enforce_quarantine_and_fail` | una regla `quarantine` separa la fila; una `warn` la deja pasar y la registra | el framework de calidad |

---

## 2. Test de integración (el pipeline entero en tu computadora)

**Qué es:** en vez de probar una pieza, corre **todo**: genera 5 semanas de datos (25-06-2025 al 31-07-2025, SF
0,03), los ingiere con Auto Loader, limpia, arma gold, corre los marts SQL y el quality gate. Usa Spark y Delta
*open source*, los mismos motores que Databricks (sin las funciones exclusivas de Databricks, que se saltean).

```bash
pytest -m integration        # ~5-10 min
```

**Qué verifica** (`tests/test_e2e.py`):
1. Que el pipeline completo termine y el **quality gate pase** (si una invariante se rompe, el test falla).
2. Que la historia guionada aparezca: Cañadón León en julio 2025 con desvío < −15 % y pérdidas por curtailment,
   hielo y falla.
3. Que las turbinas Hanse vigentes tengan el firmware HT-OS 5.0 (la foto inicial del CMMS se armó bien, error L8).
4. Que **un día nuevo** (01-08-2025) se procese de forma incremental y agregue filas sin romper el gate.

**Lo que encontró antes de tocar Databricks:** 8 errores (L1-L8 en la [bitácora](08_bitacora.md)), por ejemplo FKs
huérfanas en SCD2 y contratos que siempre se cumplían.

---

## 3. CI con GitHub Actions

Cada push a cualquier rama corre `.github/workflows/ci.yml` (detalle y configuración en
[10 · Paso 12](10_despliegue_y_cicd.md#paso-12--cicd-con-github-actions-opcional)):

```
lint ──┬──▶ unit-tests ──▶ integration-tests ──┐
       └──▶ bundle-validate (dev y prod) ──────┴──▶ deploy (sólo a mano)
```

Además del lint, verifica que los JSON de los Genie Agents y de los dashboards estén bien formados. En este proyecto
el CI quedó verde en los últimos pushes (ver la pestaña **Actions** del repo).

---

## 4. Reglas de calidad dentro del pipeline

**Qué son:** reglas que se evalúan **fila por fila** sobre los datos reales mientras el job corre. Cada regla es una
expresión SQL que tiene que ser verdadera, con una de tres acciones:

| acción | qué pasa con la fila | ejemplo |
|---|---|---|
| `warn` | sigue, pero el fallo queda registrado en `ops.dq_results` | `reloj_sincronizado` (se corrigió el reloj) |
| `quarantine` | se aparta a `ops.quarantine` con el motivo y el registro original en JSON | `ventana_valida` (una orden de CAMMESA que termina antes de empezar) |
| `fail` | **se aborta el job** | `dolar_positivo`, `id_presente` (datos que nunca deberían existir) |

Las reglas están en `src/andes_viento/silver/rules.py` y el motor en `src/andes_viento/quality/expectations.py`.

**Lo que midieron de verdad** (corrida de dev, consulta a `ops.dq_results`):

| tabla | regla | acción | filas que fallaron | de |
|---|---|---|---:|---:|
| `silver.scada_10min` | `huso_horario_correcto` | warn | 526.200 | 7,23 M |
| `silver.inverter_5min` | `unidad_correcta` (MW → kW) | warn | 208.900 | 4,27 M |
| `silver.scada_10min` | `llego_a_tiempo` | warn | 64.222 | 7,23 M |
| `silver.scada_10min` | `sensores_sin_clavarse` | warn | 45.390 | 7,23 M |
| `silver.scada_10min` | `reloj_sincronizado` | warn | 37.542 | 7,23 M |
| `silver.scada_10min` | `potencia_informada` | warn | 23.270 | 7,23 M |
| `silver.scada_10min` | `valores_fisicamente_posibles` | warn | 7.312 | 7,23 M |
| `silver.inverter_5min` | `irradiancia_valida` | warn | 2.103 | 4,27 M |
| `silver.curtailment_instructions` | `ventana_valida` | quarantine | 3 | 1.466 |

Son exactamente los problemas que inyecta el generador ([06 · Fuentes y suciedad](06_fuentes_y_suciedad.md)): el
pipeline los detectó, los corrigió y dejó registro.

**Cómo mirarlo vos:**
```sql
SELECT table_name, rule, action, sum(failed_rows) AS fallaron, sum(total_rows) AS total
FROM andes_viento_dev.ops.dq_results GROUP BY ALL ORDER BY fallaron DESC;

SELECT * FROM andes_viento_dev.ops.quarantine;        -- las filas apartadas, con el motivo
```

**En el pipeline declarativo (LDP)** las mismas ideas se escriben como *expectations*
(`CONSTRAINT ... EXPECT ... ON VIOLATION DROP ROW | FAIL UPDATE`, en `pipelines/02_silver.sql`). En la corrida real
detectaron 633 potencias fuera de rango y 2.166 temperaturas imposibles sobre 7.259.550 lecturas (ver la bitácora).

---

## 5. Quality gate (el último control antes de publicar)

**Qué es:** la última tarea del job (`quality_gate`, código en `src/andes_viento/quality/gate.py`). Corre 10
consultas que **tienen que dar 0** y revisa que la cuarentena no supere el 1 % de las filas. Si algo falla, el job
termina en rojo y Genie no ve datos rotos.

| # | invariante | qué atrapa |
|---|---|---|
| 1 | `fact_turbine_10min` tiene el mismo grano que `silver.scada_10min` | filas perdidas o duplicadas al pasar a gold |
| 2 | sin duplicados turbina × instante en silver | la deduplicación falló |
| 3 | toda medición tiene turbina (`turbine_key <> -1`) | FKs huérfanas (error L6) |
| 4 | una sola versión vigente por turbina | SCD2 roto |
| 5 | las versiones SCD2 de una turbina no se solapan | SCD2 roto |
| 6 | lo generado en 10 min nunca supera la potencia nominal (+20 %) | unidades mal convertidas (MW/kW) |
| 7 | disponibilidad contractual entre 0 y 1 | error real R7 (−0,0002) |
| 8 | en la liquidación PPA lo entregado nunca supera lo comprometido | asignación de energía mal hecha |
| 9 | la cascada presupuesto → real cierra (residuo < 0,1 MWh) | la identidad de pérdidas ([ADR-005](adr/ADR-005-identidad-de-perdidas.md)) |
| 10 | órdenes de trabajo sin duplicar | el CDC del CMMS falló |
| + | cuarentena ≤ 1 % de las filas | una fuente que llegó rota en masa |

En la corrida real el gate frenó una vez el job (R7: disponibilidad −0,0002). Se arregló el código y se reparó la
corrida.

---

## 6. Evaluación de Genie

**El problema:** Genie genera SQL a partir de una pregunta en lenguaje natural. Puede equivocarse de tabla, de
filtro o de función, y además **no es determinístico**: la misma pregunta puede dar SQL distinto otro día.

**La solución: benchmarks.** Cada agent tiene en su YAML (`genie/src/*.yml`, sección `benchmarks`) preguntas con la
respuesta escrita como **SQL esperado**. Hay 86 en total (22 + 22 + 21 + 21).

```yaml
  - q: "¿Cuál fue el desvío contra presupuesto de Cañadón León en julio 2025?"
    sql: "SELECT round(variance_pct * 100, 1) FROM ${catalog}.gold.mart_generation_vs_budget
          WHERE park_code = 'LEO' AND year_month = '2025-07'"
```

**Cómo funciona `scripts/genie_eval.py`**, para cada pregunta:
1. Corre el **SQL esperado** en el warehouse → respuesta correcta (por ejemplo `-18.4`).
2. Le hace **la misma pregunta** a Genie por la Conversation API, como lo haría una persona.
3. Compara: ¿la respuesta de Genie **contiene** los valores esperados? Números con 1 % de tolerancia (y acepta
   `-18.4` o `-0.184`, porque Genie a veces da el porcentaje como fracción), textos sin mayúsculas ni acentos, y
   etiquetas booleanas ignoradas (Genie escribe "Con curtailment" en vez de `true`).
4. Espera 3 segundos (la API tiene un límite de preguntas por minuto) y sigue con la próxima.

Al final escribe `docs/genie/resultados_benchmarks.md` (tabla legible) y `resultados_benchmarks_dev.json` (detalle
con el SQL que generó Genie y las filas que devolvió: ahí se diagnostica).

```bash
python scripts/genie_eval.py --target dev                          # las 86 (~90 min)
python scripts/genie_eval.py --target dev --only 04_finanzas_mercado   # un solo agent
python scripts/genie_eval.py --target dev --expected-only          # sólo valida los SQL esperados (rápido)
```

**El recorrido real** (cada ronda es la evaluación completa después de un arreglo):

| ronda | resultado | qué pasó / qué se arregló |
|---|---|---|
| 0 | **0/86** | todas fallaban: una función certificada tenía parámetros `DATE` (R11) |
| 1 | 64/86 (74 %) | Genie pasaba `'NULL'` como texto a las funciones (R12); metric views filtraban por código y no por nombre; faltaban instrucciones |
| 2 | 78/86 (91 %) | fila de total en `fn_perdida_curtailment`, reglas de SCD2, motivo NULL sin orden |
| 3 | 63/86 | Finanzas 0/21: el job diario recreó la función vieja porque no hice `bundle deploy` (R13) |
| 4 | parcial | bug del script: `deploy_genie --only` borraba los IDs de los otros agents (arreglado); apareció el mes en curso como faltante de USD 1,4 M (R15) |
| 5 | 78/86 (91 %) | Finanzas seguía usando `fn_explicar_desvio` para preguntas de toda la empresa |
| 6 | 80/86 (93 %) | ejemplos SQL nuevos en Finanzas; seguía eligiendo la función |
| 7 | **85/86 (98,8 %)** | se sacó `fn_explicar_desvio` de Finanzas (R16); el único "fallo" es una respuesta correcta con códigos de parque en vez de nombres |

**Lecciones de la evaluación** (detalladas en la bitácora y en [12 · Genie](12_genie.md)):
- El primer número (0 %) no era culpa de Genie: era un error de configuración que **sólo** aparece preguntando.
  Después de cada deploy, hacé al menos una pregunta.
- La mayoría de los arreglos fueron en los **datos y la metadata** (funciones, metric views, columnas nuevas), no en
  las instrucciones.
- Un benchmark mal escrito también falla: si Genie responde bien con otro formato, se corrige el SQL esperado.
- Entre dos rondas sin cambios Genie cambia 1 o 2 respuestas por agent. Un 98,8 % puede ser 96 % otro día: lo que
  importa es que no haya fallos **sistemáticos**.

---

## 7. Verificación manual (los números de negocio)

Los tests dicen que el código hace lo que dice. Falta saber si **lo que dice tiene sentido para el negocio**. Para
eso, después de cada corrida grande se revisaron a mano las respuestas a las preguntas de "por qué":

| pregunta | dónde se verificó | número real |
|---|---|---|
| ¿Por qué Cañadón León generó menos en julio 2025? | `fn_explicar_desvio('LEO','2025-07')` | −18,4 %: curtailment −7,6 %, hielo −5,0 %, recurso −4,0 % |
| ¿Hanse nos debe plata? | `fn_reclamos_garantia(2025)` | disponibilidad 96,7 % < 97 %, ≈ USD 659 mil |
| ¿Por qué el mantenimiento se multiplicó por 4? | `fact_maintenance_order` por año | 1 → 13 fallas mayores, USD 0,72 M → 3,09 M |
| ¿Conviene una batería? | `fn_ranking_baterias(12)` | no: repago ~78 años |

La lista completa, con la respuesta esperada de cada una: [genie/agent_mode.md](genie/agent_mode.md).

**Y si un número no cierra, se cambia la historia, no el número.** Ejemplo real (R10): en la primera corrida la flota
era demasiado sana y el caso de la garantía no tenía reclamos. Se agregó al generador el lote defectuoso de
multiplicadoras Hanse 2024-2025 y se volvió a correr.

**Dashboards:** cada uno de los 17 datasets de los 6 dashboards se ejecutó contra el warehouse y devolvió filas
(`risk_now` da 0 porque hoy no hay turbinas en riesgo alto, que es válido).

---

## Cómo agregar una prueba nueva

| si cambiaste... | agregá... | dónde |
|---|---|---|
| una transformación de silver | un test con un DataFrame chico armado a mano | `tests/test_transforms.py` |
| el generador | un test de que la suciedad o la historia nueva aparece | `tests/test_datagen.py` o `test_events.py` |
| una regla que nunca debería romperse | una invariante en el quality gate | `src/andes_viento/quality/gate.py` |
| una regla por fila | un `Rule(...)` con su acción | `src/andes_viento/silver/rules.py` |
| una pregunta que Genie tiene que responder | un benchmark con su SQL esperado | `genie/src/<agent>.yml` → `build_genie.py` → `deploy_genie.py` |

Antes de subir: `ruff check . && pytest -q`. Para Genie, además: `genie_eval.py --only <agent>`.
