# ADR-008 · Gobierno generado desde un diccionario YAML

**Decisión.** `governance/data_dictionary.yml` es la fuente única: de ahí salen los `COMMENT`, las PK/FK, los
tags (`pii`, dominio, dueño) y `docs/04_diccionario_de_datos.md`. Máscaras y row filters se escriben a mano
(`sql/governance/04_*.sql`) porque son decisiones de seguridad que conviene revisar línea por línea.

**Por qué.** Genie lee los comentarios: tienen que estar versionados, revisados en PR y ser iguales en dev y prod.
