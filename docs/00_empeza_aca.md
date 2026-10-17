# 00 · Empezá acá

¡Bienvenido/a! Este repo simula **Andes Viento Austral**, una generadora renovable argentina (9 parques eólicos en la
Patagonia, 4 solares en la Puna y Catamarca), y construye en Databricks todo lo necesario para que sus áreas le pregunten
a **Genie** y obtengan respuestas confiables.

## ¿Qué querés hacer?

| si querés... | leé / hacé |
|---|---|
| entender el negocio | [01 · La empresa](01_la_empresa.md) → [03 · Casos de negocio](03_casos_de_negocio.md) |
| ver cómo está armado | [05 · Arquitectura](05_arquitectura.md) (con ADRs) → [diagramas](diagrams/README.md) |
| desplegarlo en tu workspace | [10 · Despliegue](10_despliegue_y_cicd.md) o, sin terminal, [11 · Guía desde la web](11_guia_desde_la_web.md) |
| aprender SQL/Spark/Delta con estos datos | [learning/](../learning/README.md) (21 módulos con ejercicios y soluciones) |
| usar Genie como lo usaría la empresa | [12 · Genie](12_genie.md) → [Agent mode](genie/agent_mode.md) |
| ver qué salió mal (y cómo se arregló) | [08 · Bitácora](08_bitacora.md) |
| ponerte a prueba | [16 · Autoevaluación](16_autoevaluacion.md) → [desafíos finales](../learning/20_desafios_finales.md) |

## El recorrido en 5 minutos

1. **Las fuentes** ([06](06_fuentes_y_suciedad.md)): 11 sistemas mandan archivos con los problemas de la vida real
   (relojes corridos, satélite que se corta, MW vs. kW, turbinas renombradas, columnas nuevas).
2. **Bronze**: Auto Loader los toma tal cual, sin perder nada.
3. **Silver**: se limpian, se corrigen relojes y unidades, se historizan los cambios (SCD2) y lo malo va a cuarentena.
4. **Gold** ([07](07_modelado_dimensional.md)): un modelo estrella donde cada 10 minutos de cada turbina sabe cuánto
   generó, cuánto pudo generar y **por qué no** (red, falla, mantenimiento, hielo).
5. **Semántica + Genie** ([12](12_genie.md)): métricas oficiales, funciones certificadas y 4 agents con 86 benchmarks.

## Los roles

Una persona (vos + Genie Code) hace de Product Owner, Data Engineer, Analytics Engineer, Platform, Data Steward,
Analista BI, Data Scientist y SRE. Qué decide cada uno y por qué: [02 · Roles y decisiones](02_roles_y_decisiones.md).

## Glosario y preguntas frecuentes

[15 · Glosario](15_glosario.md) (curtailment, MATER, PPA, SCD2...) · [14 · FAQ](14_faq.md).
