# 23 · Etapa 19 · Producción, operación y documentación

## 🎯 Objetivo

Cerrar el proyecto como se cierra en una empresa: **desplegarlo a producción**, dejarlo **operable** (datos diarios,
reparación, cuotas, evaluación periódica de Genie) y **documentado** para la próxima persona. También tres ajustes que
aparecieron recién operando de verdad y que conviene entender.

**Archivos de esta etapa:** `docs/`, `learning/`, `README.md` y diagramas. El código ya está completo; `etapa-19` es el
proyecto final.

## 📚 Conceptos

- **Dev vs. prod:** dev es donde se prueba (cada uno tiene su copia, se puede romper); prod es lo que usa la empresa
  (estable, con permisos más estrictos y cambios sólo desde el CI).
- **Operar:** que el sistema siga funcionando solo, con alertas cuando no, y que cualquiera del equipo sepa qué hacer.
- **Documentación para quien viene:** no "qué hace el código" (eso lo dice el código), sino **por qué** es así y **qué
  hacer** cuando algo pasa.

## 🧱 Paso a paso

### 1. Producción

```sql
CREATE CATALOG IF NOT EXISTS andes_viento COMMENT 'Andes Viento Austral (prod)';   -- una vez, por SQL
```
```bash
databricks bundle validate -t prod
databricks bundle deploy   -t prod      # o desde GitHub Actions con aprobación (capítulo 22)
databricks bundle run andes_e2e -t prod
python scripts/deploy_genie.py --target prod
```
Diferencias con dev: los recursos no llevan `[dev usuario]`, los agents no llevan `[dev]`, los schedules quedan como
dice el YAML (pausados hasta que los actives) y no hay App (capítulo 21).

### 2. Tres ajustes que aparecieron operando

**a) El mes en curso (R15).** Cuando el job diario trajo el 01-10-2026, la liquidación PPA comparó 1 día entregado contra
el mes entero comprometido (un "faltante" de USD 1,4 M) y el desvío vs. presupuesto dio −97 %. Arreglos:
- `fact_ppa_settlement`: un mes que **no cerró** no se liquida (`best_option = 'MES_ABIERTO'`, faltante NULL). La
  pregunta "¿vamos a llegar?" la responde la proyección (`mart_ppa_forecast`).
- `mart_generation_vs_budget`: el presupuesto del mes en curso se **prorratea** por los días transcurridos, según el
  **último día con datos de toda la empresa** (no de cada parque: un parque con el satélite caído un día no "abre" el
  mes). Columna `is_month_to_date`.

**Lección:** la carga histórica nunca ve meses parciales; el incremental sí. Probá el job diario antes de dar por bueno
un mart mensual.

**b) La cuota de 500 tablas (R14).** Free Edition cuenta también las tablas **borradas** durante su retención (~7
días). Cada `CREATE OR REPLACE VIEW` (también las metric views) crea un objeto nuevo y deja el viejo borrado: con 10
vistas y un job diario eran ~70 "fantasmas" por ambiente. El arreglo está en `gold/marts.py`:
```python
def run_sql_file(spark, cfg, path):
    fp_table = cfg.table("ops", "sql_fingerprints")
    for stmt in split_statements(render(path.read_text(encoding="utf-8"), cfg)):
        name = view_name(stmt)                     # ¿es un CREATE OR REPLACE VIEW?
        if name is None:
            spark.sql(stmt); continue
        sha = fingerprint(stmt)                    # sha256 del texto, sin importar espacios
        if known.get(name) == sha and spark.catalog.tableExists(name):
            continue                               # no cambió: no se recrea
        spark.sql(stmt)
        ...                                        # guardar la huella nueva
```
Cómo medir la cuota y qué borrar: [docs/19 · La cuota de 500 tablas](../docs/19_operacion_diaria.md#la-cuota-de-500-tablas).

**c) La regla de oro (R13).** Un arreglo aplicado a mano en el SQL Editor se deshizo en la corrida siguiente, porque el
job usa lo **desplegado**. Por eso: siempre `bundle deploy` antes de correr, y en prod, sólo desde el CI.

### 3. Operar

Todo el día a día está en [docs/19 · Operación diaria](../docs/19_operacion_diaria.md):
- activar los schedules del job diario y del de mantenimiento;
- el chequeo de 2 minutos (última corrida, gate, último día con datos, `ops.pipeline_runs`, `ops.dq_results`);
- qué hacer cuando algo falla (leer el error, la bitácora, arreglar, desplegar, **Repair run**, anotar);
- el circuito para cambiar algo sin romper nada;
- cuidar a Genie: preguntar después de cada deploy, convertir cada queja en un benchmark, evaluar una vez por mes.

### 4. Documentar

La documentación del proyecto (`docs/`) sigue una regla: **cada documento responde una pregunta de alguien**.

| pregunta | documento |
|---|---|
| ¿qué es esto y por dónde empiezo? | `00_empeza_aca` |
| ¿qué problema resuelve? | `01` (empresa), `03` (casos) |
| ¿por qué está hecho así? | `05` + ADRs, `07`, `09` |
| ¿cómo lo despliego? | `10` (terminal), `11` (web) |
| ¿qué salió mal y cómo se arregló? | `08` (bitácora) |
| ¿cómo se probó? | `18` |
| ¿qué hago cuando falla? | `19` |
| ¿cómo lo construyo yo? | este curso |

**La bitácora es lo más valioso.** Cada error con el mensaje real, cómo se encontró, el arreglo y la lección. Cuando a
alguien le pase lo mismo, busca el mensaje y encuentra la respuesta.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| prod desde el CI con aprobación | desplegar a mano | nadie puede decir qué versión está en prod |
| huellas para no recrear vistas | recrearlas siempre | en Free Edition, la cuota; en cualquier workspace, historia y permisos que se pierden |
| prorratear el mes en curso | excluirlo | Dirección quiere ver el mes en curso; prorrateado, el número es comparable |
| documentación por pregunta | un documento gigante | nadie lee 2.000 líneas; todos buscan la respuesta a su pregunta |

## ✅ Probalo

- `databricks bundle run andes_e2e -t prod`: 12/12 en verde.
- **Genie → Andes · Operación de parques** (sin `[dev]`) responde.
- `git diff etapa-19 HEAD --stat` en tu repo: **vacío o casi** (si hiciste los ejercicios, sólo tus agregados).

## 🔥 Si falla

Los errores de esta etapa son los de las anteriores, ahora en prod. El índice rápido está en
[docs/10 · Problemas típicos](../docs/10_despliegue_y_cicd.md#problemas-típicos-índice-rápido) y todos los reales, en la
[bitácora](../docs/08_bitacora.md).

## 📍 Punto de control

**`etapa-19` es el proyecto completo.** Si tu repo llegó hasta acá con todo en verde (tests, CI, job en dev y prod,
Genie respondiendo), lo construiste vos.

## 🏋️ Ejercicio

1. Activá el job diario en prod y dejalo correr una semana. Cada día, hacé el chequeo de 2 minutos. ¿Cuánto tarda cada
   corrida? ¿Crece la cuota de tablas?
2. Escribí una entrada nueva en la bitácora con el próximo error que te pase, con el formato de las demás.
3. Pasale el repo a alguien que no lo conozca y pedile que siga sólo `docs/00_empeza_aca.md`. Anotá dónde se trabó y
   mejorá ese documento.
