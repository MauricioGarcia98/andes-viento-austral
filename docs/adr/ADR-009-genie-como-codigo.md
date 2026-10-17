# ADR-009 · Genie Agents como código

**Decisión.** Cada agent es un YAML (`genie/src/`) con instrucciones, tablas, metric views, funciones, ejemplos y
benchmarks. `scripts/build_genie.py` lo compila al `serialized_space` (`genie/agents/*.json`, con `${catalog}`),
y `scripts/deploy_genie.py` lo crea o actualiza por API (idempotente por título). Los `id` son hashes estables.

**Consecuencias.** Los cambios a un agent se revisan en un PR, se prueban en dev y se promueven a prod. Si
alguien cambia algo desde la UI, `--export` lo trae para versionarlo.
