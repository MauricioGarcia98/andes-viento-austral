# 02 · Roles: quién decide qué (y por qué)

En un equipo de datos real cada decisión tiene un dueño. En este proyecto una sola persona (vos, con Genie Code)
asume todos los roles, pero conviene saber **con qué sombrero** se toma cada decisión: así sabés a quién
preguntarle cuando algo no cierra.

| rol | sombrero | decisiones que tomó en este proyecto | por qué |
|---|---|---|---|
| **Product Owner de datos** | "¿Para qué lo hacemos?" | Que el producto final sea **Genie** (no dashboards) y que cada área tenga su agent. Priorizar 5 casos de negocio con dueño, KPI y pregunta para Genie. | Los jefes de parque no van a abrir un dashboard a las 6 de la mañana; sí van a preguntar "¿cuánto generé ayer?" desde el celular. |
| **Data Engineer** | "¿Cómo llega el dato?" | Auto Loader con `schemaHints`, reinicio del stream ante columnas nuevas, `foreachBatch` + MERGE, corrección de relojes por percentil, `for_each` en dos tandas (referencia → telemetría). | El SCADA cambia de esquema, llega tarde y duplicado: el pipeline tiene que absorberlo sin intervención humana. |
| **Analytics Engineer** | "¿Cómo se modela?" | Estrella Kimball con `dim_turbine` SCD2 por cambio de componentes; la **identidad de pérdidas** (potencial = generado + pérdidas por causa) en el hecho de 10 min; marts en SQL; metric views con nombres de negocio. | Si la descomposición de pérdidas está en el dato, "¿por qué generamos menos?" se responde sumando columnas, sin magia. |
| **Platform / DataOps** | "¿Cómo se despliega y opera?" | Asset Bundle con targets dev/prod, compute serverless, catálogo creado por SQL (Free Edition), CI con lint + tests + `bundle validate`, deploy manual con aprobación. | Lo que no está en Git no existe: jobs, dashboards, App y Genie Agents se reconstruyen con un comando. |
| **Data Steward** | "¿Se puede confiar y quién lo puede ver?" | Diccionario YAML como fuente única (comments, PK/FK, tags), reglas warn/quarantine/fail, máscaras sobre contactos y precios PPA, row filter por parque. | Genie lee los comentarios: un comentario malo es una respuesta mala. Y el precio de un PPA no lo puede ver cualquiera. |
| **Analista BI** | "¿Cómo se ve?" | Un dashboard AI/BI por caso de negocio, generado por script; contadores arriba, tendencia en el medio, detalle accionable abajo. | El dashboard es para el seguimiento mensual; Genie para la pregunta del momento. |
| **Data Scientist** | "¿Qué va a pasar?" | Health score de turbinas con residuos térmicos vs. pares del parque (no contra un umbral fijo), etiqueta `failure_within_30d` para evaluar, regla económica de umbral para limpiar paneles, proyección del PPA con desempeño de 14 días. | Modelos simples, explicables y evaluables le ganan a un modelo opaco que el Jefe de Mantenimiento no va a creer. |
| **SRE** | "¿Qué pasa cuando falla?" | Quality gate al final del job, auditoría en `ops.pipeline_runs`, reintentos sólo para infraestructura, job diario idempotente, `repair-run` documentado, bitácora de errores reales. | Un número equivocado en Genie es peor que no tener número: el job prefiere fallar a publicar algo roto. |

## Decisiones de negocio (los dueños de cada problema)

| decisión | dueño | KPI de éxito |
|---|---|---|
| Invertir o no en baterías y en qué parque | Diego Achával (CFO) | Repago simple < 8 años |
| Abrir una orden **predictiva** antes de que se rompa la multiplicadora | Ramiro Llancaqueo (Mantenimiento) | ≥ 70 % de fallas mayores anticipadas con ≥ 7 días |
| Cuándo limpiar los paneles de cada parque solar | Natalia Mamaní (jefa de Abra Pampa) + Andrea Colque (HSE) | Pérdida por suciedad < 3 % con menos agua por MWh |
| Comprar en el spot o pagar la penalidad del PPA | Sofía Bertolini (Comercial) | Costo de faltantes ≤ el mínimo de las dos opciones |
| Reclamar al fabricante por disponibilidad | Ramiro Llancaqueo + Legal | 100 % de los meses reclamables reclamados |
| Explicar el desvío vs. presupuesto al directorio | Lucía Ferreyra (CEO) | Desvío explicado en ≥ 95 % por causas con nombre |

## Cómo se trabajó (etapas)

1. **Plan** (Product Owner): empresa, áreas, casos, preguntas para Genie.
2. **Generador** (Data Engineer + Data Scientist): física del viento y el sol, historia guionada, suciedad.
3. **Medallion** (Data Engineer + Analytics Engineer): bronze → silver → gold → ops, tests.
4. **Orquestación y CI/CD** (Platform).
5. **Gobierno y capa semántica** (Data Steward + Analytics Engineer).
6. **Genie** (Product Owner + Analista BI): agents, benchmarks, App.
7. **Deploy real** (SRE): corrida real, errores, bitácora.
8. **Didáctica y visuales**: docs, ruta de aprendizaje, diagramas.
