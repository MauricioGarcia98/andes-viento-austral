# 02 · Git y GitHub

## 🎯 Objetivo

Crear **tu** repositorio en GitHub, conectarlo con tu computadora y manejar con soltura el ciclo de trabajo que vas
a repetir en todo el curso: cambiar → commitear → subir → abrir un PR → mergear. Al final vas a tener un repo vacío
`mi-andes-viento` listo para la etapa 1.

## 📚 Conceptos

| concepto | qué es | analogía |
|---|---|---|
| **git** | un programa que guarda la historia de los cambios de una carpeta | el "historial de versiones" de un documento, pero para todo un proyecto |
| **repositorio (repo)** | una carpeta con su historia completa (la subcarpeta oculta `.git/`) | |
| **commit** | una foto del proyecto en un momento, con un mensaje que dice qué cambió | un punto de guardado |
| **rama (branch)** | una línea de trabajo independiente | una copia donde probás sin tocar el original |
| **`main`** | la rama principal: lo que "está bien" | |
| **remoto (`origin`)** | la copia del repo en GitHub | |
| **push / pull / fetch** | subir commits / bajar y mezclar / bajar sin mezclar | |
| **Pull Request (PR)** | un pedido para mezclar una rama en `main`, con revisión y CI | "¿puedo agregar esto?" |
| **merge** | mezclar una rama en otra | |
| **tag** | un nombre fijo para un commit (`etapa-05`, `v1.0`) | un marcador |
| **GitHub** | un sitio que guarda repos git y agrega PRs, Actions (CI/CD), secrets, permisos | |

**git ≠ GitHub.** git funciona sin internet, en tu computadora. GitHub es un servicio donde vive una copia y donde
colaborás.

## 🧱 Paso a paso

### 1. Instalar y configurar git

- macOS: `xcode-select --install` (o `brew install git`) · Ubuntu: `sudo apt install git` · Windows: *Git for Windows*
  (git-scm.com), que trae **Git Bash** (usalo como terminal en este curso).

```bash
git --version                                    # cualquier 2.30+ sirve
git config --global user.name  "Tu Nombre"
git config --global user.email "tu@email.com"     # el mismo de tu cuenta de GitHub
git config --global init.defaultBranch main       # que los repos nuevos arranquen con "main" y no "master"
```
**Por qué:** cada commit lleva nombre y email del autor. Si el email coincide con el de GitHub, los commits aparecen
asociados a tu perfil.

### 2. Autenticarte con GitHub

GitHub **no acepta tu contraseña** para `git push` desde la terminal. Hay tres formas; elegí una:

| forma | cómo | cuándo conviene |
|---|---|---|
| **GitHub CLI** (recomendada) | instalá `gh` (cli.github.com) → `gh auth login` → GitHub.com → HTTPS → *Login with a web browser* | la más simple; también te sirve para crear repos y PRs desde la terminal |
| **Token personal (PAT)** | github.com → Settings → Developer settings → *Fine-grained tokens* → con permiso *Contents: read and write* sobre tu repo; al hacer `git push`, usalo como contraseña | si no podés instalar `gh` |
| **SSH** | `ssh-keygen -t ed25519`, subir la clave pública a GitHub → Settings → SSH keys; usar URLs `git@github.com:...` | si ya usás SSH |

**Cómo verificar:** `gh auth status` dice *Logged in to github.com*.

### 3. Crear tu repo

1. github.com → **+** (arriba a la derecha) → **New repository**.
2. **Repository name:** `mi-andes-viento`. **Private** o **Public** (con Public, GitHub Actions es gratis sin límite).
3. Marcá **Add a README file**. En *.gitignore* y *license* dejá **None** (los vas a escribir vos en la etapa 1).
4. **Create repository**.

```bash
git clone https://github.com/<tu-usuario>/mi-andes-viento.git
cd mi-andes-viento
git log --oneline         # un commit: "Initial commit"
```

**Por qué con README:** así el repo nace con un commit y una rama `main` en GitHub, y `git clone` deja todo
conectado (el remoto `origin` ya configurado). Sin README tenés que hacer `git init`, `git remote add` y el primer
push a mano.

### 4. El ciclo de trabajo (lo vas a repetir cientos de veces)

```bash
git switch -c etapa-01               # 1) una rama nueva para el trabajo (switch -c = crear y cambiarse)
# ... editás archivos ...
git status                           # 2) qué cambió (rojo = sin preparar, verde = preparado)
git diff                             #    ver las líneas cambiadas
git add pyproject.toml src/          # 3) preparar (stage) lo que va en el commit
git commit -m "etapa-01: cimientos"  # 4) guardar la foto con un mensaje
git push -u origin etapa-01          # 5) subir la rama (-u: recordá que esta rama va a origin/etapa-01)
```

