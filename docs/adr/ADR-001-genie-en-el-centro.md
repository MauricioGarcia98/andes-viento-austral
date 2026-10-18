# ADR-001 · Genie en el centro

**Contexto.** NovaMart enseñó a construir un lakehouse. Andes tiene otro objetivo: que las áreas de una empresa
real usen Genie todos los días. Los jefes de parque no abren dashboards; preguntan.

**Decisión.** El entregable final son 4 Genie Agents (2 por dominio) + Agent mode + una App. Todo lo demás
(gold, metric views, funciones, comentarios) se diseña pensando en "¿Genie lo va a entender?":
- tablas anchas y bien comentadas (`v_park_daily`) en vez de 20 joins,
- métricas oficiales en metric views con sinónimos en el idioma de la gente,
- respuestas certificadas como funciones de UC (trusted assets),
- 20+ benchmarks por agent para medir si responde bien.

**Consecuencias.** Más trabajo en semántica y gobierno; a cambio, Genie responde con números que coinciden con
los dashboards y con Finanzas. Lo que no se puede medir con un benchmark no se considera "listo".
