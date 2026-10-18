# 22 · Etapa 18 · CI/CD con GitHub Actions

## 🎯 Objetivo

Que **cada cambio que subís se pruebe solo** (lint, tests unitarios, el pipeline entero en local y la validación del
bundle contra tu workspace) y que el **despliegue** sea un botón en GitHub, con aprobación para producción. Así nadie
rompe `main` sin enterarse y nadie despliega a prod desde su computadora.

**Archivo:** `.github/workflows/ci.yml`.

## 📚 Conceptos

| concepto | qué es | en este archivo |
|---|---|---|
| **workflow** | un archivo YAML en `.github/workflows/` que GitHub ejecuta ante ciertos eventos | `ci.yml` |
| **evento (`on`)** | qué lo dispara | `push`, `pull_request`, `workflow_dispatch` (a mano) |
| **job** | un conjunto de pasos que corre en una máquina limpia (*runner*) | `lint`, `unit-tests`, ... |
| **step** | un comando o una acción reutilizable (`uses:`) | `actions/checkout@v4`, `run: pytest` |
| **`needs`** | dependencias entre jobs | los tests esperan al lint |
| **`if`** | condición para correr un job | `bundle-validate` sólo si hay credenciales |
| **variables y secrets** | configuración del repo; los secrets no se muestran nunca en los logs | `DATABRICKS_HOST`, `DATABRICKS_TOKEN` |
| **environment** | un "ambiente" con sus propios secrets y reglas (por ejemplo, aprobación obligatoria) | `dev`, `prod` |
| **CI** | integración continua: probar cada cambio | lint + tests + validate |
| **CD** | despliegue continuo (acá, a demanda) | el job `deploy` |

## 🧱 Paso a paso

### 1. El encabezado

```yaml
name: CI/CD

on:
  push:
  pull_request:
  workflow_dispatch:
    inputs:
      deploy_target:
        description: "Target del bundle a desplegar: dev | prod (vacío = no desplegar)"
        required: false
        default: ""
      deploy_genie:
        description: "¿Desplegar también los Genie Agents?"
        type: boolean
        default: false

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```
- `push` sin filtro: corre en **cualquier rama**. `pull_request`: corre en cada PR.
- `workflow_dispatch` con `inputs`: aparece el botón **Run workflow** en la pestaña Actions, con dos campos.
- `concurrency`: si subís dos commits seguidos a la misma rama, se cancela la corrida vieja (ahorra minutos).

### 2. Los jobs

```
lint ──┬──▶ unit-tests ──▶ integration-tests ──┐
       └──▶ bundle-validate ───────────────────┴──▶ deploy (sólo a mano)
```

**`lint`** (~30 s):
```yaml
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install ruff==0.6.9
      - run: ruff check src tests scripts apps
      - name: JSON de Genie y dashboards bien formados
        run: |
          for f in genie/agents/*.json dashboards/*.lvdash.json; do python -m json.tool "$f" > /dev/null || exit 1; done
```
Versión de ruff **fija**: una versión nueva podría agregar reglas y romper el CI sin que cambies nada. Verificar los
JSON atrapa un dashboard o un agent mal generado antes de desplegar.

**`unit-tests`** e **`integration-tests`**:
```yaml
  unit-tests:
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: "17" }
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: pip }
      - run: pip install -e ".[dev]"
      - run: pytest -m "not integration"
```
Java 17 para Spark local (capítulo 03). `cache: pip` reusa las descargas entre corridas (PySpark pesa ~300 MB). El de
integración es igual con `pytest -m integration` y espera a los unitarios: si una pieza falla, no tiene sentido correr
el pipeline entero.

**`bundle-validate`**:
```yaml
  bundle-validate:
    needs: lint
    if: ${{ vars.DATABRICKS_HOST != '' }}
    env:
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_TOKEN: ${{ secrets.DATABRICKS_TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - uses: databricks/setup-cli@main
      - run: databricks bundle validate -t dev
      - run: databricks bundle validate -t prod
```
- Valida el bundle **contra tu workspace** (resuelve el `lookup` del warehouse, verifica permisos).
- `if: vars.DATABRICKS_HOST != ''`: si todavía no configuraste las credenciales (o alguien hace un *fork*), el job se
  **saltea** en vez de fallar.
- La CLI lee `DATABRICKS_HOST` y `DATABRICKS_TOKEN` de las variables de entorno: no hace falta `auth login`.

