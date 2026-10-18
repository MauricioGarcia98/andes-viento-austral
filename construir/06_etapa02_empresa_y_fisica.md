# 06 · Etapa 2 · La empresa en código y la física

## 🎯 Objetivo

Escribir **la verdad del negocio** (parques, fabricantes, contratos, feriados, dólar, inflación y la historia que
Genie tiene que poder explicar) y **la física** que convierte esa verdad en números: cuánto sopla, cuánto genera una
turbina con ese viento, qué temperatura hace, cuánto sol llega a un panel.

Va antes que las fuentes porque **las fuentes son consecuencia de esto**: el SCADA reporta lo que dice la física, con
la suciedad de cada fabricante. Si la física está bien, todo lo demás "cierra" solo.

**Archivos:** `src/andes_viento/datagen/__init__.py`, `rand.py`, `reference.py`, `physics.py`.

## 📚 Conceptos

- **Datos sintéticos realistas:** no alcanza con números al azar. Para que un análisis tenga sentido, los datos tienen
  que tener **estructura**: estacionalidad (sopla más en primavera), correlación (dos turbinas del mismo parque ven
  el mismo frente de viento), causas (con hielo se para) y una historia.
- **Determinismo:** la misma semilla tiene que dar **exactamente** los mismos datos, en tu computadora o en un
  clúster de 100 máquinas. Sin eso no podés comparar corridas ni reproducir un error.
- **Expresión de Spark vs. UDF:** una *UDF* de Python es una función tuya que Spark llama fila por fila; los datos
  viajan entre la JVM y Python y es 10-50 veces más lenta. Una **expresión** (`F.sin(...)`, `F.when(...)`) se ejecuta
  adentro de la JVM, optimizada. Todo el generador está hecho con expresiones.
- **Curva de potencia:** cuánta potencia da una turbina según el viento. Debajo de ~3 m/s no arranca (*cut-in*);
  crece aproximadamente con el cubo del viento; desde ~12 m/s da la nominal; arriba de 25 m/s se frena por
  seguridad (*cut-out*).

## 🧱 Paso a paso

### 1. `rand.py`: azar determinístico y distribuido

**El problema:** `F.rand(seed)` de Spark depende de cómo están repartidas las filas entre las particiones. Si el
clúster cambia (o pasás de local a Databricks), cambian los datos.

**La solución:** derivar el "azar" de **los datos mismos** con un hash.
```python
_MOD = 2_147_483_647  # primo de Mersenne 2^31-1

def uniform(*cols, salt: str) -> Column:
    """Número uniforme en [0, 1) derivado de las columnas + una sal."""
    parts = [F.col(c) if isinstance(c, str) else c for c in cols]
    return F.pmod(F.xxhash64(*parts, F.lit(salt)), F.lit(_MOD)) / F.lit(float(_MOD))
```
- `xxhash64(turbina, instante, "viento")` da siempre el mismo número para esa combinación, en cualquier máquina.
- `pmod(..., primo) / primo` lo lleva a [0, 1): un "dado" reproducible.
- La **sal** (`salt`) separa usos: el número para "¿hay una falla?" y el de "¿cuánto ruido tiene el sensor?" tienen que
  ser independientes aunque sean de la misma fila.

Sobre `uniform` se construyen `int_between` (entero en un rango), `pick` (elegir de una lista) y `weighted_pick`
(elegir con pesos, armando un `CASE WHEN` con probabilidades acumuladas). `uniform_sql` es lo mismo como texto SQL,
para usar dentro de funciones de orden superior (`transform`, `filter`) que no aceptan objetos `Column` de Python.

**El azar del driver** (para tablas chicas y secuenciales, como el clima día a día):
```python
def prng(seed: int, *keys) -> random.Random:
    key = "|".join(str(k) for k in keys).encode()
    return random.Random(seed * 1_000_003 + zlib.crc32(key))
```
Un generador de Python sembrado con un hash **estable** (`crc32`). `hash()` de Python **no sirve**: cambia en cada
proceso (por seguridad), y los datos cambiarían en cada corrida.

### 2. `reference.py`: la empresa

Es un archivo largo pero simple: datos, sin lógica. Escribilo leyendo
`git show etapa-02:src/andes_viento/datagen/reference.py`. Lo que importa es **por qué** está cada cosa:

