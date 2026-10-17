# ADR-002 · El scale_factor escala la flota, no los días

**Contexto.** La historia del negocio (curtailment creciente desde 2023, devaluación de dic-2023, firmware nuevo
en 2025, julio 2025 en Cañadón León) necesita los 45 meses completos a cualquier escala.

**Decisión.** `scale_factor` multiplica la cantidad de turbinas e inversores por parque (mínimo 1). SF=1 es la
flota real (380 turbinas, 220 inversores); SF=0,1 cabe en Free Edition (~3 GB); SF=10 es una flota hipotética
de 3.800 turbinas para practicar performance.

**Consecuencias.** Con pocas turbinas por parque, una falla pesa más en el porcentaje del parque (a SF 0,1 una
turbina es 1/4 de Cañadón León): los porcentajes del caso "¿por qué generó menos?" cambian algo con la escala,
la historia no. Los contratos PPA se escalan con la flota para que el cumplimiento sea comparable.
