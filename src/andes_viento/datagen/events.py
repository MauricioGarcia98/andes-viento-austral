"""Tablas "guía" del generador: chicas, secuenciales y calculadas en el driver.

Las fuentes grandes (SCADA, inversores, clima horario) se generan distribuidas en Spark,
pero necesitan saber QUÉ PASÓ cada día: si hubo un frente frío, si una turbina estaba
rota, si CAMMESA mandó bajar potencia. Eso se decide acá, con procesos que dependen del
día anterior (clima AR(1), suciedad acumulada) y que no tienen sentido fila por fila.

Regla de oro del determinismo: toda serie arranca en `cfg.start_date`, sin importar
hasta qué fecha se pida. Así el día 2026-10-01 generado por el job diario es idéntico
al que saldría de regenerar toda la historia.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

from andes_viento.config import ProjectConfig
from andes_viento.datagen import physics as ph
from andes_viento.datagen import reference as R
from andes_viento.datagen.rand import prng

ART = timezone(timedelta(hours=-3))


def local_epoch(d: date, hour: float = 0.0) -> int:
    """Epoch (segundos UTC) de una fecha/hora LOCAL argentina."""
    return int(datetime(d.year, d.month, d.day, tzinfo=ART).timestamp() + hour * 3600)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def month_starts(start: date, end: date):
    d = date(start.year, start.month, 1)
    while d <= end:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


# =============================================================================
# Flota a la escala pedida
# =============================================================================
@dataclass(frozen=True)
class Unit:
    asset_id: str
    asset_type: str        # WTG | INV
    park: str
    idx: int               # 1..n dentro del parque
    tag: str               # nombre original
    new_tag: str | None    # nombre después del renombre (sólo Cerro Arenales)
    manufacturer: str | None
    rated_kw: float
    dc_kwp: float
    panels: int
    wake: float            # pérdida por estela (algunas turbinas "tapan" a otras)
    commissioning: date


@lru_cache(maxsize=8)
def _fleet(scale_factor: float, seed: int) -> tuple[Unit, ...]:
    cfg = ProjectConfig(scale_factor=scale_factor, seed=seed)
    units: list[Unit] = []
    n_wtg = n_inv = 0
    for park in R.PARKS:
        n = cfg.units(park.units_real)
        for i in range(1, n + 1):
            rng = prng(seed, "unit", park.code, i)
            if park.tech == "WIND":
                n_wtg += 1
                m = R.MANUFACTURERS[park.manufacturer]
                new_tag = f"{park.code}-WTG{i:03d}" if park.code == R.TURBINE_RENAME[0] else None
                units.append(Unit(f"WTG{n_wtg:05d}", "WTG", park.code, i, f"{park.code}-{i:02d}", new_tag,
                                  m.code, float(m.rated_kw), 0.0, 0, round(rng.uniform(0.92, 1.04), 3),
                                  park.commissioning))
            else:
                n_inv += 1
                panels = park.panels_real // park.units_real
                dc = panels * cfg.profile.panel_wp / 1000
                units.append(Unit(f"INV{n_inv:05d}", "INV", park.code, i, f"{park.code}-INV{i:02d}", None,
                                  None, float(cfg.profile.inverter_kw), round(dc, 1), panels,
                                  round(rng.uniform(0.97, 1.01), 3), park.commissioning))
    return tuple(units)


def fleet(cfg: ProjectConfig, asset_type: str | None = None) -> list[Unit]:
    units = _fleet(cfg.scale_factor, cfg.seed)
    return [u for u in units if asset_type is None or u.asset_type == asset_type]


def park_capacity_kw(cfg: ProjectConfig) -> dict[str, float]:
    cap: dict[str, float] = {}
    for u in fleet(cfg):
        cap[u.park] = cap.get(u.park, 0.0) + u.rated_kw
    return cap


def park_units(cfg: ProjectConfig) -> dict[str, int]:
    out: dict[str, int] = {}
    for u in fleet(cfg):
        out[u.park] = out.get(u.park, 0) + 1
    return out


# =============================================================================
# Clima diario por parque (procesos AR(1) por región)
# =============================================================================
def _rain_params(park: R.Park, month: int) -> tuple[float, float]:
    """(probabilidad de lluvia diaria, mm medios) según región y mes."""
    if park.region == "PATAGONIA":
        return (0.17 if month in (5, 6, 7, 8) else 0.10), 3.0
    if park.altitude_m > 3_000:  # Puna: lluvias de verano ("invierno altiplánico")
        return {1: 0.35, 2: 0.33, 3: 0.22, 12: 0.15}.get(month, 0.02), 6.0
    return {1: 0.16, 2: 0.15, 3: 0.10, 12: 0.08}.get(month, 0.03), 5.0


WIND_DAY_SIGMA = 0.12  # cuánto se aparta un día "de frente" de uno normal (log-normal regional)


@lru_cache(maxsize=4)
def _park_days(seed: int, start: date, end: date) -> tuple[dict, ...]:
    rows: list[dict] = []
    state = {r: {"x": 0.0, "y": 0.0} for r in ("PATAGONIA", "NOA")}
    story = R.STORY["leo_july_2025"]
    for d in daterange(start, end):
        regional = {}
        for region, st in state.items():
            rng = prng(seed, "wx", region, d)
            st["x"] = 0.75 * st["x"] + 0.66 * rng.gauss(0, 1)
            st["y"] = 0.80 * st["y"] + 0.60 * rng.gauss(0, 1)
            regional[region] = (math.exp(WIND_DAY_SIGMA * st["x"] - WIND_DAY_SIGMA ** 2 / 2), 2.5 * st["y"])
        for park in R.PARKS:
            rng = prng(seed, "wxp", park.code, d)
            wmult, tanom = regional[park.region]
            wmult *= math.exp(0.06 * rng.gauss(0, 1) - 0.0018)
            tanom += rng.gauss(0, 0.8)
            p_rain, mm = _rain_params(park, d.month)
            precip = round(rng.expovariate(1 / mm), 1) if rng.random() < p_rain else 0.0
            cold_wave = False
            if park.code == story["park"]:
                if d.year == 2025 and d.month == 7:  # julio guionado: el viento no depende del azar regional
                    wmult = story["wind_anomaly"] * math.exp(0.06 * rng.gauss(0, 1) - 0.0018)
                cw0, cw1 = story["cold_wave"]
                if cw0 <= d <= cw1:
                    tanom, cold_wave = tanom - 7.0, True
                    precip = max(precip, 1.5 if d.day % 2 == 0 else 0.0)
            t_day = ph.temp_c_py(park.code, local_epoch(d, 12), tanom) - 3.0
            snow = round(precip * 1.2, 1) if (precip > 0 and t_day < 1.0) else 0.0
            ice_start = ice_end = None
            ice_prone = park.tech == "WIND" and (park.province == "Santa Cruz" or park.altitude_m >= 400)
            if ice_prone and d.month in (5, 6, 7, 8, 9) and t_day < 0.5 and (precip > 0 or rng.random() < 0.22):
                ice_start = rng.randint(0, 6)
                ice_end = min(23, ice_start + rng.randint(4, 14 if cold_wave else 10))
            cloud = 1.0
            dust_add = 0.0
            if park.tech == "SOLAR":
                if precip > 0:
                    cloud = rng.uniform(0.35, 0.60)
                elif rng.random() < (0.25 if d.month in (1, 2, 3, 12) else 0.06):
                    cloud = rng.uniform(0.60, 0.85)
                else:
                    cloud = rng.uniform(0.95, 1.0)
                dusty = d.month in (7, 8, 9, 10)
                if dusty and rng.random() < (0.07 if park.altitude_m > 3_000 else 0.04):
                    dust_add = rng.uniform(0.015, 0.045)
            rh = min(99.0, (90.0 if precip > 0 else 45.0 + 15 * rng.random()) + (8 if cold_wave else 0))
            rows.append({
                "park": park.code, "date": d, "wind_mult": round(wmult, 4), "temp_anom": round(tanom, 2),
                "precip_mm": precip, "snow_cm": snow, "rh_pct": round(rh, 1), "cloud": round(cloud, 3),
                "dust_add": round(dust_add, 4), "ice_start_h": ice_start, "ice_end_h": ice_end,
                "road_closed": snow >= 4.0, "cold_wave": cold_wave,
            })
    return tuple(rows)


def park_days(cfg: ProjectConfig, end: date) -> list[dict]:
    return list(_park_days(cfg.seed, cfg.start_date, max(end, cfg.start_date)))


def park_day_index(cfg: ProjectConfig, end: date) -> dict[tuple[str, date], dict]:
    return {(r["park"], r["date"]): r for r in park_days(cfg, end)}


# =============================================================================
# Suciedad de paneles + limpiezas (política histórica: calendario fijo ~75 días)
# =============================================================================
SOILING_BASE = {"SUS": 0.0017, "ABR": 0.0015, "TIN": 0.0009, "FIA": 0.0011}
CLEANING_PANELS_PER_DAY = 60_000  # una cuadrilla limpia ~60 mil paneles por día (SF=1)
WATER_L_PER_PANEL = 1.2


def soiling(cfg: ProjectConfig, end: date) -> tuple[dict[tuple[str, date], float], list[dict]]:
    """Devuelve (pérdida por suciedad al inicio de cada día, lista de limpiezas)."""
    wx = park_day_index(cfg, end)
    series: dict[tuple[str, date], float] = {}
    cleanings: list[dict] = []
    for park in R.SOLAR_PARKS:
        panels = sum(u.panels for u in fleet(cfg, "INV") if u.park == park.code)
        days_needed = max(1, math.ceil(panels / (CLEANING_PANELS_PER_DAY * max(cfg.scale_factor, 0.05))))
        s, last_clean, cleaning_until = 0.02, cfg.start_date - timedelta(days=40), None
        for d in daterange(cfg.start_date, end):
            w = wx[(park.code, d)]
            series[(park.code, d)] = round(s, 4)
            rng = prng(cfg.seed, "soil", park.code, d)
            dry = 1.4 if d.month in (7, 8, 9, 10) else 1.0
            s = min(0.35, s + SOILING_BASE[park.code] * dry * rng.uniform(0.6, 1.4) + w["dust_add"])
            if w["precip_mm"] > 4:
                s *= 0.25
            elif w["precip_mm"] > 1:
                s *= 0.7
            if cleaning_until is None and d >= park.commissioning:
                # política histórica: cada ~75 días (la fecha exacta depende de la agenda de la cuadrilla)
                every = 75 + prng(cfg.seed, "cl", park.code, last_clean).randint(-4, 6)
                due = (d - last_clean).days >= every
                post_storm = s > 0.15 and (d - last_clean).days > 40
                if due or post_storm:
                    cleaning_until = d + timedelta(days=days_needed - 1)
                    cleanings.append({"park": park.code, "start": d, "end": cleaning_until,
                                      "water_m3": round(panels * WATER_L_PER_PANEL / 1000, 1), "panels": panels,
                                      "trigger": "CALENDARIO" if due else "TORMENTA"})
            if cleaning_until is not None and d >= cleaning_until:
                s, last_clean, cleaning_until = rng.uniform(0.003, 0.01), d, None
    return series, cleanings


# =============================================================================
# Paradas de turbinas e inversores (preventivo, fallas menores, fallas mayores)
# =============================================================================
def travel_hours(park: R.Park) -> float:
    return round(park.distance_km / 75 + 0.5, 1)  # camioneta por ripio a ~75 km/h + carga


def downtime_events(cfg: ProjectConfig, end: date) -> list[dict]:
    wx = park_day_index(cfg, end + timedelta(days=60))
    story = R.STORY["leo_july_2025"]
    events: list[dict] = []
    for u in fleet(cfg):
        park = R.PARKS_BY_CODE[u.park]
        first = max(u.commissioning, cfg.start_date)
        per_unit: list[dict] = []
        for m0 in month_starts(first, end):
            rng = prng(cfg.seed, "dt", u.asset_id, m0)
            dim = (date(m0.year + (m0.month == 12), m0.month % 12 + 1, 1) - m0).days
            if u.asset_type == "WTG":
                # ---------------------------------------------------- preventivo semestral
                if m0.month in ((3, 10) if u.idx % 2 else (4, 11)):
                    d = m0 + timedelta(days=rng.randint(4, 24))
                    s = local_epoch(d, 8.0)
                    per_unit.append(_event(u, "PREVENTIVE", "PREVENTIVO", s, s + rng.randint(8, 12) * 3600,
                                           travel=travel_hours(park)))
                # ---------------------------------------------------- falla menor
                if rng.random() < cfg.profile.minor_fault_rate_month:
                    d = m0 + timedelta(days=rng.randint(0, dim - 1))
                    s = local_epoch(d, rng.uniform(0, 24))
                    if rng.random() < 0.45:  # se resuelve con un reset remoto desde el centro de control
                        per_unit.append(_event(u, "MINOR_FAULT", "CONTROL", s, s + int(rng.uniform(0.5, 3) * 3600),
                                               remote=True))
                    else:
                        delay = rng.uniform(12, 48) if wx.get((u.park, d), {}).get("road_closed") else 0.0
                        wait = rng.uniform(24, 96) if rng.random() < 0.25 else 0.0
                        repair = rng.uniform(2, 10)
                        dur = travel_hours(park) + delay + wait + repair
                        per_unit.append(_event(u, "MINOR_FAULT", rng.choice(["PITCH", "YAW", "CONVERTIDOR", "SENSOR"]),
                                               s, s + int(dur * 3600), travel=travel_hours(park),
                                               access_delay=delay, wait=wait, repair=repair))
                # ---------------------------------------------------- falla mayor (1 vez por año como máx.)
                if m0.month == 1 or m0 == date(first.year, first.month, 1):
                    yr = prng(cfg.seed, "major", u.asset_id, m0.year)
                    if yr.random() < cfg.profile.major_failure_rate_year:
                        month = yr.randint(max(m0.month, 1), 12)
                        d = date(m0.year, month, yr.randint(1, 28))
                        if d <= end:
                            comp = yr.choices(list(R.COMPONENTS), weights=[0.4, 0.3, 0.3])[0]
                            per_unit.append(_major(cfg, u, park, comp, d, yr, wx))
                # ------------------------------------- lote defectuoso de multiplicadoras HTW (2024-2025)
                lot = R.STORY["htw_gearbox_lot"]
                if u.manufacturer == lot["manufacturer"] and lot["from"] <= m0 <= lot["to"]:
                    lr = prng(cfg.seed, "htw-lot", u.asset_id, m0)
                    if lr.random() < lot["rate_year"] / 12:
                        d = m0 + timedelta(days=lr.randint(0, dim - 1))
                        if d <= end:
                            per_unit.append(_major(cfg, u, park, "GEARBOX", d, lr, wx))
            else:
                # ---------------------------------------------------- inversores
                if rng.random() < 0.06:
                    d = m0 + timedelta(days=rng.randint(0, dim - 1))
                    s = local_epoch(d, rng.uniform(7, 17))
                    dur = travel_hours(park) + rng.uniform(3, 60)
                    per_unit.append(_event(u, "MINOR_FAULT", rng.choice(["IGBT", "VENTILACION", "AISLACION"]),
                                           s, s + int(dur * 3600), travel=travel_hours(park)))
        # historia guionada: multiplicadora de la turbina 1 de Cañadón León en pleno invierno
        if u.park == story["park"] and u.idx == 1 and story["gearbox_failure"] <= end:
            yr = prng(cfg.seed, "story", u.asset_id)
            per_unit = [e for e in per_unit if e["kind"] != "MAJOR_FAILURE"]
            per_unit.append(_major(cfg, u, park, "GEARBOX", story["gearbox_failure"], yr, wx, forced_days=21))
        events.extend(_drop_overlaps(per_unit))
    return events


def _event(u: Unit, kind: str, component: str, start: int, end: int, *, remote: bool = False,
           travel: float = 0.0, access_delay: float = 0.0, wait: float = 0.0, repair: float = 0.0,
           degrade_start: int | None = None) -> dict:
    return {"asset_id": u.asset_id, "asset_type": u.asset_type, "park": u.park, "kind": kind,
            "component": component, "start": int(start), "end": int(end), "degrade_start": degrade_start,
            "remote": remote, "travel_h": round(travel, 1), "access_delay_h": round(access_delay, 1),
            "parts_wait_h": round(wait, 1), "repair_h": round(repair, 1)}


def _major(cfg: ProjectConfig, u: Unit, park: R.Park, comp: str, d: date, rng, wx,
           forced_days: int | None = None) -> dict:
    start = local_epoch(d, rng.uniform(0, 24))
    warn_days = R.COMPONENTS[comp][1] + rng.randint(-4, 6)
    surprise = forced_days is None and rng.random() < 0.15  # falla sin aviso previo: el modelo no la ve
    wait_days = {"GEARBOX": (12, 20), "MAIN_BEARING": (8, 14), "GENERATOR_BEARING": (3, 7)}[comp]
    repair_h = {"GEARBOX": (60, 96), "MAIN_BEARING": (48, 72), "GENERATOR_BEARING": (16, 30)}[comp]
    travel = travel_hours(park)
    wait = rng.uniform(*wait_days) * 24
    repair = rng.uniform(*repair_h)
    delay = 0.0
    if park.province == "Santa Cruz" and d.month in (6, 7, 8):
        delay = rng.uniform(5, 8) * 24  # nieve en la ruta + grúa que no puede izar con viento
    elif wx.get((u.park, d), {}).get("road_closed"):
        delay = rng.uniform(1, 3) * 24
    if forced_days is not None:  # historia guionada: la parada dura exactamente lo pedido
        wait = forced_days * 24 - travel - repair - delay
    total_h = travel + wait + repair + delay
    return _event(u, "MAJOR_FAILURE", comp, start, start + int(total_h * 3600), travel=travel,
                  access_delay=delay, wait=wait, repair=repair,
                  degrade_start=None if surprise else start - warn_days * 86_400)


def _drop_overlaps(events: list[dict]) -> list[dict]:
    """Una turbina no puede estar en dos paradas a la vez: gana la más grave."""
    rank = {"MAJOR_FAILURE": 0, "MINOR_FAULT": 1, "PREVENTIVE": 2}
    kept: list[dict] = []
    for e in sorted(events, key=lambda x: (rank[x["kind"]], x["start"])):
        if all(e["end"] <= k["start"] or e["start"] >= k["end"] for k in kept):
            kept.append(e)
    return sorted(kept, key=lambda x: x["start"])


# =============================================================================
# Cortes de comunicación (VSAT) y episodios de sensores
# =============================================================================
def comm_outages(cfg: ProjectConfig, end: date) -> list[dict]:
    out: list[dict] = []
    for park in R.PARKS:
        for m0 in month_starts(max(cfg.start_date, park.commissioning), end):
            rng = prng(cfg.seed, "comm", park.code, m0)
            n = rng.randint(2, 4) if park.link == "VSAT" else (1 if rng.random() < 0.15 else 0)
            for _ in range(n):
                d = m0 + timedelta(days=rng.randint(0, 27))
                winter = d.month in (6, 7, 8) and park.region == "PATAGONIA"
                dur = rng.uniform(1, 14 if park.link == "VSAT" else 4) * (1.6 if winter else 1.0)
                s = local_epoch(d, rng.uniform(0, 24))
                out.append({"park": park.code, "start": s, "end": s + int(dur * 3600),
                            "buffered": rng.random() < 0.6})
    return out


def clock_skews(cfg: ProjectConfig, end: date) -> list[dict]:
    out: list[dict] = []
    for u in fleet(cfg, "WTG"):
        for year in range(cfg.start_date.year, end.year + 1):
            rng = prng(cfg.seed, "skew", u.asset_id, year)
            if rng.random() < 0.06:
                d = date(year, rng.randint(1, 12), rng.randint(1, 28))
                s = local_epoch(d, rng.uniform(0, 24))
                offset = rng.choice([-1, 1]) * rng.randint(180, 840)
                out.append({"asset_id": u.asset_id, "start": s, "end": s + rng.randint(10, 60) * 86_400,
                            "offset_s": offset})
    return out


STUCK_SENSORS = {"gearbox_bearing_c": (35.0, 60.0), "wind_ms": (4.0, 9.0), "vibration_mm_s": (1.2, 3.0)}


def stuck_sensors(cfg: ProjectConfig, end: date) -> list[dict]:
    out: list[dict] = []
    for u in fleet(cfg, "WTG"):
        for year in range(cfg.start_date.year, end.year + 1):
            rng = prng(cfg.seed, "stuck", u.asset_id, year)
            for _ in range(rng.randint(1, 2)):
                sensor = rng.choice(list(STUCK_SENSORS))
                d = date(year, rng.randint(1, 12), rng.randint(1, 28))
                s = local_epoch(d, rng.uniform(0, 24))
                lo, hi = STUCK_SENSORS[sensor]
                out.append({"asset_id": u.asset_id, "sensor": sensor, "start": s,
                            "end": s + int(rng.uniform(6, 72) * 3600), "value": round(rng.uniform(lo, hi), 2)})
    return out


# =============================================================================
# Curtailment: instrucciones de despacho de CAMMESA
# =============================================================================
def curtailment_instructions(cfg: ProjectConfig, end: date) -> list[dict]:
    """Días de congestión en la red patagónica y la instrucción que recibe cada parque.

    La línea de 500 kV que saca la energía de la Patagonia está saturada: cuando sopla
    mucho y la demanda es baja (noches, fines de semana, feriados, primavera) CAMMESA
    ordena bajar potencia. Los parques "al final de la línea" (Santa Cruz) sufren más.
    """
    wx = park_day_index(cfg, end)
    cap = park_capacity_kw(cfg)
    growth = R.STORY["curtailment_growth"]
    story = R.STORY["leo_july_2025"]
    season = {9: 1.5, 10: 1.6, 11: 1.5, 12: 1.3, 1: 1.1, 2: 1.0, 3: 0.9, 4: 0.8, 5: 0.7, 6: 0.6, 7: 0.6, 8: 0.9}
    out: list[dict] = []
    seq = 0
    for d in daterange(cfg.start_date, end):
        rng = prng(cfg.seed, "cong", d)
        weekend = d.weekday() >= 5 or d in R.HOLIDAYS_AR
        windy = wx[("CRV", d)]["wind_mult"]
        p = 0.16 * growth.get(d.year, 1.1) * season[d.month] * (1.6 if weekend else 1.0) * windy ** 2
        congested = rng.random() < min(0.85, p)
        if congested:
            night = rng.random() < 0.6 or not weekend
            h0 = rng.randint(0, 5) if night else rng.randint(10, 15)
            dur = rng.randint(3, 11)
        for park in R.WIND_PARKS:
            if d < park.commissioning:
                continue
            prk = prng(cfg.seed, "curt", park.code, d)
            forced = (park.code == story["park"] and story["grid_maintenance"][0] <= d <= story["grid_maintenance"][1])
            if forced:
                start, stop = local_epoch(d, 0), local_epoch(d, 24)
                frac, reason = story["grid_limit_fraction"], "MANTENIMIENTO_ET"
            elif congested and prk.random() < park.curtail_exposure:
                start = local_epoch(d, h0 + prk.choice([0, 0, 1]))
                stop = start + (dur + prk.randint(-1, 2)) * 3600
                frac = round(max(0.15, 0.85 - park.curtail_exposure * prk.uniform(0.4, 0.8)), 2)
                reason = "RESTRICCION_TRANSPORTE"
            elif prk.random() < 0.004:
                start = local_epoch(d, prk.randint(8, 16))
                stop, frac, reason = start + prk.randint(1, 3) * 3600, 0.5, "CONTROL_FRECUENCIA"
            else:
                continue
            seq += 1
            out.append({"instruction_id": f"DSP-{d:%Y%m%d}-{park.cammesa_code}-{seq % 100:02d}",
                        "park": park.code, "start": start, "end": stop, "limit_frac": frac,
                        "limit_mw": round(cap[park.code] / 1000 * frac, 2), "reason": reason})
    return out


# =============================================================================
# Mercado: tipo de cambio, inflación, precio spot
# =============================================================================
def fx_rate(d: date) -> float:
    """Tipo de cambio oficial ARS/USD (interpolación geométrica entre fines de mes)."""
    deval = R.STORY["devaluation"]
    prev_m = date(d.year - (d.month == 1), (d.month - 2) % 12 + 1, 1)
    v_prev = R.FX_END_OF_MONTH.get(prev_m.year, R.FX_END_OF_MONTH[2023])[prev_m.month - 1]
    if prev_m < date(2023, 1, 1):
        v_prev = 177.0
    v_end = R.FX_END_OF_MONTH[d.year][d.month - 1]
    if d.year == deval.year and d.month == deval.month:
        return round(366.0 + (d.day - 1) * 0.6, 2) if d < deval else round(800.0 + (d.day - 13) * 0.45, 2)
    days = (date(d.year + (d.month == 12), d.month % 12 + 1, 1) - date(d.year, d.month, 1)).days
    return round(v_prev * (v_end / v_prev) ** (d.day / days), 2)


def cpi_index(d: date) -> float:
    """Índice de precios (ene-2023 = 1.0) con la inflación mensual acumulada."""
    idx = 1.0
    for y in range(2023, d.year + 1):
        for m in range(1, 13):
            if (y, m) >= (d.year, d.month):
                return idx
            idx *= 1 + R.INFLATION_MONTHLY_PCT[y][m - 1] / 100
    return idx


def labor_rate_ars(d: date) -> float:
    """Costo de la hora-hombre de campo en ARS: sigue a la inflación con un mes de rezago."""
    lag = date(d.year - (d.month == 1), (d.month - 2) % 12 + 1, 1)
    return round(4_800 * cpi_index(max(lag, date(2023, 1, 1))), 0)


def spot_price_usd(node: str, d: date, hour: int, rng, congested: bool) -> float:
    base = 44.0 + {6: 26, 7: 28, 8: 20, 1: 10, 2: 8, 12: 5}.get(d.month, 0)
    shape = {0: -14, 1: -16, 2: -17, 3: -17, 4: -16, 5: -12, 6: -6, 7: 0, 8: 3, 9: 4, 10: 4, 11: 4,
             12: 3, 13: 2, 14: 2, 15: 2, 16: 3, 17: 6, 18: 12, 19: 20, 20: 22, 21: 18, 22: 8, 23: -4}[hour]
    if d.weekday() >= 5 or d in R.HOLIDAYS_AR:
        base -= 8
    price = (base + shape) * rng.uniform(0.9, 1.1)
    if node == "PATAGONIA" and congested:
        price = rng.uniform(4, 15)  # nodo desacoplado: sobra energía y no hay línea para sacarla
    return round(max(2.0, price), 2)


# =============================================================================
# Presupuesto P50 (Monte Carlo con la misma física del generador)
# =============================================================================
BUDGET_ASSUMPTIONS = {  # (disponibilidad, curtailment) que Finanzas asume cada año en la Patagonia
    2023: (0.97, 0.03), 2024: (0.97, 0.035), 2025: (0.97, 0.04), 2026: (0.97, 0.05),
}
REFORECAST_2025 = (date(2025, 7, 1), 0.07)  # en julio 2025 Finanzas re-presupuesta el 2do semestre


def expected_unit_kw(cfg: ProjectConfig, park: R.Park, year: int, month: int, samples: int = 1_200) -> float:
    """Potencia media esperada (kW) de UN equipo del parque en ese mes, sin pérdidas."""
    rng = prng(cfg.seed, "budget", park.code, year, month)
    first = date(year, month, 1)
    days = (date(year + (month == 12), month % 12 + 1, 1) - first).days
    total = 0.0
    if park.tech == "WIND":
        m = R.MANUFACTURERS[park.manufacturer]
        for _ in range(samples):
            t = local_epoch(first, rng.uniform(0, days * 24))
            day_mult = (math.exp(WIND_DAY_SIGMA * rng.gauss(0, 1) - WIND_DAY_SIGMA ** 2 / 2)
                        * math.exp(0.06 * rng.gauss(0, 1) - 0.0018))
            w = ph.wind_ms_py(park.code, t, day_mult, rng.uniform(0.92, 1.04), rng.random())
            total += ph.power_kw_py(w, m.rated_kw, m.rated_wind_ms)
        return total / samples
    dc = park.panels_real // park.units_real * cfg.profile.panel_wp / 1000
    cloud = 0.80 if (park.altitude_m > 3_000 and month in (1, 2, 3, 12)) else 0.95
    for _ in range(samples):
        t = local_epoch(first, rng.uniform(0, days * 24))
        poa = ph.poa_clear_py(park.code, t) * cloud
        temp = ph.temp_c_py(park.code, t) + poa * 0.03
        dc_kw = dc * poa / 1000 * (1 - 0.004 * (temp - 25)) * (1 - 0.04)
        total += min(cfg.profile.inverter_kw, dc_kw * 0.975)
    return total / samples
