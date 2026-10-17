"""Configuración central del proyecto Andes Viento Austral.

Un único objeto `ProjectConfig` resuelve:
  * nombres de 3 niveles (catalog.schema.table) de Unity Catalog,
  * rutas de la zona de aterrizaje (UC Volume), checkpoints y esquemas de Auto Loader,
  * el `scale_factor`, que escala la CANTIDAD DE EQUIPOS (turbinas e inversores).

¿Por qué escalar equipos y no días? Porque la historia del negocio (2023 → sep-2026,
con la crisis de curtailment, la devaluación y el invierno de 2025) tiene que estar
completa a cualquier escala. Con SF=1 la flota es la real: 380 aerogeneradores y
1,2 millones de paneles (~220 inversores centrales).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date

LAYERS = ("landing", "bronze", "silver", "gold", "ops")

# Fuentes que llegan a landing (una carpeta por fuente).
SOURCES = (
    "scada_turbine",        # telemetría 10 min (JSON gz, con schema drift en 2025)
    "inverter_5min",        # inversores solares 5 min (CSV, con columna nueva en 2025)
    "cmms_assets",          # registro de activos del CMMS: componentes y renombres (CSV CDC)
    "cmms_work_orders",     # órdenes de mantenimiento (JSON CDC)
    "cmms_crews",           # cuadrillas (CSV)
    "cammesa_dispatch",     # instrucciones de despacho / curtailment (JSON)
    "cammesa_spot_prices",  # precio spot horario por nodo (CSV formato CAMMESA)
    "ppa_contracts",        # contratos PPA MATER (CSV CDC)
    "weather",              # pronóstico y observación horaria por parque (JSON)
    "fx_rates",             # tipo de cambio ARS/USD diario (CSV)
    "generation_budget",    # presupuesto P50 mensual por parque (CSV, de Finanzas)
)

# Entidades silver (lo que recorre el for_each del Job).
SILVER_ENTITIES = (
    "assets", "crews", "contracts", "fx_rates", "spot_prices", "budget",
    "dispatch", "weather", "work_orders", "inverter", "scada",
)

EXPECTED_TABLES = {
    "bronze": list(SOURCES),
    "silver": [
        "assets_history", "turbine_tags", "crews", "contracts_history", "fx_rates", "spot_prices",
        "generation_budget", "curtailment_instructions", "weather_hourly", "work_orders",
        "work_order_parts", "inverter_5min", "scada_10min",
    ],
    "gold": [
        "dim_date", "dim_park", "dim_turbine", "dim_inverter", "dim_weather", "dim_contract", "dim_crew",
        "fact_turbine_10min", "fact_inverter_hourly", "fact_curtailment_hourly", "fact_maintenance_order",
        "fact_availability_daily", "fact_ppa_settlement",
        "mart_generation_vs_budget", "mart_curtailment_battery", "mart_turbine_health",
        "mart_panel_cleaning", "mart_ppa_forecast", "mart_warranty_claims",
    ],
    "ops": ["pipeline_runs", "watermarks", "dq_results", "quarantine", "park_access"],
}


def is_databricks() -> bool:
    """True cuando el código corre dentro de un runtime de Databricks."""
    return "DATABRICKS_RUNTIME_VERSION" in os.environ


@dataclass(frozen=True)
class ScaleProfile:
    """Flota a SF=1 (la real de la empresa).

    SCADA: 380 turbinas x 144 registros/día ≈ 20M filas/año... por turbina-año son
    52.560 registros; con re-envíos satelitales y alarmas llega a ≈ 200M filas/año
    "en crudo" a nivel de sensor (la tabla ancha tiene ≈ 20M filas/año).
    """

    inverter_kw: int = 2_500        # inversor central de 2,5 MW AC
    panel_wp: int = 550             # panel bifacial de 550 Wp
    dc_ac_ratio: float = 1.2
    minor_fault_rate_month: float = 0.12  # fallas menores por turbina-mes
    major_failure_rate_year: float = 0.045  # multiplicadora / rodamiento por turbina-año


@dataclass(frozen=True)
class ProjectConfig:
    catalog: str = "andes_viento"
    schema_prefix: str = ""  # en local: "andes_" para no chocar con otras bases
    volume: str = "raw"
    base_path: str | None = None  # override local (por defecto /Volumes/...)
    scale_factor: float = 1.0
    start_date: date = date(2023, 1, 1)
    end_date: date = date(2026, 9, 30)
    seed: int = 2009  # año de fundación de la empresa
    profile: ScaleProfile = field(default_factory=ScaleProfile)

    # ------------------------------------------------------------------ nombres
    def schema(self, layer: str) -> str:
        if layer not in LAYERS:
            raise ValueError(f"Capa desconocida: {layer}. Válidas: {LAYERS}")
        return f"{self.catalog}.{self.schema_prefix}{layer}"

    def table(self, layer: str, name: str) -> str:
        return f"{self.schema(layer)}.{name}"

    # ------------------------------------------------------------------- rutas
    @property
    def root_path(self) -> str:
        if self.base_path:
            return self.base_path.rstrip("/")
        return f"/Volumes/{self.catalog}/{self.schema_prefix}landing/{self.volume}"

    def landing_path(self, source: str) -> str:
        return f"{self.root_path}/landing/{source}"

    def checkpoint_path(self, name: str) -> str:
        return f"{self.root_path}/_checkpoints/{name}"

    def schema_location(self, source: str) -> str:
        return f"{self.root_path}/_schemas/{source}"

    # ------------------------------------------------------------------ volumen
    def units(self, n_real: int) -> int:
        """Equipos de un parque a esta escala (mínimo 1: todo parque existe)."""
        return max(1, int(round(n_real * self.scale_factor)))

    @property
    def n_days(self) -> int:
        return (self.end_date - self.start_date).days + 1


def local_config(base_path: str, scale_factor: float = 0.02, **kwargs) -> ProjectConfig:
    """Config para tests / ejecución local con Spark + Delta OSS."""
    return ProjectConfig(
        catalog="spark_catalog",
        schema_prefix="andes_",
        base_path=base_path,
        scale_factor=scale_factor,
        **kwargs,
    )


def config_from_widgets(dbutils) -> ProjectConfig:  # pragma: no cover - sólo Databricks
    """Construye la config a partir de los widgets/parámetros del job."""

    def get(name: str, default: str) -> str:
        try:
            value = dbutils.widgets.get(name)
            return value if value != "" else default
        except Exception:
            return default

    return ProjectConfig(
        catalog=get("catalog", "andes_viento"),
        scale_factor=float(get("scale_factor", "0.1")),
        start_date=date.fromisoformat(get("start_date", "2023-01-01")),
        end_date=date.fromisoformat(get("end_date", "2026-09-30")),
    )
