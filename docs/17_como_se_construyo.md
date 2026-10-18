# 17 · Cómo se construyó, de cero al deploy real

> **Para qué sirve este documento:** contar en orden **qué se hizo, por qué en ese orden y cómo se verificó cada
> paso**, para que puedas repetir el proceso con otro negocio. Si sólo querés desplegar lo que ya está, andá a
> [10 · Replicar desde cero](10_despliegue_y_cicd.md).
>
> El proyecto lo construyó **Claude Code** (un asistente de programación con IA) trabajando con el dueño del repo,
> en dos días (17 y 18 de octubre de 2026), en 26 commits. Cada decisión de diseño está acá o en los
> [ADRs](05_arquitectura.md#decisiones-adrs); cada error real, en la [bitácora](08_bitacora.md).

## El método, en una línea

**Planificar → construir por etapas chicas → probar en local → desplegar → medir → arreglar → anotar.**
Ninguna etapa se dio por terminada sin una prueba que la verifique.

```
 Etapa 0        1-2            3              4             5              6           7               8
 pedido y  ─▶ esqueleto + ─▶ medallion + ─▶ bundle,  ─▶ gobierno,  ─▶ Genie   ─▶ deploy real, ─▶ docs,
 plan         generador      test local    jobs, CI    semántica,     como      Genie medido,   diagramas,
                                                       dashboards     código    errores R1-R16  learning
```

---

## Etapa 0 · Entender el pedido y planificar (antes de escribir código)

**Qué se pidió:** un proyecto de datos de punta a punta en Databricks, para aprender, con calidad de producción, en
español rioplatense, sobre una empresa ficticia lo más real posible (una generadora renovable argentina), con
**Genie en el centro**: que las áreas de la empresa le pregunten a Genie y obtengan respuestas confiables.

**Qué se hizo:**
1. Leer el pedido completo y separar requisitos técnicos (Unity Catalog, serverless, Free Edition, bundle, CI/CD,
   LDP, metric views, Genie...) de requisitos de negocio (casos, personas, preguntas).
2. Revisar el proyecto anterior del mismo autor, **NovaMart**, para reusar lo que ya funcionaba y no repetir sus 4
   errores de deploy (están al principio de la bitácora).
3. Hacer **cuatro preguntas** cuya respuesta cambiaba el diseño:

| pregunta | respuesta elegida | qué cambió |
|---|---|---|
| ¿Cuántos Genie Agents y cómo agruparlos? | 4 agents en 2 dominios | Operación (parques, mantenimiento) y Comercial (PPA, finanzas) |
| ¿Nombres de catálogos? | `andes_viento_dev` / `andes_viento` | un catálogo por ambiente |
| ¿Capturas de pantalla? | mockups + capturas de NovaMart | la guía web usa imágenes de NovaMart (mismos menús) |
| ¿Desplegar de verdad? | sí, dev y prod | el proyecto tenía que correr en un workspace real |

4. Escribir el **plan** (empresa, escala, estructura de carpetas, modelo, etapas, verificación) y mostrarlo antes
   de programar.

**Por qué así:** cambiar un plan cuesta minutos; cambiar 5.000 líneas de código cuesta días.

---

## Etapas 1-2 · Esqueleto y generador de datos

**Qué se hizo:**
1. **El esqueleto:** `pyproject.toml` (el paquete `andes_viento`), la estructura `src/`, `notebooks/`, `tests/`, la
   configuración de `ruff` y `pytest`.
2. **La empresa en código** (`src/andes_viento/datagen/reference.py`): 13 parques con su provincia, fabricante,
   enlace (fibra o satélite), viento medio, altura; 3 fabricantes con sus formatos de SCADA; personas; cuadrillas;
   contratos PPA; feriados argentinos; inflación y dólar mes a mes.
3. **La física** (`physics.py`): viento como función continua del tiempo (estacionalidad, ciclo diario, rachas),
   curva de potencia, temperatura, irradiancia solar. Está escrita **dos veces**, en Spark (para generar millones de
   filas en paralelo) y en Python (para simulaciones chicas), y un test verifica que den lo mismo.
4. **Los eventos** (`events.py`): fallas, mantenimientos, cortes de comunicación, relojes corridos, sensores
   clavados, órdenes de CAMMESA, suciedad de paneles. Se calculan en el *driver* (son pocos) y se mandan a todos los
   nodos por *broadcast* ([ADR-003](adr/ADR-003-generador-con-fisica.md)).
5. **La historia guionada** (`reference.STORY`): lo que Genie tiene que poder explicar. Por ejemplo, julio 2025 en
   Cañadón León: ola polar, mantenimiento de la estación transformadora con tope de red del 50 % y una multiplicadora
   rota.
6. **Los 11 generadores** (`generators.py`) y el escritor (`writer.py`): cada fuente con su formato real (JSON
   comprimido, CSV con `;` y coma decimal, CDC) y su **suciedad** (duplicados, nulos, 3 formatos de fecha, MW en vez
   de kW, columnas nuevas desde cierta fecha) ([06 · Fuentes](06_fuentes_y_suciedad.md)).

**Decisiones clave:**
- **Determinístico:** la misma semilla da exactamente los mismos datos. Sin eso no se puede depurar.
- **El `scale_factor` escala la flota, no los días** ([ADR-002](adr/ADR-002-scale-factor-por-flota.md)): con 0,1 hay 37
  turbinas pero los mismos 3 años y 9 meses de historia.
- **Sin UDFs de Python:** todo en funciones nativas de Spark (10-50 veces más rápido).

**Cómo se verificó:** tests de física, eventos y generador (`test_physics.py`, `test_events.py`, `test_datagen.py`).

---

## Etapa 3 · El pipeline medallion y la prueba local

**Qué se hizo, capa por capa:**

| capa | qué hace | código |
|---|---|---|
| **landing** | archivos crudos en un volumen de Unity Catalog, una carpeta por fuente y día | `datagen/writer.py` |
| **bronze** | Auto Loader los lee tal cual; con `schemaHints` fija los tipos difíciles; si aparece una columna nueva, reinicia el stream solo | `ingestion/bronze.py` |
| **silver** | tipa, corrige relojes y husos, convierte MW → kW, anula sensores clavados, deduplica, historiza activos (SCD2), aplica CDC a órdenes, aplica reglas de calidad | `silver/` |
| **gold** | modelo estrella: 7 dimensiones y 5 hechos; cada 10 minutos de cada turbina sabe cuánto generó, cuánto pudo generar y **por qué no** | `gold/` |
| **marts** | 9 archivos SQL, uno por caso de negocio | `sql/marts/` |
| **ops** | auditoría de corridas, watermarks, resultados de calidad, cuarentena | `setup.py`, `utils/audit.py` |

**La prueba local:** antes de tocar Databricks, el pipeline completo se corrió con Spark y Delta en la computadora
(`pytest -m integration`). Eso encontró **8 errores** (L1-L8 en la bitácora), por ejemplo:
- 540 claves foráneas huérfanas porque la primera versión SCD2 empezaba con el primer dato y no "desde siempre" (L6).
- Contratos PPA que siempre se cumplían: el caso de negocio no tenía gracia (L7).
- La foto inicial del CMMS no incluía los cambios anteriores al inicio (L8).

**Por qué así:** un error encontrado en local cuesta 5 minutos; en la nube, una corrida de 45 minutos.

---

## Etapa 4 · Orquestación, pipeline declarativo y CI/CD

**Qué se hizo:**
1. **El bundle** (`databricks.yml` + `resources/`): todo lo del workspace como código, con dos *targets* (dev y prod).
2. **El job principal** (`andes_e2e.job.yml`): 12 tareas con las funciones avanzadas de Lakeflow Jobs:
   - `condition_task` (`should_generate`): ¿generar datos o sólo procesar?
   - 3 `for_each_task`: generar 11 fuentes, procesar 8 entidades de referencia y 3 de telemetría, en paralelo.
   - `run_if: NONE_FAILED`: bronze corre por cualquiera de las dos ramas de la condición.
3. **El job diario** (simula la llegada de un día nuevo) y el **de mantenimiento** (OPTIMIZE, VACUUM, ANALYZE).
4. **El pipeline declarativo** (`pipelines/*.sql`): el mismo problema resuelto con LDP, para comparar estilos
   ([ADR-006](adr/ADR-006-imperativo-y-declarativo.md)).
5. **Los notebooks delgados** (`notebooks/`): cada uno hace `%run ./_bootstrap` y llama a **una** función del paquete.
   La lógica vive en `src/`, donde se puede testear.
6. **CI/CD** (`.github/workflows/ci.yml`): lint, tests, `bundle validate` y deploy manual con aprobación para prod.

**Cómo se verificó:** `databricks bundle validate -t dev` y `-t prod`.

---

## Etapa 5 · Gobierno, capa semántica y dashboards

**Qué se hizo:**
1. **Gobierno desde un YAML** ([ADR-008](adr/ADR-008-gobierno-desde-yaml.md)): `governance/data_dictionary.yml` describe
   cada tabla y columna gold. Un script genera de ahí los comentarios, PK/FK, tags (dominio, dueño, PII) y el
   [diccionario de datos](04_diccionario_de_datos.md). Así la documentación y la base nunca se contradicen.
2. **Seguridad:** máscaras sobre emails, teléfonos y precios de contratos; *row filter* para que cada jefe de parque
   vea sólo su parque (`sql/governance/04_masks_and_row_filters.sql`).
3. **Metric views** (`sql/semantic/01_metric_views.sql`): 7 vistas con las métricas oficiales (energía generada,
   pérdida por curtailment, disponibilidad...) y sinónimos en el idioma de la gente ("recorte", "limitación").
4. **Funciones de Unity Catalog** (`02_functions.sql`): 7 "respuestas certificadas" que Genie puede invocar, como
   `fn_explicar_desvio(parque, mes)`.
5. **6 dashboards** generados por script (`scripts/build_dashboards.py`), uno por caso de negocio.

**Por qué:** Genie lee los comentarios, las metric views y las funciones. Un comentario malo es una respuesta mala
([12 · Genie](12_genie.md), la pirámide).

---

## Etapa 6 · Genie como código

**Qué se hizo:**
1. **Un YAML por agent** (`genie/src/*.yml`): tablas, metric views, funciones, instrucciones, ejemplos SQL, preguntas
   de muestra y **benchmarks** (pregunta + SQL esperado) ([ADR-009](adr/ADR-009-genie-como-codigo.md)).
2. `scripts/build_genie.py` los convierte al formato de la API (`serialized_space`).
3. `scripts/deploy_genie.py` crea o actualiza los agents (idempotente: busca por título).
4. `scripts/genie_ask.py` (una pregunta) y `scripts/genie_eval.py` (las 86) usan la Conversation API.
5. Una **App** de Streamlit (`apps/genie_chat/`) como ejemplo de chat propio con la Conversation API.
6. Para **Genie Code**: `.assistant_instructions.md` y 2 *skills* con las convenciones del proyecto.
7. [Preguntas de Agent mode](genie/agent_mode.md) con la respuesta esperada.

---

## Etapa 7 · El deploy real (donde aparece la verdad)

Todo se desplegó y corrió en un workspace **Free Edition** real. Esta etapa tuvo tres partes.

### 7a · Las primeras corridas del job (errores R1-R10)

| corrida | resultado | qué se aprendió |
|---|---|---|
| #1 | falló en `gold_marts` | se desplegó antes del arreglo de una ventana SQL sin paréntesis (R2, el mismo error que L5 en local); había 5 corridas a la vez y Free Edition no deja más (R1) |
| reparaciones | verde | Auto Loader ignora archivos sobrescritos (R3), el separador de SQL cortaba en `;` dentro de los comentarios (R4), un alias tapado en una metric view (R5), `SHOW VIEWS` no anda entre catálogos (R6), disponibilidad −0,0002 frenada por el gate (R7) |
| calibración | — | la flota era "demasiado sana" y los casos de negocio no tenían reclamos: se agregó el lote defectuoso de multiplicadoras (R10) |
| **#3** | **12/12 verde en ~43 min** | la corrida de referencia; sus tiempos están en el README |

También: la API de Genie exige las listas ordenadas (R8) y la App necesita un nombre único (R9).

### 7b · Genie medido (errores R11-R16)

Con los datos listos, se corrió la evaluación de las 86 preguntas. El recorrido fue 0 % → 74 % → 91 % → 98,8 %. Cada
salto tuvo una causa concreta (tabla completa en [18 · Pruebas](18_pruebas.md#6-evaluación-de-genie)):
- **R11:** Genie rechaza funciones certificadas con parámetros `DATE` (0 % hasta arreglarlo).
- **R12:** Genie pasa el texto `'NULL'` en vez del valor nulo → las funciones se volvieron tolerantes.
- **R13:** un arreglo aplicado a mano se deshizo porque el job usó la versión desplegada → regla de oro: `bundle deploy`
  antes de correr.
- **R15:** el job diario trajo un mes parcial que aparecía como un faltante de USD 1,4 M → mes en curso sin liquidar.
- **R16:** Genie prefiere una función certificada aunque no sirva → cada función, sólo en el agent donde encaja.

### 7c · Prod, job diario, LDP y la cuota de tablas

- **Prod:** 12/12 verde. Genie desplegado también en prod.
- **Job diario:** agregó el 2026-10-01 en ~12 minutos; la condición salteó la generación, como debía.
- **LDP:** verde al primer intento en 3 minutos.
- **R14:** Databricks avisó que se llegaba al 85 % de la cuota de 500 tablas. Causa: las tablas borradas cuentan ~7
  días y cada `CREATE OR REPLACE VIEW` dejaba una "fantasma". Arreglo: las vistas se recrean sólo si cambiaron; se
  borraron proyectos viejos del workspace ([19 · Operación](19_operacion_diaria.md)).

---

## Etapa 8 · Documentación, visuales y ruta de aprendizaje

- **Docs** (`docs/00` a `19`), cada caso de negocio en el formato problema → KPI → tablas → dashboard → preguntas.
- **12 diagramas** Excalidraw (svg y png) y animaciones (el job, el proceso completo, la arquitectura).
- **21 módulos** en `learning/`, de un `SELECT` a un Genie Agent, con ejercicios y soluciones.
- **README** con los resultados reales y la portada animada con los tiempos medidos.

---

## Línea de tiempo (de los commits)

| cuándo (oct-2026) | hito |
|---|---|
| 17, 17:17 | repo creado |
| 17, 21:03 | etapas 1-2: esqueleto y generador |
| 17, 21:51 | etapas 3-6 (primera versión completa) |
| 17, 22:14 | primera corrida real + prueba local completa |
| 17, 23:04 - 23:14 | arreglos R1-R10, Genie desplegado en dev, bitácora |
| 18, 00:00 - 01:16 | Genie medido y arreglado (R11, R12); rondas 1 y 2 |
| 18, 01:32 - 02:48 | prod, job diario, LDP, cuota de tablas (R13-R15) |
| 18, 02:57 - 04:28 | README con resultados, rondas 5-7 de Genie (R16), 98,8 % |

El detalle de cada cambio está en `git log`.

---

## Si lo hicieras de nuevo con otro negocio

1. **Empezá por las preguntas**, no por las tablas: ¿qué le van a preguntar a Genie y qué decisión habilita cada
   respuesta?
2. **Escribí la historia** que los datos tienen que contar (los "por qué") antes de generar un solo dato.
3. **Probá en local todo lo que se pueda**; la nube es para lo que sólo existe en la nube.
4. **Desplegá temprano** una versión chica: los errores de plataforma (cuotas, permisos, APIs) sólo aparecen ahí.
5. **Medí a Genie con benchmarks desde el primer día.** Sin medición, "anda bien" es una opinión.
6. **Anotá cada error** con su causa y su arreglo: es la documentación más útil para el próximo.
