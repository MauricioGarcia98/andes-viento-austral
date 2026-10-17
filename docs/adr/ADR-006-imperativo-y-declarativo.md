# ADR-006 · Imperativo como principal, declarativo como comparación

**Decisión.** El pipeline completo corre como Job (notebooks delgados + paquete Python testeado). Una parte
(SCADA + CAMMESA + activos + presupuesto) se implementa también en Lakeflow Declarative Pipelines (SQL).

**Por qué.** La corrección de relojes por percentil, la asignación de pérdidas y los MERGE con reglas de
negocio son más claros y testeables en Python. El declarativo muestra cuánto código se ahorra en lo estándar
(SCD2 con `AUTO CDC`, expectations). En Free Edition sólo puede haber un pipeline activo a la vez.
