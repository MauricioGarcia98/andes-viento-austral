# 01 · Borrar todo (y guardar la referencia)

## 🎯 Objetivo

Desmontar el proyecto **completo**, en Databricks y en GitHub, sin dejar restos que después te confundan (un job
viejo que sigue corriendo, un catálogo con tablas de antes, un token olvidado) y **sin perder la referencia** que vas
a usar para comparar mientras lo reconstruís.

Si nunca desplegaste el proyecto y empezás de cero, saltá directo al [capítulo 02](02_git_y_github.md).

## 📚 Conceptos

- **Lo que vive en Databricks** se divide en dos: lo que creó el **bundle** (jobs, pipeline, dashboards, App, el esquema
  `ldp`, los archivos subidos) y lo que se creó **fuera del bundle** (los catálogos, que se crearon por SQL; los
  Genie Agents, que se crearon con un script; los archivos de Genie Code; los tokens). El bundle sabe borrar lo
  suyo; lo demás hay que borrarlo a mano.
- **Borrar en Unity Catalog no es instantáneo para la cuota:** lo borrado se puede recuperar ~7 días con `UNDROP` y
  mientras tanto sigue contando en la cuota de 500 tablas de Free Edition. Si borrás y reconstruís el mismo día, vas
  a tener el doble de tablas contando durante una semana ([R14 de la bitácora](../docs/08_bitacora.md)).
- **En GitHub, borrar un repo borra todo lo que cuelga de él**: issues, PRs, Actions, secrets, variables y
  environments. No hay papelera.

## 🧱 Paso a paso

### Paso 1 · Guardar la referencia (no te lo saltees)

El curso, los tags de los puntos de control y el código terminado viven en el repo. Antes de borrar nada:

- **Si el repo de referencia es de otra persona** (por ejemplo `MauricioGarcia98/andes-viento-austral`): no lo
  borres; vas a trabajar en un repo **tuyo y nuevo**. Saltá al paso 2.
- **Si el repo es tuyo y lo vas a borrar**, hacé una copia completa, con todas las ramas y tags:
  ```bash
  git clone --mirror https://github.com/<tu-usuario>/andes-viento-austral.git andes-backup.git
  ```
  `--mirror` copia **todo**: ramas, tags, notas. Un `git clone` normal trae sólo la rama por defecto y los tags
  alcanzables desde ella, y la rama `curso` quedaría afuera. Para usar la copia después:
  `git clone andes-backup.git andes-referencia`.

**Cómo verificar:** `git --git-dir=andes-backup.git tag | grep etapa` lista `etapa-01` a `etapa-19`.

### Paso 2 · Anotar qué hay desplegado

En Databricks, abrí **Genie** y anotá los agents `Andes · ...`. Abrí **Jobs & Pipelines** y anotá los `andes-viento-*`.
Si tenés la CLI configurada:
```bash
databricks jobs list | grep andes
databricks api get /api/2.0/genie/spaces | grep -o '"title":"Andes[^"]*"'
```

### Paso 3 · Pausar lo automático

Si activaste los schedules, pausalos primero (**Jobs & Pipelines → el job → Schedules & Triggers → Pause**).
Así ningún job arranca a mitad del desmontaje y recrea tablas que acabás de borrar.

### Paso 4 · Borrar los Genie Agents

**Por qué primero:** un agent apunta a tablas y funciones. Si borrás primero los catálogos, el agent queda roto y
hay que borrarlo igual.

- **Desde la web:** **Genie** → en cada agent `Andes · ...`, menú **⋮ → Move to trash** (o *Delete*).
- **Desde la terminal:**
  ```bash
  databricks api get /api/2.0/genie/spaces          # buscá el "space_id" de cada agent Andes
  databricks api delete /api/2.0/genie/spaces/<space_id>
  ```

### Paso 5 · Borrar lo que creó el bundle (dev y prod)

```bash
cd andes-viento-austral          # tu copia local del repo, con databricks.yml
databricks bundle destroy -t dev
databricks bundle destroy -t prod     # sólo si desplegaste prod
```

Muestra la lista de lo que va a borrar y pide confirmación (agregá `--auto-approve` para no confirmar). Borra los 3
jobs, el pipeline LDP, los 6 dashboards, la App, el esquema `ldp` y la carpeta `.bundle/andes-viento-austral/<target>`
con los archivos subidos.

**Sin terminal:** borrá cada cosa a mano: **Jobs & Pipelines** (cada `andes-viento-*` → ⋮ → *Delete*),
**Dashboards** (los 6 `Andes · ...`), **Compute → Apps → andes-genie-chat → Delete** y la carpeta
`Workspace → Users → <vos> → .bundle → andes-viento-austral`.

**Por qué `destroy` y no borrar a mano:** el bundle guarda un registro de lo que creó (el *state*). `destroy` borra
exactamente eso, ni más ni menos. A mano es fácil olvidarse un dashboard.

### Paso 6 · Borrar los catálogos (los datos)

