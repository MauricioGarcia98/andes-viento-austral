# ADR-003 · Generador con física continua y tablas guía

**Contexto.** Datos aleatorios fila por fila no tienen autocorrelación (un frente dura días, no 10 minutos) y
hacen imposible el mantenimiento predictivo (la firma de una falla dura semanas).

**Decisión.**
1. El viento es una **función continua del tiempo**: suma de senos (períodos de 1,7, 4,3 y 9,7 días) con fases
   por región y parque × estacionalidad × ciclo diario × anomalía diaria AR(1). Dos turbinas del mismo parque
   ven el mismo frente sin simular paso a paso.
2. Lo que es secuencial y chico (clima diario, fallas, curtailment, suciedad acumulada, presupuesto) se calcula
   en el **driver** con `random.Random` sembrado por `crc32` (estable entre procesos) y se une por broadcast.
3. Toda la física existe en Spark y en Python; un test verifica que den lo mismo.
4. El generador "conoce el futuro" (horizonte de 45 días): una falla del día 20 ya degrada la turbina el día 1.

**Consecuencias.** Datos realistas y determinísticos; el job diario genera exactamente lo que habría salido
regenerando toda la historia.
