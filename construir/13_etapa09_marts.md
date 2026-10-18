# 13 · Etapa 9 · Marts en SQL

## 🎯 Objetivo

Escribir **un mart por caso de negocio**: tablas que responden directamente las preguntas de las áreas (¿por qué
generamos menos?, ¿conviene una batería?, ¿qué turbina se va a romper?, ¿cuándo limpiar?, ¿llegamos al volumen del
contrato?, ¿cuánto nos debe el fabricante?). Se escriben en **SQL**, y un *runner* de Python los ejecuta en orden
reemplazando los nombres de catálogo y esquema.

**Archivos:** `src/andes_viento/gold/marts.py`, `sql/marts/01..09_*.sql` y dos tests nuevos en
`tests/test_transforms.py`.

## 📚 Conceptos

- **Mart:** una tabla (o vista) pensada para **una pregunta de negocio**, con nombres que entiende ese negocio. Se
  apoya en las dimensiones y hechos de gold.
- **CTE (`WITH ... AS`):** pasos intermedios con nombre dentro de una consulta. Permiten leer un SQL largo de arriba
  hacia abajo, como una receta.
- **Funciones de ventana en SQL:** `avg(x) OVER (PARTITION BY turbina ORDER BY día ROWS BETWEEN 6 PRECEDING AND
  CURRENT ROW)` = el promedio móvil de 7 días. `WINDOW w7 AS (...)` le pone nombre a una ventana para reusarla.
- **`CREATE OR REPLACE TABLE ... AS SELECT` (CTAS):** reemplaza la tabla entera de forma atómica. Los marts son chicos
  y se recalculan completos en cada corrida.
- **Plantillas `${gold}`:** el SQL no sabe en qué catálogo corre; el runner reemplaza `${gold}` por
  `andes_viento_dev.gold` (o `spark_catalog.andes_gold` en local).

## 🧱 Paso a paso

### 1. `marts.py`: el runner de SQL

```python
SQL_DIR = Path(__file__).resolve().parents[3] / "sql"

def render(sql, cfg):
    for layer in LAYERS:
        sql = sql.replace("${" + layer + "}", cfg.schema(layer))
    return sql.replace("${catalog}", cfg.catalog)
```
`parents[3]` sube de `src/andes_viento/gold/marts.py` a la raíz del repo, donde está `sql/`. Funciona igual en tu
computadora y en Databricks (el bundle sube la misma estructura).

**`split_statements`, el separador de sentencias:** un archivo `.sql` tiene varias sentencias separadas por `;`, pero
`spark.sql()` ejecuta **una**. Separar por `;` parece trivial y no lo es:
```sql
COMMENT ON TABLE x IS 'Grano: 1 fila por parque; incluye solares';   -- un ; adentro de un texto
CREATE VIEW mv WITH METRICS LANGUAGE YAML AS $$ ... $$;                 -- YAML entre $$ (capítulo 18)
-- un comentario; con punto y coma
```
El separador recorre el texto carácter por carácter y sabe si está dentro de un texto (`'...'`, `"..."`), de un
identificador (`` `...` ``), de un bloque `$$...$$` o de un comentario `--` (que descarta). Sólo corta en un `;` que
está "afuera". La primera versión cortaba en cualquier `;` y rompía los comentarios del diccionario que tienen punto y
coma (R4 de la bitácora). Por eso tiene su test.

**`run_sql_file`, `run_sql_folder` y `build_marts`:** corren los archivos en orden alfabético (`01_`, `02_`...: el
número define las dependencias). `run_sql_folder(..., skip_errors=True)` saltea lo que no existe en Spark local
(máscaras, metric views) en vez de fallar.

(`run_sql_file` también evita recrear vistas que no cambiaron: guarda una huella de cada vista en
`ops.sql_fingerprints`. Se agregó al final del proyecto por la cuota de tablas de Free Edition, R14; está explicado en
el [capítulo 23](23_etapa19_prod_y_operacion.md).)

### 2. Los 9 archivos SQL, en orden

