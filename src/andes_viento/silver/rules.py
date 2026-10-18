"""Reglas de calidad por entidad (expresiones SQL que deben ser VERDADERAS).

warn        la fila sigue; el fallo se cuenta en ops.dq_results (ej.: sensor clavado)
quarantine  la fila se aparta a ops.quarantine con el motivo (ej.: turbina desconocida)
fail        se aborta el job: dato que NUNCA debería existir (ej.: dólar negativo)

Quién decide la acción: el Data Steward junto con el dueño del dato (ver docs/02_roles_y_decisiones.md).
"""

from andes_viento.quality.expectations import Rule

SCADA = [
    Rule("turbina_conocida", "asset_id IS NOT NULL"),
    Rule("fecha_parseable", "ts_utc IS NOT NULL"),
    Rule("no_viene_del_futuro", "ts_utc <= received_ts + INTERVAL 1 HOUR"),
    Rule("potencia_informada", "power_kw IS NOT NULL", "warn"),
    Rule("valores_fisicamente_posibles", "size(bad_values) = 0", "warn"),
    Rule("sensores_sin_clavarse", "size(stuck_sensors) = 0", "warn"),
    Rule("reloj_sincronizado", "NOT clock_corrected", "warn"),
    Rule("huso_horario_correcto", "NOT tz_corrected", "warn"),
    Rule("llego_a_tiempo", "NOT late_arrival", "warn"),
]

INVERTER = [
    Rule("inversor_conocido", "asset_id IS NOT NULL"),
    Rule("fecha_parseable", "ts_utc IS NOT NULL"),
    Rule("irradiancia_valida", "NOT poa_sentinel", "warn"),
    Rule("potencia_ac_en_rango", "ac_power_kw IS NULL OR ac_power_kw <= 2600", "warn"),
    Rule("unidad_correcta", "NOT unit_converted", "warn"),
]

ASSETS = [
    Rule("id_presente", "asset_id IS NOT NULL", "fail"),
    Rule("tag_presente", "asset_tag IS NOT NULL"),
    Rule("fecha_cambio_parseable", "updated_at IS NOT NULL"),
]

WORK_ORDERS = [
    Rule("orden_con_id", "order_id IS NOT NULL"),
    Rule("evento_con_fecha", "event_ts IS NOT NULL"),
    Rule("activo_resuelto", "asset_id IS NOT NULL OR order_type = 'LIMPIEZA' OR is_deleted", "warn"),
    Rule("costos_no_negativos", "coalesce(labor_cost_ars, 0) >= 0 AND coalesce(crane_cost_usd, 0) >= 0"),
    Rule("cierre_despues_de_apertura", "work_end_ts IS NULL OR work_end_ts >= created_ts - INTERVAL 30 DAYS", "warn"),
]

DISPATCH = [
    Rule("ventana_valida", "valid_to_ts > valid_from_ts"),
    Rule("limite_no_negativo", "limit_mw >= 0"),
]

SPOT = [
    Rule("hora_cammesa_valida", "cammesa_hour BETWEEN 1 AND 24"),
    Rule("precio_positivo", "price_ars_mwh > 0"),
]

FX = [
    Rule("fecha_valida", "fx_date IS NOT NULL"),
    Rule("dolar_positivo", "ars_per_usd > 0", "fail"),
]

CONTRACTS = [
    Rule("precio_positivo", "price_usd_mwh > 0"),
    Rule("vigencia_coherente", "end_date > start_date"),
    Rule("email_valido", "contact_email RLIKE '^[^@]+@[^@]+[.][a-z]{2,}$'", "warn"),
]

WEATHER = [
    Rule("fecha_valida", "valid_ts IS NOT NULL"),
    Rule("temperatura_plausible", "temp_c BETWEEN -40 AND 50", "warn"),
]

BUDGET = [Rule("p50_no_negativo", "budget_p50_mwh >= 0")]

CREWS = [Rule("cuadrilla_con_id", "crew_id IS NOT NULL")]
