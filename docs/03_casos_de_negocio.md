# 03 · Casos de negocio

Cada caso sigue el mismo formato: **problema → quién lo sufre → decisión que habilita → KPI de éxito → datos
necesarios → tablas gold/marts → dashboard → preguntas para Genie**. Más un caso transversal: el "¿por qué?"
que se responde con Agent mode.

<details open>
<summary><b>Caso 0 (transversal) · "¿Por qué el parque X generó 18 % menos en julio?"</b></summary>

| | |
|---|---|
| **Problema** | Todos los meses el directorio ve un desvío contra el presupuesto y nadie puede explicar cuánto es viento, cuánto red, cuánto fallas. Cada área tira la pelota a otra. |
| **Quién lo sufre** | Lucía Ferreyra (CEO) frente al directorio; Diego Achával (CFO) frente a los bancos. |
| **Decisión que habilita** | Dónde poner la plata y la atención: ¿baterías (red), repuestos en stock (fallas), anti-hielo (clima)? |
| **KPI de éxito** | ≥ 95 % del desvío explicado por causas con nombre (`lost_other_mwh` chico). |
| **Datos** | SCADA (viento, potencia, estado), instrucciones de CAMMESA, órdenes del CMMS, clima, presupuesto P50. |
| **Tablas** | `gold.mart_generation_vs_budget` (cascada mensual), `gold.v_park_daily`, `gold.fn_explicar_desvio()` |
| **Dashboard** | `Andes · Dirección · Generación vs presupuesto` |
| **Genie** | Agent mode: "¿Por qué Cañadón León generó 18 % menos que el presupuesto en julio 2025?" (real a SF 0,1: −18,4 %) → ver [genie/agent_mode.md](genie/agent_mode.md) |

La identidad que lo hace posible:
```
real = presupuesto + efecto del recurso − (curtailment − lo presupuestado) − (fallas + mant. − lo presupuestado)
              − hielo − suciedad − otras
```
</details>

<details>
<summary><b>Caso 1 · Energía perdida por curtailment: ¿en qué parque conviene invertir en baterías?</b></summary>

| | |
|---|---|
| **Problema** | La línea de 500 kV que saca la energía de la Patagonia está saturada. Cuando sopla fuerte y la demanda es baja (noches, fines de semana, feriados, primavera) CAMMESA ordena bajar potencia. Esa energía se tira. |
| **Quién lo sufre** | Finanzas (ingresos que no entran), Comercial (faltantes de PPA), jefes de parque de Santa Cruz (los más "al final de la línea"). |
| **Decisión que habilita** | Invertir o no en un sistema de baterías (BESS), de qué tamaño y en qué parque. |
| **KPI de éxito** | Repago simple < 8 años; MWh recuperados / MWh curtaileados. |
| **Datos** | Instrucciones de despacho de CAMMESA (con versiones y anulaciones), SCADA (potencial vs. generado), precio spot horario por nodo, precio de los PPA. |
| **Tablas** | `gold.fact_curtailment_hourly`, `gold.mart_curtailment_battery`, `gold.mv_curtailment`, `gold.fn_ranking_baterias()`, `gold.fn_perdida_curtailment()` |
| **Dashboard** | `Andes · Caso 1 · Curtailment y baterías` |
| **Genie (Finanzas y mercado)** | "¿Cuántos MWh y USD perdimos por curtailment en 2025?" · "¿En qué parque conviene invertir en baterías?" · "¿A qué hora nos limitan más?" · "¿Por qué el curtailment valorizado a spot es tan bajo?" (el nodo Patagonia se desacopla y el precio cae justo cuando nos recortan) |

**Trampa didáctica:** a precio spot el curtailment "vale poco" porque, con la línea saturada, el precio del nodo
Patagonia se derrumba. Pero esa energía estaba comprometida en PPA a ~65 USD/MWh. Valorizar con el precio
equivocado lleva a no invertir nunca en baterías.
</details>

