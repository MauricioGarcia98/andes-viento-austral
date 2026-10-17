# 06 · Fuentes de datos y la "suciedad" que traen

Volúmenes a **scale_factor = 1** (flota real) para 2023-01-01 → 2026-09-30. A SF 0,1 todo es ~10 veces menor.

| fuente | sistema origen | formato en landing | frecuencia | volumen SF=1 | dueño |
|---|---|---|---|---|---|
| `scada_turbine` | SCADA de cada fabricante → concentrador del parque → VSAT/fibra | JSON gzip | 10 min por turbina | ~75 M filas (≈ 200 M lecturas de sensor/año) | Operación |
| `inverter_5min` | Plataforma de monitoreo solar | CSV | 5 min, sólo de día | ~50 M filas | Operación NOA |
| `cmms_assets` | CMMS (registro de activos) | CSV CDC (op I/U/D) | cada cambio | ~2 mil filas | Mantenimiento |
| `cmms_work_orders` | CMMS (órdenes) | JSON CDC con imagen completa | cada hito | ~60 mil filas | Mantenimiento |
| `cmms_crews` | CMMS | CSV | cada cambio | 7 filas | Mantenimiento |
| `cammesa_dispatch` | CAMMESA (instrucciones de despacho) | JSON | cada instrucción | ~10 mil filas | Comercial |
| `cammesa_spot_prices` | CAMMESA (precios horarios) | CSV `;` formato CAMMESA | diario + definitivos mensuales | ~130 mil filas | Finanzas |
| `ppa_contracts` | Comercial (sistema de contratos) | CSV CDC | cada adenda | ~40 filas | Comercial |
| `weather` | Proveedor meteorológico | JSON gzip | horario (observado + pronóstico) | ~850 mil filas | Operación |
| `fx_rates` | BNA | CSV `;` | días hábiles | ~900 filas | Finanzas |
| `generation_budget` | Finanzas (presupuesto P50) | CSV | anual + re-presupuesto | ~700 filas | Finanzas |

## La suciedad, una por una (y dónde se resuelve)

| problema real | cómo aparece en los datos | dónde se resuelve | regla de calidad |
|---|---|---|---|
| **3 formatos de fecha** según fabricante | AWS: `2025-07-15T10:20:00-03:00` · HTW: `ts_epoch_ms` · PEI: `15/07/2025 10:20:00` hora local | `silver.transforms.parse_scada_time` | `fecha_parseable` (quarantine) |
| **Relojes desfasados** | el `ts` de algunas turbinas corre 3 a 14 min durante semanas | `estimate_clock_offset` (percentil 5 de la demora) | `reloj_sincronizado` (warn) |
| **Cambio de huso horario** | Pampa del Castillo manda UTC desde el 1-abr-2024 en el mismo formato | mismo método: offset ≈ -3 h → `tz_corrected` | `huso_horario_correcto` (warn) |
| **Huecos satelitales** | cortes de 1-14 h en parques VSAT; 40 % se pierde, 60 % llega después | lo perdido se estima en el mart (`data_gap_mwh`) | `llego_a_tiempo` (warn) |
| **Datos tardíos** | re-envíos con `received_at` horas o días después (otro `ingest_date`) | MERGE insert-only + watermark por `_ingested_at` en gold | — |
| **Duplicados** | 0,4 % de re-envíos idénticos; CSV de inversores re-exportados | `dedupe_first_arrival` (gana la primera copia) | gate: sin duplicados |
| **Sensores clavados** | temperatura, anemómetro o vibración con el mismo valor 6-72 h | `flag_stuck_sensors` (6 lecturas iguales = 1 h) → null + viento del parque | `sensores_sin_clavarse` (warn) |
| **Unidades mezcladas kW/MW** | PEI manda MW (y declara la unidad sólo desde el firmware 2.4); FIA exportó MW en la columna `ac_power_kw` | `fix_power_units` (unidad declarada o magnitud + viento) | `unidad_correcta` (warn) |
| **Turbinas renombradas** | Cerro Arenales pasa de `CRV-07` a `CRV-WTG007` (jun-2024); dos turbinas siguen con el nombre viejo 6 semanas | `silver.asset_tags`: TODOS los nombres que tuvo cada equipo | `turbina_conocida` (quarantine) |
| **Valores imposibles** | viento 99,9 (código de error), 999 °C, potencia 1,5× la nominal | `null_impossible` | `valores_fisicamente_posibles` (warn) |
| **Nulos** | 0,4 % por sensor | se propagan; el potencial usa el viento del parque | `potencia_informada` (warn) |
| **Schema drift JSON** | HT-OS 5.0 agrega `ice_detector`, `oil_particle_count`, `tower_accel_mg` desde mar-2025 | Auto Loader `addNewColumns` + reinicio del stream en código | — |
| **Schema drift CSV** | columna `soiling_sensor_pct` desde jun-2025 | Auto Loader con `schemaHints` (sin `.schema()`) | — |
| **CDC** | activos, contratos y órdenes con op I/U/D, re-envíos, órdenes creadas por error y borradas | SCD2 (`scd2_merge`), `merge_cdc` con DELETE | — |
| **Formato argentino** | `45.231,50` (punto de miles, coma decimal), `dd/MM/yyyy` | `ar_number`, `try_date` | `precio_positivo`, `dolar_positivo` (fail) |
| **Hora 1..24 de CAMMESA** | la hora 24 es de 23 a 24 | `clean_spot_prices` | `hora_cammesa_valida` |
| **Versiones de precio** | PRELIMINAR al día siguiente, DEFINITIVO el 10 del mes siguiente | MERGE con `version_rank` (DEFINITIVO no se pisa) | — |
| **Instrucciones corregidas y anuladas** | v1 con un horario, v2 MODIFICADA; algunas ANULADA | última versión por `instruction_id`; gold excluye anuladas | `ventana_valida` |
| **Fechas viejas del CMMS** | `dd/MM/yyyy HH:mm` antes de la migración de mar-2024 | `local_to_utc` con varios formatos | `evento_con_fecha` |
| **Inflación** | la hora-hombre en pesos se multiplica por ~8 entre 2023 y 2025 | gold convierte a USD con el dólar del día de cierre | — |
| **Feriados sin dólar** | el BNA no publica fines de semana ni feriados | `dim_date.fx_ars_usd` repite el último publicado | — |

## Estacionalidad y eventos del país que están en los datos

- **Viento patagónico** más fuerte en primavera-verano (oct-ene), más flojo en invierno; frentes de 2 a 10 días.
- **Sol de la Puna**: irradiancia altísima (3.700 m), "invierno altiplánico" con lluvias en ene-mar que limpian paneles,
  tormentas de polvo en ago-oct.
- **Hielo en palas** en Santa Cruz y en los parques altos de Chubut (may-sep); **nieve** que corta la RN40 y la RN3.
- **Curtailment** creciente 2023 → 2026, más en noches, fines de semana, **feriados** y primavera.
- **Precio spot**: alto en invierno (gas) y en el pico de las 19-22 h; el nodo Patagonia se desacopla con congestión.
- **Macro**: inflación mensual (25 % en dic-2023, ~2 % en 2025), devaluación del 13-dic-2023, crawling peg.
- **Historia guionada**: julio 2025 en Cañadón León (ola polar del 3 al 5, mantenimiento de la ET del 10 al 20 con tope
  del 60 %, multiplicadora rota el 26 con 21 días de parada).
