# 12 · Etapa 8 · Gold: dimensiones y hechos

## 🎯 Objetivo

Construir el **modelo estrella** que usan el negocio, los dashboards y Genie: 7 dimensiones (qué, quién, dónde,
cuándo) y 5 hechos (lo que pasó, medido). La pieza central es la **identidad de pérdidas**: cada 10 minutos de cada
turbina saben cuánto generaron, cuánto **podían** generar y **por qué no** (red, falla, mantenimiento, hielo, otras).
Con eso, "¿por qué generamos menos?" se responde sumando columnas.

**Archivos:** `src/andes_viento/gold/__init__.py`, `gold/dimensions.py`, `gold/facts.py`.

## 📚 Conceptos

- **Modelo estrella (Kimball):** una tabla de **hechos** en el centro (las medidas: kWh, horas, USD) rodeada de
  **dimensiones** (los contextos: turbina, parque, día). Cada hecho tiene claves (`turbine_key`, `park_key`,
  `date_key`) que apuntan a las dimensiones. Es el modelo más fácil de consultar para una persona y para Genie
  ([07 · Modelado](../docs/07_modelado_dimensional.md)).
- **Grano:** qué representa **una fila** de un hecho. Hay que poder decirlo en una frase: "una turbina en un bloque de
  10 minutos". Si no se puede, el hecho está mal diseñado.
- **Clave sustituta:** un número propio del modelo (`turbine_key`) en lugar de la clave del sistema (`asset_id`).
  Con SCD2 hace falta: una turbina tiene varias versiones y cada versión tiene su clave.
- **Join *point-in-time*:** unir cada hecho con la versión de la dimensión **vigente en ese momento** (la
  multiplicadora que tenía la turbina **cuando** midió, no la de hoy).
- **Miembro "desconocido" (clave −1):** una fila especial en cada dimensión para los hechos sin correspondencia. Un
  hecho **nunca** se pierde por una clave rota; queda apuntando a "Desconocido" y el gate lo cuenta.

## 🧱 Paso a paso

### 1. `dimensions.py`

| dimensión | tipo | grano | de dónde sale |
|---|---|---|---|
| `dim_date` | fija | un día | calendario + feriados argentinos + dólar |
| `dim_park` | SCD1 | un parque | `reference.PARKS` + conteo de equipos vigentes |
| `dim_turbine` | **SCD2** | una versión de turbina | `silver.assets_history` |
| `dim_inverter` | SCD1 | un inversor | activos vigentes |
| `dim_weather` | fija | parque × día | `silver.weather_hourly` |
| `dim_contract` | **SCD2** | una versión de contrato | `silver.contracts_history` |
| `dim_crew` | SCD1 | una cuadrilla | `silver.crews` |

**`dim_date`:**
```python
    days = spark.sql(f"SELECT explode(sequence(DATE'{cfg.start_date}', DATE'{end}', INTERVAL 1 DAY)) AS date")
    w = Window.orderBy("date").rowsBetween(Window.unboundedPreceding, 0)
    ... .withColumn("fx_ars_usd", F.last("ars_per_usd", ignorenulls=True).over(w))
```
- Llega hasta `end_date + 400 días`: margen para el job diario y para proyecciones.
- **El dólar de los días sin cotización** (fines de semana y feriados): `last(..., ignorenulls=True)` sobre una ventana
  "desde el principio hasta hoy" = **la última cotización conocida**. Así cualquier costo en pesos de cualquier día se
  puede pasar a dólares.
- Nombres de meses y días en castellano, estaciones **australes** (julio es invierno), `is_business_day`.

**`dim_turbine` (SCD2):**
```python
    reason = (F.when(prev("asset_tag").isNull(), "ALTA")
              .when(F.col("is_deleted"), "BAJA")
              .when(prev("asset_tag") != F.col("asset_tag"), "RENOMBRE")
              .when(prev("gearbox_serial") != F.col("gearbox_serial"), "CAMBIO_MULTIPLICADORA")
              ...)
    dim = (hist ... .select(
        F.xxhash64("asset_id", "valid_from").alias("turbine_key"),
        ...,
        F.when(F.col("version") == 1, F.lit(BEGIN_OF_TIME).cast("timestamp"))
         .otherwise(F.col("valid_from")).alias("effective_from"),
        F.coalesce("valid_to", F.lit(FAR_FUTURE).cast("timestamp")).alias("effective_to"), ...))
```
- `turbine_key = xxhash64(asset_id, valid_from)`: una clave **determinística** por versión. Reconstruir la dimensión
  da las mismas claves; los hechos viejos siguen apuntando bien.
