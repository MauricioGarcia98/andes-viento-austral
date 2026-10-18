# ADR-007 · El catálogo se crea por SQL

**Contexto.** En Databricks Free Edition (Default Storage) crear un catálogo por la API del bundle falla con
`Metastore storage root URL does not exist`. Lo aprendimos en NovaMart.

**Decisión.** Antes del primer deploy, una sola vez, en el SQL Editor:
`CREATE CATALOG IF NOT EXISTS andes_viento_dev; CREATE CATALOG IF NOT EXISTS andes_viento;`.
El bundle sólo declara el esquema `ldp` (para que exista antes del pipeline); las capas las crea `00_setup`.
