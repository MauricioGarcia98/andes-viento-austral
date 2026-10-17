# Diagramas y animaciones

Todos se generan como código (`src/build_diagrams.py`) y son archivos `.excalidraw` normales: abrilos en
https://excalidraw.com (*File → Open*) para editarlos.

| # | diagrama | animado |
|---|---|---|
| 00 | [Proceso completo](00_proceso_completo.svg) | [SVG animado](../animations/proceso_completo.svg) |
| 01 | [La empresa: parques, bases y áreas](01_empresa.svg) | |
| 02 | [Arquitectura](02_arquitectura.svg) | [GIF](../animations/02_arquitectura.gif) |
| 03 | [Linaje de tablas](03_linaje.svg) | (excanim) |
| 04 | [Modelo estrella](04_modelo_estrella.svg) | |
| 05 | [Matriz bus](05_matriz_bus.svg) | |
| 06 | [SCD2 de una turbina](06_scd2.svg) | |
| 07 | [Ejecución de Spark](07_ejecucion_spark.svg) | |
| 08 | [DAG del job](08_dag_job.svg) | [SVG animado del run](../animations/job_run.svg) |
| 09 | [CI/CD](09_cicd.svg) | |
| 10 | [Ruta de aprendizaje](10_ruta_aprendizaje.svg) | [GIF](../animations/10_ruta_aprendizaje.gif) |
| 11 | [La capa Genie](11_capa_genie.svg) | |

Los `.excanim` (en `../animations/`) guardan el orden de aparición de cada elemento (`customData.step`).

## Regenerar

```bash
cd docs/diagrams/src && npm install && npm run bundle && cd -
CHROMIUM_PATH=/ruta/a/chromium ./docs/diagrams/build_all.sh
```
Íconos: librerías públicas de libraries.excalidraw.com (copiadas en `libraries/`).