| # | objeto | caso de negocio | la idea clave |
|---|---|---|---|
| 01 | `v_contract_park_month`, `v_park_price_month` | base comercial | cada contrato reparte su volumen entre sus parques; el precio de realización de un parque es el PPA ponderado por volumen |
| 02 | `mart_generation_vs_budget` | 0 · ¿por qué generamos menos? | la **cascada** real vs. presupuesto |
| 03 | `fact_ppa_settlement` | 4 · cumplimiento PPA | liquidación mensual: faltante, penalidad vs. compra spot |
| 04 | `mart_curtailment_battery` | 1 · baterías | simulación de 3 tamaños de batería |
| 05 | `mart_turbine_health` | 2 · mantenimiento predictivo | residuos térmicos contra los pares del parque |
| 06 | `mart_panel_cleaning` | 3 · limpieza de paneles | regla económica: limpiar cuando lo perdido supera el costo |
| 07 | `mart_ppa_forecast` | 4 · ¿vamos a llegar este mes? | entregado + proyección con el desempeño de 14 días |
| 08 | `mart_warranty_claims` | 5 · garantía del fabricante | disponibilidad móvil 12 meses vs. 97 % y *liquidated damages* |
| 09 | `v_park_daily` | todas | **una vista ancha** por parque y día para Genie |

Escribilos en ese orden leyendo cada archivo de la referencia (`git show etapa-09:sql/marts/02_mart_generation_vs_budget.sql`).
Cada uno empieza con un comentario que explica la regla de negocio: escribilo vos primero, antes del SQL.
Lo esencial de los más importantes:

**02 · La cascada del presupuesto:**
```
presupuesto = potencial_presupuestado × disponibilidad_supuesta × (1 − curtailment_supuesto)
real        = potencial_real − curtailment − fallas − mantenimiento − hielo − suciedad − otras
desvío      = efecto del recurso − exceso de curtailment − exceso de indisponibilidad − hielo − suciedad − otras
```
- `resource_effect_mwh = potencial real − potencial presupuestado`: cuánto del desvío es **el viento** (o el sol).
- `budget_curtailment_allowance_mwh` y `budget_availability_allowance_mwh`: lo que el presupuesto **ya asumía**.
  Sólo el **exceso** sobre eso es desvío.
- `lost_other_mwh` cierra la identidad: si no, la cascada no suma. El quality gate verifica que cierre con menos de
  0,1 MWh de diferencia.
- Usa el presupuesto **original** del año (`v1`), no el re-presupuesto: el directorio compara contra lo aprobado.

**05 · El modelo predictivo, en SQL:**
```sql
peers AS (
    -- promedio del RESTO del parque ese día = (suma del parque - la propia) / (n - 1)
    SELECT d.*,
           ((sum(gearbox_c) OVER pd) - gearbox_c) / nullif((count(gearbox_c) OVER pd) - 1, 0) AS peer_gearbox_c, ...
    FROM d
    WINDOW pd AS (PARTITION BY park_code, reading_date)
),
feat AS (
    SELECT p.*, avg(gearbox_c - peer_gearbox_c) OVER w7 AS gearbox_residual_7d, ...
    WINDOW w7 AS (PARTITION BY turbine_id ORDER BY reading_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
           w30_prev AS (PARTITION BY turbine_id ORDER BY reading_date ROWS BETWEEN 37 PRECEDING AND 7 PRECEDING)
),
```
- **Por qué contra los pares y no contra un umbral fijo:** en verano todo calienta. Comparada con las otras turbinas
  del mismo parque **el mismo día** (mismo viento, misma temperatura), una multiplicadora que calienta 5 °C más tiene
  un problema.
- "El resto del parque" = (suma − la propia) / (n − 1): sin incluirse a sí misma.
- **Primero agregar por día, después las ventanas:** ordenar 1 fila por turbina y día, no 144.
- `health_score` = 100 menos penalidades por residuo, vibración y alarmas; < 60 = riesgo **ALTO**.
- **La etiqueta** `failure_within_30d` (¿hubo una falla mayor en los 30 días siguientes?) permite **medir** el modelo:
  21 de 26 fallas anticipadas.
