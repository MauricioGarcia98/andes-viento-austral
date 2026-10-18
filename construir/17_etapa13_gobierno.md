# 17 · Etapa 13 · Gobierno en Unity Catalog

## 🎯 Objetivo

Que cada tabla y columna de gold tenga **descripción en el idioma del negocio, dueño, claves y etiquetas**, y que los
datos sensibles estén **protegidos**: los contactos y precios de los clientes enmascarados para quien no es de
Comercial, y cada jefe de parque viendo sólo su parque. Todo **generado desde un único archivo YAML**, para que la
documentación y la base nunca se contradigan.

**Archivos:** `governance/data_dictionary.yml`, `scripts/build_governance.py`, `sql/governance/01_comments.sql`,
`02_constraints.sql`, `03_tags.sql` (generados), `04_masks_and_row_filters.sql` (a mano) y
`docs/04_diccionario_de_datos.md` (generado).

## 📚 Conceptos

- **Comentarios:** `COMMENT ON TABLE` y `ALTER COLUMN ... COMMENT`. Aparecen en Catalog Explorer y **Genie los lee**
  para entender qué es cada columna. Un comentario malo es una respuesta mala de Genie.
- **PK/FK informativas:** en Databricks, las claves primarias y foráneas **no se validan** al escribir (no frenan un
  INSERT). Sirven para documentar las relaciones, para que el optimizador las use (`RELY`) y para que Genie sepa cómo
  unir tablas.
- **Tags:** pares clave-valor sobre tablas y columnas (`dominio = operacion`, `pii = email`). Se usan para buscar,
  auditar y aplicar políticas.
- **Máscara de columna (column mask):** una función SQL que recibe el valor y decide qué mostrar según quién consulta.
  El dato no cambia; cambia lo que ve cada usuario.
- **Filtro de fila (row filter):** una función que decide, fila por fila, si el usuario puede verla.
- **`is_member('grupo')` / `is_account_group_member('grupo')`:** funciones que dicen si el usuario actual está en un
  grupo del workspace o de la cuenta.

## 🧱 Paso a paso

### 1. El diccionario: `governance/data_dictionary.yml`

```yaml
tables:
  dim_park:
    domain: operacion
    owner: "Martín Quiroga (Gerente de Operaciones)"
    grain: 1 fila por parque
    comment: "Los 13 parques de Andes Viento Austral: 9 eólicos (Chubut y Santa Cruz) y 4 solares (Jujuy y Catamarca)."
    pk: [park_key]
    columns:
      park_code: "Código corto del parque: RAW, MAD, GAR, CRV, PAM, DES, PIC, SJU, LEO (eólicos) y SUS, ABR, TIN, FIA (solares)."
      park_name: "Nombre del parque (ej. 'Cañadón León', 'Susques Solar'). Los usuarios lo nombran así."
      guaranteed_availability: "Disponibilidad garantizada por el fabricante (0,97 = 97 %)."
    tags: {dominio: operacion}
  dim_contract:
    ...
    columns:
      contact_email: ["Email del contacto comercial del cliente.", {pii: email}]
```
**Cómo escribir un buen comentario (para Genie):**
- **Unidades** siempre: "en MWh", "en USD", "0,97 = 97 %".
- **Valores posibles** cuando son pocos: "'Eólico' o 'Solar'", los 13 códigos de parque.
- **Cómo lo nombra la gente:** "Los usuarios lo nombran así".
- **Cómo usarla:** "Para la versión actual filtrar `is_current = true`".
- El **grano** de la tabla, siempre.

Una columna con etiqueta se escribe como lista: `[comentario, {tag: valor}]`.

### 2. `scripts/build_governance.py`: generar el SQL

