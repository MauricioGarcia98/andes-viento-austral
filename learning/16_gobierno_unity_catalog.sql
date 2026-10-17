-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 16 · Gobierno con Unity Catalog
-- MAGIC Comentarios (para humanos y para Genie), PK/FK, tags de PII, máscaras de columna, row filters, linaje y auditoría.
-- MAGIC Todo lo genera `scripts/build_governance.py` desde `governance/data_dictionary.yml` + `sql/governance/04_*.sql`.

-- COMMAND ----------

USE CATALOG andes_viento_dev;

-- COMMAND ----------

DESCRIBE TABLE EXTENDED gold.dim_contract;

-- COMMAND ----------

-- Tags de columna (PII) desde information_schema
SELECT table_name, column_name, tag_name, tag_value FROM information_schema.column_tags
WHERE schema_name = 'gold' ORDER BY table_name, column_name;

-- COMMAND ----------

-- PK/FK declaradas
SELECT tc.table_name, tc.constraint_name, tc.constraint_type FROM information_schema.table_constraints tc
WHERE tc.table_schema = 'gold' ORDER BY 1, 3;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Máscaras y filtros: probalo con otro usuario
-- MAGIC Como admin ves todo. Para ver el efecto: creá un usuario o grupo de prueba, dale `SELECT` sobre `gold` y
-- MAGIC agregá una fila en `ops.park_access` sólo para `LEO`. Ese usuario verá contactos enmascarados y sólo Cañadón León
-- MAGIC en `fact_availability_daily` y `fact_maintenance_order`.

-- COMMAND ----------

SELECT contract_id, contact_email, contact_phone, price_usd_mwh FROM gold.dim_contract WHERE is_current LIMIT 5;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. Agregá un comentario a `gold.mart_ppa_forecast.spot_14d_usd_mwh` en el YAML, regenerá y aplicá.
-- MAGIC 2. Escribí una máscara que muestre sólo el dominio del email (`***@cliente.com`).
-- MAGIC 3. Usá `system.access.table_lineage` para ver de qué tablas sale `gold.mart_generation_vs_budget`.
-- MAGIC 4. ¿Quién consultó `gold.dim_contract` en la última semana? (`system.access.audit` si tu workspace lo tiene)

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

ALTER TABLE gold.mart_ppa_forecast ALTER COLUMN spot_14d_usd_mwh COMMENT 'Precio spot medio de los últimos 14 días (USD/MWh), referencia para cubrir faltantes';

-- COMMAND ----------

CREATE OR REPLACE FUNCTION ops.mask_email_domain(email STRING) RETURNS STRING
RETURN CASE WHEN ops.can_see_commercial() THEN email ELSE concat('***@', split(email, '@')[1]) END;

-- COMMAND ----------

SELECT source_table_full_name, target_table_full_name, max(event_time) AS ultima_vez
FROM system.access.table_lineage
WHERE target_table_full_name = 'andes_viento_dev.gold.mart_generation_vs_budget'
GROUP BY ALL;

-- COMMAND ----------

SELECT event_time, user_identity.email, action_name
FROM system.access.audit
WHERE request_params.full_name_arg = 'andes_viento_dev.gold.dim_contract' AND event_date > current_date() - 7
ORDER BY event_time DESC LIMIT 20;