- **Ojo con la sintaxis:** `(sum(x) OVER pd) - x` lleva paréntesis. Sin ellos, Spark lee `OVER pd - x` y falla con
  `INVALID_IDENTIFIER pd-gearbox_c` (L5 y R2 de la bitácora).

**06 · Limpieza de paneles:** la suciedad estimada es `1 − PR / PR_referencia` (*performance ratio* contra el
percentil 95 del parque). Se acumula en dólares lo perdido desde la última limpieza; **conviene limpiar cuando eso
supera el costo de una limpieza**, salvo que el pronóstico traiga lluvia (> 4 mm), que limpia gratis. Es una regla de
umbral clásica: simple, explicable y mejor que "cada 75 días".

**03 · La liquidación PPA:** la energía de cada parque se asigna primero a los contratos (a prorrata de lo que cada
uno reclama). Faltante = comprometido × (1 − tolerancia) − entregado. Ante un faltante, la **mejor opción** es la más
barata entre pagar la penalidad o comprar en el spot (+5 % de cargos). Un mes todavía abierto no se liquida (R15).

**09 · `v_park_daily`:** junta por parque y día la generación, las pérdidas, el presupuesto diario, la disponibilidad,
el clima y el precio. **Genie responde mejor con pocas tablas anchas y bien comentadas que con 20 joins.**

### 3. Los tests nuevos

En `tests/test_transforms.py` se suman `test_split_statements_respects_strings_and_dollar_blocks` (un `;` dentro de un
texto, un comentario y un bloque `$$` no cortan) y `test_view_name_and_fingerprint`.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| marts en SQL | en PySpark | son reglas de negocio: en SQL las lee un analista, Genie Code y quien revisa el PR |
| silver en Python | todo en SQL | silver tiene lógica de ingeniería (relojes, unidades, CDC) que conviene testear función por función |
| un mart por caso | un mart "para todo" | cada caso tiene su grano; mezclarlos obliga a filtros raros |
| recalcular completos | incremental | son chicos (miles de filas); la complejidad no se paga |
| la regla de negocio en el encabezado | documentarla aparte | el que lee el SQL tiene la explicación al lado |

## ✅ Probalo

```bash
pytest tests/test_transforms.py -v      # 9 passed
pytest -m "not integration"             # 27 passed
python -c "
from andes_viento.gold.marts import split_statements
print(len(split_statements(open('sql/marts/02_mart_generation_vs_budget.sql').read())))"   # 1
```
Los marts se ejecutan de verdad en el test de integración del capítulo 14.

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `[INVALID_IDENTIFIER] The unquoted identifier pd-gearbox_c is invalid` | `OVER pd - x` sin paréntesis | `(sum(x) OVER pd) - x` |
| `[PARSE_SYNTAX_ERROR] at or near '''` | el separador cortó en un `;` dentro de un texto | `split_statements` (y su test) |
| `does not support REPLACE TABLE AS SELECT` (local) | falta `USING DELTA` | `CREATE OR REPLACE TABLE ... USING DELTA AS ...` (L4) |
| `TABLE_OR_VIEW_NOT_FOUND` de un mart | el orden de los archivos | el número del archivo define el orden: 01 antes que 02 |
| la cascada no cierra | falta un término o `lost_other_mwh` no está calculado como cierre | revisá la identidad en el 02 |

## 📍 Punto de control

```bash
git commit -am "etapa-09: marts en SQL" && git diff etapa-09 HEAD --stat
```

## 🏋️ Ejercicio

1. Escribí un mart `10_mart_ice_losses.sql`: energía perdida por hielo por parque y mes, con el número de días con
   condición "Hielo" de `dim_weather`. ¿Qué parque pierde más?
2. En `mart_turbine_health`, cambiá la ventana de 7 días por una de 3. ¿Mejoran o empeoran las fallas anticipadas con
   ≥ 7 días? (pista: consultá `failure_within_30d` y `days_to_failure` en el test de integración o en Databricks).
3. Agregá a `mart_panel_cleaning` el agua usada por MWh recuperado. ¿Qué parque es más eficiente?
