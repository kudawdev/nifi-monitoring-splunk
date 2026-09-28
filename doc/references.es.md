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

- **nifi:api:process_groups_history**

Historial de estado de los process groups monitoreados, desde `/flow/process-groups/{id}/status/history`.

- **nifi:api:processors_history**

Historial de estado de los procesadores monitoreados, desde `/flow/processors/{id}/status/history`.

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
