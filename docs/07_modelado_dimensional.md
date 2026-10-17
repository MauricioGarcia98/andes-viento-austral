# 07 · Modelado dimensional (Kimball)

## Modelo estrella

```
                         dim_date ─────────────┐
                            │                  │
   dim_weather ──── fact_turbine_10min ──── dim_turbine (SCD2)
        │              │        │
        │              │        └── dim_park ─── fact_curtailment_hourly
        │              │                │        fact_availability_daily
        └──── fact_inverter_hourly ── dim_inverter
                                        │
   dim_crew ──── fact_maintenance_order ┘
   dim_contract (SCD2) ──── fact_ppa_settlement
```

Diagrama: [modelo estrella](diagrams/04_modelo_estrella.svg).

## Matriz bus (procesos × dimensiones conformadas)

| proceso de negocio (hecho) | grano | date | park | turbine | inverter | weather | contract | crew |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Medición de turbinas (`fact_turbine_10min`) | turbina × 10 min | ● | ● | ● | | ● | | |
| Generación solar (`fact_inverter_hourly`) | inversor × hora | ● | ● | | ● | ● | | |
| Curtailment (`fact_curtailment_hourly`) | parque × hora | ● | ● | | | | | |
| Disponibilidad (`fact_availability_daily`) | turbina × día | ● | ● | ● | | | | |
| Mantenimiento (`fact_maintenance_order`) | orden | ● | ● | ● | ● | | | ● |
| Liquidación PPA (`fact_ppa_settlement`) | contrato × mes | ● | ○ | | | | ● | |

● clave directa · ○ a través de `source_parks`. Diagrama: [matriz bus](diagrams/05_matriz_bus.svg).

## Tipos de hecho

| tipo | ejemplo | característica |
|---|---|---|
| Transaccional / medición | `fact_turbine_10min` | una fila por evento; aditivo en energía y pérdidas |
| Agregado | `fact_inverter_hourly`, `fact_curtailment_hourly` | se pre-agrega porque nadie mira un inversor cada 5 min |
| Periodic snapshot | `fact_availability_daily`, `fact_ppa_settlement` | una foto por período; ratios semi-aditivos (¡no se promedian promedios!) |
| Accumulating snapshot | `fact_maintenance_order` | una fila por orden que se ACTUALIZA en cada hito (creada → en curso → cerrada) |

## SCD Tipo 2: `dim_turbine`

Cada cambio de componente, firmware o nombre crea una versión. Ejemplo real de los datos:

| turbine_key | turbine_id | turbine_tag | gearbox_serial | firmware | change_reason | effective_from | effective_to |
|---|---|---|---|---|---|---|---|
| 1001… | WTG00033 | LEO-01 | GBX412233 | HT-OS 4.1 | ALTA | 2023-02-14 | 2025-03-01 |
| 1002… | WTG00033 | LEO-01 | GBX412233 | HT-OS 5.0 | ACTUALIZACION_FIRMWARE | 2025-03-01 | 2025-08-16 |
| 1003… | WTG00033 | LEO-01 | GBX887120 | HT-OS 5.0 | CAMBIO_MULTIPLICADORA | 2025-08-16 | 9999-12-31 |

Los hechos se unen **point-in-time** (`ts_utc` entre `effective_from` y `effective_to`): una medición de julio 2025
queda asociada a la multiplicadora vieja, la que se rompió. Así el Data Scientist puede comparar "antes y después"
del cambio de componente sin mezclar historias. Diagrama: [SCD2](diagrams/06_scd2.svg).

Casos finos que resuelve `silver/scd2.py`:
1. varios cambios del mismo activo en un mismo lote (carga histórica),
2. re-envíos idénticos (no crean versión),
3. llegadas tardías (un cambio más viejo que la versión vigente se ignora),
4. bajas (op = D → versión con `is_deleted`),
5. idempotencia (re-ejecutar no duplica).

## Por qué `v_park_daily` (una tabla ancha) además de la estrella

Genie y los analistas preguntan casi siempre "por parque y por día". Una vista ancha con todo (generación,
potencial, pérdidas por causa, presupuesto diario, disponibilidad, clima, factor de capacidad) y bien comentada
hace que Genie no tenga que adivinar 5 joins. La estrella sigue siendo la fuente de verdad; la vista es una
**interfaz**.

## Decisiones de modelado que conviene discutir

- `park_code` está en los hechos además de `park_key` (desnormalización deliberada): lo usa el **row filter**
  por parque y el liquid clustering.
- Las pérdidas se guardan en kWh por slot y se agregan; los **ratios** (disponibilidad, factor de capacidad,
  cumplimiento) se calculan siempre como cociente de sumas, nunca como promedio de ratios.
- El presupuesto usa la versión **v1** (aprobada por el directorio); el re-presupuesto de julio 2025 queda en
  `reforecast_p50_mwh` para comparar.
