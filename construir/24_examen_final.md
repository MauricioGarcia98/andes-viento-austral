# 24 · Examen final: un caso de negocio nuevo, de punta a punta, sin mirar

## 🎯 Objetivo

Demostrar que sabés hacerlo **sin seguir una guía**: agregar al proyecto un caso de negocio nuevo que recorra **todas
las capas**, desde un archivo sucio hasta una respuesta de Genie medida con benchmarks. Si lo terminás, dominás el
proyecto.

**Reglas:**
- Podés mirar **tu propio código** y la documentación de Databricks. **No** mires el repo de referencia ni le pidas a una
  IA que lo escriba.
- Cada paso tiene un criterio de aceptación. No pases al siguiente sin cumplirlo.
- Tiempo estimado: 1 a 2 días.

## El caso: "¿Cuánto nos cuesta la nieve en las rutas?"

**Problema (lo plantea Ramiro Llancaqueo, Jefe de Mantenimiento):** en invierno, las rutas de Santa Cruz se cortan por
nieve y las cuadrillas no pueden llegar. Una falla que se resolvería en 1 día dura 5. Quiere saber **cuánta energía y
cuánta plata** se pierden por esas demoras, en qué parques y meses, para decidir si conviene tener una **cuadrilla
fija en Santa Cruz** en invierno (cuesta USD 45.000 por temporada).

**La pregunta para Genie:** *"¿Conviene tener una cuadrilla fija en Santa Cruz en invierno?"*

## Las 8 partes

### 1. La fuente (generador)

Agregá una fuente nueva, `vialidad_rutas`: el estado de las rutas de acceso a cada parque, por día, como lo publicaría
la Dirección de Vialidad: CSV con `;`, fecha `dd/MM/yyyy`, estado `TRANSITABLE | PRECAUCION | CORTADA`, motivo, y
suciedad realista (días repetidos, un parque mal escrito, días que faltan).

**Aceptación:** está en el registro `SOURCES`, `generate_all` crea su carpeta en landing, y hay un test en
`test_datagen.py` que verifica que en julio 2025 hay rutas cortadas en Santa Cruz y no en la Puna. Los cortes tienen que
ser **coherentes** con la nieve que ya genera `events.py` (no inventes otra nieve).

### 2. Bronze

**Aceptación:** `bronze.vialidad_rutas` se llena de forma incremental; la segunda ingesta da 0 filas nuevas.

### 3. Silver

Una función `clean_vialidad` (fecha, código de parque normalizado, estado en mayúsculas) y reglas de calidad (al menos
una `quarantine` y una `warn`). Deduplicá los días repetidos.

**Aceptación:** un test unitario por cada problema de suciedad que inyectaste en el paso 1.

### 4. Gold

Un hecho nuevo `fact_access_daily` (parque × día) con el estado de la ruta y, uniendo con `fact_maintenance_order`, las
**horas de demora por acceso** de las órdenes de ese día y la **energía perdida durante esas demoras** (pista: las
órdenes tienen `access_delay_h`; la energía, en `fact_turbine_10min`).

**Aceptación:** una invariante nueva en el quality gate que verifique algo de tu hecho (por ejemplo, que la energía
perdida por demoras nunca supere la pérdida total por fallas del día).

### 5. El mart del caso

`mart_snow_access.sql`: por parque y temporada de invierno, horas de demora, MWh perdidos por demoras, su valor (al
precio de realización del parque) y la comparación con el costo de la cuadrilla fija. Con la regla de decisión escrita
en el encabezado.

**Aceptación:** el test de integración pasa y el mart da un resultado que podés **explicar** (¿conviene o no? ¿en qué
parques?).

### 6. Gobierno y semántica

Entradas en el diccionario (comentarios para Genie, dueño, grano, PK), una medida nueva en una metric view y una
función certificada `fn_costo_nieve(anio)` que siga **las 7 reglas** del capítulo 18.

**Aceptación:** la función tiene parámetros `STRING`/`INT` (ningún `DATE`), tolera `'NULL'` y devuelve una fila de total.

### 7. Genie

Sumá la tabla, la función y **10 benchmarks** nuevos al agent de Mantenimiento predictivo (o creá uno). Desplegá.

**Aceptación:** `genie_eval.py --only <agent>` da al menos 9/10 en tus benchmarks nuevos **sin bajar** los que ya
pasaban. Si algo falla, arreglalo de abajo hacia arriba en la pirámide (capítulo 20) y anotá qué hiciste.

### 8. Operación y documentación

Un dashboard (o una página nueva en el de Mantenimiento), el caso escrito en `docs/03_casos_de_negocio.md` con el
formato problema → quién lo sufre → decisión → KPI → datos → tablas → dashboard → preguntas, y **una entrada en la
bitácora** con el error más difícil que te pasó.

**Aceptación:** el CI en verde, el job e2e de dev en verde con tu caso, y Genie respondiendo la pregunta principal
desde la plataforma.

## Autoevaluación

| parte | lo logré | me costó | lo que aprendí |
|---|:-:|---|---|
| 1. Fuente | | | |
| 2. Bronze | | | |
| 3. Silver | | | |
| 4. Gold | | | |
| 5. Mart | | | |
| 6. Gobierno y semántica | | | |
| 7. Genie | | | |
| 8. Operación y docs | | | |

Si te trabaste en una parte, volvé al capítulo de esa etapa y hacé su ejercicio. Si pudiste con todo: **construiste un
lakehouse de punta a punta, gobernado, operado y con Genie en el centro, vos solo.**

## ¿Y después?

- [docs/13 · Cómo hacerlo más real](../docs/13_hacerlo_mas_real.md): lo que le falta para ser una empresa de verdad.
- [learning/20 · Desafíos finales](../learning/20_desafios_finales.md): 10 proyectos abiertos más.
- Probá `scale_factor = 1` en un workspace pago y medí qué se rompe ([docs/09](../docs/09_performance_y_escala.md)).