Después, en GitHub aparece un botón **Compare & pull request** → escribís qué hiciste → **Create pull request** →
cuando el CI esté verde (capítulo 22) → **Merge pull request** → **Delete branch**. Y en tu computadora:

```bash
git switch main && git pull          # traer el merge a tu main local
```

**Por qué ramas + PR aunque trabajes solo:** `main` siempre funciona; el PR corre el CI antes de mezclar (si algo se
rompe, te enterás antes); y queda registro de qué entró y por qué.

**Buenos mensajes de commit:** una línea que diga **qué** y, si hace falta, un párrafo con el **por qué**.
`etapa-05: bronze con Auto Loader y schemaHints` sirve; `cambios` o `arreglo` no.

### 5. Ignorar lo que no va al repo

El archivo `.gitignore` lista lo que git no tiene que seguir. En este proyecto (lo escribís en la etapa 1):
el entorno virtual (`.venv/`), cachés (`__pycache__/`, `.pytest_cache/`), los datos locales de Spark
(`spark-warehouse/`, `metastore_db/`), la carpeta de estado del bundle (`.databricks/`) y archivos con IDs del
workspace (`genie/deployed_*.json`).

**Regla de oro: nunca subas un secreto** (token, contraseña) a un repo, ni siquiera privado. Los secretos van en
GitHub Secrets (capítulo 22) o en tu `~/.databrickscfg`, fuera del repo.

### 6. Tags y puntos de control

```bash
git tag -a etapa-01 -m "Cimientos"     # tag anotado (con autor, fecha y mensaje)
git push origin etapa-01                # los tags no se suben solos
git tag                                  # listar
git diff etapa-01 etapa-02 --stat       # qué cambió entre dos tags
git checkout etapa-01                    # ver el proyecto en ese punto ("detached HEAD": sólo mirar)
git switch main                          # volver
```

### 7. Proteger `main` (recomendado)

**Settings → Branches → Add branch ruleset** (o *Add rule*) → rama `main` → marcá **Require a pull request before
merging** y, cuando tengas CI (capítulo 22), **Require status checks to pass**. Así nadie (ni vos por apuro) sube
directo a `main` sin pasar el CI.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| un repo por proyecto | un monorepo con NovaMart y Andes | el bundle, el CI y los permisos son por repo; mezclados se pisan |
| ramas cortas + PR | commitear todo a `main` | sin PR no hay CI antes de mezclar ni registro de por qué |
| tags anotados | tags livianos (`git tag etapa-01`) | los anotados guardan autor, fecha y mensaje |
| merge commit | rebase y force-push | en ramas compartidas, reescribir la historia rompe las copias de los demás |

## ✅ Probalo

```bash
cd mi-andes-viento
echo "# Mi Andes Viento" > README.md
git switch -c prueba && git commit -am "Probar el ciclo" && git push -u origin prueba
```
Abrí el PR en GitHub, mergealo y borrá la rama. Después:
```bash
git switch main && git pull && git log --oneline     # 2-3 commits, el último es el merge
```

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `Support for password authentication was removed` | GitHub no acepta contraseñas | paso 2 (gh o PAT) |
| `! [rejected] main -> main (fetch first)` | GitHub tiene commits que vos no | `git pull` y después `git push` |
| `CONFLICT (content): Merge conflict in X` | los dos lados cambiaron las mismas líneas | abrí X, buscá `<<<<<<<` / `=======` / `>>>>>>>`, dejá la versión correcta, borrá las marcas, `git add X && git commit` |
| `fatal: not a git repository` | estás en otra carpeta | `cd mi-andes-viento` |
| subí un token sin querer | — | **revocalo ya** (borrarlo del repo no alcanza: queda en la historia) y creá uno nuevo |
| `detached HEAD` | hiciste checkout de un tag | `git switch main` |

## 📍 Punto de control

Un repo `mi-andes-viento` en GitHub, clonado en tu computadora, con `main` protegido y un PR mergeado.

## 🏋️ Ejercicio

1. Creá una rama `ejercicio`, agregá un archivo `NOTAS.md`, commiteá en dos commits separados y abrí un PR.
2. En GitHub, editá `NOTAS.md` desde la web en `main` (un cambio en la misma línea). Volvé a tu rama, hacé
   `git pull origin main` y resolvé el conflicto.
3. Poné un tag `practica` en tu último commit, subilo y borralo (`git push origin :refs/tags/practica`).
