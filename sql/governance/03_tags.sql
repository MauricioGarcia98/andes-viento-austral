-- GENERADO por scripts/build_governance.py desde governance/data_dictionary.yml. No editar a mano.

ALTER TABLE ${gold}.dim_date SET TAGS ('dominio' = 'comun', 'duenio' = 'Datos');
ALTER TABLE ${gold}.dim_park SET TAGS ('dominio' = 'operacion', 'duenio' = 'Martín Quiroga');
ALTER TABLE ${gold}.dim_turbine SET TAGS ('dominio' = 'mantenimiento', 'duenio' = 'Ramiro Llancaqueo');
ALTER TABLE ${gold}.dim_inverter SET TAGS ('dominio' = 'operacion', 'duenio' = 'Martín Quiroga');
ALTER TABLE ${gold}.dim_weather SET TAGS ('dominio' = 'operacion', 'duenio' = 'Martín Quiroga');
ALTER TABLE ${gold}.dim_contract ALTER COLUMN client_cuit SET TAGS ('pii' = 'identificador_fiscal');
ALTER TABLE ${gold}.dim_contract ALTER COLUMN contact_name SET TAGS ('pii' = 'nombre');
ALTER TABLE ${gold}.dim_contract ALTER COLUMN contact_email SET TAGS ('pii' = 'email');
ALTER TABLE ${gold}.dim_contract ALTER COLUMN contact_phone SET TAGS ('pii' = 'telefono');
ALTER TABLE ${gold}.dim_contract ALTER COLUMN price_usd_mwh SET TAGS ('clasificacion' = 'confidencial');
ALTER TABLE ${gold}.dim_contract SET TAGS ('dominio' = 'comercial', 'duenio' = 'Sofía Bertolini');
ALTER TABLE ${gold}.dim_crew ALTER COLUMN leader_name SET TAGS ('pii' = 'nombre');
ALTER TABLE ${gold}.dim_crew ALTER COLUMN leader_phone SET TAGS ('pii' = 'telefono');
ALTER TABLE ${gold}.dim_crew SET TAGS ('dominio' = 'mantenimiento', 'duenio' = 'Ramiro Llancaqueo');
ALTER TABLE ${gold}.fact_turbine_10min SET TAGS ('dominio' = 'operacion', 'duenio' = 'Martín Quiroga');
ALTER TABLE ${gold}.fact_inverter_hourly SET TAGS ('dominio' = 'operacion', 'duenio' = 'Martín Quiroga');
ALTER TABLE ${gold}.fact_curtailment_hourly SET TAGS ('dominio' = 'comercial', 'duenio' = 'Diego Achával');
ALTER TABLE ${gold}.fact_maintenance_order SET TAGS ('dominio' = 'mantenimiento', 'duenio' = 'Ramiro Llancaqueo');
ALTER TABLE ${gold}.fact_availability_daily SET TAGS ('dominio' = 'mantenimiento', 'duenio' = 'Ramiro Llancaqueo');
ALTER TABLE ${gold}.fact_ppa_settlement SET TAGS ('dominio' = 'comercial', 'duenio' = 'Sofía Bertolini');
ALTER TABLE ${gold}.mart_generation_vs_budget SET TAGS ('dominio' = 'direccion', 'duenio' = 'Lucía Ferreyra');
ALTER TABLE ${gold}.mart_curtailment_battery SET TAGS ('dominio' = 'finanzas', 'duenio' = 'Diego Achával');
ALTER TABLE ${gold}.mart_turbine_health SET TAGS ('dominio' = 'mantenimiento', 'duenio' = 'Joaquín Ortiz');
ALTER TABLE ${gold}.mart_panel_cleaning SET TAGS ('dominio' = 'operacion', 'duenio' = 'Natalia Mamaní');
ALTER TABLE ${gold}.mart_ppa_forecast SET TAGS ('dominio' = 'comercial', 'duenio' = 'Sofía Bertolini');
ALTER TABLE ${gold}.mart_warranty_claims SET TAGS ('dominio' = 'mantenimiento', 'duenio' = 'Ramiro Llancaqueo');
