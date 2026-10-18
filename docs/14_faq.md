# 14 · Preguntas frecuentes

<details><summary><b>¿Necesito pagar algo o poner una tarjeta?</b></summary>
No. Todo corre en Databricks <b>Free Edition</b>, que no pide tarjeta. Tiene cuotas (cómputo diario, 5 corridas a la
vez, 500 tablas, 1 App) y el proyecto está pensado para entrar en ellas con <code>scale_factor = 0.1</code>.
</details>

<details><summary><b>¿Por dónde empiezo si nunca usé Databricks?</b></summary>
Por <a href="00_empeza_aca.md">00 · Empezá acá</a> (las 7 palabras mínimas) y después la
<a href="11_guia_desde_la_web.md">guía desde la web</a>: todo con clics, sin instalar nada.
</details>

<details><summary><b>¿Tengo que saber programar?</b></summary>
Para desplegarlo y usar Genie, no (guía web). Para cambiarlo, SQL alcanza para los marts, el gobierno y la capa
semántica; Python hace falta para el generador y silver. La <a href="../learning/README.md">ruta de aprendizaje</a>
arranca desde un <code>SELECT</code>.
</details>

<details><summary><b>Me llegó un mail: "reached 80 % (u 85 %) of the 500 Table per Metastore quota". ¿Qué hago?</b></summary>
Es la cuota de Free Edition: 500 tablas en todo tu workspace, <b>contando las borradas en los últimos ~7 días</b>.
No es urgente: lo que ya existe sigue funcionando. Medí, no uses <code>full_refresh</code> esos días y borrá lo que no
uses. Paso a paso: <a href="19_operacion_diaria.md#la-cuota-de-500-tablas">19 · La cuota de 500 tablas</a> (y R14 en la bitácora).
</details>

<details><summary><b>Arreglé algo en el SQL Editor y en la corrida siguiente "volvió" el error. ¿Por qué?</b></summary>
Porque el job usa el código <b>desplegado</b>, no lo que corriste a mano. Arreglalo en el repo y hacé
<code>databricks bundle deploy</code> antes de correr (R13 en la bitácora).
</details>

<details><summary><b>Genie me respondió distinto que ayer a la misma pregunta. ¿Está roto?</b></summary>
No necesariamente: Genie no es determinístico. Entre dos evaluaciones sin cambios variaron 1 o 2 respuestas por
agent. Lo preocupante son los fallos <b>repetidos</b> en el mismo tema: ahí hay que mirar el SQL y arreglar la causa
(<a href="12_genie.md#cómo-mejorar-un-agent-el-circuito">12 · Cómo mejorar un agent</a>).
</details>

<details><summary><b>¿Por qué el mes en curso dice "MES_ABIERTO" en la liquidación de los PPA?</b></summary>
Porque el job diario trae día a día y un mes incompleto no se liquida: compararía 1 día entregado contra el mes
entero comprometido. Para "¿vamos a llegar a fin de mes?" está la proyección (<code>fn_proyeccion_ppa</code>). Ver R15.
</details>

<details><summary><b>¿Cómo sé que lo que dice el proyecto es cierto?</b></summary>
Por las <a href="18_pruebas.md">7 capas de pruebas</a>: 27 tests unitarios, un test del pipeline entero, CI en cada
push, reglas de calidad fila por fila, 10 controles al final del job, 86 preguntas de prueba para Genie y la
verificación manual de los números de negocio.
</details>

<details><summary><b>¿Por qué no usé Free Edition con SF 1?</b></summary>
Free Edition tiene cuotas diarias de cómputo serverless y un tope de corridas simultáneas. SF 0,1 (37 turbinas,
~3 GB) entra cómodo; SF 1 en un workspace pago tarda proporcionalmente más (ver `09_performance_y_escala.md`).
</details>

<details><summary><b>¿Por qué el catálogo se crea a mano?</b></summary>
Porque con Default Storage la API que usa el bundle falla con `Metastore storage root URL does not exist`.
Por SQL funciona. Ver ADR-007 y la bitácora.
</details>

<details><summary><b>¿Por qué los datos terminan el 30/09/2026 si hoy es octubre?</b></summary>
El generador cubre 2023-01-01 → 2026-09-30. El job diario agrega un día por vez (2026-10-01, ...). Por eso las
instrucciones de Genie dicen "hoy = último día con datos", nunca `current_date()`.
</details>

<details><summary><b>¿Por qué los porcentajes de Cañadón León cambian con el scale_factor?</b></summary>
A SF 0,1 Cañadón León tiene 4 turbinas: si una rompe la multiplicadora pierde 1/4 de la flota. A SF 1 tiene 45.
La historia es la misma; el peso de cada causa cambia (ADR-002).
</details>

<details><summary><b>¿Por qué SQL para los marts y Python para silver?</b></summary>
Silver tiene lógica de ingeniería (relojes, unidades, CDC) que conviene testear con pytest. Los marts son reglas de
negocio que leen analistas y Genie Code: en SQL las entienden más personas.
</details>

<details><summary><b>¿Qué pasa si corro el job dos veces?</b></summary>
Nada malo: todo es idempotente. Bronze no re-lee archivos (checkpoint), silver usa MERGE, gold usa watermarks y
`replaceWhere`. Con `generate=true` se regeneran los mismos archivos (mismo seed) y Auto Loader los ve como nuevos
sólo si cambió su contenido o fecha de modificación (por eso la segunda corrida usa `generate=false`).
</details>

<details><summary><b>¿Cómo veo las máscaras funcionando si soy admin?</b></summary>
Como admin ves todo. Agregá otro usuario al workspace (o un grupo de prueba), dale SELECT sobre `gold` y consultá
como ese usuario. Ver `learning/16_gobierno_unity_catalog.sql`.
</details>

<details><summary><b>¿Genie puede equivocarse?</b></summary>
Sí. Por eso hay 86 benchmarks y `genie_eval.py`. Cuando falla, el arreglo casi siempre está en la metadata
(comentarios, metric views, funciones), no en las instrucciones. Ver `12_genie.md`.
</details>

<details><summary><b>¿Por qué NovaMart y Andes son repos distintos?</b></summary>
NovaMart es para entender la plataforma. Andes es para parecerse a un negocio real y usar Genie como lo usaría una
empresa. Comparten patrones (bundle, bronze, SCD2) y los errores aprendidos.
</details>
