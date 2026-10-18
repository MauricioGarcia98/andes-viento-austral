"""La "física" del negocio: viento, curva de potencia, sol y temperatura.

Cada fórmula existe DOS veces y deben dar lo mismo (hay un test que lo verifica):
  * como expresión de Spark (`*_col`), para generar cientos de millones de filas
    de forma distribuida, sin UDFs de Python (que serían 10-50x más lentas);
  * como función de Python (`*_py`), para tablas chicas del driver (presupuesto P50,
    instrucciones de despacho) y para los tests.

El viento es una función CONTINUA del tiempo (suma de senos con fases por región y
parque): así la serie tiene autocorrelación realista (los frentes duran días) y dos
turbinas del mismo parque "ven" el mismo frente, sin tener que simular paso a paso.
"""

from __future__ import annotations

import math
import zlib
from datetime import datetime, timezone

from pyspark.sql import Column
from pyspark.sql import functions as F

from andes_viento.datagen.reference import (
    PARKS_BY_CODE,
    TEMP_AMPLITUDE,
    TEMP_DIURNAL,
    TEMP_MEAN,
    WIND_SEASONAL,
)

TWO_PI = 2 * math.pi
ART_OFFSET_S = 3 * 3600  # Argentina: UTC-3 todo el año (sin horario de verano desde 2009)

# Ondas sinópticas: (período en días, amplitud relativa, ¿fase regional o del parque?)
SYNOPTIC = ((4.3, 0.22, "region"), (9.7, 0.14, "region"), (1.7, 0.08, "park"))
CUT_IN_MS = 3.0
CUT_OUT_MS = 25.0


def _phase(key: str) -> float:
    return (zlib.crc32(key.encode()) % 10_000) / 10_000 * TWO_PI


def phases(park_code: str) -> list[float]:
    park = PARKS_BY_CODE[park_code]
    return [_phase(f"{park.region if scope == 'region' else park.code}-{i}")
            for i, (_, _, scope) in enumerate(SYNOPTIC)]


# =============================================================================
# Viento
# =============================================================================
def wind_ms_py(park_code: str, epoch_s: float, day_mult: float = 1.0, wake: float = 1.0,
               turb_u: float = 0.5) -> float:
    park = PARKS_BY_CODE[park_code]
    local = datetime.fromtimestamp(epoch_s - ART_OFFSET_S, tz=timezone.utc)
    hour_local = local.hour + local.minute / 60
    syn = 1.0 + sum(a * math.sin(TWO_PI * epoch_s / (86_400 * p) + ph)
                    for (p, a, _), ph in zip(SYNOPTIC, phases(park_code), strict=True))
    diurnal = 1.0 + 0.07 * math.sin(TWO_PI * (hour_local - 9) / 24)
    w = (park.wind_mean_ms * WIND_SEASONAL[local.month - 1] * syn * diurnal * day_mult * wake
         * (1 + 0.12 * (turb_u - 0.5)))
    return max(0.0, w)


def wind_ms_col(park_code: str, epoch: Column, month_local: Column, hour_local: Column,
                day_mult: Column, wake: Column | float = 1.0, turb_u: Column | float = 0.5) -> Column:
    park = PARKS_BY_CODE[park_code]
    seasonal = F.element_at(F.array(*[F.lit(v) for v in WIND_SEASONAL]), month_local)
    syn = F.lit(1.0)
    for (p, a, _), ph in zip(SYNOPTIC, phases(park_code), strict=True):
        syn = syn + F.lit(a) * F.sin(F.lit(TWO_PI) * epoch / F.lit(86_400 * p) + F.lit(ph))
    diurnal = 1.0 + 0.07 * F.sin(F.lit(TWO_PI) * (hour_local - 9) / 24)
    wake = F.lit(wake) if isinstance(wake, float) else wake
    turb_u = F.lit(turb_u) if isinstance(turb_u, float) else turb_u
    w = F.lit(park.wind_mean_ms) * seasonal * syn * diurnal * day_mult * wake * (1 + 0.12 * (turb_u - 0.5))
    return F.greatest(F.lit(0.0), w)


def wind_by_park_col(park_col: Column, epoch: Column, month_local: Column, hour_local: Column,
                     day_mult: Column, wake: Column | float = 1.0, turb_u: Column | float = 0.5) -> Column:
    """`wind_ms_col` para un DataFrame con varios parques (CASE WHEN por parque)."""
    expr = None
    for code, park in PARKS_BY_CODE.items():
        if park.tech != "WIND":
            continue
        w = wind_ms_col(code, epoch, month_local, hour_local, day_mult, wake, turb_u)
        expr = F.when(park_col == code, w) if expr is None else expr.when(park_col == code, w)
    return expr.otherwise(F.lit(None).cast("double"))


