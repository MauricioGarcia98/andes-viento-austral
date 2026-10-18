# Agent mode: preguntas de "por qué" y la respuesta que debería encontrar

> Agent mode (en Genie One o activado en un Genie Agent) arma un **plan de varios pasos**: consulta, mira el
> resultado, decide la próxima consulta y al final explica. Estas preguntas no tienen una tabla con la respuesta:
> hay que **combinar** fuentes. Las respuestas esperadas salen de la corrida real en Free Edition
> (`scale_factor = 0.1`, catálogo `andes_viento_dev`, octubre 2026). Con otro `scale_factor` los porcentajes
> cambian algo; la historia, no.

Cómo evaluar una respuesta de Agent mode: ✅ encontró las causas principales con su orden de magnitud ·
⚠️ encontró algunas · ❌ inventó causas o no cuantificó.

---

## 1. "¿Por qué Cañadón León generó 18 % menos que el presupuesto en julio 2025?"

**Agent:** Operación de parques (o Finanzas y mercado) · **quién pregunta:** Lucía Ferreyra (CEO)

**Respuesta esperada** (`fn_explicar_desvio('Cañadón León', '2025-07')`):

| concepto | MWh | % del presupuesto |
|---|---:|---:|
| Presupuesto P50 | 6.988,5 | 100 % |
| Efecto del recurso: julio un poco menos ventoso | −279,9 | −4,0 % |
| Curtailment por encima de lo presupuestado | −527,8 | **−7,6 %** |
| Fallas y mantenimiento por encima de lo presupuestado | −55,6 | −0,8 % |
| Hielo en palas | −350,0 | **−5,0 %** |
| Otras (performance, huecos de dato) | −70,7 | −1,0 % |
| **Generación real** | **5.704,6** | **81,6 % → −18,4 %** |

Lo que un buen análisis agrega al revisar las causas:
- **Curtailment:** 14 instrucciones de CAMMESA con motivo `MANTENIMIENTO_ET` (10 al 20 de julio, tope del 50 %):
  819 MWh perdidos en el mes, contra 49 MWh en julio 2024. No es la congestión habitual: es un evento puntual de la red.
- **Hielo:** ola polar del 3 al 5 de julio (mínimas de −14 °C), días con condición "Hielo" en `dim_weather` el 4 y el 5.
- **Falla:** multiplicadora de LEO-01 el 26 de julio (orden correctiva MAYOR, 21 días de parada, ~USD 214 mil).
  En julio pesa poco (−0,8 %) porque entra a fin de mes: **el golpe grande va a agosto**.
- **Comparación:** San Julián Meseta (mismo fabricante, misma región) cayó sólo 3 %: el problema es local.

## 2. "¿Por qué Cerro Arenales también cayó en julio 2025 si no tuvo curtailment?"

**Respuesta esperada:** −16,8 % vs. presupuesto, sin curtailment extra (de hecho, 264 MWh menos curtailment que lo
presupuestado). Las causas son **clima**: menos viento (−12,4 %) y **hielo en palas (−11,4 %, 725 MWh)**. CRV está a
610 m de altura y es propenso a hielo. Una buena respuesta separa "problema de red" (LEO) de "problema de clima" (CRV).

## 3. "¿Por qué Hanse Turbinen Werke nos debe plata?"

**Agent:** Mantenimiento predictivo · **quién pregunta:** Ramiro Llancaqueo

**Respuesta esperada:**
- En 2025 la disponibilidad contractual de HTW fue **96,7 %** (garantía 97 %) contra 99,6 % de Aurora y 99,4 % de Pampa
  Eólica Industrial.
- La causa es un **lote defectuoso de multiplicadoras**: 13 fallas mayores en 2024 y 10 en 2025 (casi todas de HTW),
  contra 1 en 2023.
- Las 4 plantas HTW (Cañadón León, Pico Truncado Alto, Bahía Deseado, San Julián Meseta) tienen meses con la móvil de
  12 meses debajo de 97 %. Pico Truncado es la peor (92,6 % en nov-2025).
- *Liquidated damages* devengados en 2025: **≈ USD 659 mil** (`fn_reclamos_garantia(2025)`).
- Las horas de ruta cortada por nieve son fuerza mayor y NO se reclaman.

## 4. "¿Por qué el mantenimiento costó 4 veces más en dólares en 2024 que en 2023?"

