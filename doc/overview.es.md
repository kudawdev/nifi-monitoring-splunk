# Vista General

Dentro de Splunk, el menú propio de la app es:

- Home
- Nifi Monitor Overview
- Nifi Instance Panels
    - Flow's & Metrics Monitoring Panel
    - Bulletin Monitoring Panel
    - Logs Monitoring Panel
    - Status History
- Configuration
    - NiFi Instances
    - Internal Monitoring
- Alerts
- Search

## Home

Un diagrama de dónde viene la información de la app.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

## Nifi Monitor Overview

Un resumen de todas las instancias de NiFi monitoreadas:

- Estado del servidor por nodo
- Estado de repositorios por nodo
- Comportamiento de errores de bulletin por nodo

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview.png)

## Nifi Instance Panels

Detalle por nodo.

### Flow's & Metrics Monitoring Panel

Operación y uso de recursos del nodo a lo largo del tiempo, con
selectores de escala para distintos volúmenes de datos y métricas de JVM
por nodo.

![image](/nifi-monitoring-splunk/assets/images/splunk/monitoring_panel.png)
![image](/nifi-monitoring-splunk/assets/images/splunk/behaviour_overtime_1.png)
![image](/nifi-monitoring-splunk/assets/images/splunk/behaviour_overtime_2.png)

### Bulletin Monitoring Panel

Errores tipo bulletin generados por los componentes de NiFi, para
trazabilidad cuando algo falla.

![image](/nifi-monitoring-splunk/assets/images/splunk/bulletin_panel.png)

### Logs Monitoring Panel

Logs de aplicación, bootstrap, usuario y request de NiFi de cada
instancia configurada, buscables sin abrir una terminal en cada host.

![image](/nifi-monitoring-splunk/assets/images/splunk/logs_panel.png)

### Status History

Status history de los procesadores y grupos de procesos configurados en
[Status history](configuration-pull.es.md#4-status-history) — throughput,
flow files en cola y los demás contadores del Status History propio de
NiFi, por instancia a lo largo del tiempo.

## Configuration

### NiFi Instances

Abre el [Lookup de Instancias](configuration.es.md#lookup-de-instancias):
toda instancia o cluster monitoreado necesita una fila aquí antes de que
sus datos aparezcan en los paneles de arriba.

### Internal Monitoring

Etiquetado **Nifi TA Monitoring**. Reporta sobre el add-on, no sobre
NiFi: cantidad de eventos por sourcetype e index — el primer lugar para
mirar cuando un panel está vacío, o al [actualizar](upgrading.es.md) y
hay que cambiar `index_nifi` — y, en un cluster, roles de los miembros y
heap por nodo.