# =============================================================================
# Curva de potencia (aproximación cúbica entre cut-in y velocidad nominal)
# =============================================================================
def power_kw_py(wind: float, rated_kw: float, rated_ms: float) -> float:
    if wind < CUT_IN_MS or wind >= CUT_OUT_MS:
        return 0.0
    frac = (wind ** 3 - CUT_IN_MS ** 3) / (rated_ms ** 3 - CUT_IN_MS ** 3)
    return rated_kw * min(1.0, max(0.0, frac))


def power_kw_col(wind: Column, rated_kw: Column, rated_ms: Column) -> Column:
    frac = (F.pow(wind, 3) - CUT_IN_MS ** 3) / (F.pow(rated_ms, 3) - CUT_IN_MS ** 3)
    p = rated_kw * F.least(F.lit(1.0), F.greatest(F.lit(0.0), frac))
    return F.when((wind < CUT_IN_MS) | (wind >= CUT_OUT_MS), F.lit(0.0)).otherwise(p)


def rotor_rpm_col(wind: Column, rpm_max: Column, rated_ms: Column) -> Column:
    ramp = rpm_max * (0.45 + 0.55 * (wind - CUT_IN_MS) / (rated_ms - CUT_IN_MS))
    return (F.when((wind < CUT_IN_MS) | (wind >= CUT_OUT_MS), F.lit(0.0))
            .otherwise(F.least(rpm_max, ramp)))


# =============================================================================
# Temperatura
# =============================================================================
def temp_c_py(park_code: str, epoch_s: float, day_anom: float = 0.0) -> float:
    park = PARKS_BY_CODE[park_code]
    local = datetime.fromtimestamp(epoch_s - ART_OFFSET_S, tz=timezone.utc)
    doy = local.timetuple().tm_yday
    hour = local.hour + local.minute / 60
    base = TEMP_MEAN[park.region] - 0.0065 * park.altitude_m
    if park.region == "PATAGONIA":
        base -= 0.35 * (abs(park.lat) - 45)
    seasonal = TEMP_AMPLITUDE[park.region] * math.cos(TWO_PI * (doy - 20) / 365)
    diurnal = TEMP_DIURNAL[park.region] * math.sin(TWO_PI * (hour - 9) / 24)
    return base + seasonal + diurnal + day_anom


def temp_c_col(park_col: Column, doy: Column, hour_local: Column, day_anom: Column) -> Column:
    base = None
    for code, park in PARKS_BY_CODE.items():
        b = TEMP_MEAN[park.region] - 0.0065 * park.altitude_m
        if park.region == "PATAGONIA":
            b -= 0.35 * (abs(park.lat) - 45)
        amp, diu = TEMP_AMPLITUDE[park.region], TEMP_DIURNAL[park.region]
        v = (F.lit(b) + F.lit(amp) * F.cos(F.lit(TWO_PI) * (doy - 20) / 365)
             + F.lit(diu) * F.sin(F.lit(TWO_PI) * (hour_local - 9) / 24))
        base = F.when(park_col == code, v) if base is None else base.when(park_col == code, v)
    return base.otherwise(F.lit(None)) + day_anom


# =============================================================================
# Sol (cielo despejado simplificado + corrección por altura)
# =============================================================================
def _cos_zenith_py(lat: float, lon: float, epoch_s: float) -> float:
    t = datetime.fromtimestamp(epoch_s, tz=timezone.utc)
    doy = t.timetuple().tm_yday
    decl = math.radians(23.45) * math.sin(TWO_PI * (284 + doy) / 365)
    solar_time = (t.hour + t.minute / 60 + lon / 15) % 24
    omega = math.radians(15 * (solar_time - 12))
    phi = math.radians(lat)
    return math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(omega)


def poa_clear_py(park_code: str, epoch_s: float) -> float:
    """Irradiancia en el plano de los módulos (W/m²) con cielo despejado."""
    park = PARKS_BY_CODE[park_code]
    cz = _cos_zenith_py(park.lat, park.lon, epoch_s)
    if cz <= 0.05:
        return 0.0
    ghi = 1_098 * cz ** 1.15 * (1 + 0.08 * park.altitude_m / 1_000)
    return min(1_250.0, ghi * (1 + 0.18 * (1 - cz)))


def poa_clear_col(lat: Column, lon: Column, alt_m: Column, doy_utc: Column, hour_utc: Column) -> Column:
    decl = F.lit(math.radians(23.45)) * F.sin(F.lit(TWO_PI) * (284 + doy_utc) / 365)
    solar_time = F.pmod(hour_utc + lon / 15, F.lit(24.0))
    omega = F.radians(15 * (solar_time - 12))
    phi = F.radians(lat)
    cz = F.sin(phi) * F.sin(decl) + F.cos(phi) * F.cos(decl) * F.cos(omega)
    ghi = 1_098 * F.pow(F.greatest(cz, F.lit(0.0)), 1.15) * (1 + 0.08 * alt_m / 1_000)
    return F.when(cz <= 0.05, F.lit(0.0)).otherwise(F.least(F.lit(1_250.0), ghi * (1 + 0.18 * (1 - cz))))