En el **SQL Editor**:
```sql
DROP CATALOG IF EXISTS andes_viento_dev CASCADE;
DROP CATALOG IF EXISTS andes_viento     CASCADE;
```
`CASCADE` borra todo lo de adentro: esquemas, tablas, vistas, metric views, funciones y el volumen con los archivos
crudos. Sin `CASCADE` falla si el catálogo no está vacío (es una protección).

> ⚠️ Lo borrado sigue contando ~7 días en la cuota de 500 tablas. Si vas a reconstruir enseguida, no pasa nada grave
> (el proyecto usa ~58 tablas por ambiente), pero no repitas el ciclo "borrar y recrear" varias veces en la semana.

### Paso 7 · Limpiar tu carpeta del workspace

**Workspace → Users → <tu email>** y borrá lo que haya quedado:
- el **Git folder** `andes-viento-austral` (si lo usaste),
- `.assistant_instructions.md` y la carpeta `.assistant/` (los copió `install_assistant_files.py`).

### Paso 8 · Revocar los tokens

Un token es una contraseña. Si queda vivo y se filtra, alguien puede entrar a tu workspace.

- **Databricks:** ícono de usuario → **Settings → Developer → Access tokens** → revocá los que creaste para el
  proyecto (por ejemplo el de GitHub Actions). Por terminal: `databricks tokens list` y `databricks tokens delete <id>`.
- **GitHub:** si creaste un token personal para `git push`, revocalo en **github.com → Settings → Developer settings →
  Personal access tokens**.

### Paso 9 · Borrar el repo de GitHub (sólo si es tuyo)

**github.com → tu repo → Settings → General → abajo de todo, "Danger Zone" → Delete this repository** → escribí el
nombre completo del repo para confirmar.

Esto borra también los secrets (`DATABRICKS_TOKEN`), las variables (`DATABRICKS_HOST`), los environments, los PRs y
el historial de Actions.

**Alternativa más suave:** *Archive this repository* lo deja en sólo lectura sin borrarlo.

### Paso 10 · Limpiar tu computadora

```bash
rm -rf andes-viento-austral        # la copia local (NO borres andes-backup.git ni andes-referencia)
```
Si querés desconectar la CLI: abrí `~/.databrickscfg` y borrá la sección del perfil (por ejemplo `[DEFAULT]`). Las
credenciales OAuth en caché están en `~/.databricks/token-cache.json`.

## 🤔 Por qué este orden

```
referencia → pausar → Genie → bundle → catálogos → carpetas → tokens → repo → compu
```

- **Referencia primero:** todo lo demás es recuperable desde ahí; la referencia no.
- **Pausar antes de borrar:** un job programado podría arrancar a mitad de camino.
- **Genie antes que los datos:** los agents dependen de las tablas.
- **Bundle antes que los catálogos:** si borrás el catálogo con los jobs vivos, la próxima corrida de un job
  intentaría crear esquemas y tablas de nuevo (o fallaría).
- **Tokens antes que el repo:** el secret del repo es una copia del token; borrar el repo no invalida el token.
- **El repo al final:** mientras exista, tenés el `databricks.yml` para hacer `bundle destroy`.

## ✅ Probalo

| dónde | qué tiene que pasar |
|---|---|
| Genie | ningún agent `Andes · ...` |
| Jobs & Pipelines | ningún `andes-viento-*` |
| Dashboards | ningún `Andes · ...` |
| Compute → Apps | sin `andes-genie-chat` |
| Catalog | sin `andes_viento_dev` ni `andes_viento` |
| SQL: `SHOW TABLES DROPPED IN andes_viento_dev.gold` | error de que el catálogo no existe (lo borrado ya no se ve por esquema) |
| GitHub | el repo no existe (o está archivado) |
| tu backup | `git --git-dir=andes-backup.git tag` muestra `etapa-01` ... `etapa-19` |

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `bundle destroy`: *no deployment found* | ya estaba destruido o desplegaste desde otra carpeta o usuario | borrá a mano lo que quede (paso 5, "sin terminal") |
| `bundle destroy` pide un catálogo que no existe | borraste el catálogo antes que el bundle | igual completa; si no, borrá los jobs a mano |
| `DROP CATALOG`: *catalog is not empty* | faltó `CASCADE` | agregá `CASCADE` |
| `DROP CATALOG`: permisos | no sos dueño del catálogo | en Free Edition sos admin: revisá que estés en el workspace correcto |
| la App no se borra | está corriendo | **Stop** y después **Delete** |
| el mail de la cuota sigue llegando | lo borrado cuenta ~7 días | esperar |

## 🏋️ Ejercicio

Antes de borrar, exportá un Genie Agent para ver cómo está guardado por dentro:
```bash
python scripts/deploy_genie.py --export <space_id> > mi_agent.json
```
Abrí el JSON y encontrá las instrucciones, las tablas y los benchmarks. En el [capítulo 20](20_etapa16_genie.md) vas a
escribir eso mismo desde un YAML.
