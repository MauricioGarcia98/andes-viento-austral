# 01 · La empresa: Andes Viento Austral S.A.

> Empresa **ficticia**, pero construida con los problemas de una generadora renovable real en la Argentina.
> Los números macro (inflación, dólar) están inspirados en 2023-2026 y redondeados: no son datos oficiales.

## Historia en 8 hitos

| año | hito | qué dejó en los datos |
|---|---|---|
| 2009 | Un grupo de ingenieros petroleros de **Comodoro Rivadavia** funda la empresa para aprovechar "el otro recurso de la Patagonia": el viento. | La base de mantenimiento sigue en Comodoro: todos los tiempos de viaje salen de ahí. |
| 2012 | Primer parque: **Rawson Sur** (45 aerogeneradores daneses de Aurora Wind Systems). | El SCADA danés manda fechas ISO con offset `-03:00`. |
| 2016-2019 | Programa **RenovAr**: Puerto Madryn Norte, Garayalde, Cerro Arenales, Pampa del Castillo y Bahía Deseado. Entra un fabricante nacional (**Pampa Eólica Industrial**) y uno alemán (**Hanse Turbinen Werke**). | Tres SCADA distintos: tres formatos de fecha y la potencia de PEI en **MW**. |
| 2018 | Se habilita el **MATER**: primeros contratos PPA con industrias (Aluminios Patagónicos, Cementera del Plata). | Nace el problema de "cumplir el volumen comprometido". |
| 2019-2020 | Crisis: cepo, pesificación de contratos viejos, pandemia. Se frenan inversiones. | El CMMS viejo exporta `dd/MM/yyyy HH:mm` hasta que lo migran en 2024. |
| 2021 | Diversificación al **sol**: compra 4 parques en la Puna jujeña y Catamarca (1,2 millones de paneles). | Polvo, agua escasa y parques a 3.700 m; datos por satélite (VSAT). |
| 2023 | **Cañadón León** entra en servicio... justo cuando la línea de 500 kV que saca la energía de la Patagonia se satura. Devaluación del 13 de diciembre (el dólar oficial pasa de ~366 a ~800). | El **curtailment** crece año a año; los costos en pesos explotan. |
| 2025 | Repotenciación: Hanse actualiza el firmware a **HT-OS 5.0** y agrega 3 sensores (detector de hielo, partículas en aceite, acelerómetro de torre). Julio 2025: ola polar, mantenimiento de la ET Santa Cruz Norte y una multiplicadora rota en Cañadón León. | *Schema drift* en el JSON del SCADA. El famoso "**¿por qué Cañadón León generó 15 % menos en julio?**" (−15,4 % medido a SF 0,1). |

## La flota (a scale_factor = 1)

| parque | código | provincia | tecnología | equipos | fabricante | enlace | km a la base |
|---|---|---|---|---|---|---|---|
| Rawson Sur | RAW | Chubut | eólico | 45 × 3,6 MW | Aurora Wind Systems | fibra | 380 |
| Puerto Madryn Norte | MAD | Chubut | eólico | 40 × 3,6 MW | Aurora Wind Systems | fibra | 440 |
| Garayalde | GAR | Chubut | eólico | 35 × 3,0 MW | Pampa Eólica Industrial | VSAT | 160 |
| Cerro Arenales | CRV | Chubut | eólico | 50 × 3,6 MW | Aurora Wind Systems | fibra | 25 |
| Pampa del Castillo | PAM | Chubut | eólico | 45 × 3,0 MW | Pampa Eólica Industrial | fibra | 60 |
| Bahía Deseado | DES | Santa Cruz | eólico | 38 × 4,5 MW | Hanse Turbinen Werke | VSAT | 290 |
| Pico Truncado Alto | PIC | Santa Cruz | eólico | 42 × 4,5 MW | Hanse Turbinen Werke | fibra | 130 |
| San Julián Meseta | SJU | Santa Cruz | eólico | 40 × 4,5 MW | Hanse Turbinen Werke | VSAT | 350 |
| Cañadón León | LEO | Santa Cruz | eólico | 45 × 4,5 MW | Hanse Turbinen Werke | VSAT | 520 |
| Susques Solar | SUS | Jujuy | solar | 400 mil paneles, 73 inversores | — | VSAT | 180 |
| Abra Pampa Solar | ABR | Jujuy | solar | 300 mil paneles, 55 inversores | — | VSAT | 220 |
| Tinogasta Sol | TIN | Catamarca | solar | 250 mil paneles, 46 inversores | — | fibra | 480 |
| Fiambalá Solar | FIA | Catamarca | solar | 250 mil paneles, 46 inversores | — | VSAT | 520 |

