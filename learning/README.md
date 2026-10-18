# 🎓 Ruta de aprendizaje · Andes Viento Austral

21 módulos progresivos, todos con **los datos del proyecto**, ejercicios y soluciones.

**Antes de empezar** necesitás el proyecto desplegado y el job principal corrido una vez (los módulos consultan las
tablas de `andes_viento_dev`): seguí la [guía desde la web](../docs/11_guia_desde_la_web.md) o la
[guía por terminal](../docs/10_despliegue_y_cicd.md).

**Dónde están en el workspace:** si trajiste el código con un Git folder, en `andes-viento-austral/learning/`. Si
desplegaste con la terminal, en `Workspace → Users → <tu usuario> → .bundle → andes-viento-austral → dev → files →
learning`.

**Cómo abrir un módulo:** clic en el archivo → arriba elegí el cómputo (*Serverless* para los `.py`, *Serverless
Starter Warehouse* para los `.sql`) → corré las celdas de a una con Shift + Enter.

| # | módulo | tema | tablas que usa |
|---|---|---|---|
| 00 | [Bienvenida y entorno](00_bienvenida_y_entorno.py) | capas, volumen, recorrida | todas |
| 01 | [SQL: SELECT, WHERE, ORDER](01_sql_select_filtros_orden.sql) | lo básico y los NULL | `dim_park`, `v_park_daily` |
| 02 | [Agregaciones](02_sql_agregaciones.sql) | GROUP BY, HAVING, ratios bien calculados | `v_park_daily`, `mart_warranty_claims` |
| 03 | [JOINs](03_sql_joins.sql) | estrella, point-in-time, anti-join | `fact_*`, `dim_*` |
| 04 | [Subconsultas y CTEs](04_sql_subconsultas_ctes.sql) | preguntas en pasos, "hoy" del negocio | marts |
| 05 | [Funciones de ventana](05_sql_funciones_ventana.sql) | residuos vs. pares, móviles, QUALIFY | `fact_turbine_10min` |
| 06 | [Fechas, husos, tipos y nulos](06_sql_fechas_husos_tipos_nulos.sql) | 3 formatos, UTC vs. local, try_cast | `bronze.scada_turbine` |
| 07 | [SQL avanzado](07_sql_avanzado.sql) | structs, arrays, HOF, PIVOT, MERGE | bronze, silver |
| 08 | [Spark: arquitectura y DataFrames](08_spark_arquitectura_dataframes.py) | lazy, particiones, azar determinístico | generador |
| 09 | [Spark: transformaciones avanzadas](09_spark_transformaciones_avanzadas.py) | lag, explode, range join | silver |
| 10 | [Performance](10_spark_performance.py) | pruning, clustering, broadcast, skew | gold |
| 11 | [Delta Lake](11_delta_lake.sql) | historia, time travel, CDF, OPTIMIZE | silver |
| 12 | [Streaming y Auto Loader](12_streaming_autoloader.py) | checkpoints, schemaHints, drift | landing |
| 13 | [Calidad y SCD2](13_calidad_y_scd2.py) | reglas, cuarentena, versiones | `ops`, `silver` |
| 14 | [Modelado dimensional](14_modelado_dimensional.sql) | grano, bus, identidad de pérdidas | gold |
| 15 | [Declarativo vs. imperativo](15_declarativo_vs_imperativo.sql) | LDP, expectations, AUTO CDC | `ldp.*` |
| 16 | [Gobierno en Unity Catalog](16_gobierno_unity_catalog.sql) | comments, tags, máscaras, row filters, linaje | gold |
| 17 | [Metric views y funciones](17_metric_views_y_funciones.sql) | MEASURE(), trusted assets | `mv_*`, `fn_*` |
| 18 | [Genie](18_genie_agents.md) | agents, benchmarks, Agent mode, API | Genie |
| 19 | [Orquestación y CI/CD](19_orquestacion_cicd.md) | jobs, bundles, GitHub Actions | bundle |
| 20 | [Desafíos finales](20_desafios_finales.md) | 10 proyectos abiertos | todo |

**Cómo usarla:** un módulo por día. Intentá los ejercicios antes de mirar las soluciones (están más abajo en cada
notebook). Si te trabás, preguntale a Genie Code: tiene las convenciones del proyecto (`.assistant_instructions.md`).
