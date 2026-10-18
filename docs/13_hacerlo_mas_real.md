# 13 · Cómo hacerlo más real

El proyecto simula una empresa con mucho detalle, pero hay cosas que en la vida real son distintas. Si querés llevarlo
a producción (o hacerlo más difícil para aprender), esto es lo que cambiaría.

## Datos y fuentes

| hoy (simulado) | en la realidad | cómo acercarse |
|---|---|---|
| Archivos en un Volume | SCADA vía OPC UA / MQTT → Kafka/Event Hubs; CMMS por API (SAP PM, Maximo) | Auto Loader sobre un bucket que llena un conector; `readStream.format("kafka")` |
| Energía medida por SCADA | Lo que se factura es el **medidor SMEC** de CAMMESA (15 min, en el punto de conexión) | agregar la fuente `smec_meter` y conciliar SCADA vs. medidor (pérdidas eléctricas internas ~2 %) |
| Precio spot inventado | CAMMESA publica precios, despacho y restricciones (DTE, PRIS) | descargar los archivos reales y adaptar el contrato de bronze |
| Curva de potencia cúbica | Curva certificada del fabricante por densidad de aire; corrección por altura y temperatura | tabla `power_curve` por modelo y densidad; potencial por interpolación |
| Clima del "proveedor" | ERA5, GFS, proveedores comerciales; pronóstico por ensamble | ingesta GRIB/NetCDF, P10/P50/P90 de pronóstico |
| Fallas con firma térmica | Además: espectro de vibraciones (CMS de alta frecuencia), análisis de aceite de laboratorio, boroscopías | fuente `cms_vibration` (espectros) y features de frecuencia |

## Negocio

- **PPA liquidado por hora**, con prioridad de despacho, cargos de transporte y el mecanismo de reasignación del MATER.
- **Contratos en pesos ajustables** (los viejos de RenovAr están en USD; algunos privados por CER/UVA).
- **Seguro y garantías**: las fallas mayores tienen deducibles; la grúa tiene ventanas de viento < 12 m/s.
- **Comunidades**: el agua de limpieza en la Puna requiere acuerdos con comunidades (HSE como dueño real del dato).
- **Regulación**: Resoluciones de la Secretaría de Energía cambian reglas del MATER y prioridad de despacho.

## Plataforma

- **Service principals** para correr jobs y para la App (no el usuario personal).
- **Grupos de cuenta** (`andes_operacion`, `andes_comercial`, ...) y ABAC con *governed tags* en vez de funciones a mano.
- **Predictive optimization** en vez del job de mantenimiento.
- **Lakehouse Monitoring** sobre `fact_turbine_10min` (drift de distribuciones de sensores).
- **Alertas SQL** y notificaciones a Slack/Teams cuando el quality gate falla o un PPA proyecta faltante.
- **MLflow + Model Serving** para el modelo de fallas, con features en Feature Engineering de UC.
- Ambientes separados por **workspace** (dev/prod) con el mismo metastore, no sólo por catálogo.
- **Delta Sharing** para mandarle a cada cliente PPA su liquidación.

## Genie

- Usuarios reales en grupos reales: medir el éxito por **preguntas respondidas sin ayuda** (logs de Genie).
- Revisar semanalmente las preguntas con 👎 y convertirlas en benchmarks.
- Benchmarks en el CI: `genie_eval.py` en un workflow nocturno; si baja el % de aciertos, se avisa.