**Total:** 380 aerogeneradores (~1,5 GW) y 1,2 millones de paneles (~660 MWp). Con `scale_factor = 0.1` la flota es de 37 turbinas y 23 inversores: la historia es la misma, los volúmenes, 10 veces menores.

## Personas (todas ficticias)

| persona | cargo | área | qué le pregunta a Genie |
|---|---|---|---|
| Lucía Ferreyra | Directora General (CEO) | Dirección | "¿Por qué este trimestre generamos menos que el presupuesto?" |
| Martín Quiroga | Gerente de Operaciones | Operación de parques | "¿Qué parque perdió más energía la semana pasada y por qué?" |
| Valeria Ñancucheo, Micaela Quilaqueo y otros 11 | Jefes/as de parque | Operación de parques | "¿Cuánto generé ayer contra lo esperado?" |
| Ramiro Llancaqueo | Jefe de Mantenimiento | Mantenimiento | "¿Qué turbinas se van a romper en las próximas semanas?" |
| Joaquín Ortiz | Ingeniero de Confiabilidad | Mantenimiento | "¿Con cuántos días de anticipación detectamos las fallas?" |
| Sofía Bertolini | Gerente Comercial | Comercial PPA | "¿Llegamos al volumen del data center este mes?" |
| Paula Giménez | Analista Comercial | Comercial PPA | "¿Cómo cambió el precio de cada contrato con las adendas?" |
| Diego Achával | Director de Finanzas (CFO) | Finanzas | "¿En qué parque conviene poner baterías?" |
| Camila Iturbe | Analista de Riesgo de Mercado | Finanzas | "¿Cuánto vale la energía que nos recorta CAMMESA?" |
| Andrea Colque | Responsable de Medioambiente (HSE) | HSE | "¿Cuánta agua usamos para limpiar paneles en la Puna?" |
| Florencia Paz | Head of Data & Analytics | Datos | (construye todo esto con Genie Code) |

## Áreas y sus Genie Agents

```
Dominio OPERACIÓN                         Dominio COMERCIAL
├── Agent "Operación de parques"          ├── Agent "Comercial PPA"
│   jefes de parque, Gerencia Operaciones │   Gerencia Comercial
└── Agent "Mantenimiento predictivo"      └── Agent "Finanzas y mercado"
    Mantenimiento, Confiabilidad              CFO, Riesgo, Dirección

Dirección usa Genie One / Agent mode para las preguntas de "por qué".
```

## Clientes PPA (MATER)

| contrato | cliente | sector | desde | precio USD/MWh | parques de origen |
|---|---|---|---|---|---|
| PPA-2018-001 | Aluminios Patagónicos S.A. | Aluminio | 2018 | 58,0 | Rawson Sur, Puerto Madryn Norte |
| PPA-2019-002 | Cementera del Plata S.A. | Cemento | 2019 | 61,5 | Cerro Arenales, Pampa del Castillo |
| PPA-2020-003 | Automotriz Zárate S.A. | Automotriz | 2020 | 63,0 | Garayalde, Cerro Arenales |
| PPA-2021-004 | Litio de la Puna S.A. | Minería | 2021 | 66,0 | Susques, Abra Pampa |
| PPA-2021-005 | Supermercados La Estrella S.A. | Retail | 2021 | 68,0 | Bahía Deseado, Tinogasta |
| PPA-2022-006 | Frigorífico Pampeano S.A. | Alimentos | 2022 | 64,5 | Pico Truncado, Bahía Deseado (rescinde en 2026) |
| PPA-2023-007 | Data Center Austral S.R.L. | Tecnología | 2023 | 71,0 | San Julián Meseta, Cañadón León (adenda +20 % en 2024) |
| PPA-2025-008 | Papelera Mesopotámica S.A. | Papel | 2025 | 62,0 | Fiambalá, Pico Truncado |

Los precios se indexan +2 % cada enero (adendas que generan versiones SCD2 en `dim_contract`).
