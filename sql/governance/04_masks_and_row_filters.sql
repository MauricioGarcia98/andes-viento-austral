-- =============================================================================
-- Máscaras de columna y filtros de fila (Unity Catalog ABAC "a mano")
-- -----------------------------------------------------------------------------
-- Decisión del Data Steward + Comercial + Legal:
--   * Contactos de clientes (nombre, email, teléfono, CUIT): sólo Comercial y Finanzas.
--   * Precio de cada PPA: confidencial comercial -> sólo Comercial, Finanzas y Dirección.
--   * Teléfono del líder de cuadrilla: sólo Mantenimiento.
--   * Cada jefe de parque ve SÓLO su parque en las tablas de operación (row filter con
--     una tabla de accesos en ops.park_access: principal, park_code; '*' = todos).
-- Los admins del workspace (y quien corre el Job) ven todo.
-- =============================================================================

CREATE OR REPLACE FUNCTION ${ops}.can_see_commercial()
RETURNS BOOLEAN
COMMENT 'Verdadero si el usuario pertenece a Comercial, Finanzas o Dirección (o es admin)'
RETURN is_member('admins') OR is_account_group_member('andes_comercial')
    OR is_account_group_member('andes_finanzas') OR is_account_group_member('andes_direccion');

CREATE OR REPLACE FUNCTION ${ops}.mask_email(email STRING)
RETURNS STRING
COMMENT 'Enmascara emails: mlescano@cliente.com -> m*******@cliente.com'
RETURN CASE WHEN ${ops}.can_see_commercial() THEN email
            ELSE regexp_replace(email, '^(.)[^@]*', '$1*******') END;

CREATE OR REPLACE FUNCTION ${ops}.mask_text(value STRING)
RETURNS STRING
COMMENT 'Oculta texto personal (nombres, teléfonos, CUIT) a quien no es de Comercial/Finanzas'
RETURN CASE WHEN ${ops}.can_see_commercial() THEN value ELSE '[RESERVADO]' END;

CREATE OR REPLACE FUNCTION ${ops}.mask_price(price DOUBLE)
RETURNS DOUBLE
COMMENT 'El precio de cada PPA es confidencial: NULL para quien no es de Comercial/Finanzas/Dirección'
RETURN CASE WHEN ${ops}.can_see_commercial() THEN price ELSE NULL END;

CREATE OR REPLACE FUNCTION ${ops}.mask_crew_phone(phone STRING)
RETURNS STRING
COMMENT 'Teléfono de cuadrillas: completo para Mantenimiento, últimos 4 dígitos para el resto'
RETURN CASE WHEN is_member('admins') OR is_account_group_member('andes_mantenimiento') THEN phone
            ELSE concat('***-', right(phone, 4)) END;

CREATE OR REPLACE FUNCTION ${ops}.park_filter(park STRING)
RETURNS BOOLEAN
COMMENT 'Row filter: el usuario ve los parques asignados en ops.park_access (o todos si es admin o tiene *)'
RETURN is_member('admins')
    OR EXISTS (SELECT 1 FROM ${ops}.park_access a
               WHERE a.principal = current_user() AND (a.park_code = '*' OR a.park_code = park));

ALTER TABLE ${gold}.dim_contract ALTER COLUMN contact_email SET MASK ${ops}.mask_email;
ALTER TABLE ${gold}.dim_contract ALTER COLUMN contact_name SET MASK ${ops}.mask_text;
ALTER TABLE ${gold}.dim_contract ALTER COLUMN contact_phone SET MASK ${ops}.mask_text;
ALTER TABLE ${gold}.dim_contract ALTER COLUMN client_cuit SET MASK ${ops}.mask_text;
ALTER TABLE ${gold}.dim_contract ALTER COLUMN price_usd_mwh SET MASK ${ops}.mask_price;
ALTER TABLE ${gold}.dim_crew ALTER COLUMN leader_phone SET MASK ${ops}.mask_crew_phone;

ALTER TABLE ${gold}.fact_maintenance_order SET ROW FILTER ${ops}.park_filter ON (park_code);
ALTER TABLE ${gold}.fact_availability_daily SET ROW FILTER ${ops}.park_filter ON (park_code);
