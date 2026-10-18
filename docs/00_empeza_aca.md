# 00 · Empezá acá

¡Bienvenido/a! Este repo simula **Andes Viento Austral**, una generadora de energía renovable argentina (9 parques
eólicos en la Patagonia, 4 solares en la Puna y Catamarca), y construye en **Databricks** todo lo necesario para que
las áreas de la empresa le pregunten a **Genie** (el asistente de Databricks que responde en lenguaje natural sobre
los datos) y obtengan respuestas confiables.

Es un proyecto **para aprender**, pero hecho como se haría en una empresa: con pruebas, control de calidad,
seguridad, despliegue automático y documentación de cada error real que apareció.

## Lo mínimo que hay que saber antes de empezar

| palabra | en una línea |
|---|---|
| **Databricks** | una plataforma en la nube para guardar, procesar y analizar datos. Hay una versión gratis (*Free Edition*). |
| **Workspace** | tu espacio en Databricks: la página web donde están tus archivos, datos y procesos. |
| **Unity Catalog** | donde se guardan y gobiernan las tablas: `catálogo.esquema.tabla`. |
| **Job** | un proceso automático con pasos (tareas). El de este proyecto tiene 12. |
| **Bundle** | el archivo `databricks.yml`: describe como código todo lo que el proyecto crea en el workspace. |
| **Medallion** | las capas de datos: **bronze** (crudo) → **silver** (limpio) → **gold** (listo para el negocio). |
| **Genie Agent** | un "experto" al que le preguntás en castellano y responde con los datos de su área. |

Todo lo demás: [15 · Glosario](15_glosario.md).

## ¿Qué querés hacer?

| si querés... | leé / hacé (en este orden) |
|---|---|
| **entender de qué se trata** (sin código) | [01 · La empresa](01_la_empresa.md) → [03 · Casos de negocio](03_casos_de_negocio.md) → [12 · Genie](12_genie.md) |
| **tenerlo funcionando en tu Databricks, sin terminal** | [11 · Guía desde la web](11_guia_desde_la_web.md) |
| **tenerlo funcionando, con terminal** (incluye tests locales y CI/CD) | [10 · Replicar desde cero](10_despliegue_y_cicd.md) |
| **saber cómo se construyó, paso a paso** | [17 · Cómo se construyó](17_como_se_construyo.md) |
| **saber cómo se probó** | [18 · Pruebas](18_pruebas.md) |
| **mantenerlo andando** (datos diarios, fallas, cuota de tablas) | [19 · Operación diaria](19_operacion_diaria.md) |
| **entender la arquitectura** | [05 · Arquitectura](05_arquitectura.md) (con las decisiones, ADRs) → [diagramas](diagrams/README.md) |
| **entender los datos** | [06 · Fuentes y suciedad](06_fuentes_y_suciedad.md) → [07 · Modelado](07_modelado_dimensional.md) → [04 · Diccionario](04_diccionario_de_datos.md) |
| **aprender SQL, Spark y Delta con estos datos** | [learning/](../learning/README.md) (21 módulos con ejercicios y soluciones) |
| **usar Genie como lo usaría la empresa** | [12 · Genie](12_genie.md) → [preguntas de Agent mode](genie/agent_mode.md) |
| **ver qué salió mal y cómo se arregló** | [08 · Bitácora](08_bitacora.md) (24 errores reales) |
| **ponerte a prueba** | [16 · Autoevaluación](16_autoevaluacion.md) → [desafíos finales](../learning/20_desafios_finales.md) |

## El recorrido de un dato, en 6 pasos

1. **Las fuentes** ([06](06_fuentes_y_suciedad.md)): 11 sistemas (el SCADA de las turbinas, los inversores solares,
   el sistema de mantenimiento, CAMMESA, los contratos...) mandan archivos con los problemas de la vida real: relojes
   corridos, satélite que se corta, MW en vez de kW, turbinas renombradas, columnas nuevas.
2. **Bronze:** Auto Loader toma cada archivo nuevo tal cual llegó, sin perder nada.
3. **Silver:** se limpia, se corrigen relojes y unidades, se guarda la historia de los cambios (SCD2) y lo que está
   mal va a cuarentena.
4. **Gold** ([07](07_modelado_dimensional.md)): un modelo estrella donde cada 10 minutos de cada turbina sabe cuánto
   generó, cuánto **pudo** generar y **por qué no** (red, falla, mantenimiento, hielo).
5. **Semántica:** métricas oficiales (metric views) y respuestas certificadas (funciones), con descripciones en
   castellano que Genie lee.
6. **Genie** ([12](12_genie.md)): 4 agents, uno por área, medidos con 86 preguntas de prueba (85 correctas).

![Proceso completo](animations/proceso_completo.svg)

## Los roles

Una persona hace de Product Owner, Data Engineer, Analytics Engineer, Platform, Data Steward, Analista BI, Data
Scientist y SRE. Qué decide cada uno y por qué: [02 · Roles y decisiones](02_roles_y_decisiones.md).

## Todos los documentos

| # | documento | para qué |
|---|---|---|
| 00 | Empezá acá | este índice |
| 01 | [La empresa](01_la_empresa.md) | historia, parques, personas, clientes |
| 02 | [Roles y decisiones](02_roles_y_decisiones.md) | quién decide qué |
| 03 | [Casos de negocio](03_casos_de_negocio.md) | los 5 problemas que resuelve, con KPI y preguntas para Genie |
| 04 | [Diccionario de datos](04_diccionario_de_datos.md) | cada tabla y columna de gold (generado) |
| 05 | [Arquitectura](05_arquitectura.md) | capas, decisiones (ADRs), imperativo vs. declarativo |
| 06 | [Fuentes y suciedad](06_fuentes_y_suciedad.md) | las 11 fuentes y sus problemas |
| 07 | [Modelado dimensional](07_modelado_dimensional.md) | el modelo estrella |
| 08 | [Bitácora](08_bitacora.md) | cada error real, cómo se encontró y cómo se arregló |
| 09 | [Performance y escala](09_performance_y_escala.md) | volúmenes, tiempos y cómo escalar |
| 10 | [Replicar desde cero (terminal)](10_despliegue_y_cicd.md) | instalación, despliegue, CI/CD |
| 11 | [Guía desde la web](11_guia_desde_la_web.md) | lo mismo, sin terminal |
| 12 | [Genie](12_genie.md) | cómo están armados los agents y cómo mejorarlos |
| 13 | [Cómo hacerlo más real](13_hacerlo_mas_real.md) | lo que falta para un negocio de verdad |
| 14 | [FAQ](14_faq.md) | preguntas frecuentes |
| 15 | [Glosario](15_glosario.md) | términos de la plataforma y del negocio |
| 16 | [Autoevaluación](16_autoevaluacion.md) | preguntas para ponerte a prueba |
| 17 | [Cómo se construyó](17_como_se_construyo.md) | la cronología, etapa por etapa |
| 18 | [Pruebas](18_pruebas.md) | las 7 capas de pruebas y sus resultados reales |
| 19 | [Operación diaria](19_operacion_diaria.md) | datos diarios, fallas, cambios, cuota de tablas |
