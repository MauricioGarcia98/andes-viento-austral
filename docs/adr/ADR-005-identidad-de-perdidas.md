# ADR-005 · La descomposición de pérdidas vive en el hecho de 10 minutos

**Decisión.** Cada fila de `fact_turbine_10min` tiene `potential_kwh` (curva de potencia × viento medido, o el
viento medio del parque si el anemómetro está clavado) y la pérdida asignada a UNA causa según el estado de la
turbina (`LIMITADA_RED`, `FALLA`, `MANTENIMIENTO`, `HIELO`, resto = "otras").

**Por qué.** Así "¿por qué generamos menos?" se responde sumando columnas, en cualquier agregación (parque,
mes, fabricante, hora), y los dashboards, los marts y Genie coinciden. La cascada mensual
(`mart_generation_vs_budget`) cierra por construcción (lo controla el quality gate).
