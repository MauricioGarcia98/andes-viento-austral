# 15 · Glosario

| término | qué es |
|---|---|
| **Aerogenerador / WTG** | Wind Turbine Generator: la turbina eólica. |
| **Multiplicadora (gearbox)** | Caja que multiplica las ~12 rpm del rotor a ~1.500 rpm del generador. Su falla es la más cara. |
| **Curva de potencia** | Potencia que da una turbina según el viento: 0 debajo de 3 m/s, nominal desde ~12 m/s, corte en 25 m/s. |
| **Factor de capacidad** | Energía generada / (potencia instalada × horas). En la Patagonia, ~50 %. |
| **SCADA** | Sistema de supervisión y control: manda las mediciones de cada turbina cada 10 minutos. |
| **CMMS** | Sistema de gestión de mantenimiento: activos, órdenes, repuestos, cuadrillas. |
| **CAMMESA** | Compañía Administradora del Mercado Mayorista Eléctrico: despacha y fija precios en la Argentina. |
| **Curtailment** | Orden de bajar potencia por falta de capacidad de transporte (o por estabilidad de la red). Energía que se tira. |
| **Precio spot** | Precio horario del mercado mayorista por nodo. |
| **Nodo desacoplado** | Cuando la línea está saturada, el precio del nodo exportador cae: sobra energía y no hay cómo sacarla. |
| **MATER** | Mercado a Término de Energías Renovables: contratos privados entre generadores y grandes usuarios. |
| **PPA** | Power Purchase Agreement: contrato de compra de energía a largo plazo (precio, volumen, penalidades). |
| **Take-or-pay / penalidad** | Pago por la energía comprometida que no se entregó. |
| **BESS** | Battery Energy Storage System: sistema de baterías. |
| **Disponibilidad contractual** | % del tiempo que la turbina estuvo disponible según la definición de la garantía (con exclusiones). |
| **Liquidated damages (LD)** | Compensación que paga el fabricante si la disponibilidad queda debajo de lo garantizado. |
| **P50 / P90** | Producción esperada con 50 % / 90 % de probabilidad de superarla. El presupuesto usa P50. |
| **Soiling** | Suciedad en los paneles que reduce la generación. |
| **POA** | Plane of Array: irradiancia en el plano de los paneles (W/m²). |
| **PR (performance ratio)** | Energía real / energía esperada por la irradiancia. |
| **VSAT** | Enlace satelital: barato en lugares remotos, con cortes. |
| **ET** | Estación transformadora. |
| **Medallion** | Capas bronze (crudo) → silver (limpio) → gold (negocio). |
| **Auto Loader** | Ingesta incremental de archivos de Databricks (`cloudFiles`). |
| **Schema drift** | Cambio de esquema en la fuente (columnas nuevas). |
| **SCD2** | Slowly Changing Dimension tipo 2: guardar la historia de una dimensión con versiones. |
| **Point-in-time join** | Unir un hecho con la versión de la dimensión vigente en ese momento. |
| **Watermark** | Marca de "hasta dónde procesé" para cargas incrementales. |
| **Liquid clustering** | Organización física de Delta por columnas, sin particiones fijas. |
| **Metric view** | Vista de UC con métricas definidas en YAML; se consultan con `MEASURE()`. |
| **Trusted asset** | Función o consulta certificada que Genie usa y marca como confiable. |
| **Genie Agent** | Experto conversacional sobre un conjunto de datos (ex Genie space). |
| **Agent mode** | Modo de Genie que planifica varios pasos para preguntas abiertas. |
| **Genie Code** | El asistente para construir (ex Databricks Assistant). |
| **Asset Bundle (DAB)** | Infraestructura como código de Databricks (`databricks.yml`). |
