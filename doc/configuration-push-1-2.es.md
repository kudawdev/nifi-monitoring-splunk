---
title: Estrategia push (1.2)
---

# Estrategia push: Envío Directo (1.2)

!!! note "Para la versión 1.2.x de las dos apps"
    Esta es la configuración tal como era en la release 1.2.3, con el flow
    que traía esa release. Para la 2.0, ver
    [Estrategia push (2.0)](config-nifi-monitoring-2-0-push.es.md), que cubre
    NiFi 1.x y 2.x.

Esta configuración establece a NiFi como la vía principal para enviar datos
a Splunk, mediante un conjunto de procesadores, y debe usarse cuando NiFi no
tiene métodos de autenticación activados.

Configura solo una estrategia: las dos en funcionamiento generan
información duplicada.

## 1. Configuración del HTTP Event Collector (HEC) en Splunk

Se necesita un HTTP Event Collector (HEC). Permite enviar eventos desde las
instancias de NiFi a Splunk por HTTP y HTTPS.

En el menú de Splunk selecciona **Settings > Data Inputs**. En el listado de
Local Inputs identifica **HTTP Event Collector** y agrega uno nuevo. En el
proceso deberás:

- asignar un nombre al data input,
- establecer el sourcetype en **automático**,
- seleccionar el *App Context* **NIFI Monitoring**, y
- seleccionar el índice donde se almacenarán los datos.

Se recomienda un índice dedicado para este monitoreo. Si no existe, créalo
antes de esta configuración.

Al crear el HEC obtienes un **Token Value**, necesario luego para configurar
el envío de datos desde NiFi.

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_1.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_2.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_3.png)

## 2. Importar el Flow Definition en NiFi

Descarga el Flow Definition de la configuración 1.2,
[`flow_definition/NiFiMonitoring.json` en 1.2.3](https://github.com/kudawdev/nifi-monitoring-splunk/blob/1.2.3/flow_definition/NiFiMonitoring.json).

El Flow Definition es la estructura de un grupo de procesos que recolecta
los datos de NiFi y los envía a Splunk. Es un archivo JSON que se puede
importar directamente.

Para importarlo, arrastra una caja de *process group* al lienzo de NiFi.

![image](/nifi-monitoring-splunk/assets/images/nifi/1_add_process_group.png)

En la ventana emergente, selecciona el ícono de importación, busca en tu
equipo y elige el flow definition `NiFiMonitoring.json`.

![image](/nifi-monitoring-splunk/assets/images/nifi/2_import_flow_definition.png)

Una vez importado, haz clic en **Add** para finalizar.

![image](/nifi-monitoring-splunk/assets/images/nifi/3_load_flow_definition.png)

Verás el grupo de procesos, que contiene:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

![image](/nifi-monitoring-splunk/assets/images/nifi/4_flow_definition_loaded.png)

## 3. Configuración de variables globales

Las variables globales son indispensables para que el flow funcione. Para
configurarlas, haz clic derecho sobre la caja NiFiMonitoring > **Variables**.

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable.png)

Se abre una ventana emergente donde configuras:

- `nifi_api_url`: la ruta de la API REST de NiFi (ej. `http://127.0.0.1:8080/nifi-api/`).
- `nifi_path`: la ruta de instalación de NiFi en el servidor (en un
  cluster, debe estar instalado en la misma ruta en cada nodo), ej.
  `/home/nifi/nifi-1.10.0/`.
- `process_groups_list`: los **ID de los grupos de procesos** a monitorear,
  uno por línea.
- `processors_list`: los **ID de los procesadores** a monitorear, uno por
  línea.
- `splunk_hec`: la dirección del servidor Splunk donde se configuró el HTTP
  Event Collector (ej. `http://<host>:8088/`).
- `splunk_hec_token`: el token obtenido al
  [configurar el HTTP Event Collector](#1-configuracion-del-http-event-collector-hec-en-splunk).

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable_2.png)

## 4. Configuración de componentes

Con las variables configuradas, crea los siguientes componentes. Abre la
configuración de NiFi desde el menú > **Controller Settings**.

![image](/nifi-monitoring-splunk/assets/images/nifi/controller_settings.png)

Se abre una ventana emergente como la siguiente:

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings.png)

En la pestaña **Reporting Task Controller Services**, agrega el controller
service **JsonRecordSetWriter**, que parsea los resultados de las reporting
tasks para su indexación en Splunk. Para agregarlo, haz clic en el botón
(+).

Filtra la lista con el nombre del elemento a agregar, selecciónalo y
agrégalo.

![image](/nifi-monitoring-splunk/assets/images/nifi/add_controller_service.png)

Una vez agregado, habilítalo: haz clic en el ícono de rayo (ϟ) y confirma en
la ventana emergente. Deberías tener una configuración como la siguiente.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_2.png)

En la misma ventana, en la pestaña **Reporting Task**, agrega estas
reporting tasks:

- MonitorDiskUsage
- SiteToSiteBulletinReportingTask
- SiteToSiteMetricsReportingTask

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_3.png)

Agrégalas de la misma manera que en el paso anterior, con el ícono (+). Una
vez agregadas verás algo como:

![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_task.png)

Configúralas así:

- **MonitorDiskUsage**: una reporting task interna que genera eventos cuando
  se supera el umbral de uso del filesystem, capturados en un flujo
  específico.

![image](/nifi-monitoring-splunk/assets/images/nifi/monitor_disk_usage.png)

- **SiteToSiteBulletinReportingTask**: una reporting task interna que genera
  eventos a medida que se generan bulletins, capturados en un flujo
  específico:

    * Destination URL: `http://${hostname(true)}:8080/nifi`
    * Input Port Name: `bulletin_report`
    * Instance URL: `http://${hostname(true)}:8080/nifi`
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`

![image](/nifi-monitoring-splunk/assets/images/nifi/bulletin_reporting_task.png)

- **SiteToSiteMetricsReportingTask**: una reporting task interna que genera
  eventos a medida que el mismo ambiente genera métricas, capturados en un
  flujo específico:

    * Destination URL: `http://${hostname(true)}:8080/nifi`
    * Input Port Name: `reporting_task`
    * Instance URL: `http://${hostname(true)}:8080/nifi`
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`
    * Output Format: `Record Format`

![image](/nifi-monitoring-splunk/assets/images/nifi/metrics_reporting_task.png)

Una vez configuradas, inicia cada reporting task haciendo clic en start (►).

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_4.png)

## 5. Habilitación del envío de datos

Con todo lo anterior listo, inicia el grupo de procesos: haz clic derecho
sobre él y luego **Start**.

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_1.png)

Si todo está configurado correctamente, se inicia el envío de los datos a
Splunk. Para que se vean en la app, configura el
[Lookup de Instancias](instance-lookup.es.md).