**Fabricantes** (`Manufacturer`, `MANUFACTURERS`): tres, cada uno con su modelo, potencia nominal y, sobre todo, **su
forma de mandar los datos**:

| fabricante | `ts_format` | `power_unit` | por qué existe |
|---|---|---|---|
| AWS (danés) | `iso_offset` (`2025-07-15T10:00:00-03:00`) | kW | el formato "bueno" |
| HTW (alemán) | `epoch_ms` (milisegundos desde 1970) | kW | otro formato; además su firmware agrega sensores en 2025 |
| PEI (argentino) | `local_dmy` (`15/07/2025 10:00`, hora local sin zona) | **MW** | ambigüedad de fechas y unidades |

Los tres formatos y las unidades son el trabajo de silver (capítulo 10). `guaranteed_availability` y
`ld_usd_per_point_mw` son los términos de la garantía (caso de negocio 5).

**Cambios de esquema y de comportamiento** (lo que hace "sucia" la realidad):
```python
SCHEMA_DRIFT_SCADA = ("HTW", date(2025, 3, 1), ["ice_detector", "oil_particle_count", "tower_accel_mg"])
SCHEMA_DRIFT_INVERTER = ("soiling_sensor_pct", date(2025, 6, 1))
TZ_SWITCH = ("PAM", date(2024, 4, 1))         # un parque pasa a mandar UTC sin avisar
TURBINE_RENAME = ("CRV", date(2024, 6, 1))    # "CRV-07" pasa a "CRV-WTG007"
INVERTER_MW_BUG = ("FIA", date(2024, 3, 1))   # potencia en MW en una columna que dice kW
```
Cada tupla es "qué pasa, a quién y desde cuándo". Tenerlos como constantes permite que el generador **los produzca**
y que los tests **verifiquen** que silver los corrige.

**Parques** (`Park`, `PARKS`): 13, con todo lo que el negocio necesita saber de cada uno: tecnología, provincia,
coordenadas (para el sol), equipos a escala 1, fabricante, nodo de CAMMESA, base y distancia (tiempos de viaje de
las cuadrillas), enlace (`VSAT` = satélite: se corta más), viento medio, **exposición al curtailment** (0 a 1: qué tan
"al final de la línea" está; Cañadón León 0,90), jefe de parque, costo del agua (solares) y altura (la Puna a 3.700 m
es fría aunque esté en el trópico).
`PARKS_BY_CODE`, `WIND_PARKS` y `SOLAR_PARKS` son índices para no recorrer la lista cada vez.

**El clima base:** `WIND_SEASONAL` (12 factores, enero a diciembre: sopla más en primavera-verano), `TEMP_MEAN`,
`TEMP_AMPLITUDE`, `TEMP_DIURNAL` por región.

**La historia** (`STORY`), la parte más importante:
```python
STORY = {
    "leo_july_2025": {
        "park": "LEO",
        "cold_wave": (date(2025, 7, 3), date(2025, 7, 5)),            # ola polar: hielo en palas
        "grid_maintenance": (date(2025, 7, 10), date(2025, 7, 20)),   # mantenimiento de la ET
        "grid_limit_fraction": 0.50,                                  # la red acepta el 50 %
        "gearbox_failure": date(2025, 7, 26),                          # multiplicadora rota: 21 días
        "wind_anomaly": 0.98,                                          # julio un 2 % menos ventoso
    },
    "htw_gearbox_lot": {"manufacturer": "HTW", "from": date(2024, 3, 1), "to": date(2025, 12, 31), "rate_year": 0.60},
    "curtailment_growth": {2023: 0.55, 2024: 0.80, 2025: 1.00, 2026: 1.10},
    "devaluation": date(2023, 12, 13),
}
```
Es lo que **tiene** que aparecer en los datos para que las preguntas de "por qué" tengan respuesta. Se diseñó
**antes** que el generador: primero las preguntas para Genie, después la historia, después los datos.
(Los valores son de la calibración real: R10 de la bitácora cuenta cómo se agregó `htw_gearbox_lot` porque la flota
salía "demasiado sana".)

