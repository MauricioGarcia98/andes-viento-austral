# 🛠️ Construilo vos: Andes Viento Austral desde un repo vacío

> **Qué es esto:** un curso para que puedas **borrar todo** (el proyecto en Databricks y el repo en GitHub) y
> **volver a construirlo vos mismo**, sin pedirle a una IA que lo haga. Archivo por archivo y en el orden en que
> se construyó, con cada bloque de código explicado: **qué hace, por qué se hizo así y no de otra forma, qué
> problemas vas a encontrar y cómo se resuelven**.
>
> No es lo mismo que las guías de despliegue ([docs/10](../docs/10_despliegue_y_cicd.md) y
> [docs/11](../docs/11_guia_desde_la_web.md)). Esas te enseñan a **desplegar** el código terminado; esto te enseña
> a **escribirlo**.

## Para quién es

Para alguien que sabe un poco de programación (variables, funciones, un `SELECT`) y quiere dominar de verdad
**Databricks**, **GitHub** y **CI/CD** construyendo un proyecto real. Si nunca programaste, empezá por los módulos 00 a
07 de [learning/](../learning/README.md) (SQL) y volvé.

## Qué vas a saber hacer al terminar

- Organizar un proyecto de datos como un paquete de Python testeable, con lint y tests.
- Generar datos sintéticos realistas y reproducibles con Spark.
- Construir un pipeline medallion completo: Auto Loader, limpieza, SCD2, CDC, modelo dimensional y marts.
- Proteger la calidad: reglas por fila, cuarentena y un *quality gate* que frena la publicación.
- Llevar todo a Databricks como código: Asset Bundles, jobs con condiciones y *for each*, pipelines declarativos.
- Gobernar los datos: comentarios, claves, tags, máscaras y filtros por fila en Unity Catalog.
- Preparar los datos para Genie (metric views, funciones certificadas) y versionar los Genie Agents como código,
  con una evaluación automática.
- Automatizar con GitHub Actions: lint, tests, validación y despliegue con aprobación.
- Operar el proyecto: datos diarios, reparar corridas, cuidar las cuotas y diagnosticar errores.

## Cómo está armado

**Parte 0: borrar todo.** El orden correcto para desmontar el proyecto sin dejar restos ni perder la referencia.

**Parte 1: fundamentos.** Las herramientas, antes de usarlas.

**Parte 2: construcción.** 19 etapas. Cada una termina en un **punto de control**: un tag de git con el proyecto
exactamente como tiene que quedar al terminar esa etapa.

**Parte 3: examen final.** Un caso de negocio nuevo, de punta a punta, sin mirar.

| # | capítulo | tag al terminar | tiempo |
|---|---|---|---|
| 00 | este documento | — | 15 min |
| **Parte 0** | | | |
| 01 | [Borrar todo (y guardar la referencia)](01_borrar_todo.md) | — | 30 min |
| **Parte 1 · Fundamentos** | | | |
| 02 | [Git y GitHub](02_git_y_github.md) | — | 2 h |
| 03 | [Python, entornos, lint y tests](03_python_y_herramientas.md) | — | 1 h 30 |
| 04 | [La plataforma Databricks](04_databricks_fundamentos.md) | — | 2 h |
| **Parte 2 · Construcción** | | | |
| 05 | [Cimientos: paquete, configuración y utilidades](05_etapa01_cimientos.md) | `etapa-01` | 2 h |
| 06 | [La empresa en código y la física](06_etapa02_empresa_y_fisica.md) | `etapa-02` | 2 h |
| 07 | [Eventos: lo que le pasa a la empresa](07_etapa03_eventos.md) | `etapa-03` | 2 h |
| 08 | [Las 11 fuentes sucias](08_etapa04_fuentes.md) | `etapa-04` | 3 h |
| 09 | [Bronze con Auto Loader](09_etapa05_bronze.md) | `etapa-05` | 1 h 30 |
| 10 | [Silver I: limpiar](10_etapa06_silver_transformaciones.md) | `etapa-06` | 3 h |
| 11 | [Silver II: cargar, SCD2 y CDC](11_etapa07_silver_carga.md) | `etapa-07` | 2 h |
| 12 | [Gold: dimensiones y hechos](12_etapa08_gold.md) | `etapa-08` | 3 h |
| 13 | [Marts en SQL](13_etapa09_marts.md) | `etapa-09` | 3 h |
| 14 | [Quality gate y el pipeline completo en local](14_etapa10_gate_y_e2e.md) | `etapa-10` | 1 h 30 |
| 15 | [Asset Bundle, notebooks y el job principal](15_etapa11_bundle_y_job.md) | `etapa-11` | 3 h |
| 16 | [Job diario, mantenimiento y LDP](16_etapa12_jobs_y_ldp.md) | `etapa-12` | 2 h |
| 17 | [Gobierno en Unity Catalog](17_etapa13_gobierno.md) | `etapa-13` | 2 h |
| 18 | [Capa semántica: metric views y funciones](18_etapa14_semantica.md) | `etapa-14` | 2 h |
| 19 | [Dashboards como código](19_etapa15_dashboards.md) | `etapa-15` | 1 h |
| 20 | [Genie como código](20_etapa16_genie.md) | `etapa-16` | 3 h |
| 21 | [La App y Genie Code](21_etapa17_app_y_genie_code.md) | `etapa-17` | 1 h |
| 22 | [CI/CD con GitHub Actions](22_etapa18_cicd.md) | `etapa-18` | 2 h |
| 23 | [Producción, operación y documentación](23_etapa19_prod_y_operacion.md) | `etapa-19` | 2 h |
| **Parte 3** | | | |
| 24 | [Examen final](24_examen_final.md) | — | 1-2 días |

