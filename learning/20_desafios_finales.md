# 20 · Desafíos finales

Sin soluciones: son para que los encares como en un trabajo real (y los discutas con Genie Code).

1. **El jefe de parque desde el celular.** Hacé que el agent de Operación responda "¿cuánto hice ayer?" sin decir el
   parque, usando `current_user()` y `ops.park_access`. Medilo con 5 benchmarks nuevos.
2. **Batería en serio.** Reemplazá la simulación diaria de `mart_curtailment_battery` por una horaria que respete el
   estado de carga entre días y que descargue en las horas de precio spot más alto. ¿Cambia el ranking?
3. **Modelo predictivo de verdad.** Entrená una regresión logística (scikit-learn + MLflow) con las features de
   `mart_turbine_health` y la etiqueta `failure_within_30d`. Compará precisión/recall y días de anticipación con el
   health score por reglas. Registrá el modelo en UC y usalo desde una función.
4. **Política de limpieza óptima.** Simulá 2025 con la regla del umbral (`mart_panel_cleaning`) vs. la política
   histórica cada 75 días: MWh ganados, agua usada, USD netos.
5. **Escalar a SF=1.** Corré el pipeline con `scale_factor=1` en un workspace pago. Medí cada tarea, encontrá el cuello
   de botella (pista: `silver_scada`) y proponé 3 mejoras con evidencia del Query Profile.
6. **Liquidación horaria del PPA.** El MATER liquida por hora, no por mes. Rehacé `fact_ppa_settlement` horario con
   precio spot de cada hora. ¿Cambia la decisión spot vs. penalidad?
7. **Datos reales.** Reemplazá `cammesa_spot_prices` por los precios publicados por CAMMESA (descarga manual a landing)
   y adaptá el contrato de bronze. ¿Qué rompe?
8. **Alertas.** Un job que cada mañana mande por email/Slack las turbinas en riesgo ALTO y los PPA que proyectan
   faltante, usando la Conversation API para redactar el resumen.
9. **Genie One para el directorio.** Escribí 10 preguntas de "por qué" del directorio, corrélas en Agent mode y
   documentá dónde se equivoca y qué metadata le faltó.
10. **Costos.** Usá `system.billing.usage` para calcular cuánto cuesta (DBU) cada corrida del job y cada consulta de Genie.