- `change_reason` dice **por qué** hay una versión nueva (lo pregunta Mantenimiento: "¿cuántas multiplicadoras se
  cambiaron?").
- **La primera versión vale "desde siempre" (1900):** el CMMS se carga a las 9 de la mañana del primer día; las
  lecturas de las 00:00 a las 9:00 de ese día no tenían versión vigente y quedaban huérfanas. Fueron 540 (L6 de la
  bitácora, lo atrapó el gate).
- `effective_to = 9999-12-31` para la vigente: así el join *point-in-time* es un simple `>=` y `<`, sin casos con NULL.

**`dim_weather`:** agrega el clima horario por parque y día (observado y pronóstico) y le pone una **condición**
legible: "Hielo", "Nevada", "Polvo en suspensión", "Lluvia", "Viento extremo", "Calma", "Normal". Genie responde
"¿cuántos días de hielo hubo?" con esa columna. `weather_key = yyyymmdd · 100 + índice del parque` es una clave
legible (`2025071509` = Cañadón León, 15-07-2025) que los hechos calculan sin unir.

`dim_contract` repite el patrón SCD2 de turbinas. Todas agregan su fila **−1**. `load_dimensions` las reescribe
completas (son chicas).

### 2. `facts.py`

**El join *point-in-time*:**
```python
def _pit_join(fact, dim, natural_key, fact_key, ts_col, key_col, extra=()):
    d = dim.select(F.col(natural_key).alias("_nk"), key_col, F.col("effective_from").alias("_ef"),
                   F.col("effective_to").alias("_et"), *extra)
    joined = fact.join(F.broadcast(d), (fact[fact_key] == d["_nk"]) & (fact[ts_col] >= d["_ef"])
                       & (fact[ts_col] < d["_et"]), "left")
    return joined.drop("_nk", "_ef", "_et").withColumn(key_col, F.coalesce(F.col(key_col), F.lit(UNKNOWN_KEY).cast("bigint")))
```
`left` + `coalesce(..., -1)`: un hecho sin versión no se pierde, queda en "desconocido".

**La carga incremental (`_incremental`):**
```
watermark anterior ─▶ fechas (reading_date) que recibieron datos nuevos en silver ─▶ recalcular SÓLO esas fechas
                      (filas con _ingested_at > watermark)                          ─▶ replaceWhere reading_date IN (...)
                                                                                    ─▶ watermark = max(_ingested_at)
```
- La primera vez (sin watermark) o con `full_refresh`, se escribe todo.
- **Por qué por fecha y no por fila:** si llega una lectura tardía del 15 de julio, hay que recalcular **todo** el 15 de
  julio de ese parque (el viento promedio del parque cambia, los agregados diarios cambian). Recalcular días enteros con
  `replaceWhere` es correcto e idempotente.
- `if dates == []: return 0`: el job diario sin datos nuevos para una tabla no hace nada.

**`fact_turbine_10min`, la identidad de pérdidas:**
```python
    f = (f ... .join(slots, ["park_code", "ts_utc"], "left")          # instrucciones de CAMMESA en slots de 10 min
        .withColumn("_park_wind", F.avg("wind_ms").over(Window.partitionBy("park_code", "ts_utc")))
        .withColumn("wind_used_ms", F.coalesce("wind_ms", "_park_wind"))       # anemómetro roto: el del parque
        .withColumn("potential_kw", _power_curve(F.col("wind_used_ms"), F.col("_rated_kw"), F.col("_rated_ms")))
        .withColumn("_gen_kw", F.greatest(F.coalesce("power_kw", F.lit(0.0)), F.lit(0.0)))
        .withColumn("_lost_kwh", F.greatest(F.coalesce("potential_kw", 0.0) - F.col("_gen_kw"), 0.0) / 6))
    lost = lambda st: F.when(F.col("status_code").isin(*st), F.col("_lost_kwh")).otherwise(0.0)
    ...
        F.round(lost([4]), 3).alias("lost_curtailment_kwh"),
        F.round(lost([1]), 3).alias("lost_fault_kwh"),
        F.round(lost([2]), 3).alias("lost_maintenance_kwh"),
        F.round(lost([3]), 3).alias("lost_icing_kwh"),
        F.round(lost([0, 5, 6]), 3).alias("lost_other_kwh"),
```
**La identidad** ([ADR-005](../docs/adr/ADR-005-identidad-de-perdidas.md)):
```
potential_kwh = energy_kwh + lost_curtailment + lost_fault + lost_maintenance + lost_icing + lost_other
```
- **El potencial** es la curva de potencia aplicada al viento medido. Si el anemómetro está roto o clavado (NULL en
  silver), se usa **el viento promedio del resto del parque** en ese mismo instante (`wind_source =
  'promedio_parque'`). Sin eso, una turbina parada por falla con el anemómetro apagado "no habría perdido nada".
- **La diferencia** potencial − generado se asigna **entera a una causa**, según el estado de esos 10 minutos. `/ 6`
  pasa de kW (potencia) a kWh (energía en 10 minutos).
- `lost_other` (generando normal pero menos de lo que dice la curva) absorbe la eficiencia y el ruido.
- `data_quality_flags` lista qué se corrigió en esa lectura: Genie y los analistas pueden filtrar los datos dudosos.

**Los otros hechos:**

| hecho | tipo Kimball | grano | lo interesante |
|---|---|---|---|
| `fact_inverter_hourly` | agregado | inversor × hora | `expected_clean_kwh`: lo que daría con paneles limpios (irradiancia × potencia DC × temperatura); la diferencia con lo real es la suciedad (capítulo 13) |
| `fact_curtailment_hourly` | agregado | parque × hora | se arma **desde** `fact_turbine_10min`; le suma el precio spot del nodo en dólares: `lost_value_spot_usd` |
| `fact_maintenance_order` | *accumulating snapshot* | una orden | se reescribe entera; tiempos de respuesta, espera, reparación y parada; mano de obra en pesos **pasada a dólares con el dólar del día de cierre**; `is_warranty_relevant` |
| `fact_availability_daily` | *periodic snapshot* | turbina × día | tres disponibilidades: **contractual** (la de la garantía, excluye red, hielo, mantenimiento programado y sin dato), técnica y por energía |

**La disponibilidad contractual:**
```python
    excluded = F.col("curtailed_h") + F.col("icing_h") + F.col("maintenance_h") + no_data
    _clamp01(F.try_divide(period - excluded - F.col("fault_h"), period - excluded)).alias("availability_contractual")
```
`1 − falla / (24 − excluidas)`, como en la norma IEC 61400-26: al fabricante sólo se le cuentan las horas de falla que
son su responsabilidad. `_clamp01` acota a [0, 1]: las horas redondeadas sumaban 24,0002 y la disponibilidad daba
−0,0002; el gate frenó el job (R7 de la bitácora). `try_divide` da NULL si el denominador es 0 (un día entero
excluido) en vez de fallar.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| estrella | una tabla ancha gigante | redundancia enorme (el nombre del parque repetido 7 millones de veces) y difícil de mantener; igual hay una vista ancha por parque y día para Genie (`v_park_daily`, capítulo 13) |
| pérdidas por causa en el hecho de 10 min | calcularlas en cada consulta | cada análisis las calcularía distinto; con la identidad, todos suman lo mismo |
| viento del parque como sustituto | dejar NULL | una falla con el anemómetro apagado "no perdería energía" |
| claves por hash | `monotonically_increasing_id()` | cambia en cada reconstrucción y rompe los hechos ya escritos |
| primera versión desde 1900 | desde el primer registro | lecturas huérfanas el primer día (L6) |
| incremental por fecha con `replaceWhere` | MERGE por fila | recalcular el día entero es más simple, idempotente y correcto para los agregados |

## ✅ Probalo

Gold necesita silver completo (activos incluidos), así que la prueba de verdad es el test de integración del capítulo
14. Mientras tanto:
```bash
ruff check src
pytest -m "not integration"     # 25 passed (nada se rompió)
python -c "from andes_viento.gold import facts, dimensions; print(len(dimensions.DIMENSIONS), 'dimensiones,', len(facts.FACTS + facts.DERIVED) + 1, 'hechos')"
```

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| hechos con `turbine_key = -1` | no hay versión vigente en ese instante | primera versión desde `BEGIN_OF_TIME`; `effective_to` en `FAR_FUTURE` |
| `fact_turbine_10min` tiene más filas que `silver.scada_10min` | el join con los slots de curtailment duplica | `dropDuplicates(["park_code", "ts_utc"])` en los slots |
| la disponibilidad da negativa o > 1 | redondeos | `_clamp01` |
| `[DIVIDE_BY_ZERO]` | modo ANSI | `try_divide` |
| el incremental no recalcula un día con datos tardíos | el watermark se tomó del destino, no de silver | `_max_ingested(silver)` y `_changed_dates` por `_ingested_at` |
| `[INVALID_IDENTIFIER] pd-gearbox_c` | un `OVER` sin paréntesis en SQL | es del capítulo 13 (L5) |

## 📍 Punto de control

```bash
git commit -am "etapa-08: gold, dimensiones y hechos" && git diff etapa-08 HEAD --stat
```

## 🏋️ Ejercicio

1. Escribí en SQL la verificación de la identidad de pérdidas para un día: `sum(potential_kwh)` contra la suma de
   `energy_kwh` y las cinco pérdidas. ¿Cuánto da la diferencia?
2. Agregá a `fact_availability_daily` una columna `availability_excl_snow` que además excluya las horas con la ruta
   cortada por nieve. ¿De dónde sacarías ese dato? (pista: `access_delay_h` de las órdenes).
3. Agregá a `dim_date` una columna `is_long_weekend` (feriado pegado a un fin de semana). ¿Para qué caso de negocio
   serviría?