Total: unas **45-50 horas**. A un capítulo por día, unas 5 semanas.

## Cómo es cada capítulo

Todos los capítulos de construcción tienen las mismas secciones:

1. **🎯 Objetivo**: qué vas a tener al final y por qué esta etapa va en este lugar.
2. **📚 Conceptos**: la teoría mínima, explicada desde cero.
3. **🧱 Paso a paso**: qué archivo crear y qué escribir. El código se explica **por bloques**. Lo trivial (imports,
   prints) se nombra sin explicar.
4. **🤔 Por qué así y no de otra forma**: las alternativas y por qué no se eligieron.
5. **✅ Probalo**: el comando exacto y lo que tenés que ver.
6. **🔥 Si falla**: los errores reales de esa etapa (con el mensaje) y cómo resolverlos.
7. **📍 Punto de control**: cómo comparar tu código con el tag.
8. **🏋️ Ejercicio**: una variante para hacer sin copiar.

## Los puntos de control (cómo usar los tags)

La rama `curso` del repo de referencia tiene **un commit por etapa**, cada uno con un tag (`etapa-01` ... `etapa-19`).
En cada etapa el proyecto compila, pasa el lint y pasa sus tests. `etapa-19` es el proyecto final completo.

```bash
# una vez: clonar la referencia en una carpeta APARTE de la tuya
git clone https://github.com/MauricioGarcia98/andes-viento-austral.git andes-referencia
cd andes-referencia
git fetch origin curso --tags

git checkout etapa-05                    # ver el proyecto como queda al terminar la etapa 5
git diff etapa-04 etapa-05 --stat        # qué archivos agrega la etapa 5
git diff etapa-04 etapa-05               # exactamente qué líneas agrega
git show etapa-05:src/andes_viento/ingestion/bronze.py    # un archivo de esa etapa
```

Y para comparar **tu** versión con la de referencia (desde tu repo):
```bash
git remote add referencia https://github.com/MauricioGarcia98/andes-viento-austral.git
git fetch referencia --tags
git diff etapa-05 HEAD -- src/andes_viento/ingestion/bronze.py   # tu archivo contra el de referencia
```

## Reglas para que sirva

1. **Escribí el código vos**, aunque lo estés leyendo de al lado. Copiar y pegar enseña a copiar y pegar. Tipear te
   obliga a leer cada línea y a preguntarte por qué está.
2. **No avances sin que el "✅ Probalo" dé lo esperado.** Cada etapa se apoya en la anterior.
3. **Cuando algo falle, primero leé el error entero.** Después buscalo en el "🔥 Si falla" del capítulo y en la
   [bitácora](../docs/08_bitacora.md). Recién después compará con el tag.
4. **Commiteá al final de cada etapa** con un mensaje claro (`etapa-05: bronze con Auto Loader`). Es tu propio
   punto de control.
5. **Hacé el ejercicio.** Es la diferencia entre "lo seguí" y "lo sé hacer".

## Qué necesitás

- Una computadora con macOS, Linux o Windows (con WSL recomendado), 8 GB de RAM y ~5 GB libres.
- Una cuenta de GitHub (gratis) y una de Databricks Free Edition (gratis).
- Las herramientas se instalan en los capítulos 02, 03 y 04.

## Si te trabás

| problema | dónde mirar |
|---|---|
| un error que no entendés | el "🔥 Si falla" del capítulo → [bitácora](../docs/08_bitacora.md) → [FAQ](../docs/14_faq.md) |
| una palabra que no conocés | [glosario](../docs/15_glosario.md) |
| tu código no hace lo mismo que el de referencia | `git diff etapa-NN HEAD -- <archivo>` |
| querés entender una decisión grande | [ADRs](../docs/05_arquitectura.md#decisiones-adrs) |
| querés ver la cronología original | [docs/17 · Cómo se construyó](../docs/17_como_se_construyo.md) |
