# 18 · Genie: Agents, benchmarks, Agent mode y Conversation API

> Teoría completa en [`docs/12_genie.md`](../docs/12_genie.md). Acá, la práctica.

## 1. Probá los 4 agents

Abrí **Genie** en el menú de la izquierda → "Andes · Operación de parques [dev]" y preguntá:

| agent | pregunta | qué tiene que hacer |
|---|---|---|
| Operación de parques | ¿Por qué Cañadón León generó menos en julio 2025? | llamar a `fn_explicar_desvio` |
| Mantenimiento predictivo | ¿Qué turbinas tienen riesgo alto hoy? | llamar a `fn_turbinas_en_riesgo` |
| Comercial PPA | ¿Vamos a llegar al volumen comprometido este mes? | llamar a `fn_proyeccion_ppa` |
| Finanzas y mercado | ¿En qué parque conviene poner baterías? | llamar a `fn_ranking_baterias` |

Fijate en el sello **"Trusted"** cuando la respuesta sale de una función de UC.

## 2. Corré los benchmarks

En cada agent: **Benchmarks → Run all**. Hay 20+ preguntas con el SQL esperado. Anotá cuáles fallan.
Desde la consola: `python scripts/genie_eval.py --target dev` (escribe `docs/genie/resultados_benchmarks.md`).

## 3. Agent mode (preguntas de "por qué")

En Genie One (o en un agent con *Agent mode* activado) preguntá las 5 de [`docs/genie/agent_mode.md`](../docs/genie/agent_mode.md)
y compará con la respuesta esperada. Agent mode arma un plan, corre varias consultas y explica.

## 4. Conversation API

```bash
python scripts/genie_ask.py --agent 03_comercial_ppa "¿Qué contrato tuvo más faltantes en 2025?" --follow "¿Y cuánto costó cubrirlos?"
```
Y la App: **Compute → Apps → andes-genie-chat**.

## Ejercicios

1. Un jefe de parque pregunta "¿cuánto hice ayer?". Genie no sabe qué parque. ¿Qué agregás: una instrucción, un ejemplo
   SQL o una función con `current_user()` + `ops.park_access`? Implementalo en `genie/src/01_operacion_parques.yml`.
2. Agregá 3 benchmarks nuevos al agent Comercial, corré `build_genie.py` y `deploy_genie.py`, y medí.
3. Encontrá una pregunta que el agent de Finanzas responda MAL. Arreglala siguiendo el orden de la skill
   `andes-genie-agent-authoring` (comentario → metric view → función → ejemplo → instrucción).
4. Exportá el space que modificaste en la UI con `deploy_genie.py --export <space_id>` y compará con el JSON del repo.

## Soluciones (orientativas)

1. Lo más robusto es una **función** `fn_mi_parque_ayer()` que lea `ops.park_access` con `current_user()`: Genie la usa
   como trusted asset y la respuesta respeta el row filter. Una instrucción sola ("si no dice el parque, preguntá cuál")
   también sirve como red de seguridad.
2. Ver `genie/src/03_comercial_ppa.yml`: cada benchmark es `q` + `sql` con `${catalog}`.
3. Típico: "precio de la energía" es ambiguo (spot vs. PPA). Solución: sinónimos en la metric view + una línea en las
   instrucciones ("aclarar siempre si es spot o PPA").
4. El export trae los `id` que generó la UI; si los cambios sirven, pasalos al YAML (la fuente de verdad).
