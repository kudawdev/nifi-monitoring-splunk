# Splunkbase 2.0.0 — material de publicación

Capturas para las fichas de Splunkbase, una carpeta por app. El prefijo
numérico es el orden de subida: la primera es la portada de la ficha.

Reemplazan **todas** las capturas de la 1.2.3: eran de 2021 (Simple XML, menús
que ya no existen) y tres mostraban el host `nifi01.entelbd.local`, de un
cliente. Las del TA eran dos imágenes subidas dos veces cada una.

## Nifi Monitoring for Splunk — https://splunkbase.splunk.com/app/6125

| Archivo | Origen | Nota |
|---|---|---|
| `nifi_monitoring/01_overview.png` | `doc/assets/images/splunk/view_overview.png` | Portada |
| `nifi_monitoring/02_instance.png` | `view_instance.png` | Recortada a 1600×1080: estado, "Now" y "JVM and system" |
| `nifi_monitoring/03_components.png` | `view_components.png` | |
| `nifi_monitoring/04_bulletins.png` | `view_bulletins.png` | |
| `nifi_monitoring/05_cluster.png` | `view_cluster.png` | |
| `nifi_monitoring/06_logs.png` | `view_logs.png` | |
| `nifi_monitoring/07_alerts.png` | `view_alerts.png` | Recortada a 1600×875: sin el panel "Fired" vacío |

## Nifi Monitoring TA — https://splunkbase.splunk.com/app/6124

| Archivo | Origen | Nota |
|---|---|---|
| `nifi_TA_monitoring/01_input_form.png` | `ta_input_form.png` | Portada |
| `nifi_TA_monitoring/02_inputs_created.png` | `ta_inputs_created.png` | |
| `nifi_TA_monitoring/03_collection_health.png` | `view_collection_health.png` | Vista de la app, responde "¿la recolección funciona?" |

## Corregir en la ficha al publicar

- **App, requisitos:** dice Splunk 8.2 y pide la visualización *Status
  Indicator*. La 2.0.0 es Splunk 9.4–10.x y solo depende de *Lookup File
  Editor* (app 1724).
- **Ambas, compatibilidad:** declaran 10.2–10.6; debe coincidir con
  `doc/compatibility.md` (Splunk 9.4–10.x).
