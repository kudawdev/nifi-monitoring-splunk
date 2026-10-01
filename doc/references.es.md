# Sourcetypes

Los distintos sourcetypes utilizados por la aplicación entregan un tipo de información que les corresponde. La mayoría provienen del input modular de la TA, que consulta la API REST de NiFi (la ruta **pull**); `nifi:reporting:task` y `nifi:reporting:bulletin` provienen de las reporting tasks propias de NiFi, que envían al HEC de Splunk (la ruta **push**) — ver [Compatibilidad y estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion).

### Logs

- **nifi:log:app** / **nifi:log:bootstrap**

El registro de la actividad propia de NiFi — carga de archivos, tiempos de ejecución, boletines generados por los componentes — desde `nifi-app.log` y `nifi-bootstrap.log`.

- **nifi:log:user**

El registro de la actividad web donde interactúan los usuarios de NiFi y las acciones que realizan (`nifi-user.log`).

- **nifi:log:request**

El log de requests de NiFi (`nifi-request.log`), en el mismo formato NCSA combined que el `access_combined` propio de Splunk. A diferencia de los demás logs, cada evento trae su propio timestamp — el momento del request, no el de la recolección.

- **nifi:log:deprecation**

Indica los componentes deprecados que una instancia todavía usa (`nifi-deprecation.log`); es el input para los reportes de migración al pasar entre versiones de NiFi.

### API REST (pull)

- **nifi:api:flow_status**

Información básica sobre el estado y el procesamiento de la instancia de NiFi, desde `/flow/status`.

- **nifi:api:system_diagnostics**

Recursos de sistema en uso y disponibles, desde `/system-diagnostics`. En un cluster es el agregado de todos los nodos.

- **nifi:api:node_diagnostics**

Diagnóstico de sistema por nodo en un cluster, un evento por miembro, desde `/system-diagnostics?nodewise=true`.

- **nifi:api:cluster_nodes**

Un evento por miembro del cluster desde `/controller/cluster`: estado, roles (Primary Node / Cluster Coordinator), heartbeat y los contadores propios de cola y threads del nodo. Solo se completa en un cluster.

- **nifi:api:process_groups_status**

Historial de estado de los process groups monitoreados, desde `/flow/process-groups/{id}/status/history`: un evento plano por snapshot (uno por minuto, por defecto), con la hora del propio snapshot, el id y el nombre del grupo y cada métrica como campo. El input retoma desde el último snapshot que escribió, así que cada uno se indexa una sola vez; un grupo configurado por primera vez trae solo su última hora.

- **nifi:api:processors_status**

Lo mismo para los procesadores monitoreados, desde `/flow/processors/{id}/status/history`.

- **nifi:api:process_groups_history**, **nifi:api:processors_history**

El historial anidado tal como lo envía el flujo push: la respuesta completa en un evento. La TA ya no los escribe; el dataset `Component_Status` lee las dos formas.

- **nifi:api:flow_metrics**

Muestras de métricas en formato Prometheus, desde `/flow/metrics/json`. Requiere NiFi 1.16 o superior y viene desactivado por defecto por el volumen que genera.

- **nifi:api:bulletin_board**

Boletines — errores y advertencias generados por los componentes — desde `/flow/bulletin-board`, mapeados a los mismos nombres de campo que `nifi:reporting:bulletin` para que ambas fuentes alimenten los mismos dashboards.

- **nifi:api:version_info**

La versión de la instancia de NiFi consultada, usada para habilitar endpoints y campos que dependen de la versión.

### Reporting tasks (push)

- **nifi:reporting:task**

Reportes internos de estado y métricas a un nivel más detallado que el flow status, enviados por la `SiteToSiteMetricsReportingTask` de NiFi.

- **nifi:reporting:bulletin**

Boletines internos donde se especifican errores ocurridos durante el funcionamiento, enviados por la `SiteToSiteBulletinReportingTask` de NiFi.

## Datamodel

El datamodel `NIFI` agrupa los sourcetypes por concepto, así un panel no necesita saber por qué camino de recolección llegó un evento:

| Dataset | Qué contiene | Lo alimenta |
|---|---|---|
| `Bulletins` | Todos los boletines; hijos `Bulletin_Board` (pull) y `Reporting_Bulletin` (push) | `nifi:api:bulletin_board`, `nifi:reporting:bulletin` |
| `Throughput` | Datos que entran, salen y escribe el flujo completo, como `bytes_in`, `bytes_out`, `bytes_written`, `flowfiles_in`, `flowfiles_out`; hijos `Reporting_Task` (push) y `Flow_Metrics_Root` (pull) | `nifi:reporting:task`, el `nifi:api:flow_metrics` del grupo raíz |
| `Component_Status` | Una fila por snapshot de estado de un componente, como `component_label`, `component_kind` y las métricas del lookup `nifi_status_metrics`; hijos `Processors` y `Process_Groups` | `nifi:api:*_status`, y el `nifi:api:*_history` del flujo push |
| `Flow_Status`, `System_Diagnostics`, `Node_Diagnostics`, `Cluster_Nodes`, `Flow_Metrics`, `Version_Info`, `Logs`, `Request_Log` | Un sourcetype cada uno | el de su nombre |

## Umbrales

Todas las vistas y todas las alertas leen los mismos umbrales, en dos niveles:

1. **Por instancia**, en la fila de la instancia en el inventario (*Configuration > NiFi Instances*). Una columna vacía significa que rige el macro.
2. **Para todas las instancias**, en los macros. Sobrescríbelos en `local/macros.conf` de `nifi_monitoring`.

| Columna del inventario | Macro | Por defecto | Significado |
|---|---|---|---|
| `heap_threshold` / `heap_threshold_critical` | `nifi_threshold_heap` / `nifi_threshold_heap_critical` | 85 / 95 | % del heap máximo que deja una instancia degradada / crítica |
| `repo_threshold` / `repo_threshold_critical` | `nifi_threshold_repo` / `nifi_threshold_repo_critical` | 80 / 90 | % del volumen de un repositorio |
| `backpressure_threshold` | `nifi_threshold_backpressure` | 80 | % del límite de objetos o de tamaño de una conexión |
| `bulletin_threshold` | `nifi_threshold_bulletins` | 5 | Boletines ERROR en `nifi_recent_window` que disparan la alerta de boletines |

Estos rigen para todas las instancias y no tienen columna en el inventario:

| Macro | Por defecto | Significado |
|---|---|---|
| `nifi_threshold_bulletins_degraded` | 1 | Boletines ERROR en `nifi_recent_window` que dejan una instancia degradada; súbelo para un NiFi cuyos flujos registran errores habitualmente |
| `nifi_recent_window` | `-15m` | Qué significa "ahora" para la salud y los conteos de boletines |
| `nifi_backpressure_horizon` | 3600 | Segundos hacia adelante en que la predicción de backpressure de NiFi se considera inminente |
| `nifi_heap_sustained_samples` | 3 | Muestras seguidas sobre el umbral de heap que espera la alerta de heap sostenido |
| `nifi_stale_factor` | 3 | Intervalos de polling sin datos que vuelven *stale* una instancia |
| `nifi_default_interval` | 60 | Segundos entre consultas, cuando no se puede leer el intervalo del input |

`nifi_fleet` arma una fila por instancia con los umbrales que le corresponden, y `nifi_health` convierte esa fila en `ok`, `degraded`, `critical`, `stale` o `no_data`, con un motivo. Los números de heap y de repositorio del Overview se colorean con el umbral de la instancia a la que pertenecen.
