# 16 · Autoevaluación

Respondé sin mirar; las respuestas están al final (colapsadas).

1. ¿Por qué el `scale_factor` escala la cantidad de turbinas y no la cantidad de días?
2. En un CSV con `addNewColumns`, ¿por qué no se puede usar `.schema()` en Auto Loader? ¿Qué se usa?
3. ¿Qué hace el código cuando Auto Loader corta con `UNKNOWN_FIELD_EXCEPTION`? ¿Por qué no usar los reintentos del job?
4. ¿Cómo se detecta que Pampa del Castillo empezó a mandar la hora en UTC?
5. ¿Qué es un sensor "clavado" y cómo se reemplaza el viento para calcular el potencial?
6. ¿Por qué la primera versión de `dim_turbine` vale "desde 1900"?
7. Escribí la identidad que permite explicar el desvío vs. presupuesto.
8. ¿Por qué el curtailment valorizado a spot es engañosamente bajo?
9. ¿Qué compara el health score de una turbina y por qué no usa un umbral fijo de temperatura?
10. ¿Cuándo conviene comprar en el spot en vez de pagar la penalidad del PPA?
11. ¿Qué horas excluye la disponibilidad contractual?
12. ¿Por qué las dependencias de una `condition_task` necesitan `outcome`? ¿Y por qué `run_if: NONE_FAILED`?
13. ¿Qué gana Genie con una metric view frente a una tabla con la misma columna?
14. ¿Por qué las funciones de UC aceptan nombre O código de parque?
15. Si Genie responde mal "¿cuánto curtailment tuvo LEO en 2025?", ¿qué revisás primero?
16. ¿Qué ventaja tiene versionar el `serialized_space` en Git?
17. Arreglaste una función en el SQL Editor y al otro día el error volvió. ¿Qué pasó y qué tendrías que haber hecho?
18. Tu workspace tiene 180 tablas y Databricks dice que estás al 85 % de 500. ¿Cómo puede ser?
19. ¿Por qué un benchmark de Genie se escribe como SQL esperado y no como un número fijo?
20. ¿En qué capa de pruebas atraparías: (a) un reloj corrido mal corregido, (b) una disponibilidad negativa en gold,
    (c) Genie usando la función equivocada?

<details><summary><b>Respuestas</b></summary>

1. Para que la historia de negocio (2023-2026) esté completa a cualquier escala (ADR-002).
2. Porque con esquema fijo no hay evolución posible (`CF_ADD_NEW_NOT_SUPPORTED`). Se usa `cloudFiles.schemaHints`.
3. Reinicia el stream (hasta 3 veces): Auto Loader ya guardó el esquema ampliado. Los reintentos del job son para
   fallas de infraestructura y se gastan en errores esperables.
4. El percentil 5 de (recepción − hora del equipo) pasa a valer ~−3 h: `tz_corrected`.
5. Un sensor que repite exactamente el mismo valor 6 lecturas seguidas (1 h). Se usa el viento medio del resto del parque.
6. Para que las mediciones previas a la carga inicial del CMMS (o del mismo día antes de las 9) tengan versión.
7. real = presupuesto + recurso − (curtailment − asumido) − (fallas + mant. − asumido) − hielo − suciedad − otras.
8. Porque con la línea saturada el nodo Patagonia se desacopla y el precio cae justo en esas horas; esa energía estaba
   comprometida en PPA a ~65 USD/MWh.
9. La temperatura de la turbina contra el promedio del RESTO de su parque el mismo día (mismo viento y temperatura
   ambiente) y la vibración contra su propia historia. Un umbral fijo dispara en verano y no ve fallas en invierno.
10. Cuando el precio spot esperado (+ cargos) es menor que la penalidad por MWh del contrato.
11. Curtailment (red), hielo (fuerza mayor climática), mantenimiento programado, sin dato y demoras por ruta cortada.
12. Porque el motor tiene que saber qué rama sigue cada tarea (si no: `INVALID_PARAMETER_VALUE`). `NONE_FAILED` deja
    correr una tarea aunque una de sus dependencias haya quedado "excluded" por la otra rama.
13. Una definición única (ej. ratio = cociente de sumas) y sinónimos en el idioma del negocio.
14. Porque Genie le pasa lo que dijo el usuario.
15. Que la pregunta caiga en la tabla correcta (`fact_curtailment_hourly` vs. `v_park_daily`), el comentario de la
    columna, y si existe una función/metric view para eso; recién después, las instrucciones.
16. Revisión en PR, mismo agent en dev y prod, historia de cambios y rollback.
17. El job recreó la función con el SQL **desplegado**, que era el viejo. Había que arreglarlo en el repo y hacer
    `databricks bundle deploy` antes de correr (R13).
18. La cuota cuenta también los objetos borrados durante su retención (~7 días): catálogos borrados, `full_refresh` y
    cada `CREATE OR REPLACE VIEW` (R14).
19. Porque los datos cambian (el job diario agrega días, otro `scale_factor` cambia los números): el SQL calcula la
    respuesta correcta en el momento de evaluar.
20. (a) test unitario (`test_clock_skew_and_late_resend`); (b) quality gate (invariante "disponibilidad entre 0 y
    1"); (c) evaluación de Genie (benchmarks).
</details>