**`deploy`**:
```yaml
  deploy:
    needs: [unit-tests, integration-tests, bundle-validate]
    if: ${{ github.event_name == 'workflow_dispatch' && inputs.deploy_target != '' }}
    environment: ${{ inputs.deploy_target }}
    env: { DATABRICKS_HOST: ..., DATABRICKS_TOKEN: ... }
    steps:
      - uses: actions/checkout@v4
      - uses: databricks/setup-cli@main
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: databricks bundle deploy -t ${{ inputs.deploy_target }}
      - name: Genie Agents
        if: ${{ inputs.deploy_genie }}
        run: |
          pip install "databricks-sdk>=0.60"
          python scripts/deploy_genie.py --target ${{ inputs.deploy_target }}
```
- Sólo corre **a mano** y **después de que todo pasó** (`needs`).
- `environment: prod` activa las reglas del environment: si le pusiste *required reviewers*, el job **espera tu
  aprobación** antes de desplegar.
- Si se pide, despliega también los Genie Agents (que no están en el bundle).

### 3. Configurar GitHub (una vez)

1. **Token de Databricks:** ícono de usuario → *Settings → Developer → Access tokens → Generate new token*. Ponele una
   descripción ("GitHub Actions") y un vencimiento (90 días). Copialo: se muestra **una sola vez**.
2. **GitHub → tu repo → Settings → Secrets and variables → Actions:**
   - pestaña *Variables* → **New repository variable**: `DATABRICKS_HOST` = `https://dbc-....cloud.databricks.com`;
   - pestaña *Secrets* → **New repository secret**: `DATABRICKS_TOKEN` = el token.
3. **Settings → Environments → New environment:** `dev` (sin reglas) y `prod` con **Required reviewers** = vos.
4. **Settings → Branches → regla para `main`** (capítulo 02): **Require status checks to pass** y elegí `lint`,
   `unit-tests` e `integration-tests`. Desde ahora, un PR con el CI rojo no se puede mergear.

**Por qué el host es una variable y el token un secret:** el host no es secreto (y verlo en los logs ayuda a depurar);
el token sí: GitHub lo reemplaza por `***` en cualquier log.

**En una empresa** el token no sería tuyo: se crea un **service principal** para el CI con permisos sólo sobre lo que
despliega, y prod se despliega con `run_as` ese service principal. En Free Edition hay un solo usuario.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| deploy manual | deploy automático en cada merge a `main` | con un workspace de práctica y cuotas, cada deploy corre cosas; mejor decidir cuándo |
| aprobación en prod | cualquiera despliega | producción tiene que tener un segundo par de ojos |
| integración en el CI | sólo unitarios | el test de integración es el que encontró L6, L7 y L8 |
| saltear `bundle-validate` sin credenciales | que falle | un *fork* o un repo recién creado no tienen secrets: no es un error del código |
| versiones fijas de herramientas | `latest` | el CI tiene que ser reproducible |

## ✅ Probalo

1. Subí un commit a una rama: pestaña **Actions** → aparece la corrida con `lint`, `unit-tests`,
   `integration-tests` y (si configuraste el host) `bundle-validate`. Todos en verde en ~10 minutos.
2. Rompé algo a propósito (un `import os` sin usar) y subilo: `lint` falla y los tests no corren. Arreglalo.
3. **Actions → CI/CD → Run workflow** → `deploy_target = dev` → corre todo y despliega. Con `prod`, se frena esperando tu
   aprobación (**Review deployments → Approve**).

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `JAVA_GATEWAY_EXITED` en los tests | falta `setup-java` | el paso de Java 17 antes de pytest |
| `bundle-validate` no aparece | la variable no está configurada | `DATABRICKS_HOST` como **variable** (no secret) |
| `Error: default auth: cannot configure default credentials` | falta el token o está vencido | el secret `DATABRICKS_TOKEN`; generá uno nuevo |
| el deploy a prod no arranca | espera la aprobación | **Review deployments** en la corrida |
| `Resource not accessible by integration` | permisos del token de GitHub en *forks* | normal en PRs desde forks: los secrets no se comparten |
| el CI pasa y en Databricks falla | el CI valida y testea, no corre el job | el job corre en Databricks: revisá la corrida (capítulo 15) |

## 📍 Punto de control

```bash
git add .github && git commit -m "etapa-18: CI/CD con GitHub Actions" && git push
git diff etapa-18 HEAD --stat
```
Y en GitHub: la pestaña **Actions** en verde.

## 🏋️ Ejercicio

1. Agregá un job que corra `python scripts/build_governance.py` y falle si el SQL generado no coincide con el commiteado
   (`git diff --exit-code sql/governance`). Así nadie edita el SQL generado a mano.
2. Hacé lo mismo para `build_genie.py` y `build_dashboards.py`.
3. Agregá un job programado (`on: schedule`) que una vez por semana corra `genie_eval.py --only 01_operacion_parques`
   contra dev y suba el resultado como *artifact*.