<details>
<summary><b>Caso 2 · Mantenimiento predictivo: multiplicadoras y rodamientos</b></summary>

| | |
|---|---|
| **Problema** | Una multiplicadora rota en Santa Cruz en invierno = **3 semanas parada**: repuesto importado, grúa de 600 t desde Comodoro, ruta con nieve. Hoy se entera cuando salta la alarma. |
| **Quién lo sufre** | Ramiro Llancaqueo (Mantenimiento), los jefes de parque, Comercial (energía que falta para los PPA). |
| **Decisión que habilita** | Abrir una orden **predictiva**: pedir el repuesto y reservar la grúa días antes, parar en una ventana de poco viento. |
| **KPI de éxito** | ≥ 70 % de las fallas mayores con alerta ALTA ≥ 7 días antes; < 2 falsas alarmas por turbina-año. |
| **Datos** | SCADA de temperaturas (rodamiento de multiplicadora, principal, generador), vibraciones, alarmas, partículas en aceite (HT-OS 5.0); historia de componentes (SCD2); órdenes correctivas para etiquetar. |
| **Tablas** | `gold.mart_turbine_health`, `gold.fact_maintenance_order`, `gold.dim_turbine` (SCD2), `gold.mv_salud_turbinas`, `gold.fn_turbinas_en_riesgo()` |
| **Dashboard** | `Andes · Caso 2 · Mantenimiento predictivo` |
| **Genie (Mantenimiento predictivo)** | "¿Qué turbinas tienen riesgo alto hoy?" · "¿Con cuántos días de anticipación detectamos las fallas de 2025?" · "¿Cuánto tarda en promedio el cambio de una multiplicadora en Santa Cruz vs. Chubut?" |

**Idea clave:** no se compara la temperatura contra un umbral fijo (en verano todo calienta), sino contra las
**otras turbinas del mismo parque el mismo día** (mismo viento, misma temperatura ambiente). El 15 % de las fallas
del generador son "sorpresa" (sin firma previa): el modelo no las ve y está bien que no las vea.
</details>

<details>
<summary><b>Caso 3 · Limpieza de paneles en la Puna</b></summary>

| | |
|---|---|
| **Problema** | El polvo de la Puna baja la generación de a poco (y de golpe con las tormentas de agosto-octubre). Limpiar cuesta agua transportada en camión cisterna (escasa, cara y sensible para las comunidades) y una cuadrilla de 8 personas. Hoy se limpia "cada ~75 días". |
| **Quién lo sufre** | Jefes de parque solares (Rodrigo Colque, Natalia Mamaní...), HSE (agua), Comercial (contrato con Litio de la Puna). |
| **Decisión que habilita** | Cuándo limpiar cada parque: limpiar cuando lo perdido desde la última limpieza supera el costo de limpiar, salvo que el pronóstico traiga lluvia. |
| **KPI de éxito** | Pérdida por suciedad < 3 % anual con igual o menos agua por MWh generado. |
| **Datos** | Inversores cada 5 min (irradiancia, temperatura de módulo, potencia DC/AC), sensores de suciedad (desde jun-2025), órdenes de limpieza (agua, costo), pronóstico de lluvia, precio PPA. |
| **Tablas** | `gold.fact_inverter_hourly`, `gold.mart_panel_cleaning`, `gold.mv_limpieza`, `gold.fn_recomendacion_limpieza()` |
| **Dashboard** | `Andes · Caso 3 · Limpieza de paneles` |
| **Genie (Operación de parques)** | "¿Qué parques solares conviene limpiar hoy?" · "¿Cuánta energía perdimos por suciedad en Susques en 2025?" · "¿La estimación de suciedad coincide con los sensores nuevos?" |
</details>

<details>
<summary><b>Caso 4 · Cumplimiento de PPA: ¿spot o penalidad?</b></summary>