**Componentes y alarmas** (`COMPONENTS`, `ALARM_CODES`): qué se rompe, con cuántos días de aviso visibles en las
temperaturas (lo que el modelo predictivo puede detectar) y cuánto cuesta. Cada fabricante tiene sus códigos de alarma.

**Personas, cuadrillas y contratos** (`PEOPLE`, `CREWS`, `CONTRACTS`): todo inventado. En los contratos,
`share_of_sources` es qué fracción de la generación esperada de sus parques se comprometió (50-75 % en un PPA real;
L7 de la bitácora cuenta que con valores bajos los contratos "siempre cumplían" y el caso no tenía gracia).
`CONTRACT_TERMINATION` hace que un contrato se rescinda en 2026 (un DELETE en el CDC).

**Calendario y macro:** `HOLIDAYS_AR` (feriados 2023-2026: baja la demanda y sube el curtailment),
`INFLATION_MONTHLY_PCT` y `FX_END_OF_MONTH` (inspirados en la Argentina real y redondeados).

### 3. `physics.py`: la física, dos veces

**Por qué dos veces:** cada fórmula existe como expresión de Spark (`*_col`), para generar millones de filas en
paralelo, y como función de Python (`*_py`), para cálculos chicos en el driver (el presupuesto, los tests). Un test
(capítulo 07) verifica que las dos den **exactamente** lo mismo.

**El viento como función continua del tiempo:**
```python
ART_OFFSET_S = 3 * 3600   # Argentina: UTC-3 todo el año (sin horario de verano desde 2009)
SYNOPTIC = ((4.3, 0.22, "region"), (9.7, 0.14, "region"), (1.7, 0.08, "park"))

def wind_ms_py(park_code, epoch_s, day_mult=1.0, wake=1.0, turb_u=0.5) -> float:
    park = PARKS_BY_CODE[park_code]
    local = datetime.fromtimestamp(epoch_s - ART_OFFSET_S, tz=timezone.utc)
    hour_local = local.hour + local.minute / 60
    syn = 1.0 + sum(a * math.sin(TWO_PI * epoch_s / (86_400 * p) + ph)
                    for (p, a, _), ph in zip(SYNOPTIC, phases(park_code), strict=True))
    diurnal = 1.0 + 0.07 * math.sin(TWO_PI * (hour_local - 9) / 24)
    w = (park.wind_mean_ms * WIND_SEASONAL[local.month - 1] * syn * diurnal * day_mult * wake
         * (1 + 0.12 * (turb_u - 0.5)))
    return max(0.0, w)
```
El viento es el producto de:

| factor | qué representa |
|---|---|
| `wind_mean_ms` | el viento medio del parque (Cañadón León 11,2 m/s) |
| `WIND_SEASONAL[mes]` | la estación |
| `syn` | **los frentes**: tres ondas senoidales de 4,3, 9,7 y 1,7 días. Las dos primeras tienen fase **regional** (todos los parques de la Patagonia ven el mismo frente) y la tercera, del parque |
| `diurnal` | el ciclo diario (±7 %) |
| `day_mult` | la anomalía de ese día (un proceso aleatorio que se calcula en el capítulo 07) |
| `wake` | el efecto estela: una turbina detrás de otra recibe menos viento |
| `turb_u` | la turbulencia, un número al azar por turbina e instante |

**Por qué una función del tiempo y no una simulación paso a paso:** una simulación (el viento de las 10:10 depende del
de las 10:00) obliga a calcular en orden, en una sola máquina. Una función de `epoch` se calcula **para cualquier
instante, en cualquier orden y en paralelo**, y aun así tiene autocorrelación realista (los frentes duran días).

`_phase` usa `crc32` (estable) para que las fases sean siempre las mismas. `wind_ms_col` es la misma fórmula con
`F.sin`, `F.element_at`... `wind_by_park_col` arma un `CASE WHEN parque = 'LEO' THEN ... WHEN ...` para un DataFrame
con todos los parques.

**La curva de potencia:**
```python
def power_kw_py(wind, rated_kw, rated_ms) -> float:
    if wind < CUT_IN_MS or wind >= CUT_OUT_MS:
        return 0.0
    frac = (wind ** 3 - CUT_IN_MS ** 3) / (rated_ms ** 3 - CUT_IN_MS ** 3)
    return rated_kw * min(1.0, max(0.0, frac))
```
Cúbica entre *cut-in* y la velocidad nominal, plana después, cero fuera de rango. La potencia del viento crece con el
cubo de la velocidad: duplicar el viento multiplica por ocho la energía disponible.

