# 15 · Glosario

Dos tablas: primero los **conceptos de la plataforma** (Databricks, datos, herramientas) y después los **términos del
negocio** (energía, mercado eléctrico argentino).

## Conceptos de la plataforma

| término | qué es | dónde aparece en el proyecto |
|---|---|---|
| **Databricks** | Plataforma en la nube para guardar, procesar y analizar datos con Spark y SQL. | todo |
| **Free Edition** | La versión gratuita de Databricks, con cuotas (cómputo diario, 5 corridas a la vez, 500 tablas, 1 App). | [10](10_despliegue_y_cicd.md#paso-1--crear-la-cuenta-de-databricks-free-edition) |
| **Workspace** | Tu espacio de trabajo en Databricks: la página web con tus carpetas, datos y procesos. Tiene una URL propia (el *host*). | |
| **Unity Catalog (UC)** | El sistema que guarda y gobierna las tablas, vistas, funciones y volúmenes, con permisos. | `catálogo.esquema.tabla` |
| **Catálogo / esquema / tabla** | Los tres niveles de UC. Ejemplo: `andes_viento_dev` (catálogo) `.gold` (esquema) `.dim_park` (tabla). | |
| **Metastore** | El "registro" de Unity Catalog de toda tu cuenta. La cuota de 500 tablas es por metastore. | [19](19_operacion_diaria.md#la-cuota-de-500-tablas) |
| **Volumen** | Una carpeta de archivos dentro de UC. Acá caen los archivos crudos (`landing`). | `/Volumes/<catálogo>/landing/raw` |
| **Serverless** | Cómputo que Databricks prende y apaga solo: no creás servidores (*clusters*). | todo el proyecto |
| **SQL warehouse** | El motor que ejecuta consultas SQL, dashboards y Genie. En Free Edition: *Serverless Starter Warehouse*. | |
| **Notebook** | Un documento con celdas de código (Python o SQL) que se ejecutan una por una. | `notebooks/` |
| **Job** | Un proceso automático formado por tareas que dependen unas de otras. | `resources/*.job.yml` |
| **Tarea (task)** | Un paso de un job: un notebook, una condición, un *for each*... | 12 en el job principal |
| **for each** | Una tarea que repite lo mismo para una lista de valores, en paralelo. | `generate_data` (11 fuentes) |
| **condition task** | Una tarea que decide qué rama del job sigue (sí / no). | `should_generate` |
| **Run / corrida** | Una ejecución de un job. Tiene un *run_id*. | |
| **Repair run** | Volver a correr sólo las tareas que fallaron (y las que dependen de ellas). | [19](19_operacion_diaria.md#cuando-algo-falla) |
| **Lakeflow Declarative Pipelines (LDP)** | Otra forma de escribir pipelines: declarás las tablas y el motor resuelve el orden. | `pipelines/*.sql` |
| **Expectation** | Una regla de calidad en un pipeline declarativo (`CONSTRAINT ... EXPECT`). | `pipelines/02_silver.sql` |
| **Asset Bundle (DAB)** | Infraestructura como código: `databricks.yml` describe jobs, pipelines, dashboards y Apps. | `databricks.yml`, `resources/` |
| **Target** | Una variante del despliegue del bundle: `dev` (desarrollo) o `prod` (producción). | `databricks.yml` |
| **Deploy / desplegar** | Subir el código y crear o actualizar los recursos del bundle en el workspace. | `databricks bundle deploy` |
| **Databricks CLI** | El programa de terminal para hablar con Databricks (`databricks ...`). | [10](10_despliegue_y_cicd.md#paso-2--instalar-las-herramientas-en-tu-computadora) |
| **SDK** | La librería de Python para hablar con Databricks desde un script (`databricks-sdk`). | `scripts/` |
| **Git folder** | Una carpeta del workspace conectada a un repositorio de GitHub. | [11](11_guia_desde_la_web.md#3-traer-el-código-git-folder) |
| **CI/CD** | Integración y despliegue continuos: GitHub corre los tests (y si querés, despliega) en cada cambio. | `.github/workflows/ci.yml` |
| **Token (PAT)** | Una contraseña larga para que un programa (por ejemplo GitHub Actions) entre a tu workspace. Nunca va en el repo. | |
| **Delta Lake** | El formato de las tablas: archivos Parquet + un registro de cambios que permite MERGE, historia y *time travel*. | todas las tablas |
| **Spark / PySpark** | El motor que procesa datos en paralelo; PySpark es su versión para Python. | `src/` |
| **Dashboard (AI/BI)** | Un tablero con gráficos sobre consultas SQL. | `dashboards/` |
| **Databricks App** | Una aplicación web propia que corre dentro de Databricks. | `apps/genie_chat/` |
| **Genie** | El asistente que responde preguntas en lenguaje natural generando SQL sobre tus datos. | [12](12_genie.md) |
| **Conversation API** | La API para hacerle preguntas a un Genie Agent desde un programa. | `scripts/genie_ask.py` |
| **Benchmark (de Genie)** | Una pregunta de prueba con su respuesta correcta escrita como SQL. | `genie/src/*.yml` |
| **`serialized_space`** | La configuración completa de un Genie Agent en JSON (tablas, instrucciones, ejemplos, benchmarks). | `genie/agents/*.json` |
| **Retención (de borrados)** | Lo que se borra en UC se puede recuperar ~7 días con `UNDROP`; mientras tanto sigue contando en la cuota. | [19](19_operacion_diaria.md#la-cuota-de-500-tablas) |
| **Test unitario / de integración** | Prueba de una pieza chica / prueba del pipeline entero. | [18](18_pruebas.md) |
| **Quality gate** | La última tarea del job: 10 controles que, si fallan, frenan la publicación. | `quality/gate.py` |
| **Cuarentena** | Donde van las filas que no pasan una regla de calidad, con el motivo. | `ops.quarantine` |

## Términos de datos y del negocio

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
