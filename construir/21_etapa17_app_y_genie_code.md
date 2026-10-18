# 21 · Etapa 17 · La App y Genie Code

## 🎯 Objetivo

Dos piezas alrededor de Genie:
1. una **Databricks App** (un chat propio hecho con Streamlit) que usa la Conversation API: el ejemplo de cómo meter
   Genie en una herramienta propia de la empresa. Es **opcional**: Genie ya se usa desde la plataforma;
2. los archivos para **Genie Code** (el asistente que ayuda a **construir** dentro del workspace), para que conozca las
   convenciones del proyecto.

**Archivos:** `apps/genie_chat/app.py`, `app.yaml`, `requirements.txt`, `genie_client.py`, el bloque de la App en
`databricks.yml`, `.assistant_instructions.md`, `.assistant/skills/*/SKILL.md`, `scripts/install_assistant_files.py`.

## 📚 Conceptos

- **Databricks App:** una aplicación web (Streamlit, Dash, Flask...) que corre **dentro** de Databricks, con su URL,
  sin servidores propios. Se autentica con un **service principal** propio (una "cuenta de máquina"), al que hay que
  darle permisos.
- **Service principal:** una identidad que no es una persona. Las Apps, los jobs de producción y el CI la usan para
  que nada dependa de la cuenta de alguien.
- **Genie Code** (ex Databricks Assistant): lee un archivo de instrucciones (`.assistant_instructions.md`) y *skills*
  (`.assistant/skills/<nombre>/SKILL.md`) desde tu carpeta del workspace y los usa para responder con las reglas del
  proyecto.

## 🧱 Paso a paso

### 1. La App

**`app.yaml`** (cómo se arranca):
```yaml
command: ["streamlit", "run", "app.py", "--server.headless", "true"]
env:
  - name: GENIE_TITLE_PREFIX
    value: "Andes ·"
```
**`requirements.txt`**: `databricks-sdk`, `streamlit`, `pandas` (se instalan al arrancar la App).

**`app.py`**, los bloques:
```python
w = WorkspaceClient()                         # dentro de la App se autentica solo (con su service principal)

@st.cache_data(ttl=300)
def spaces() -> dict[str, str]:
    resp = w.api_client.do("GET", "/api/2.0/genie/spaces")
    return {s["title"]: s["space_id"] for s in resp.get("spaces", []) if s["title"].startswith(PREFIX)}

agent = st.sidebar.selectbox("Agent", list(available))
...
if question := st.chat_input("Ej.: ¿Por qué Cañadón León generó menos en julio 2025?"):
    ans = GenieClient(w, available[agent]).ask(question, st.session_state.get("conv"))
    st.session_state["conv"] = ans.conversation_id          # repreguntar en la misma conversación
    st.markdown(ans.text or ans.description or "")
    if ans.rows:
        st.dataframe(pd.DataFrame(ans.rows, columns=ans.columns))
    if ans.sql:
        with st.expander("Ver el SQL que generó Genie"):
            st.code(ans.sql, language="sql")
```
- **La lista de agents se descubre por API** (los que empiezan con `Andes ·`) y se cachea 5 minutos.
- **`st.session_state`**: Streamlit vuelve a ejecutar el script entero con cada interacción; lo que tiene que
  sobrevivir (el historial, el id de la conversación) va en `session_state`.
- **Mostrar el SQL** es una decisión de confianza: el usuario puede ver de dónde salió el número.
- `genie_client.py` es una **copia** de `src/andes_viento/genie/conversation.py`: la App se despliega sola, sin el
  paquete.

**El bloque en `databricks.yml`** (sólo en el target `dev`):
```yaml
targets:
  dev:
    resources:
      apps:
        andes_genie_chat:
          name: andes-genie-chat
          source_code_path: ./apps/genie_chat
          resources:
            - name: sql-warehouse
              sql_warehouse: { id: "${var.warehouse_id}", permission: CAN_USE }
```
**Por qué sólo en dev:** el nombre de una App es **único en el workspace** (el modo `development` no le agrega
prefijo) y Free Edition permite **una sola**. Declarada en los dos targets, el deploy de prod falla con *An app with the
same name already exists* (R9). En una empresa, cada target tendría su App con su nombre.

