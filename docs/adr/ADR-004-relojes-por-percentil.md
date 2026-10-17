# ADR-004 · Relojes desfasados y husos cambiados con un solo método

**Contexto.** Algunas turbinas tienen el reloj corrido varios minutos; el SCADA de Pampa del Castillo pasó a
mandar UTC en abril 2024 sin avisar; los re-envíos satelitales llegan horas tarde.

**Decisión.** El concentrador del parque sella `received_at` con hora de GPS. Para cada turbina y día de
recepción se calcula el **percentil 5** de `received_at - ts`: es la demora mínima. Si vale ±2 min o más, se
corrige; si vale ~±3 h, es un cambio de huso (`tz_corrected`). El percentil bajo ignora los re-envíos tardíos.

**Consecuencias.** Un método simple, explicable y vectorizado resuelve dos problemas. Requiere que haya
lecturas "normales" el mismo día de recepción (siempre las hay salvo cortes de más de 24 h).