```python
def build(tables):
    for name, t in tables.items():
        full = "${gold}." + name
        comments.append(f"COMMENT ON TABLE {full} IS '{q(t['comment'])} Grano: {q(t['grain'])}.';")
        for col, spec in t.get("columns", {}).items():
            text, ctags = col_parts(spec)
            comments.append(f"ALTER TABLE {full} ALTER COLUMN {col} COMMENT '{q(text)}';")
            if ctags:
                tags.append(f"ALTER TABLE {full} ALTER COLUMN {col} SET TAGS (...);")
        tags.append(f"ALTER TABLE {full} SET TAGS ('dominio' = ..., 'duenio' = ...);")
        if t.get("pk") and not name.startswith("mart_"):
            for c in t["pk"]:
                constraints.append(f"ALTER TABLE {full} ALTER COLUMN {c} SET NOT NULL;")
            constraints.append(f"ALTER TABLE {full} DROP CONSTRAINT IF EXISTS pk_{name} CASCADE;")
            constraints.append(f"ALTER TABLE {full} ADD CONSTRAINT pk_{name} PRIMARY KEY (...){' RELY' if dim};")
    for name, t in tables.items():                    # las FK, después de TODAS las PK
        for col, ref in (t.get("fks") or {}).items():
            constraints.append(f"... ADD CONSTRAINT fk_{name}_{col} FOREIGN KEY ({col}) REFERENCES ${{gold}}.{rt} ({rc});")
```
- `q()` escapa las comillas simples (`'Cañadón León'` adentro de un texto SQL).
- **Idempotente:** `DROP CONSTRAINT IF EXISTS ... CASCADE` antes de cada `ADD`. El job lo corre en cada ejecución.
- Una PK necesita la columna `NOT NULL`. Las **FK van al final**: una FK sólo puede apuntar a una PK que ya existe.
- `RELY` en las dimensiones: le dice al optimizador "confiá en que esta clave es única" (puede eliminar joins
  innecesarios).
- Los marts no llevan PK (se recrean completos y su grano puede cambiar).
- Escribe también `docs/04_diccionario_de_datos.md`: **la documentación sale del mismo lugar que la base**.

```bash
python scripts/build_governance.py      # 19 tablas -> sql/governance/ y docs/04_diccionario_de_datos.md
```
Los tres SQL generados empiezan con `-- GENERADO ... No editar a mano.` y se commitean (el job ejecuta el SQL; no
corre Python para generarlo).

### 3. Máscaras y filtros de fila: `04_masks_and_row_filters.sql` (escrito a mano)

**Quién puede ver qué** (decisión del Data Steward con Comercial y Legal):

| dato | lo ve completo | el resto ve |
|---|---|---|
| email del contacto del cliente | Comercial, Finanzas, Dirección | `m*******@cliente.com` |
| nombre, teléfono y CUIT del cliente | Comercial, Finanzas, Dirección | `[RESERVADO]` |
| precio de cada PPA | Comercial, Finanzas, Dirección | `NULL` |
| teléfono del líder de cuadrilla | Mantenimiento | `***-5521` |
| órdenes y disponibilidad | cada jefe de parque, **sólo su parque** | — |

```sql
CREATE OR REPLACE FUNCTION ${ops}.can_see_commercial()
RETURNS BOOLEAN
RETURN is_member('admins') OR is_account_group_member('andes_comercial')
    OR is_account_group_member('andes_finanzas') OR is_account_group_member('andes_direccion');

CREATE OR REPLACE FUNCTION ${ops}.mask_email(email STRING)
RETURNS STRING
RETURN CASE WHEN ${ops}.can_see_commercial() THEN email
            ELSE regexp_replace(email, '^(.)[^@]*', '$1*******') END;

CREATE OR REPLACE FUNCTION ${ops}.park_filter(park STRING)
RETURNS BOOLEAN
RETURN is_member('admins')
    OR EXISTS (SELECT 1 FROM ${ops}.park_access a
               WHERE a.principal = current_user() AND (a.park_code = '*' OR a.park_code = park));

ALTER TABLE ${gold}.dim_contract ALTER COLUMN contact_email SET MASK ${ops}.mask_email;
...
ALTER TABLE ${gold}.fact_maintenance_order SET ROW FILTER ${ops}.park_filter ON (park_code);
ALTER TABLE ${gold}.fact_availability_daily SET ROW FILTER ${ops}.park_filter ON (park_code);
```
- Las funciones viven en `ops` (no en gold) para que los usuarios de negocio no las vean como "datos".
- **`ops.park_access`** dice quién ve qué parque (`'*'` = todos). El notebook `00_setup` le da `'*'` a quien corre el
  job: si no, el propio job (y vos) dejarían de ver las tablas.
