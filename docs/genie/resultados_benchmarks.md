# Resultados de los benchmarks de Genie

Target `dev` · generado por `scripts/genie_eval.py`.

| agent | pregunta | respuesta esperada | Genie |
|---|---|---|---|
| 01_operacion_parques | ¿Cuántos parques eólicos tiene la empresa? | `9` | ✅ |
| 01_operacion_parques | ¿Cuántos parques solares hay en cada provincia? | `Catamarca, 2` | ✅ |
| 01_operacion_parques | ¿Cuál es el último día con datos? | `2026-10-01` | ✅ |
| 01_operacion_parques | ¿Cuánta energía generó la empresa en 2025 en MWh? | `814178.4` | ✅ |
| 01_operacion_parques | ¿Qué parque generó más energía en 2025? | `San Julián Meseta, 91572.8` | ✅ |
| 01_operacion_parques | ¿Cuál fue el desvío contra presupuesto de Cañadón León en julio 2025? | `-18.4` | ✅ |
| 01_operacion_parques | ¿Cuántos MWh perdió Cañadón León por curtailment en julio 2025? | `819.0` | ✅ |
| 01_operacion_parques | ¿Cuántos MWh se perdieron por hielo en julio 2025 en Cañadón León? | `350.0` | ✅ |
| 01_operacion_parques | ¿Qué parque tuvo el peor desvío contra presupuesto en el acumulado de 2025? | `Abra Pampa Solar, -0.0584` | ✅ |
| 01_operacion_parques | Factor de capacidad de Pico Truncado Alto en 2025 | `0.5313` | ✅ |
| 01_operacion_parques | ¿En qué mes de 2025 la empresa generó más? | `2025-11, 84174.9` | ✅ |
| 01_operacion_parques | ¿Cuántos días con condición 'Nevada' tuvo Cañadón León en 2025? | `4` | ✅ |
| 01_operacion_parques | ¿Cuál es la pérdida por suciedad de Susques Solar en 2025 en MWh? | `1743.3` | ✅ |
| 01_operacion_parques | ¿Cuántas limpiezas de paneles se hicieron en 2025 por parque? | `ABR, 5` | ✅ |
| 01_operacion_parques | ¿Qué parques solares hay que limpiar según el último día? | `Tinogasta Sol, LIMPIAR` | ✅ |
| 01_operacion_parques | Suciedad media de los paneles de Abra Pampa en septiembre 2025 | `4.88` | ✅ |
| 01_operacion_parques | ¿Cuánta energía perdió la empresa por curtailment en 2025? | `10856.0` | ✅ |
| 01_operacion_parques | ¿Qué parque eólico tuvo más pérdidas por fallas en 2025? | `Pico Truncado Alto, 5810.5` | ✅ |
| 01_operacion_parques | Generación diaria de Rawson Sur en la última semana con datos | `2026-09-25, 269.4` | ✅ |
| 01_operacion_parques | ¿Cuál fue el viento medio de Garayalde en julio 2025? | `8.76` | ✅ |
| 01_operacion_parques | ¿Cuántos días con condición 'Hielo' tuvo cada parque eólico en invierno 2025? | `San Julián Meseta, 10` | ✅ |
| 01_operacion_parques | Disponibilidad contractual promedio de Bahía Deseado en 2025 | `0.9538` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas turbinas hay en total? | `37` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas turbinas tiene cada fabricante? | `Aurora Wind Systems, 13` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas fallas mayores hubo en total? | `26` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas fallas mayores de multiplicadora hubo en 2025? | `9` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántos días estuvo parada la turbina de Cañadón León que rompió la multiplicadora en julio 2025? | `21.0` | ✅ |
| 02_mantenimiento_predictivo | MTTR de correctivas en 2025 en horas | `96.1` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas órdenes preventivas se hicieron en 2024? | `73` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuál fue el costo total de mantenimiento en USD en 2025? | `2745859.0` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuánto costó la mano de obra en pesos en 2024 vs 2023? | `2023, 1.11414916E8` | ✅ |
| 02_mantenimiento_predictivo | ¿Qué parque tiene más horas de falla en 2025? | `PIC, 2277.3` | ✅ |
| 02_mantenimiento_predictivo | Disponibilidad contractual móvil 12 meses de Cañadón León en el último mes | `0.99942` | ✅ |
| 02_mantenimiento_predictivo | ¿En cuántos meses corresponde reclamar al fabricante Hanse Turbinen Werke? | `50` | ❌ |
| 02_mantenimiento_predictivo | ¿Cuántos USD de liquidated damages se devengaron en total? | `823906.0` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas turbinas están en riesgo alto hoy? | `0` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas versiones tiene la turbina WTG00033 en dim_turbine? | `3` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas multiplicadoras se reemplazaron? | `20` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas turbinas fueron renombradas? | `5` | ✅ |
| 02_mantenimiento_predictivo | Horas promedio de espera de repuestos en fallas mayores | `339.7` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas horas de demora por ruta cortada por nieve hubo en 2025? | `670.0` | ✅ |
| 02_mantenimiento_predictivo | ¿Qué cuadrilla atendió más órdenes? | `CU-PAT-04, 263` | ✅ |
| 02_mantenimiento_predictivo | ¿Cuántas órdenes están abiertas? | `7` | ✅ |
| 02_mantenimiento_predictivo | Disponibilidad contractual promedio de la flota eólica en 2025 | `0.9832` | ✅ |
| 03_comercial_ppa | ¿Cuántos contratos PPA vigentes hay? | `7` | ✅ |
| 03_comercial_ppa | ¿Qué cliente tiene el precio PPA más alto? | `Data Center Austral S.R.L., 75.35` | ✅ |
| 03_comercial_ppa | ¿Qué contrato se rescindió? | `PPA-2022-006, Frigorífico Pampeano S.A.` | ✅ |
| 03_comercial_ppa | ¿Qué contrato empezó en 2025? | `PPA-2025-008, Papelera Mesopotámica S.A.` | ✅ |
| 03_comercial_ppa | ¿Cuál fue el cumplimiento total de la cartera en 2025? | `0.9844` | ✅ |
| 03_comercial_ppa | ¿Qué cliente tuvo el peor cumplimiento en 2025? | `Data Center Austral S.R.L., 0.966` | ✅ |
| 03_comercial_ppa | ¿Cuántos meses tuvo faltante el contrato del Data Center Austral? | `5` | ✅ |
| 03_comercial_ppa | ¿Cuánto hubiera costado cubrir todos los faltantes de 2025 con la mejor opción? | `261010.0` | ✅ |
| 03_comercial_ppa | ¿En cuántos casos convenía comprar en el spot en vez de pagar la penalidad? | `0` | ✅ |
| 03_comercial_ppa | ¿Cuánto MWh entregamos a Litio de la Puna en 2025? | `67993.2` | ✅ |
| 03_comercial_ppa | ¿Cuáles son los parques de origen del contrato del data center? | `["SJU","LEO"]` | ✅ |
| 03_comercial_ppa | ¿Cuántas versiones tiene el contrato PPA-2023-007? | `5` | ✅ |
| 03_comercial_ppa | ¿Cuántos MWh/mes subió el volumen comprometido del data center con la adenda de 2024 (diferencia)? | `2206.1000000000004` | ✅ |
| 03_comercial_ppa | Precio actual del contrato de Aluminios Patagónicos | `61.55` | ✅ |
| 03_comercial_ppa | Ingresos PPA totales en 2025 en USD | `3.5434628E7` | ✅ |
| 03_comercial_ppa | ¿Qué recomendación hay hoy para el contrato del Data Center Austral? | `EN_CAMINO` | ✅ |
| 03_comercial_ppa | ¿Cuántos contratos proyectan faltante este mes? | `0` | ✅ |
| 03_comercial_ppa | Cumplimiento proyectado de la papelera este mes | `1.0` | ✅ |
| 03_comercial_ppa | ¿Cuál fue el mes con mayor costo en USD de faltantes (mejor opción) en toda la historia? | `2025-06, 222848.0` | ❌ |
| 03_comercial_ppa | Volumen comprometido total mensual de la cartera vigente | `39554.4` | ✅ |
| 03_comercial_ppa | ¿Cuántos clientes son del sector Minería? | `1` | ✅ |
| 04_finanzas_mercado | ¿Cuántos MWh se perdieron por curtailment en 2024? | `11215.3` | ✅ |
| 04_finanzas_mercado | ¿Creció el curtailment de 2023 a 2025? | `2023, 4340.6` | ❌ |
| 04_finanzas_mercado | ¿Qué parque perdió más energía por curtailment en 2025? | `Cañadón León, 3719.5` | ✅ |
| 04_finanzas_mercado | ¿Qué porcentaje del potencial perdió San Julián Meseta por curtailment en 2025? | `0.0297` | ✅ |
| 04_finanzas_mercado | Valor a precio spot del curtailment de 2025 | `146078.0` | ✅ |
| 04_finanzas_mercado | ¿Qué parque y tamaño de batería tiene el mejor repago? | `Cañadón León, BESS-30x2` | ✅ |
| 04_finanzas_mercado | ¿Cuántos años de repago tiene la batería BESS-20x4 en Cañadón León? | `92.1` | ✅ |
| 04_finanzas_mercado | ¿A qué hora local se pierde más energía por curtailment? | `6, 2944.7` | ✅ |
| 04_finanzas_mercado | ¿Cuál fue el dólar oficial el 13 de diciembre de 2023? | `800.0` | ✅ |
| 04_finanzas_mercado | Precio spot medio del nodo Patagonia en 2025 en USD/MWh | `47.53` | ✅ |
| 04_finanzas_mercado | Precio spot medio en horas con curtailment vs sin curtailment en Patagonia | `true, 11.36` | ✅ |
| 04_finanzas_mercado | Desvío total en MWh vs presupuesto de toda la empresa en 2025 | `1826.6` | ❌ |
| 04_finanzas_mercado | Desvío porcentual vs presupuesto de toda la empresa en 2024 | `0.0015` | ❌ |
| 04_finanzas_mercado | ¿Qué porcentaje de curtailment asumía el presupuesto 2025 para la Patagonia? | `0.04` | ❌ |
| 04_finanzas_mercado | ¿Cuánto costó la mano de obra de mantenimiento en dólares en 2024? | `618276.0` | ✅ |
| 04_finanzas_mercado | Costo de mantenimiento total en USD en 2023 | `715537.0` | ✅ |
| 04_finanzas_mercado | Precio de realización PPA de Cañadón León en julio 2025 | `73.87` | ✅ |
| 04_finanzas_mercado | ¿Cuál fue el efecto del recurso (viento) en el desvío de Cañadón León en julio 2025? | `-279.9` | ✅ |
| 04_finanzas_mercado | ¿Cuántas horas con orden de CAMMESA tuvo Pico Truncado Alto en 2025? | `344` | ❌ |
| 04_finanzas_mercado | ¿Cuál es el motivo más frecuente de las órdenes de CAMMESA? | `RESTRICCION_TRANSPORTE, 8688` | ✅ |
| 04_finanzas_mercado | Inversión total si se instala BESS-10x4 en todos los parques eólicos | `1.59936E7` | ❌ |

| agent | benchmarks | aciertos |
|---|---|---|
| 01_operacion_parques | 22 | 22 |
| 02_mantenimiento_predictivo | 22 | 21 |
| 03_comercial_ppa | 21 | 20 |
| 04_finanzas_mercado | 21 | 15 |
