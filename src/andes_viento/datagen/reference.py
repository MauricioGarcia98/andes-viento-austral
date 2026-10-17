"""Datos maestros de Andes Viento Austral S.A. (empresa ficticia, realidad argentina).

Todo lo que está acá es la "verdad de negocio" que el generador usa para fabricar
las fuentes: parques, fabricantes, personas, clientes PPA, feriados, inflación y
tipo de cambio. Los nombres de personas y empresas son INVENTADOS; los números
macro (inflación, dólar) están inspirados en la Argentina 2023-2026 pero redondeados:
no los uses como dato oficial.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# =============================================================================
# Bases de mantenimiento (de donde salen las cuadrillas)
# =============================================================================
BASES = {
    "CRV": ("Base Patagonia", "Comodoro Rivadavia", "Chubut"),
    "JUJ": ("Base NOA", "San Salvador de Jujuy", "Jujuy"),
}


# =============================================================================
# Fabricantes de aerogeneradores (ficticios)
# =============================================================================
@dataclass(frozen=True)
class Manufacturer:
    code: str
    name: str
    country: str
    model: str
    rated_kw: int
    rated_wind_ms: float
    rotor_rpm_max: float
    ts_format: str          # cómo manda la fecha su SCADA
    power_unit: str         # unidad "de fábrica" de la potencia
    guaranteed_availability: float
    ld_usd_per_point_mw: float  # liquidated damages: USD por punto % por MW instalado y año


MANUFACTURERS = {
    "AWS": Manufacturer("AWS", "Aurora Wind Systems", "Dinamarca", "AW-136/3.6", 3_600, 12.0, 14.0,
                        "iso_offset", "kW", 0.97, 6_500.0),
    "HTW": Manufacturer("HTW", "Hanse Turbinen Werke", "Alemania", "HT-150/4.5", 4_500, 12.5, 12.5,
                        "epoch_ms", "kW", 0.97, 7_000.0),
    "PEI": Manufacturer("PEI", "Pampa Eólica Industrial", "Argentina", "PE-120/3.0", 3_000, 11.5, 15.0,
                        "local_dmy", "MW", 0.97, 5_000.0),
}

# El fabricante alemán actualiza el firmware y AGREGA SENSORES (schema drift en el JSON).
SCHEMA_DRIFT_SCADA = ("HTW", date(2025, 3, 1), ["ice_detector", "oil_particle_count", "tower_accel_mg"])
# Los parques solares instalan sensores de suciedad (columna nueva en el CSV).
SCHEMA_DRIFT_INVERTER = ("soiling_sensor_pct", date(2025, 6, 1))


# =============================================================================
# Parques
# =============================================================================
@dataclass(frozen=True)
class Park:
    code: str
    name: str
    tech: str               # WIND | SOLAR
    province: str
    region: str             # PATAGONIA | NOA
    lat: float
    lon: float
    units_real: int         # turbinas (eólico) o inversores (solar) a SF=1
    manufacturer: str | None
    commissioning: date
    cammesa_node: str
    cammesa_code: str       # nemotécnico del agente generador en CAMMESA
    base: str
    distance_km: int
    link: str               # FIBRA | VSAT (satelital)
    wind_mean_ms: float = 0.0
    panels_real: int = 0
    curtail_exposure: float = 0.0  # 0..1: qué tan "al final de la línea" está
    park_manager: str = ""
    water_cost_usd_m3: float = 0.0
    altitude_m: int = 0


PARKS = [
    # ---------------------------------------------------------------- eólicos
    Park("RAW", "Rawson Sur", "WIND", "Chubut", "PATAGONIA", -43.36, -65.12, 45, "AWS", date(2012, 11, 20),
         "PATAGONIA", "PERAWSUR", "CRV", 380, "FIBRA", 9.1, curtail_exposure=0.30,
         park_manager="Valeria Ñancucheo", altitude_m=40),
    Park("MAD", "Puerto Madryn Norte", "WIND", "Chubut", "PATAGONIA", -42.69, -65.10, 40, "AWS", date(2015, 6, 3),
         "PATAGONIA", "PEMADNOR", "CRV", 440, "FIBRA", 8.9, curtail_exposure=0.25,
         park_manager="Tomás Huichaqueo", altitude_m=90),
    Park("GAR", "Garayalde", "WIND", "Chubut", "PATAGONIA", -44.68, -66.60, 35, "PEI", date(2017, 9, 12),
         "PATAGONIA", "PEGARAYA", "CRV", 160, "VSAT", 9.6, curtail_exposure=0.45,
         park_manager="Julieta Calfuquir", altitude_m=420),
    Park("CRV", "Cerro Arenales", "WIND", "Chubut", "PATAGONIA", -45.80, -67.55, 50, "AWS", date(2018, 3, 28),
         "PATAGONIA", "PEARENAL", "CRV", 25, "FIBRA", 10.2, curtail_exposure=0.50,
         park_manager="Hernán Sayhueque", altitude_m=610),
    Park("PAM", "Pampa del Castillo", "WIND", "Chubut", "PATAGONIA", -45.95, -67.95, 45, "PEI", date(2019, 1, 15),
         "PATAGONIA", "PEPAMCAS", "CRV", 60, "FIBRA", 10.0, curtail_exposure=0.55,
         park_manager="Lorena Antieco", altitude_m=720),
    Park("DES", "Bahía Deseado", "WIND", "Santa Cruz", "PATAGONIA", -47.70, -65.95, 38, "HTW", date(2019, 10, 1),
         "PATAGONIA", "PEBAHDES", "CRV", 290, "VSAT", 10.4, curtail_exposure=0.65,
         park_manager="Ezequiel Manquel", altitude_m=110),
    Park("PIC", "Pico Truncado Alto", "WIND", "Santa Cruz", "PATAGONIA", -46.80, -67.90, 42, "HTW", date(2020, 8, 21),
         "PATAGONIA", "PEPICTRU", "CRV", 130, "FIBRA", 10.6, curtail_exposure=0.70,
         park_manager="Agustina Painemal", altitude_m=480),
    Park("SJU", "San Julián Meseta", "WIND", "Santa Cruz", "PATAGONIA", -49.25, -68.10, 40, "HTW", date(2022, 4, 7),
         "PATAGONIA", "PESJUMES", "CRV", 350, "VSAT", 10.9, curtail_exposure=0.85,
         park_manager="Bruno Catrileo", altitude_m=260),
    Park("LEO", "Cañadón León", "WIND", "Santa Cruz", "PATAGONIA", -48.70, -70.25, 45, "HTW", date(2023, 2, 14),
         "PATAGONIA", "PECANLEO", "CRV", 520, "VSAT", 11.2, curtail_exposure=0.90,
         park_manager="Micaela Quilaqueo", altitude_m=350),
    # ----------------------------------------------------------------- solares
    Park("SUS", "Susques Solar", "SOLAR", "Jujuy", "NOA", -23.42, -66.37, 73, None, date(2021, 5, 10),
         "NOA", "PSSUSQUE", "JUJ", 180, "VSAT", panels_real=400_000, park_manager="Rodrigo Colque",
         water_cost_usd_m3=14.0, altitude_m=3_700),
    Park("ABR", "Abra Pampa Solar", "SOLAR", "Jujuy", "NOA", -22.72, -65.70, 55, None, date(2021, 11, 30),
         "NOA", "PSABRAPA", "JUJ", 220, "VSAT", panels_real=300_000, park_manager="Natalia Mamaní",
         water_cost_usd_m3=11.0, altitude_m=3_480),
    Park("TIN", "Tinogasta Sol", "SOLAR", "Catamarca", "NOA", -28.06, -67.56, 46, None, date(2022, 7, 18),
         "NOA", "PSTINOGA", "JUJ", 480, "FIBRA", panels_real=250_000, park_manager="Federico Vildoza",
         water_cost_usd_m3=7.5, altitude_m=1_200),
    Park("FIA", "Fiambalá Solar", "SOLAR", "Catamarca", "NOA", -27.68, -67.62, 46, None, date(2023, 4, 4),
         "NOA", "PSFIAMBA", "JUJ", 520, "VSAT", panels_real=250_000, park_manager="Carolina Reales",
         water_cost_usd_m3=9.0, altitude_m=1_550),
]
PARKS_BY_CODE = {p.code: p for p in PARKS}
WIND_PARKS = [p for p in PARKS if p.tech == "WIND"]
SOLAR_PARKS = [p for p in PARKS if p.tech == "SOLAR"]

# El parque Pampa del Castillo (SCADA de PEI) pasó a mandar la hora en UTC sin avisar.
TZ_SWITCH = ("PAM", date(2024, 4, 1))
# Cerro Arenales adoptó el estándar de nombres IEC 81346: "CRV-07" pasa a "CRV-WTG007".
TURBINE_RENAME = ("CRV", date(2024, 6, 1))
# Fiambalá exportaba la potencia AC en MW (en una columna que dice kW) hasta este día.
INVERTER_MW_BUG = ("FIA", date(2024, 3, 1))

# Factor estacional de viento (enero..diciembre). En la Patagonia sopla más en primavera-verano.
WIND_SEASONAL = [1.06, 1.03, 0.99, 0.96, 0.94, 0.93, 0.94, 0.97, 1.01, 1.05, 1.07, 1.07]
# Temperatura media anual "a nivel del mar" (°C) por región; después se corrige por
# latitud y altura (-6,5 °C cada 1.000 m: la Puna a 3.700 m es fría aunque esté en el trópico).
TEMP_MEAN = {"PATAGONIA": 12.0, "NOA": 28.0}
TEMP_AMPLITUDE = {"PATAGONIA": 7.5, "NOA": 6.0}  # verano-invierno
TEMP_DIURNAL = {"PATAGONIA": 5.0, "NOA": 10.0}   # día-noche (en la Puna la amplitud es enorme)


# =============================================================================
# La historia que tiene que aparecer en los datos (y que Genie debe encontrar)
# =============================================================================
STORY = {
    # Agent mode: "¿por qué Cañadón León generó 18 % menos en julio 2025?"
    "leo_july_2025": {
        "park": "LEO",
        "cold_wave": (date(2025, 7, 3), date(2025, 7, 5)),       # ola polar: hielo en palas
        "grid_maintenance": (date(2025, 7, 10), date(2025, 7, 20)),  # ET Santa Cruz Norte: tope 60 %
        "grid_limit_fraction": 0.60,
        "gearbox_failure": date(2025, 7, 26),                   # multiplicadora, RN40 con nieve: 21 días
        "wind_anomaly": 0.98,                                   # julio un 2 % menos ventoso
    },
    # Saturación de la línea 500 kV Patagonia: el curtailment crece año a año.
    "curtailment_growth": {2023: 0.55, 2024: 0.80, 2025: 1.00, 2026: 1.10},
    # Devaluación del 13-dic-2023.
    "devaluation": date(2023, 12, 13),
}

# Componentes que se rompen y su firma predictiva (días de degradación visibles en SCADA).
COMPONENTS = {
    "GEARBOX": ("Multiplicadora", 28, 140_000.0),   # (nombre, días de aviso, costo repuesto USD a SF=1)
    "MAIN_BEARING": ("Rodamiento principal", 21, 85_000.0),
    "GENERATOR_BEARING": ("Rodamiento del generador", 14, 22_000.0),
}

ALARM_CODES = {
    "AWS": {"GEARBOX": "AWS-3120", "MAIN_BEARING": "AWS-3155", "GENERATOR_BEARING": "AWS-4012",
            "MINOR": "AWS-2210", "ICE": "AWS-7001"},
    "HTW": {"GEARBOX": "HTW-E417", "MAIN_BEARING": "HTW-E422", "GENERATOR_BEARING": "HTW-E530",
            "MINOR": "HTW-W110", "ICE": "HTW-I900"},
    "PEI": {"GEARBOX": "PEI-501", "MAIN_BEARING": "PEI-505", "GENERATOR_BEARING": "PEI-610",
            "MINOR": "PEI-201", "ICE": "PEI-900"},
}
GRID_ALARM = "GRID-07"  # setpoint de CAMMESA activo


# =============================================================================
# Personas (todas ficticias) y áreas de la empresa
# =============================================================================
PEOPLE = [
    # (nombre, cargo, área, email)
    ("Lucía Ferreyra", "Directora General (CEO)", "Dirección", "lferreyra@andesviento.com.ar"),
    ("Martín Quiroga", "Gerente de Operaciones", "Operación de parques", "mquiroga@andesviento.com.ar"),
    ("Ramiro Llancaqueo", "Jefe de Mantenimiento", "Mantenimiento", "rllancaqueo@andesviento.com.ar"),
    ("Sofía Bertolini", "Gerente Comercial", "Comercial PPA", "sbertolini@andesviento.com.ar"),
    ("Diego Achával", "Director de Finanzas (CFO)", "Finanzas", "dachaval@andesviento.com.ar"),
    ("Camila Iturbe", "Analista de Riesgo de Mercado", "Finanzas", "citurbe@andesviento.com.ar"),
    ("Florencia Paz", "Head of Data & Analytics", "Datos", "fpaz@andesviento.com.ar"),
    ("Andrea Colque", "Responsable de Medioambiente (HSE)", "HSE", "acolque@andesviento.com.ar"),
    ("Joaquín Ortiz", "Ingeniero de Confiabilidad", "Mantenimiento", "jortiz@andesviento.com.ar"),
    ("Paula Giménez", "Analista Comercial", "Comercial PPA", "pgimenez@andesviento.com.ar"),
]

# Cuadrillas: (id, base, líder, teléfono, integrantes, especialidad)
CREWS = [
    ("CU-PAT-01", "CRV", "Gustavo Millaqueo", "+54 297 415-2231", 6, "Mecánica pesada (grúa)"),
    ("CU-PAT-02", "CRV", "Silvina Ancalao", "+54 297 433-8810", 5, "Eléctrica y control"),
    ("CU-PAT-03", "CRV", "Marcos Prane", "+54 297 402-1199", 5, "Palas y torre (altura)"),
    ("CU-PAT-04", "CRV", "Iván Cayupán", "+54 297 488-5521", 4, "Preventivo"),
    ("CU-NOA-01", "JUJ", "Rosa Cruz", "+54 388 455-0912", 8, "Limpieza de paneles"),
    ("CU-NOA-02", "JUJ", "Elías Tolaba", "+54 388 431-7765", 5, "Inversores y MT"),
]


# =============================================================================
# Clientes PPA en el MATER (ficticios)
# =============================================================================
@dataclass(frozen=True)
class Contract:
    contract_id: str
    client: str
    sector: str
    cuit: str
    contact_name: str
    contact_email: str
    contact_phone: str
    start: date
    end: date
    price_usd_mwh: float
    share_of_sources: float    # fracción de la P50 de sus parques que se compromete (un PPA real: 50-75 %)
    penalty_usd_mwh: float     # penalidad por MWh faltante (take-or-pay)
    tolerance_pct: float       # faltante tolerado sin penalidad
    sources: tuple[str, ...]


CONTRACTS = [
    Contract("PPA-2018-001", "Aluminios Patagónicos S.A.", "Aluminio", "30-71234567-1", "Mariano Lescano",
             "mlescano@aluminiospat.com.ar", "+54 280 444-1020", date(2018, 7, 1), date(2033, 6, 30),
             58.0, 0.60, 32.0, 0.05, ("RAW", "MAD")),
    Contract("PPA-2019-002", "Cementera del Plata S.A.", "Cemento", "30-70987654-3", "Gabriela Sosa",
             "gsosa@cementeradelplata.com.ar", "+54 11 4555-2310", date(2019, 3, 1), date(2029, 2, 28),
             61.5, 0.50, 35.0, 0.08, ("CRV", "PAM")),
    Contract("PPA-2020-003", "Automotriz Zárate S.A.", "Automotriz", "30-71555444-9", "Pablo Ruiz Díaz",
             "pruizdiaz@automotrizzarate.com.ar", "+54 3487 42-9900", date(2020, 1, 1), date(2030, 12, 31),
             63.0, 0.30, 30.0, 0.10, ("GAR", "CRV")),
    Contract("PPA-2021-004", "Litio de la Puna S.A.", "Minería", "30-71888222-5", "Verónica Choque",
             "vchoque@litiopuna.com.ar", "+54 388 422-7781", date(2021, 6, 1), date(2036, 5, 31),
             66.0, 0.70, 40.0, 0.05, ("SUS", "ABR")),
    Contract("PPA-2021-005", "Supermercados La Estrella S.A.", "Retail", "30-69111333-7", "Juan Pablo Aranda",
             "jparanda@laestrella.com.ar", "+54 351 466-3002", date(2021, 9, 1), date(2028, 8, 31),
             68.0, 0.30, 28.0, 0.10, ("DES", "TIN")),
    Contract("PPA-2022-006", "Frigorífico Pampeano S.A.", "Alimentos", "30-70333999-2", "Laura Etchegaray",
             "letchegaray@frigopampeano.com.ar", "+54 2954 41-5566", date(2022, 2, 1), date(2032, 1, 31),
             64.5, 0.35, 34.0, 0.08, ("PIC", "DES")),
    Contract("PPA-2023-007", "Data Center Austral S.R.L.", "Tecnología", "30-71999000-4", "Nicolás Brandán",
             "nbrandan@dcaustral.com.ar", "+54 11 5263-8800", date(2023, 3, 1), date(2038, 2, 28),
             71.0, 0.62, 55.0, 0.03, ("SJU", "LEO")),
    Contract("PPA-2025-008", "Papelera Mesopotámica S.A.", "Papel", "30-72100200-8", "Ana Benítez",
             "abenitez@papelerameso.com.ar", "+54 343 420-1188", date(2025, 3, 1), date(2035, 2, 28),
             62.0, 0.25, 30.0, 0.07, ("FIA", "PIC")),
]
# La Papelera aparece recién en 2025 (INSERT); el Frigorífico rescinde en 2026 (DELETE en el CDC).
CONTRACT_TERMINATION = ("PPA-2022-006", date(2026, 4, 30))


# =============================================================================
# Calendario argentino: feriados nacionales 2023-2026 (inamovibles + trasladables + puente)
# =============================================================================
HOLIDAYS_AR = {
    # 2023
    date(2023, 1, 1): "Año Nuevo", date(2023, 2, 20): "Carnaval", date(2023, 2, 21): "Carnaval",
    date(2023, 3, 24): "Día de la Memoria", date(2023, 4, 2): "Malvinas", date(2023, 4, 7): "Viernes Santo",
    date(2023, 5, 1): "Día del Trabajador", date(2023, 5, 25): "Revolución de Mayo",
    date(2023, 5, 26): "Puente turístico", date(2023, 6, 17): "Güemes", date(2023, 6, 19): "Puente turístico",
    date(2023, 6, 20): "Día de la Bandera", date(2023, 7, 9): "Independencia", date(2023, 8, 21): "San Martín",
    date(2023, 10, 13): "Puente turístico", date(2023, 10, 16): "Diversidad Cultural",
    date(2023, 11, 20): "Soberanía Nacional", date(2023, 12, 8): "Inmaculada Concepción",
    date(2023, 12, 25): "Navidad",
    # 2024
    date(2024, 1, 1): "Año Nuevo", date(2024, 2, 12): "Carnaval", date(2024, 2, 13): "Carnaval",
    date(2024, 3, 24): "Día de la Memoria", date(2024, 3, 29): "Viernes Santo", date(2024, 4, 1): "Puente turístico",
    date(2024, 4, 2): "Malvinas", date(2024, 5, 1): "Día del Trabajador", date(2024, 5, 25): "Revolución de Mayo",
    date(2024, 6, 17): "Güemes", date(2024, 6, 20): "Día de la Bandera", date(2024, 6, 21): "Puente turístico",
    date(2024, 7, 9): "Independencia", date(2024, 8, 17): "San Martín", date(2024, 10, 12): "Diversidad Cultural",
    date(2024, 11, 18): "Soberanía Nacional", date(2024, 12, 8): "Inmaculada Concepción",
    date(2024, 12, 25): "Navidad",
    # 2025
    date(2025, 1, 1): "Año Nuevo", date(2025, 3, 3): "Carnaval", date(2025, 3, 4): "Carnaval",
    date(2025, 3, 24): "Día de la Memoria", date(2025, 4, 2): "Malvinas", date(2025, 4, 18): "Viernes Santo",
    date(2025, 5, 1): "Día del Trabajador", date(2025, 5, 2): "Puente turístico",
    date(2025, 5, 25): "Revolución de Mayo", date(2025, 6, 16): "Güemes", date(2025, 6, 20): "Día de la Bandera",
    date(2025, 7, 9): "Independencia", date(2025, 8, 15): "Puente turístico", date(2025, 8, 17): "San Martín",
    date(2025, 10, 12): "Diversidad Cultural", date(2025, 11, 21): "Puente turístico",
    date(2025, 11, 24): "Soberanía Nacional", date(2025, 12, 8): "Inmaculada Concepción",
    date(2025, 12, 25): "Navidad",
    # 2026
    date(2026, 1, 1): "Año Nuevo", date(2026, 2, 16): "Carnaval", date(2026, 2, 17): "Carnaval",
    date(2026, 3, 23): "Puente turístico", date(2026, 3, 24): "Día de la Memoria", date(2026, 4, 2): "Malvinas",
    date(2026, 4, 3): "Viernes Santo", date(2026, 5, 1): "Día del Trabajador",
    date(2026, 5, 25): "Revolución de Mayo", date(2026, 6, 15): "Güemes", date(2026, 6, 20): "Día de la Bandera",
    date(2026, 7, 9): "Independencia", date(2026, 7, 10): "Puente turístico", date(2026, 8, 17): "San Martín",
    date(2026, 10, 12): "Diversidad Cultural", date(2026, 11, 23): "Soberanía Nacional",
    date(2026, 12, 7): "Puente turístico", date(2026, 12, 8): "Inmaculada Concepción", date(2026, 12, 25): "Navidad",
}

# =============================================================================
# Macro: inflación mensual (%) y tipo de cambio oficial de fin de mes (ARS por USD).
# Aproximados y redondeados (inspirados en INDEC/BCRA). 2026 = escenario del proyecto.
# =============================================================================
INFLATION_MONTHLY_PCT = {
    2023: [6.0, 6.6, 7.7, 8.4, 7.8, 6.0, 6.3, 12.4, 12.7, 8.3, 12.8, 25.5],
    2024: [20.6, 13.2, 11.0, 8.8, 4.2, 4.6, 4.0, 4.2, 3.5, 2.7, 2.4, 2.7],
    2025: [2.2, 2.4, 3.7, 2.8, 1.5, 1.6, 1.9, 1.9, 2.1, 2.3, 2.5, 2.8],
    2026: [2.4, 2.2, 2.6, 2.3, 2.0, 1.9, 2.1, 2.0, 1.8, 1.9, 2.0, 2.2],
}
FX_END_OF_MONTH = {
    2023: [186, 197, 209, 222, 240, 256, 276, 350, 350, 350, 359, 808],
    2024: [826, 843, 858, 876, 894, 912, 932, 950, 970, 990, 1_010, 1_032],
    2025: [1_052, 1_073, 1_096, 1_160, 1_165, 1_205, 1_300, 1_340, 1_380, 1_440, 1_450, 1_455],
    2026: [1_462, 1_470, 1_485, 1_492, 1_505, 1_518, 1_530, 1_541, 1_552, 1_565, 1_580, 1_595],
}