- **Genie respeta las máscaras y filtros del usuario que pregunta**: un jefe de parque que le pregunta a Genie ve sólo
  su parque, sin tener que configurar nada en Genie.
- Este archivo se escribe a mano (no sale del YAML) porque es lógica, no metadata.

### 4. Ya estaba: el notebook `07_governance`

```python
from andes_viento.gold.marts import run_sql_folder
print(run_sql_folder(spark, cfg, "governance"))
```
Desde la etapa 11 corre la carpeta `sql/governance/`; ahora tiene contenido. El gobierno sólo se aplica en Databricks:
el pipeline local (`pipeline.py`) no lo corre, porque Spark OSS no tiene Unity Catalog (ni tags, ni máscaras, ni
`information_schema`).

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| un YAML como fuente única ([ADR-008](../docs/adr/ADR-008-gobierno-desde-yaml.md)) | comentarios a mano en cada SQL | la documentación y la base se contradicen en dos semanas |
| SQL generado y commiteado | generarlo en el job | el SQL se revisa en el PR; el job no necesita Python extra |
| máscaras con funciones | vistas distintas por área | habría que mantener una vista por área y tabla, y Genie tendría que saber cuál usar |
| row filter con una tabla de accesos | un grupo por parque | 13 grupos que mantener; con la tabla, dar acceso es un INSERT |
| PK/FK aunque no se validen | no declararlas | Genie y el optimizador las usan; documentan el modelo |

## ✅ Probalo

```bash
python scripts/build_governance.py
databricks bundle deploy -t dev
```
Corré el job (o repará sólo `governance`). En **Catalog → andes_viento_dev → gold → dim_park**: pestaña *Overview* con
los comentarios; arriba, los tags; en `dim_contract`, un ícono de máscara en las columnas protegidas. En el SQL Editor:
```sql
SELECT table_name, comment FROM andes_viento_dev.information_schema.tables WHERE table_schema = 'gold';
SELECT * FROM andes_viento_dev.information_schema.table_constraints WHERE table_schema = 'gold';
SELECT contact_email, price_usd_mwh FROM andes_viento_dev.gold.dim_contract LIMIT 3;   -- como admin: completo
```

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `[PARSE_SYNTAX_ERROR] at or near '''` | un `;` dentro de un comentario cortó la sentencia | `split_statements` (capítulo 13, R4) |
| `PRIMARY KEY ... column must be NOT NULL` | falta el `SET NOT NULL` antes | el generador lo pone antes de cada PK |
| `... referenced by a foreign key` al recrear la PK | la PK tiene FKs que dependen | `DROP CONSTRAINT ... CASCADE` |
| dejás de ver filas de `fact_maintenance_order` | el row filter te filtra | tu usuario necesita `'*'` en `ops.park_access` (lo hace `00_setup`) |
| la tarea `governance` tarda ~3 minutos | son cientos de `ALTER` | es costo fijo; se podría saltear si el diccionario no cambió (idea para el ejercicio) |

## 📍 Punto de control

```bash
git commit -am "etapa-13: gobierno desde un diccionario YAML" && git diff etapa-13 HEAD --stat
```

## 🏋️ Ejercicio

1. Agregá al diccionario una columna nueva con comentario y tag `pii`, regenerá y desplegá. Verificá el tag en Catalog.
2. Creá un usuario de prueba (o pedile a alguien), agregalo a `ops.park_access` con `park_code = 'LEO'` y que consulte
   `fact_availability_daily`. ¿Ve sólo Cañadón León?
3. Hacé que la tarea `governance` no reaplique nada si el diccionario no cambió (pista: la misma idea de la huella de
   las vistas del capítulo 23).
