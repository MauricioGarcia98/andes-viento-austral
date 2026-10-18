# 18 · Etapa 14 · Capa semántica: metric views y funciones

## 🎯 Objetivo

Definir **una sola vez** las métricas oficiales de la empresa (energía generada, pérdida por curtailment,
disponibilidad contractual...) y las **respuestas certificadas** a las preguntas más importantes, para que Genie, los
dashboards y cualquier analista calculen lo mismo. Es la capa que hace que Genie responda bien
([la pirámide de 12 · Genie](../docs/12_genie.md#la-pirámide-por-qué-genie-responde-bien-o-mal)).

**Archivos:** `sql/semantic/01_metric_views.sql`, `sql/semantic/02_functions.sql`,
`src/andes_viento/semantic/__init__.py` (vacío, reservado).

## 📚 Conceptos

- **El problema de las métricas:** "disponibilidad" se puede calcular de cinco formas (promedio de días, cociente de
  sumas, contractual o técnica...). Si cada consulta la calcula a su manera, cada área tiene "su" número y nadie le
  cree a nadie.
- **Metric view:** una vista de Unity Catalog definida en YAML con **dimensiones** (por qué se agrupa) y **medidas**
  (qué se calcula, con su fórmula oficial). Se consulta con `MEASURE()`:
  ```sql
  SELECT `Parque`, MEASURE(`Energía generada (MWh)`) FROM gold.mv_generacion GROUP BY ALL
  ```
  La medida se calcula **bien** para cualquier agrupación (por parque, por mes, por provincia): un cociente de sumas
  siempre es un cociente de sumas.
- **Función de tabla de UC:** una función SQL que devuelve una tabla (`RETURNS TABLE`). En Genie se agrega como
  **respuesta certificada** (*trusted asset*): cuando la pregunta coincide, Genie la usa y marca la respuesta como
  confiable.

## 🧱 Paso a paso

### 1. Las metric views (7)

| metric view | fuente | para qué |
|---|---|---|
| `mv_generacion` | `v_park_daily` | generación, presupuesto, desvío, pérdidas por causa, factor de capacidad |
| `mv_curtailment` | `fact_curtailment_hourly` + `dim_park` | energía recortada y su valor, por motivo y hora |
| `mv_mantenimiento` | `fact_maintenance_order` + `dim_park` | órdenes, costos, MTTR |
| `mv_disponibilidad` | `mart_warranty_claims` | disponibilidad contractual (cociente de sumas) |
| `mv_ppa` | `fact_ppa_settlement` | cumplimiento, faltantes, ingresos |
| `mv_salud_turbinas` | `mart_turbine_health` + `dim_park` | turbinas en riesgo, residuos térmicos |
| `mv_limpieza` | `mart_panel_cleaning` + `dim_park` | suciedad, pérdida en USD, limpiezas |

**La anatomía** (`mv_generacion`, resumida):
```sql
CREATE OR REPLACE VIEW ${gold}.mv_generacion
WITH METRICS
LANGUAGE YAML
COMMENT 'Métricas oficiales de generación, presupuesto y pérdidas por parque y día'
AS $$
version: 1.1
comment: "Generación diaria por parque vs. presupuesto P50, con pérdidas por causa. Fuente: gold.v_park_daily"
source: ${gold}.v_park_daily
dimensions:
  - name: Parque
    expr: park_name
    comment: "Nombre del parque (ej. Cañadón León, Susques Solar)"
    synonyms: [parque, park, planta]
  - name: Código de parque
    expr: park_code
  - name: Mes
    expr: year_month
measures:
  - name: Energía generada (MWh)
    expr: SUM(generated_mwh)
    synonyms: [generación, producción, energía]
  - name: Desvío vs presupuesto (%)
    expr: SUM(generated_mwh) / SUM(budget_mwh) - 1
    comment: "Negativo = generamos menos que el presupuesto"
  - name: Pérdida por curtailment (MWh)
    expr: SUM(lost_curtailment_mwh)
    synonyms: [curtailment, recorte, limitación de red, energía perdida por CAMMESA]
$$;
```
- **Nombres en castellano de negocio** (`Energía generada (MWh)`), como los dice la gente. Con espacios y paréntesis,
  así que se consultan entre *backticks*.
- **`synonyms`:** cómo más lo llama la gente. Genie los usa para entender "recorte" o "limitación de red".
- **Las medidas son cocientes de sumas** (`SUM(a) / SUM(b) - 1`), nunca promedios de cocientes. El desvío de un año
  no es el promedio de los desvíos de cada mes.
- **Joins** (en `mv_curtailment`, `mv_salud_turbinas`, `mv_limpieza`):
  ```yaml
  joins:
    - name: park
      source: ${gold}.dim_park
      on: source.park_code = park.park_code
  dimensions:
    - name: Parque
      expr: park.park_name
  ```
  Así el usuario filtra por **nombre** ("Susques Solar") aunque la tabla tenga sólo el código.
- El YAML va entre `$$ ... $$`: por eso el separador de SQL del capítulo 13 respeta esos bloques.

**Dos errores reales de esta etapa:**
- **El alias del join no puede llamarse como una dimensión.** Con `name: parque` (el join) y `name: Parque` (la
  dimensión), como los nombres no distinguen mayúsculas, el join queda "tapado" y falla con *Can't extract a value from
  "parque.park_name"* (R5). Por eso el join se llama `park`.
- **Dimensiones por código y no por nombre:** en la primera versión, `mv_limpieza` tenía `Parque = park_code` y Genie
  filtraba `Parque = 'Susques Solar'`: cero filas. Se agregó el join a `dim_park` (ronda 1 de la evaluación de Genie).

### 2. Las funciones certificadas (7)

| función | pregunta que responde | quién la usa |
|---|---|---|
| `fn_explicar_desvio(parque, 'yyyy-MM')` | ¿por qué el parque X generó menos en el mes Y? (la cascada) | Operación |
| `fn_perdida_curtailment(parque, desde, hasta)` | ¿cuánto perdimos por curtailment y cuánto vale? | Operación, Finanzas |
| `fn_ranking_baterias(meses)` | ¿en qué parque conviene una batería? | Finanzas |
| `fn_turbinas_en_riesgo(parque)` | ¿qué turbinas se van a romper? | Mantenimiento |
| `fn_reclamos_garantia(año)` | ¿cuánto le reclamamos al fabricante? | Mantenimiento |
| `fn_recomendacion_limpieza(parque)` | ¿qué parques solares hay que limpiar hoy? | Operación |
| `fn_proyeccion_ppa(contrato)` | ¿vamos a llegar al volumen del contrato este mes? | Comercial |

**Una función bien hecha para Genie** (`fn_perdida_curtailment`):
```sql
CREATE OR REPLACE FUNCTION ${gold}.fn_perdida_curtailment(
    p_parque STRING DEFAULT NULL COMMENT 'Código o nombre del parque; NULL, vacío o TODOS = todos',
    p_desde  STRING DEFAULT NULL COMMENT 'Fecha inicial yyyy-MM-dd (incluida); NULL = desde el inicio',
    p_hasta  STRING DEFAULT NULL COMMENT 'Fecha final yyyy-MM-dd (incluida); NULL = hasta el último dato')
RETURNS TABLE (park_name STRING, curtailed_mwh DOUBLE, curtailed_pct_of_potential DOUBLE,
               value_at_spot_usd DOUBLE, value_at_ppa_usd DOUBLE, hours_with_order BIGINT)
COMMENT 'Energía perdida por curtailment ... La última fila (park_name = TOTAL EMPRESA) es el total ...'
RETURN
    SELECT coalesce(p.park_name, 'TOTAL EMPRESA'), round(sum(f.lost_curtailment_mwh), 1), ...
    FROM ${gold}.fact_curtailment_hourly f JOIN ${gold}.dim_park p ON p.park_key = f.park_key ...
    WHERE (coalesce(upper(trim(p_parque)), 'NULL') IN ('NULL', '', 'TODOS')
           OR upper(p.park_code) = upper(p_parque) OR lower(p.park_name) = lower(p_parque))
      AND (try_to_date(p_desde) IS NULL OR f.reading_date >= to_date(p_desde))
      AND (try_to_date(p_hasta) IS NULL OR f.reading_date <= to_date(p_hasta))
    GROUP BY ROLLUP (p.park_name)
    ORDER BY grouping(p.park_name), 2 DESC;
```
**Las reglas, cada una aprendida de un error real:**

| regla | por qué | error |
|---|---|---|
| **parámetros `STRING`, nunca `DATE`** | Genie **rechaza el agent entero** si una función certificada tiene un `DATE`; el error recién aparece al preguntar | R11 (0 % de aciertos) |
| aceptar `NULL`, `''`, `'NULL'` y `'TODOS'` | los parámetros los llena un LLM y a veces manda el **texto** `'NULL'` | R12 |
| `try_to_date`: una fecha inválida = sin filtro | mejor responder de más que cero filas | R12 |
| aceptar **código o nombre** del parque | Genie pasa lo que dijo el usuario ("Cañadón León" o "LEO") | — |
| una fila de **total** (`ROLLUP`) | Genie usaba la función por parque y no sumaba el total | ronda 2 |
| comentarios en las columnas que devuelve | Genie confundió `ranking` (posición) con años de repago | ronda 2 |
| `DEFAULT NULL` en todos los parámetros opcionales | Genie puede llamarla con lo que tenga | — |

`fn_explicar_desvio` tiene además una **fila 9 con el desvío total**: así responde también "¿cuánto fue el desvío?" sin
otra consulta.

### 3. Ya estaba: el notebook `08_semantic_layer`

Corre `run_sql_folder("semantic")` desde la etapa 11. Ahora tiene contenido.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| metric views | instrucciones a Genie con las fórmulas | las instrucciones se interpretan; una medida se ejecuta igual siempre |
| nombres en castellano con unidades | nombres técnicos (`lost_curtailment_mwh`) | la gente pregunta en castellano; los sinónimos y nombres claros son la mitad del trabajo de Genie |
| funciones de tabla | vistas con todos los casos | una función recibe el parque y el mes; una vista necesitaría que Genie arme el filtro (y se equivoca) |
| parámetros `STRING` | `DATE` | Genie no los admite |

## ✅ Probalo

```bash
databricks bundle deploy -t dev     # y reparar desde semantic_layer, o correr el job
```
```sql
SELECT `Parque`, MEASURE(`Desvío vs presupuesto (%)`) AS desvio
FROM andes_viento_dev.gold.mv_generacion WHERE `Mes` = '2025-07' GROUP BY ALL ORDER BY desvio;
SELECT * FROM andes_viento_dev.gold.fn_explicar_desvio('Cañadón León', '2025-07');      -- fila 9: -18,4 %
SELECT * FROM andes_viento_dev.gold.fn_perdida_curtailment('NULL', '2025-01-01', '2025-12-31');  -- con 'NULL' como texto
DESCRIBE FUNCTION andes_viento_dev.gold.fn_perdida_curtailment;    -- los 3 parámetros STRING
```

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `Can't extract a value from "parque.park_name"... got "STRING"` | el join se llama igual que una dimensión | renombrá el join (`park`) (R5) |
| `[PARSE_SYNTAX_ERROR]` dentro del YAML | el separador cortó dentro de `$$...$$` | `split_statements` respeta `$$` |
| Genie: `INVALID_CERTIFIED_ANSWER_FUNCTION_EXCEPTION ... date` | un parámetro `DATE` | `STRING` + `to_date()`; `DROP FUNCTION` antes si cambia la firma |
| `CREATE OR REPLACE FUNCTION` falla al cambiar tipos | la firma cambió | `DROP FUNCTION` y crear de nuevo |
| `MEASURE` da un número raro al agrupar | la medida es un promedio de cocientes | cocientes de sumas |
| la función volvió a la versión vieja | el job usó lo desplegado | `bundle deploy` antes de correr (R13) |

## 📍 Punto de control

```bash
git commit -am "etapa-14: capa semántica" && git diff etapa-14 HEAD --stat
```

## 🏋️ Ejercicio

1. Agregá a `mv_mantenimiento` la medida `Costo por MWh generado (USD)`. ¿De qué tablas necesitás datos? ¿Se puede
   con una sola fuente? (pista: un join).
2. Escribí `fn_peores_dias(parque, n)` que devuelva los `n` días con mayor pérdida total, con la causa principal de cada
   uno. Seguí las 7 reglas de la tabla.
3. Probá crear una función con un parámetro `DATE`, agregala a un Genie Agent de prueba (capítulo 20) y hacé una
   pregunta. Mirá el error. Borrala.
