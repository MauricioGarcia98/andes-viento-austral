-- =============================================================================
-- METRIC VIEWS: las métricas OFICIALES de Andes Viento Austral
-- -----------------------------------------------------------------------------
-- Una métrica se define UNA vez (YAML) y la usan Genie, los dashboards y el SQL:
--   SELECT `Parque`, MEASURE(`Energía generada (MWh)`) FROM gold.mv_generacion GROUP BY ALL
-- Decisión del Analytics Engineer: nombres en español "de negocio" (como los dice la gente),
-- con comentarios y sinónimos para que Genie entienda "curtailment", "recorte", "limitación".
-- Nota técnica: dentro de $$...$$ no puede haber punto y coma (el runner separa por ';').
-- =============================================================================

CREATE OR REPLACE VIEW ${gold}.mv_generacion
WITH METRICS
LANGUAGE YAML
COMMENT 'Métricas oficiales de generación, presupuesto y pérdidas por parque y día'
AS $$
version: 1.1
comment: "Generación diaria por parque vs. presupuesto P50, con pérdidas por causa. Fuente: gold.v_park_daily"
source: ${gold}.v_park_daily
dimensions:
  - name: Parque
    expr: park_name
    comment: "Nombre del parque (ej. Cañadón León, Susques Solar)"
    synonyms: [parque, park, planta]
  - name: Código de parque
    expr: park_code
  - name: Tecnología
    expr: technology
    comment: "Eólico o Solar"
  - name: Provincia
    expr: province
  - name: Región
    expr: region
  - name: Fecha
    expr: reading_date
  - name: Mes
    expr: year_month
    comment: "Año-mes yyyy-MM"
  - name: Año
    expr: year(reading_date)
  - name: Estación
    expr: season
  - name: Condición climática
    expr: weather_condition
measures:
  - name: Energía generada (MWh)
    expr: SUM(generated_mwh)
    synonyms: [generación, producción, energía]
  - name: Energía potencial (MWh)
    expr: SUM(potential_mwh)
    comment: "Lo que se podría haber generado sin pérdidas (curva de potencia x viento, o paneles limpios)"
  - name: Presupuesto P50 (MWh)
    expr: SUM(budget_mwh)
    synonyms: [presupuesto, budget, P50]
  - name: Desvío vs presupuesto (%)
    expr: SUM(generated_mwh) / SUM(budget_mwh) - 1
    comment: "Negativo = generamos menos que el presupuesto"
  - name: Pérdida por curtailment (MWh)
    expr: SUM(lost_curtailment_mwh)
    synonyms: [curtailment, recorte, limitación de red, energía perdida por CAMMESA]
  - name: Pérdida por fallas (MWh)
    expr: SUM(lost_fault_mwh)
  - name: Pérdida por mantenimiento (MWh)
    expr: SUM(lost_maintenance_mwh)
  - name: Pérdida por hielo (MWh)
    expr: SUM(lost_icing_mwh)
  - name: Pérdida por suciedad (MWh)
    expr: SUM(lost_soiling_mwh)
  - name: Factor de capacidad
    expr: SUM(generated_mwh) / SUM(installed_mw * 24)
    comment: "Energía generada / (potencia instalada x horas). 0,50 = 50 %"
  - name: Disponibilidad contractual
    expr: AVG(availability_contractual)
$$;

CREATE OR REPLACE VIEW ${gold}.mv_curtailment
WITH METRICS
LANGUAGE YAML
COMMENT 'Métricas oficiales de curtailment (órdenes de CAMMESA de bajar potencia)'
AS $$
version: 1.1
comment: "Energía perdida por curtailment y su valor, por parque eólico y hora"
source: ${gold}.fact_curtailment_hourly
joins:
  - name: parque
    source: ${gold}.dim_park
    on: source.park_key = parque.park_key
dimensions:
  - name: Parque
    expr: parque.park_name
  - name: Provincia
    expr: parque.province
  - name: Fecha
    expr: reading_date
  - name: Mes
    expr: date_format(reading_date, 'yyyy-MM')
  - name: Año
    expr: year(reading_date)
  - name: Hora local
    expr: hour(hour_local)
  - name: Motivo
    expr: coalesce(grid_reason, 'SIN_ORDEN')
    comment: "RESTRICCION_TRANSPORTE, MANTENIMIENTO_ET, CONTROL_FRECUENCIA"
measures:
  - name: Energía perdida por curtailment (MWh)
    expr: SUM(lost_curtailment_mwh)
    synonyms: [curtailment, recorte, energía perdida, MWh perdidos]
  - name: Energía potencial (MWh)
    expr: SUM(potential_mwh)
  - name: Curtailment (% del potencial)
    expr: SUM(lost_curtailment_mwh) / SUM(potential_mwh)
  - name: Horas con orden de CAMMESA
    expr: COUNT_IF(has_instruction)
  - name: Valor perdido a precio spot (USD)
    expr: SUM(lost_value_spot_usd)
  - name: Precio spot medio (USD/MWh)
    expr: AVG(spot_usd_mwh)
$$;

CREATE OR REPLACE VIEW ${gold}.mv_mantenimiento
WITH METRICS
LANGUAGE YAML
COMMENT 'Métricas oficiales de mantenimiento: órdenes, tiempos y costos'
AS $$
version: 1.1
comment: "Órdenes de trabajo del CMMS"
source: ${gold}.fact_maintenance_order
joins:
  - name: parque
    source: ${gold}.dim_park
    on: source.park_key = parque.park_key
dimensions:
  - name: Parque
    expr: parque.park_name
  - name: Tecnología
    expr: parque.technology
  - name: Mes
    expr: date_format(created_date, 'yyyy-MM')
  - name: Año
    expr: year(created_date)
  - name: Tipo de orden
    expr: order_type
  - name: Severidad
    expr: severity
  - name: Componente
    expr: component
