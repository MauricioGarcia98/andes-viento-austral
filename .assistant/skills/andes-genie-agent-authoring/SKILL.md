---
name: andes-genie-agent-authoring
description: Cómo crear o mejorar un Genie Agent de Andes Viento Austral (instrucciones, SQL de ejemplo, funciones confiables, benchmarks) y desplegarlo con la API. Usar cuando pidan "agregar una pregunta a Genie", "Genie responde mal", "nuevo agent" o "nuevo benchmark".
---

# Crear o mejorar un Genie Agent

Los agents se definen en YAML (`genie/src/NN_slug.yml`) y se compilan al `serialized_space` (`genie/agents/*.json`).
Nunca edites el JSON a mano ni cambies el agent sólo desde la UI: lo que no está en Git se pierde en el próximo deploy.

## Si Genie responde mal, en este orden
1. **¿Falta contexto en los datos?** Mejorá el COMMENT de la columna en `governance/data_dictionary.yml`
   (unidades, valores posibles, ejemplos) → `python scripts/build_governance.py` → task `governance` del job.
2. **¿Es una métrica con definición oficial?** Que viva en una metric view (`sql/semantic/01_metric_views.sql`) con
   `synonyms` en el vocabulario de la gente ("recorte", "limitación", "multa del fabricante").
3. **¿Tiene una respuesta certificada?** Función de UC en `sql/semantic/02_functions.sql` (parámetros con
   `DEFAULT NULL`, aceptar código o nombre de parque; **nunca parámetros `DATE`**: Genie rechaza el agent entero,
   usar `STRING 'yyyy-MM-dd'` y `to_date()` adentro) y agregarla a `functions:` del YAML.
4. **¿Es un patrón de SQL difícil?** Un `examples:` con la pregunta como la diría el usuario.
5. Recién al final, una línea más en `instructions:` (cortas: Genie las sigue mejor).

## Benchmarks
- Mínimo 20 por agent, cada uno con el SQL de la respuesta esperada (`benchmarks:` → `q` + `sql`).
- Usar `${catalog}` en el SQL (el deploy lo reemplaza por `andes_viento_dev` / `andes_viento`).
- Preguntas con respuesta única y estable (un número, un nombre) evalúan mejor que listas largas.
- Correr `python scripts/genie_eval.py --target dev` y mirar `docs/genie/resultados_benchmarks.md`.

## Desplegar
```bash
python scripts/build_genie.py            # valida que haya 20+ benchmarks
python scripts/deploy_genie.py --target dev
python scripts/genie_ask.py --agent 01_operacion_parques "¿Por qué Cañadón León generó menos en julio 2025?"
```

## Convenciones de las instrucciones
- "Hoy" = último día con datos, nunca `current_date()`.
- Parques por nombre (`ILIKE`) o código; clientes por nombre corto.
- Energía en MWh con 1 decimal, plata en USD sin decimales, porcentajes con 1 decimal.