**Agent:** Finanzas y mercado · **quién pregunta:** Diego Achával (CFO)

| año | órdenes | fallas mayores | mano de obra (millones ARS) | mano de obra (USD) | repuestos (USD) | grúas (USD) | total (USD) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 147 | 1 | 111 | 390 mil | 317 mil | 0 | 716 mil |
| 2024 | 165 | 13 | 583 | 618 mil | 1,94 M | 528 mil | **3,09 M** |
| 2025 | 158 | 10 | 753 | 599 mil | 1,68 M | 459 mil | 2,75 M |

**Respuesta esperada:** dos efectos distintos que hay que separar.
1. **Fallas mayores** (de 1 a 13 por el lote HTW): repuestos importados (multiplicadoras de ~USD 140 mil) y grúas de
   600 t. Explican casi todo el salto.
2. **Mano de obra en pesos x5** (111 → 583 millones) por la inflación de 2024; en dólares sube sólo 58 %, porque la
   devaluación de dic-2023 abarató el peso. En 2025, con inflación baja y dólar que sube menos, la mano de obra en
   USD casi no cambia aunque en pesos sube 29 %.

Trampa: comparar costos en pesos entre años con 200 % de inflación no dice nada. Siempre en USD (o a moneda constante).

## 5. "¿Por qué tuvimos que pagar penalidades al data center en 2025?"

**Agent:** Comercial PPA · **quién pregunta:** Sofía Bertolini

**Respuesta esperada:**
- El contrato PPA-2023-007 (Data Center Austral) compromete **13.237 MWh/mes planos** desde la adenda de jun-2024
  (+20 %), sacados de San Julián Meseta y Cañadón León (los dos parques más al final de la línea).
- Faltantes: jun-2024, ago-2024, **jun-2025 (3.399 MWh)**, jul-2025 y ago-2025. Son meses de invierno con poco viento.
  En julio-agosto 2025 se suman el curtailment de LEO y la multiplicadora rota.
- Cumplimiento 2025: **96,6 %** (tolerancia 3 %). Costo de los faltantes 2025 con la mejor opción: **≈ USD 225 mil**.
- En todos los casos **convenía pagar la penalidad** (55 USD/MWh) antes que comprar en el spot de invierno.
- Lo que habilita: renegociar un perfil estacional (menos volumen en invierno) o sumar un parque con otro régimen de viento.

## 6. "¿Conviene poner baterías en Santa Cruz para no perder el curtailment?"

**Agent:** Finanzas y mercado · **quién pregunta:** Diego Achával (CFO)

**Respuesta esperada (contraintuitiva):** **hoy no.**
- En 2025 el nodo Patagonia perdió **10.856 MWh** por curtailment. A precio spot valen sólo **USD 146 mil**, porque en
  las horas con orden de CAMMESA el spot del nodo cae a **15 USD/MWh** (contra 49 sin orden: el nodo se desacopla).
- La mejor opción (`fn_ranking_baterias(12)`) es una BESS-30x2 en Cañadón León: recupera ~517 MWh/año (≈ USD 39 mil),
  con un CAPEX de ~USD 3 M. **Repago simple de ~78 años.**
- ¿Por qué tan poco? El curtailment llega en eventos largos (días enteros, como el mantenimiento de la ET de julio
  2025): una batería de 2-4 horas se llena en la primera hora y el resto se pierde igual.
- Lo que haría cambiar la decisión: CAPEX más bajo, ingresos por servicios de red (regulación de frecuencia) o
  curtailment más frecuente y más corto.

## 7. "¿Por qué Susques genera menos en septiembre si hay más sol?"

**Agent:** Operación de parques · **quién pregunta:** Rodrigo Colque (jefe de Susques)

**Respuesta esperada:** suciedad. La pérdida estimada por polvo de Susques pasa de 0,4-0,6 % en verano (las lluvias
del "invierno altiplánico" limpian los paneles) a **4,5 % en julio-agosto y 11,1 % en septiembre 2025** (tormentas
de polvo de la temporada seca). La regla económica (`mart_panel_cleaning`) recomienda **LIMPIAR** varios días de
septiembre (lo perdido desde la última limpieza superó su costo), mientras la política histórica limpiaba "cada ~75 días".
Con los sensores de suciedad instalados en jun-2025 se puede validar la estimación (`soiling_sensor_pct`).