**La temperatura:** media de la región, menos 6,5 °C cada 1.000 m de altura, menos un poco por latitud en la
Patagonia, más una onda anual (con el mínimo en invierno) y una diaria. Es lo que produce hielo en Cerro Arenales
(610 m) y heladas en la Puna.

**El sol** (`_cos_zenith_py`, `poa_clear_py`, `poa_clear_col`): la altura del sol según la latitud, el día del año
(declinación) y la hora solar; con eso, la irradiancia de cielo despejado sobre el panel, un poco mayor en altura
(menos atmósfera). Debajo de 0,05 (sol muy bajo) se toma 0.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| azar por hash de los datos | `F.rand(seed)` | depende del particionado: cambia entre local y Databricks |
| expresiones de Spark | UDFs de Python | 10-50 veces más lentas a escala 1 (cientos de millones de filas) |
| viento como función continua | simular paso a paso | no se paraleliza |
| la historia escrita como datos (`STORY`) | dejarla "emerger" del azar | no habría garantía de que las preguntas de Genie tengan respuesta |
| números macro "inspirados" y redondeados | datos oficiales exactos | es una empresa ficticia; no se quiere que alguien use estos números como fuente |

## ✅ Probalo

Todavía no hay tests (llegan en la etapa 3, cuando existan los eventos). Probalo a mano:
```bash
python - <<'EOF'
from datetime import datetime, timezone
from andes_viento.datagen import physics as ph
t = datetime(2025, 7, 15, 15, 0, tzinfo=timezone.utc).timestamp()
print(round(ph.wind_ms_py("LEO", t), 2), "m/s en Cañadón León")
print(ph.power_kw_py(2.0, 4500, 12.5), ph.power_kw_py(8.0, 4500, 12.5), ph.power_kw_py(14.0, 4500, 12.5))
print(round(ph.temp_c_py("SUS", datetime(2025, 7, 15, 9, 0, tzinfo=timezone.utc).timestamp()), 1), "°C en Susques a las 6")
print(round(ph.poa_clear_py("SUS", datetime(2025, 7, 15, 16, 0, tzinfo=timezone.utc).timestamp())), "W/m² al mediodía")
EOF
```
Tiene que dar: un viento razonable (5-20 m/s), `0.0`, algo entre 0 y 4500, y `4500.0`; una temperatura **bajo cero**
en Susques a las 6 de la mañana de julio; y una irradiancia alta (> 800) al mediodía solar.

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `KeyError: 'LEO'` | falta el parque o el código está mal | revisá `PARKS` y `PARKS_BY_CODE` |
| el viento cambia cada vez que corrés | usaste `hash()` o `random` sin semilla | `zlib.crc32` y `prng` |
| la temperatura de la Puna sale 25 °C | falta la corrección por altura | `- 0.0065 * altitude_m` |
| irradiancia de noche distinta de 0 | falta el corte `cz <= 0.05` | revisá `poa_clear_*` |
| `ruff B905` | `zip()` sin `strict` | `zip(..., strict=True)`: falla si las listas tienen distinto largo |

## 📍 Punto de control

```bash
git commit -am "etapa-02: la empresa en código y la física" && git diff etapa-02 HEAD --stat
```

## 🏋️ Ejercicio

1. Agregá un parque eólico nuevo en Río Negro (`VMA`, "Valle Medio", 30 turbinas AWS, viento medio 8,5) y verificá
   con el script de arriba que tiene viento. ¿Qué otros archivos habría que tocar para que aparezca en todo el
   proyecto? (pista: ninguno de esta etapa; buscá `PARKS` con `grep -rn PARKS src`).
2. Graficá con matplotlib el viento de LEO cada 10 minutos durante 30 días de julio 2025 usando `wind_ms_py`. ¿Se
   ven los frentes de 4 y 10 días?
3. Cambiá `CUT_OUT_MS` a 20 y pensá: ¿qué parques pierden más energía? ¿Por qué?
