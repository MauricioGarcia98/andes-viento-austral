# 14 · Preguntas frecuentes

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