| | |
|---|---|
| **Problema** | Los contratos comprometen un volumen mensual **plano**, pero el viento no es plano (invierno flojo) y el curtailment se lleva justo lo de Santa Cruz. A mitad de mes nadie sabe si va a llegar. |
| **Quién lo sufre** | Sofía Bertolini (Comercial), los clientes (Data Center Austral amplió 20 % su volumen en 2024), Finanzas. |
| **Decisión que habilita** | A mitad de mes: comprar el faltante en el spot (si está barato) o aceptar la penalidad (si el spot está caro). |
| **KPI de éxito** | Costo de faltantes = mínimo entre penalidad y compra spot en ≥ 90 % de los meses. |
| **Datos** | Contratos (SCD2 con adendas de precio y volumen), generación diaria por parque, presupuesto diario, precio spot de los últimos 14 días. |
| **Tablas** | `gold.fact_ppa_settlement` (mensual), `gold.mart_ppa_forecast` (diario "as of"), `gold.dim_contract`, `gold.mv_ppa`, `gold.fn_proyeccion_ppa()` |
| **Dashboard** | `Andes · Caso 4 · Cumplimiento PPA` |
| **Genie (Comercial PPA)** | "¿Vamos a llegar al volumen comprometido este mes con cada cliente?" · "¿Conviene comprar en el spot o pagar la penalidad con el data center?" · "¿Qué contrato tuvo más faltantes en 2025?" |
</details>

<details>
<summary><b>Caso 5 · Disponibilidad contractual vs. garantía del fabricante (97 %)</b></summary>

| | |
|---|---|
| **Problema** | Los fabricantes garantizan 97 % de disponibilidad (ventana móvil de 12 meses). Si queda debajo, pagan *liquidated damages*. Pero el cálculo contractual excluye horas (red, hielo, mantenimiento programado, fuerza mayor) y nadie lo calcula igual que el fabricante. |
| **Quién lo sufre** | Ramiro Llancaqueo (Mantenimiento) y Legal: dejan plata sobre la mesa. |
| **Decisión que habilita** | Reclamar al fabricante con un cálculo defendible, mes por mes. |
| **KPI de éxito** | 100 % de los meses reclamables identificados; cálculo reproducible. |
| **Datos** | Estados de la turbina cada 10 min (falla, mantenimiento, hielo, red, sin dato), órdenes con demoras por ruta cortada (fuerza mayor), potencia instalada, términos de garantía por fabricante. |
| **Tablas** | `gold.fact_availability_daily`, `gold.mart_warranty_claims`, `gold.mv_disponibilidad`, `gold.fn_reclamos_garantia()` |
| **Dashboard** | `Andes · Caso 5 · Garantía del fabricante` |
| **Genie (Mantenimiento predictivo)** | "¿Corresponde reclamarle a Hanse Turbinen Werke este año?" · "¿Cuánto hay devengado de liquidated damages?" · "¿Por qué cayó la disponibilidad de Santa Cruz en el invierno 2025?" |
</details>

## Matriz caso × área × agent

| caso | Dirección | Operación | Mantenimiento | Comercial | Finanzas | HSE | agent |
|---|:-:|:-:|:-:|:-:|:-:|:-:|---|
| 0 · ¿Por qué generamos menos? | ● | ● | ○ | ○ | ● | | Agent mode (Genie One) |
| 1 · Curtailment y baterías | ○ | ○ | | ○ | ● | | Finanzas y mercado |
| 2 · Mantenimiento predictivo | | ○ | ● | | | | Mantenimiento predictivo |
| 3 · Limpieza de paneles | | ● | | ○ | | ● | Operación de parques |
| 4 · Cumplimiento PPA | ○ | | | ● | ○ | | Comercial PPA |
| 5 · Garantía del fabricante | | | ● | | ○ | | Mantenimiento predictivo |

● dueño · ○ interesado