measures:
  - name: Órdenes
    expr: COUNT(*)
  - name: Órdenes abiertas
    expr: COUNT_IF(is_open)
  - name: Fallas mayores
    expr: COUNT_IF(severity = 'MAYOR')
  - name: Horas de parada
    expr: SUM(downtime_hours)
  - name: MTTR (h)
    expr: AVG(CASE WHEN order_type = 'CORRECTIVA' THEN downtime_hours END)
    comment: "Tiempo medio de reparación de correctivas, desde la falla hasta el fin del trabajo"
    synonyms: [tiempo medio de reparación]
  - name: Espera de repuestos (h)
    expr: AVG(waiting_hours)
  - name: Costo total (USD)
    expr: SUM(total_cost_usd)
  - name: Costo mano de obra (ARS)
    expr: SUM(labor_cost_ars)
  - name: Agua de limpieza (m3)
    expr: SUM(water_m3)
$$;

CREATE OR REPLACE VIEW ${gold}.mv_disponibilidad
WITH METRICS
LANGUAGE YAML
COMMENT 'Métricas oficiales de disponibilidad contractual y garantía del fabricante'
AS $$
version: 1.1
comment: "Disponibilidad contractual (garantía 97 %) por parque eólico y mes"
source: ${gold}.mart_warranty_claims
dimensions:
  - name: Parque
    expr: park_name
  - name: Fabricante
    expr: manufacturer
  - name: Mes
    expr: year_month
  - name: Año
    expr: year(month_start)
measures:
  - name: Disponibilidad contractual
    expr: 1 - SUM(chargeable_fault_h) / SUM(useful_h)
    synonyms: [disponibilidad, availability]
  - name: Horas de falla imputables
    expr: SUM(chargeable_fault_h)
  - name: Horas de fuerza mayor
    expr: SUM(force_majeure_h)
  - name: Liquidated damages devengados (USD)
    expr: SUM(ld_accrued_usd)
    synonyms: [reclamo al fabricante, multa del fabricante, LD]
  - name: Meses con reclamo
    expr: COUNT_IF(claim_eligible)
$$;

CREATE OR REPLACE VIEW ${gold}.mv_ppa
WITH METRICS
LANGUAGE YAML
COMMENT 'Métricas oficiales de contratos PPA: cumplimiento, faltantes y costos'
AS $$
version: 1.1
comment: "Liquidación mensual de PPA por contrato"
source: ${gold}.fact_ppa_settlement
dimensions:
  - name: Cliente
    expr: client_name
  - name: Contrato
    expr: contract_id
  - name: Sector
    expr: sector
  - name: Mes
    expr: year_month
  - name: Año
    expr: year(month_start)
  - name: Mejor opción
    expr: best_option
measures:
  - name: Energía comprometida (MWh)
    expr: SUM(committed_mwh)
  - name: Energía entregada (MWh)
    expr: SUM(delivered_mwh)
  - name: Cumplimiento (%)
    expr: SUM(delivered_mwh) / SUM(committed_mwh)
    synonyms: [cumplimiento del contrato, compliance]
  - name: Faltante (MWh)
    expr: SUM(shortfall_mwh)
  - name: Costo de penalidad (USD)
    expr: SUM(penalty_cost_usd)
  - name: Costo de cubrir en spot (USD)
    expr: SUM(spot_cover_cost_usd)
  - name: Costo de la mejor opción (USD)
    expr: SUM(best_option_cost_usd)
  - name: Ingresos PPA (USD)
    expr: SUM(revenue_usd)
$$;

CREATE OR REPLACE VIEW ${gold}.mv_salud_turbinas
WITH METRICS
LANGUAGE YAML
COMMENT 'Métricas oficiales de salud de turbinas (mantenimiento predictivo)'
AS $$
version: 1.1
comment: "Salud diaria por turbina"
source: ${gold}.mart_turbine_health
dimensions:
  - name: Parque
    expr: park_code
  - name: Turbina
    expr: turbine_id
  - name: Fecha
    expr: reading_date
  - name: Nivel de riesgo
    expr: risk_level
  - name: Componente sospechado
    expr: suspected_component
measures:
  - name: Turbinas en riesgo alto
    expr: COUNT(DISTINCT CASE WHEN risk_level = 'ALTO' THEN turbine_id END)
  - name: Health score medio
    expr: AVG(health_score)
  - name: Residuo térmico multiplicadora 7d (°C)
    expr: AVG(gearbox_residual_7d)
  - name: Alertas que anticiparon una falla
    expr: COUNT_IF(risk_level = 'ALTO' AND failure_within_30d)
$$;

CREATE OR REPLACE VIEW ${gold}.mv_limpieza
WITH METRICS
LANGUAGE YAML
COMMENT 'Métricas oficiales de suciedad y limpieza de paneles'
AS $$
version: 1.1
comment: "Suciedad y limpieza de paneles por parque solar y día"
source: ${gold}.mart_panel_cleaning
dimensions:
  - name: Parque
    expr: park_code
  - name: Fecha
    expr: reading_date
  - name: Mes
    expr: date_format(reading_date, 'yyyy-MM')
  - name: Recomendación
    expr: recommendation
measures:
  - name: Pérdida por suciedad (MWh)
    expr: SUM(soiling_lost_mwh)
  - name: Pérdida por suciedad (USD)
    expr: SUM(soiling_lost_usd)
  - name: Suciedad media (%)
    expr: AVG(soiling_loss_pct)
  - name: Días recomendados para limpiar
    expr: COUNT_IF(recommendation = 'LIMPIAR')
$$;