**Los permisos** (`deploy_genie.py --grant-app andes-genie-chat`):
```python
sp = w.apps.get(app_name).service_principal_client_id
for sid in spaces.values():                              # usar cada agent
    w.api_client.do("PATCH", f"/api/2.0/permissions/genie/{sid}",
                    body={"access_control_list": [{"service_principal_name": sp, "permission_level": "CAN_RUN"}]})
GRANT USE CATALOG ON CATALOG {catalog} TO `{sp}`
GRANT USE SCHEMA, SELECT, EXECUTE ON SCHEMA {catalog}.gold TO `{sp}`     # leer tablas y ejecutar funciones
GRANT USE SCHEMA, SELECT, EXECUTE ON SCHEMA {catalog}.ops TO `{sp}`      # las máscaras y filtros viven en ops
```
Sin `EXECUTE` sobre `ops`, las consultas a tablas con máscaras fallan (la máscara es una función de `ops`).

> **Ojo con las máscaras:** la App consulta con **su** service principal, no con el usuario que escribe. Las máscaras y
> filtros por parque se aplican al service principal. Para que cada usuario vea sólo lo suyo desde la App habría que
> usar la autorización "en nombre del usuario" (*on-behalf-of*), que es más avanzada. Desde la plataforma, Genie ya
> respeta los permisos de cada uno.

### 2. Genie Code

**`.assistant_instructions.md`**: dónde está cada cosa y las **10 convenciones que no se negocian** (UTC, unidades, la
identidad de pérdidas, "hoy" no es `current_date()`, *schema hints*, el reinicio del stream, las reglas de calidad, qué
necesita una tabla gold nueva, funciones `try_*`, correr los tests antes de commitear).

**Dos skills** (`.assistant/skills/`):
- `andes-medallion-conventions`: cómo agregar una fuente o una tabla respetando las capas.
- `andes-genie-agent-authoring`: el orden para diagnosticar y mejorar un agent (de abajo hacia arriba en la pirámide,
  con las reglas R11-R16).

**`install_assistant_files.py`** los sube a tu carpeta del workspace (`/Users/<vos>/`) con el SDK; con `--workspace`, a
la raíz para todos (requiere admin).

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| App como ejemplo opcional | la App como forma principal de usar Genie | Genie desde la plataforma ya respeta permisos, tiene historial, *feedback* y monitoreo |
| copia del cliente en la App | importar el paquete | la App se despliega con su carpeta; el paquete no está ahí |
| sólo en dev | dev y prod | nombre único y una App por workspace en Free Edition |
| instrucciones para Genie Code en el repo | escribirlas en la interfaz | se versionan y se instalan con un comando |

## ✅ Probalo

```bash
databricks bundle deploy -t dev                                            # crea la App (si no estaba)
python scripts/deploy_genie.py --target dev --grant-app andes-genie-chat   # permisos
databricks bundle run andes_genie_chat -t dev                              # arranca la App (~3 min)
python scripts/install_assistant_files.py
```
**Compute → Apps → andes-genie-chat** → abrí la URL → elegí un agent → preguntá. Para Genie Code: abrí un notebook → ✨ →
*"¿cómo agrego una fuente nueva a este proyecto?"*: tiene que responder con el registro `SOURCES`, el contrato de bronze,
las reglas de silver y un test.

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `An app with the same name already exists` | la App está en dos targets o ya existía | sólo en dev; o borrala en Compute → Apps (R9) |
| la App dice "No veo Genie Agents" | el service principal no tiene `CAN_RUN` | `--grant-app` |
| la App responde con error de permisos en una tabla | falta `SELECT`/`EXECUTE` en gold u ops | `--grant-app` (hace los GRANT) |
| la App no arranca | dependencias | **Logs** de la App: casi siempre es `requirements.txt` |
| Genie Code no conoce las convenciones | no se instalaron los archivos | `install_assistant_files.py` |

## 📍 Punto de control

```bash
git commit -am "etapa-17: App y Genie Code" && git diff etapa-17 HEAD --stat
```

## 🏋️ Ejercicio

1. Agregá a la App un botón 👍/👎 por respuesta que guarde la pregunta, el SQL y el voto en una tabla
   `ops.genie_feedback` (pista: la App necesita permiso de escritura en `ops`).
2. Agregá a `.assistant_instructions.md` una convención nueva (por ejemplo, cómo nombrar los marts) y probá que Genie
   Code la respeta.
3. Leé la skill `andes-genie-agent-authoring` y usala con Genie Code para mejorar un benchmark que haya fallado.
