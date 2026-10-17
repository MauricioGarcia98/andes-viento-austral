# 04 · Diccionario de datos (gold)

> Generado desde `governance/data_dictionary.yml`. Data Steward: Florencia Paz.

| tabla | dominio | dueño | grano |
|---|---|---|---|
| [`dim_date`](#dim_date) | comun | Datos | 1 fila por día calendario |
| [`dim_park`](#dim_park) | operacion | Martín Quiroga (Gerente de Operaciones) | 1 fila por parque |
| [`dim_turbine`](#dim_turbine) | mantenimiento | Ramiro Llancaqueo (Jefe de Mantenimiento) | 1 fila por versión de turbina (SCD2) |
| [`dim_inverter`](#dim_inverter) | operacion | Martín Quiroga (Gerente de Operaciones) | 1 fila por inversor |
| [`dim_weather`](#dim_weather) | operacion | Martín Quiroga (Gerente de Operaciones) | 1 fila por parque y día |
| [`dim_contract`](#dim_contract) | comercial | Sofía Bertolini (Gerente Comercial) | 1 fila por versión de contrato (SCD2) |
| [`dim_crew`](#dim_crew) | mantenimiento | Ramiro Llancaqueo (Jefe de Mantenimiento) | 1 fila por cuadrilla |
| [`fact_turbine_10min`](#fact_turbine_10min) | operacion | Martín Quiroga (Gerente de Operaciones) | 1 fila por turbina cada 10 minutos |
| [`fact_inverter_hourly`](#fact_inverter_hourly) | operacion | Martín Quiroga (Gerente de Operaciones) | 1 fila por inversor y hora |
| [`fact_curtailment_hourly`](#fact_curtailment_hourly) | comercial | Diego Achával (CFO) | 1 fila por parque eólico y hora |
| [`fact_maintenance_order`](#fact_maintenance_order) | mantenimiento | Ramiro Llancaqueo (Jefe de Mantenimiento) | 1 fila por orden de trabajo (accumulating snapshot) |
| [`fact_availability_daily`](#fact_availability_daily) | mantenimiento | Ramiro Llancaqueo (Jefe de Mantenimiento) | 1 fila por turbina y día |
| [`fact_ppa_settlement`](#fact_ppa_settlement) | comercial | Sofía Bertolini (Gerente Comercial) | 1 fila por contrato y mes |
| [`mart_generation_vs_budget`](#mart_generation_vs_budget) | direccion | Lucía Ferreyra (CEO) / Diego Achával (CFO) | 1 fila por parque y mes |
| [`mart_curtailment_battery`](#mart_curtailment_battery) | finanzas | Diego Achával (CFO) | 1 fila por parque, opción de batería y mes |
| [`mart_turbine_health`](#mart_turbine_health) | mantenimiento | Joaquín Ortiz (Ingeniero de Confiabilidad) | 1 fila por turbina y día |
| [`mart_panel_cleaning`](#mart_panel_cleaning) | operacion | Natalia Mamaní (Jefa de parque Abra Pampa) / Andrea Colque (HSE) | 1 fila por parque solar y día |
| [`mart_ppa_forecast`](#mart_ppa_forecast) | comercial | Sofía Bertolini (Gerente Comercial) | 1 fila por contrato y fecha de corte |
| [`mart_warranty_claims`](#mart_warranty_claims) | mantenimiento | Ramiro Llancaqueo (Jefe de Mantenimiento) | 1 fila por parque eólico y mes |

## dim_date

Calendario operativo con feriados nacionales argentinos, estación austral y dólar oficial BNA (último publicado).

**Grano:** 1 fila por día calendario · **Dueño:** Datos

**PK:** `date_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `date_key` | Clave entera yyyymmdd (ej. 20250715). |  |
| `date` | Fecha calendario (día operativo local, UTC-3). |  |
| `year_month` | Año-mes en texto 'yyyy-MM' (ej. '2025-07'). Usar para agrupar por mes. |  |
| `month_name` | Nombre del mes en español en minúscula (enero..diciembre). |  |
| `season` | Estación del hemisferio sur: verano (dic-feb), otoño, invierno (jun-ago), primavera. |  |
| `is_holiday` | Verdadero si es feriado nacional argentino (incluye días puente). |  |
| `holiday_name` | Nombre del feriado (ej. 'Día de la Independencia'). |  |
| `fx_ars_usd` | Tipo de cambio oficial BNA vendedor, pesos por dólar. Fines de semana y feriados repiten el último publicado. |  |

## dim_park

Los 13 parques de Andes Viento Austral: 9 eólicos (Chubut y Santa Cruz) y 4 solares (Jujuy y Catamarca).

**Grano:** 1 fila por parque · **Dueño:** Martín Quiroga (Gerente de Operaciones)

**PK:** `park_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `park_key` | Clave subrogada del parque (-1 = desconocido). |  |
| `park_code` | Código corto del parque: RAW, MAD, GAR, CRV, PAM, DES, PIC, SJU, LEO (eólicos) y SUS, ABR, TIN, FIA (solares). |  |
| `park_name` | Nombre del parque (ej. 'Cañadón León', 'Susques Solar'). Los usuarios lo nombran así. |  |
| `technology` | 'Eólico' o 'Solar'. |  |
| `province` | Provincia: Chubut, Santa Cruz, Jujuy o Catamarca. |  |
| `region` | PATAGONIA (eólicos) o NOA (solares). |  |
| `installed_mw` | Potencia instalada en MW a la escala del proyecto (suma de equipos vigentes). |  |
| `cammesa_node` | Nodo de precio de CAMMESA: PATAGONIA o NOA. |  |
| `distance_to_base_km` | Distancia en km a la base de mantenimiento (Comodoro Rivadavia o Jujuy). |  |
| `travel_hours` | Horas de viaje estándar de una cuadrilla desde la base. |  |
| `comm_link` | Enlace de datos: FIBRA o VSAT (satelital, con cortes). |  |
| `park_manager` | Jefe/a de parque responsable. |  |
| `turbine_manufacturer` | Fabricante de los aerogeneradores del parque (null en solares). |  |
| `guaranteed_availability` | Disponibilidad garantizada por el fabricante (0,97 = 97 %). |  |
| `ld_usd_per_point_mw` | Liquidated damages: USD por punto porcentual por MW instalado y año. |  |
| `water_cost_usd_m3` | Costo del agua de limpieza puesta en el parque, USD por m3 (solares). |  |

## dim_turbine

Aerogeneradores con historia SCD2: cambia de versión al reemplazar multiplicadora o rodamientos, actualizar firmware o renombrar. Para la versión actual filtrar is_current = true.

**Grano:** 1 fila por versión de turbina (SCD2) · **Dueño:** Ramiro Llancaqueo (Jefe de Mantenimiento)

**PK:** `turbine_key`  
**FK:**   

| columna | descripción | etiquetas |
|---|---|---|
| `turbine_key` | Clave subrogada de la VERSIÓN de la turbina (-1 = desconocida). |  |
| `turbine_id` | Identificador estable del CMMS (ej. WTG00031). No cambia aunque cambie el nombre. |  |
| `turbine_tag` | Nombre operativo (ej. 'CRV-WTG007'; antes de jun-2024 en Cerro Arenales era 'CRV-07'). |  |
| `manufacturer` | Fabricante: Aurora Wind Systems, Hanse Turbinen Werke o Pampa Eólica Industrial. |  |
| `model` | Modelo del aerogenerador (ej. HT-150/4.5). |  |
| `rated_kw` | Potencia nominal en kW. |  |
| `gearbox_serial` | Número de serie de la multiplicadora instalada en esta versión. |  |
| `change_reason` | Motivo de la nueva versión: ALTA, RENOMBRE, CAMBIO_MULTIPLICADORA, CAMBIO_RODAMIENTO_PPAL, CAMBIO_RODAMIENTO_GENERADOR, ACTUALIZACION_FIRMWARE. |  |
| `effective_from` | Inicio de vigencia de la versión (UTC). |  |
| `effective_to` | Fin de vigencia (UTC); 9999-12-31 si es la vigente. |  |
| `is_current` | Verdadero para la versión vigente. |  |

## dim_inverter

Inversores centrales de 2,5 MW de los parques solares.

**Grano:** 1 fila por inversor · **Dueño:** Martín Quiroga (Gerente de Operaciones)

**PK:** `inverter_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `inverter_tag` | Nombre del inversor (ej. 'SUS-INV03'). |  |
| `dc_kwp` | Potencia DC instalada (paneles) en kWp. |  |
| `panels` | Cantidad de paneles conectados. |  |

## dim_weather

Clima diario por parque (observado y pronóstico del día anterior) con una condición resumida.

**Grano:** 1 fila por parque y día · **Dueño:** Martín Quiroga (Gerente de Operaciones)

**PK:** `weather_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `weather_key` | Clave yyyymmdd*100 + índice del parque (ej. 2025071509). |  |
| `weather_condition` | Resumen del día: Normal, Calma, Viento extremo, Lluvia, Nevada, Hielo, Polvo en suspensión, Sin dato. |  |
| `is_extreme` | Verdadero si hubo hielo, nevada o viento extremo. |  |
| `wind_avg_ms` | Viento medio a 100 m (m/s). |  |
| `temp_min_c` | Temperatura mínima (°C). |  |
| `snow_cm` | Nieve acumulada en el día (cm). |  |
| `ice_risk_hours` | Horas con riesgo ALTO de hielo en palas. |  |
| `dust_aod` | Profundidad óptica de aerosoles (polvo en suspensión); > 0,13 es mucho polvo en la Puna. |  |
| `forecast_wind_error_pct` | Error del pronóstico de viento del día anterior, en % (positivo = sobreestimó). |  |
| `forecast_precip_mm` | Lluvia pronosticada (mm) el día anterior. |  |

## dim_contract

Contratos PPA del MATER con clientes industriales. SCD2: cada adenda (precio, volumen, contacto, rescisión) crea una versión.

**Grano:** 1 fila por versión de contrato (SCD2) · **Dueño:** Sofía Bertolini (Gerente Comercial)

**PK:** `contract_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `contract_id` | Identificador del contrato (ej. PPA-2023-007). |  |
| `client_name` | Razón social del cliente (ej. 'Data Center Austral S.R.L.'). |  |
| `sector` | Sector del cliente: Aluminio, Cemento, Automotriz, Minería, Retail, Alimentos, Tecnología, Papel. |  |
| `client_cuit` | CUIT del cliente. | pii=identificador_fiscal |
| `contact_name` | Nombre del contacto comercial del cliente. | pii=nombre |
| `contact_email` | Email del contacto comercial del cliente. | pii=email |
| `contact_phone` | Teléfono del contacto comercial del cliente. | pii=telefono |
| `price_usd_mwh` | Precio del contrato en USD por MWh (confidencial comercial). | clasificacion=confidencial |
| `committed_mwh_month` | Volumen comprometido por mes (MWh). |  |
| `penalty_usd_mwh` | Penalidad por MWh faltante (take-or-pay), en USD. |  |
| `tolerance_pct` | Faltante tolerado sin penalidad (0,05 = 5 %). |  |
| `source_parks` | Parques de origen de la energía del contrato (array de park_code). |  |

## dim_crew

Cuadrillas de mantenimiento propias (base Patagonia y base NOA).

**Grano:** 1 fila por cuadrilla · **Dueño:** Ramiro Llancaqueo (Jefe de Mantenimiento)

**PK:** `crew_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `leader_name` | Líder de la cuadrilla. | pii=nombre |
| `leader_phone` | Teléfono del líder de la cuadrilla. | pii=telefono |
| `specialty` | Especialidad (mecánica pesada, eléctrica, palas, preventivo, limpieza, inversores). |  |

## fact_turbine_10min

Mediciones SCADA limpias de cada aerogenerador cada 10 minutos, con energía potencial y la pérdida asignada a su causa. potential_kwh = energy_kwh + lost_* (aprox.).

**Grano:** 1 fila por turbina cada 10 minutos · **Dueño:** Martín Quiroga (Gerente de Operaciones)

**PK:** `turbine_id, ts_utc`  
**FK:** `park_key` → `dim_park.park_key`, `turbine_key` → `dim_turbine.turbine_key`, `weather_key` → `dim_weather.weather_key`, `date_key` → `dim_date.date_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `reading_date` | Día operativo local (UTC-3). |  |
| `ts_utc` | Inicio del slot de 10 minutos en UTC (reloj corregido). |  |
| `ts_local` | Inicio del slot en hora argentina. |  |
| `state` | Estado: PRODUCIENDO, LIMITADA_RED (curtailment de CAMMESA), FALLA, MANTENIMIENTO, HIELO, VIENTO_BAJO, VIENTO_EXTREMO. |  |
| `energy_kwh` | Energía generada en el slot (kWh). |  |
| `potential_kwh` | Energía que se podría haber generado según la curva de potencia y el viento (kWh). |  |
| `lost_curtailment_kwh` | kWh perdidos por orden de CAMMESA de bajar potencia. |  |
| `lost_fault_kwh` | kWh perdidos por fallas. |  |
| `lost_maintenance_kwh` | kWh perdidos por mantenimiento programado. |  |
| `lost_icing_kwh` | kWh perdidos por hielo en palas. |  |
| `lost_other_kwh` | Otras pérdidas (performance). |  |
| `wind_ms` | Viento medido por el anemómetro de la turbina (m/s); null si estaba clavado. |  |
| `gearbox_bearing_c` | Temperatura del rodamiento de la multiplicadora (°C). |  |
| `vibration_mm_s` | Vibración RMS del tren de potencia (mm/s). |  |
| `oil_particle_count` | Partículas en el aceite de la multiplicadora (sólo HT-OS 5.0, desde mar-2025). |  |
| `data_quality_flags` | Problemas corregidos: reloj_corregido, huso_corregido, unidad_mw_a_kw, llego_tarde, sensor_clavado, viento_sustituido. |  |

## fact_inverter_hourly

Generación solar por inversor y hora, con la energía que se esperaría con paneles limpios.

**Grano:** 1 fila por inversor y hora · **Dueño:** Martín Quiroga (Gerente de Operaciones)

**PK:** `inverter_id, hour_ts_utc`  
**FK:** `park_key` → `dim_park.park_key`, `inverter_key` → `dim_inverter.inverter_key`, `date_key` → `dim_date.date_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `energy_kwh` | Energía AC generada en la hora (kWh). |  |
| `expected_clean_kwh` | Energía esperada con paneles limpios para la irradiancia medida (kWh). |  |
| `performance_ratio` | energy_kwh / expected_clean_kwh. |  |
| `soiling_sensor_pct` | Suciedad medida por sensor (%), disponible desde jun-2025. |  |

## fact_curtailment_hourly

Curtailment por parque y hora: energía perdida por órdenes de CAMMESA y su valor al precio spot del nodo.

**Grano:** 1 fila por parque eólico y hora · **Dueño:** Diego Achával (CFO)

**PK:** `park_code, hour_ts_utc`  
**FK:** `park_key` → `dim_park.park_key`, `date_key` → `dim_date.date_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `lost_curtailment_mwh` | MWh que no se pudieron generar por la orden de CAMMESA. |  |
| `grid_limit_mw` | Tope de potencia ordenado por CAMMESA (MW). |  |
| `grid_reason` | Motivo: RESTRICCION_TRANSPORTE, MANTENIMIENTO_ET, CONTROL_FRECUENCIA. |  |
| `spot_usd_mwh` | Precio spot del nodo en USD/MWh (ojo: con congestión el nodo Patagonia se desacopla y cae). |  |
| `lost_value_spot_usd` | Valor de la energía perdida a precio spot (USD). |  |

## fact_maintenance_order

Órdenes de mantenimiento del CMMS con hitos, tiempos (respuesta, espera de repuestos, reparación) y costos en USD.

**Grano:** 1 fila por orden de trabajo (accumulating snapshot) · **Dueño:** Ramiro Llancaqueo (Jefe de Mantenimiento)

**PK:** `order_id`  
**FK:** `park_key` → `dim_park.park_key`, `crew_key` → `dim_crew.crew_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `order_type` | CORRECTIVA, PREVENTIVA o LIMPIEZA. |  |
| `severity` | MAYOR (multiplicadora, rodamientos) o MENOR. |  |
| `component` | Componente intervenido (GEARBOX, MAIN_BEARING, GENERATOR_BEARING, PITCH, YAW, CONVERTIDOR, IGBT, LIMPIEZA...). |  |
| `downtime_hours` | Horas desde la falla hasta el fin de la reparación. |  |
| `waiting_hours` | Horas esperando repuestos/grúa después de llegar. |  |
| `access_delay_h` | Horas de demora por ruta cortada (nieve): fuerza mayor para la garantía. |  |
| `labor_cost_ars` | Costo de mano de obra en pesos (sube con la inflación). |  |
| `total_cost_usd` | Costo total en USD: repuestos + mano de obra al dólar del cierre + grúa + agua. |  |
| `water_m3` | Agua usada en limpiezas de paneles (m3). |  |

## fact_availability_daily

Disponibilidad diaria por turbina: contractual (garantía del fabricante), técnica y por energía.

**Grano:** 1 fila por turbina y día · **Dueño:** Ramiro Llancaqueo (Jefe de Mantenimiento)

**PK:** `turbine_id, reading_date`  
**FK:** `park_key` → `dim_park.park_key`, `date_key` → `dim_date.date_key`  

| columna | descripción | etiquetas |
|---|---|---|
| `availability_contractual` | 1 - horas de falla / (24 - horas excluidas). Excluye red, hielo, mantenimiento programado y sin dato. |  |
| `fault_h` | Horas en falla. |  |
| `excluded_h` | Horas excluidas del cálculo contractual. |  |

## fact_ppa_settlement

Liquidación mensual de cada PPA: comprometido, entregado, faltante y costo de cubrirlo (penalidad vs. compra spot).

**Grano:** 1 fila por contrato y mes · **Dueño:** Sofía Bertolini (Gerente Comercial)

**PK:** `contract_id, month_start`  

| columna | descripción | etiquetas |
|---|---|---|
| `compliance_pct` | Entregado / comprometido (1 = 100 %). |  |
| `shortfall_mwh` | MWh faltantes por debajo del mínimo (comprometido menos tolerancia). |  |
| `penalty_cost_usd` | Costo de pagar la penalidad por el faltante (USD). |  |
| `spot_cover_cost_usd` | Costo de comprar el faltante en el spot (USD, +5 % de cargos). |  |
| `best_option` | CUMPLE, COMPRAR_SPOT o PAGAR_PENALIDAD. |  |

## mart_generation_vs_budget

Real vs. presupuesto P50 aprobado (v1) con la cascada del desvío: recurso, curtailment, fallas, mantenimiento, hielo, suciedad y otras. Usar para responder '¿por qué el parque X generó N % menos?'.

**Grano:** 1 fila por parque y mes · **Dueño:** Lucía Ferreyra (CEO) / Diego Achával (CFO)

**PK:** `park_code, month_start`  

| columna | descripción | etiquetas |
|---|---|---|
| `variance_pct` | Desvío vs. presupuesto (-0,18 = 18 % menos). |  |
| `resource_effect_mwh` | Efecto del recurso (viento/sol) vs. lo presupuestado, en MWh (negativo = sopló menos). |  |
| `lost_curtailment_mwh` | Pérdida por curtailment del mes (MWh). El presupuesto ya asume budget_curtailment_allowance_mwh. |  |
| `lost_fault_mwh` | Pérdida por fallas (MWh). El presupuesto asume budget_availability_allowance_mwh para fallas + mantenimiento. |  |
| `lost_icing_mwh` | Pérdida por hielo en palas (MWh), no presupuestada. |  |
| `data_gap_mwh` | Energía estimada de los huecos de comunicación satelital. |  |

## mart_curtailment_battery

Energía perdida por curtailment y cuánto recuperaría una batería (BESS) de 3 tamaños; base del caso de inversión.

**Grano:** 1 fila por parque, opción de batería y mes · **Dueño:** Diego Achával (CFO)


| columna | descripción | etiquetas |
|---|---|---|
| `option_code` | BESS-10x4 (10 % de la potencia del parque, 4 h), BESS-20x4, BESS-30x2. |  |
| `recovered_value_usd` | USD que habría recuperado la batería en el mes. |  |
| `battery_capex_usd` | Inversión estimada de la batería (280 USD/kWh). |  |

## mart_turbine_health

Salud diaria de cada turbina para mantenimiento predictivo: temperatura vs. pares del parque, vibración vs. su historia, alarmas y riesgo.

**Grano:** 1 fila por turbina y día · **Dueño:** Joaquín Ortiz (Ingeniero de Confiabilidad)

**PK:** `turbine_id, reading_date`  

| columna | descripción | etiquetas |
|---|---|---|
| `health_score` | 0-100 (100 = sana). Menos de 60 = riesgo ALTO. |  |
| `risk_level` | BAJO, MEDIO, ALTO o SIN_DATOS_SUFICIENTES. |  |
| `gearbox_residual_7d` | °C que la multiplicadora calienta de más vs. sus pares (promedio 7 días). |  |
| `vibration_ratio` | Vibración de 7 días / vibración de los 30 días previos. |  |
| `failure_within_30d` | Etiqueta: hubo falla MAYOR en los 30 días siguientes (sirve para evaluar el modelo). |  |

## mart_panel_cleaning

Suciedad estimada de los paneles, pérdida acumulada en USD desde la última limpieza y recomendación (LIMPIAR, ESPERAR, ESPERAR_LLUVIA, LIMPIANDO).

**Grano:** 1 fila por parque solar y día · **Dueño:** Natalia Mamaní (Jefa de parque Abra Pampa) / Andrea Colque (HSE)

**PK:** `park_code, reading_date`  

| columna | descripción | etiquetas |
|---|---|---|
| `soiling_loss_pct` | Pérdida estimada por suciedad (0,08 = 8 %). |  |
| `lost_usd_since_cleaning` | USD perdidos por suciedad desde la última limpieza. |  |
| `cleaning_cost_usd` | Costo de la última limpieza (agua + cuadrilla), USD. |  |
| `recommendation` | LIMPIAR cuando lo perdido supera el costo de limpiar y no se pronostica lluvia. |  |

## mart_ppa_forecast

Proyección diaria de cumplimiento de cada PPA en el mes y recomendación: EN_CAMINO, COMPRAR_SPOT o PAGAR_PENALIDAD.

**Grano:** 1 fila por contrato y fecha de corte · **Dueño:** Sofía Bertolini (Gerente Comercial)

**PK:** `contract_id, as_of_date`  

| columna | descripción | etiquetas |
|---|---|---|
| `as_of_date` | Fecha de corte de la proyección. Para 'este mes' usar la máxima. |  |
| `projected_compliance_pct` | Cumplimiento proyectado al cierre del mes. |  |
| `recommendation` | Qué conviene hacer con el faltante proyectado. |  |

## mart_warranty_claims

Disponibilidad contractual mensual y móvil 12 meses vs. la garantía del fabricante (97 %) y los liquidated damages a reclamar.

**Grano:** 1 fila por parque eólico y mes · **Dueño:** Ramiro Llancaqueo (Jefe de Mantenimiento)

**PK:** `park_code, month_start`  

| columna | descripción | etiquetas |
|---|---|---|
| `availability_12m` | Disponibilidad contractual móvil de 12 meses. |  |
| `ld_accrued_usd` | Liquidated damages devengados en el mes (USD) si la móvil 12 m está debajo de la garantía. |  |
| `claim_eligible` | Verdadero si corresponde reclamar al fabricante. |  |

