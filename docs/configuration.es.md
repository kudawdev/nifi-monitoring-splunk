# Configuración de NIFI

En esta etapa se detallarán todos los pasos necesarios que se deben realizar por el lado de nuestras instancias nifi que se quieren monitorear.

Hay dos vías de configuración que permiten el envío de eventos a Splunk y su elección dependerá de los mecanismos de autenticación que NIFI tenga habilitado.

- Envío directo: Esta configuración establecerá NIFI como la vía principal para el envío de datos a Splunk y debe ser utilizada cuando NIFI no tenga activado métodos de autenticación.

- Data Input NIFI: Splunk se encargará de realizar peticiones a las instancias de NIFI para rescatar la información del Monitoring API por medio de la habilitación y uso del Data Input NIFI. Esta configuración debe ser utilizada cuando NIFI cuente con autenticación basica.

## Carga del flujo NiFi
El flujo nifi encargado de procesar y enviar los datos al splunk puede ser configurado de dos maneras: como un flow definition o como template.

## NiFi Flow Definition

El archivo Flow Definition es la estructura del grupo de proceso para el monitoreo de NiFi en Splunk y formato JSON el cual puede ser directamente importado.
Descarga y utiliza esta definición para la configuración del NiFi Monitoring a través de este link [NifiMonitoring](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/template/NifiMonitoring.json)

## Carga del flow definition

Podrás cargar el flow definition arrastrando una caja de process group al lienzo de NiFi

![image](/nifi-monitoring-splunk/assets/images/nifi/1_add_process_group.png)

En la ventana emergente, selecciona el ícono de importación, busca en tu equipo y selecciona el flow definition a importar.

![image](/nifi-monitoring-splunk/assets/images/nifi/2_import_flow_definition.png)

Una vez importado, haz clic en "add" para finalizar la importación del flow definition.

![image](/nifi-monitoring-splunk/assets/images/nifi/3_load_flow_definition.png)

Finalmente, verás el grupo de procesadores y en su interior contiene la siguiente estructura:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

![image](/nifi-monitoring-splunk/assets/images/nifi/4_flow_definition_loaded.png)

## Template

Descarga y utiliza el template proporciado para la configuración de NiFi Monitoring a través de este link [NifiMonitoringTemplate](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/template/NifiMonitoringTemplate.xml). También podrás encontrar este archivo dentro de la carpeta **template** del proyecto.

## Carga de template

Podrás cargar el template desde la caja lateral Operate o haciendo clic derecho sobre una zona vacía y seleccionar la opción Upload template.

![image](/nifi-monitoring-splunk/assets/images/nifi/add_template.png)

En la ventana emergente busque en su equipo y seleccione el template que utilizará.

![image](/nifi-monitoring-splunk/assets/images/nifi/upload_template.png)

## Selección de Template

Para utilizar el template que fue previamente cargado, arrastre del menú la opción template a la hoja de trabajo. Se abrirá una ventana emergente y seleccione el template a utilizar.

![image](/nifi-monitoring-splunk/assets/images/nifi/select_template.png)

![image](/nifi-monitoring-splunk/assets/images/nifi/choose_template.png)

El template desplegado debe tener la siguiente estructura:

- La primera vista contiene Nifi_Monitoring_Splunk

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_monitoring_process_group.png)

En su interior contiene la siguiente estructura:

-	Ingesta API
-	Ingesta Logs
-	Ingesta ReportingTask

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_monitoring_process_group_2.png)


## Configuración de variables globales

Es fundamental configurar las variables globales ya que son indispensable para su funcionamiento. Para configurar los parámetros haga clic derecho sobre la caja Nifi_Monitoring_Splunk > Variables.

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable.png)

Se desplegará una ventana emergente donde tendrá que configurar los siguientes parámetros:

- nifi_path: Corresponde a la ruta de instalación del servidor nifi (en caso de cluster debe estar instalado en la misma ruta en cada nodo). Ejemplo: /home/nifi/nifi-1.10.0/
- splunk_hec: Es la dirección del servidor splunk donde se configuró el data input HTTP Event Collector. Ejemplo: 127.0.0.1:8088
- splunk_hec_token: Token obtenido al configurar [HTTP Event Collector](/nifi-monitoring-splunk/es/installation/#configuracion-de-http-event-collector-hec).

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable_2.png)


## Configuración de componentes

Posterior a la configuración de las variables es necesario crear los siguientes componentes. Para configurar accede a Nifi Settings desde el menú > controller Settings

![image](/nifi-monitoring-splunk/assets/images/nifi/controller_settings.png)

Se desplegará una ventana emergente como la siguiente:

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings.png)

En la pestaña Reporting Task Controller Services, agrega el controller service JsonRecordSetWriter, el cual permitirá parsear los resultados obtenidos desde el servicio Reporting Task para su posterior indexación en splunk. Para añadir, click en el botón (+)

Se desplegará la ventana para agregar el controller. Filtra la lista de opciones con el elemento que se agregará, selecciónalo y añádelo a la configuración.

![image](/nifi-monitoring-splunk/assets/images/nifi/add_controller_service.png)

Una vez agregado, deberás habilitar su funcionamiento haciendo clic sobre el ícono de rayo (ϟ) y en la ventana emergente confirmar. Esto habilitará el controller y deberás tener una configuración como la siguiente.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_2.png)

En esta misma ventana, en la pestaña Reporting Task se deberá configurar los siguientes reportes.

- MonitorDiskUsage
- SitetoSiteBulletinReportingTask
- SitetoSiteMetricsReportingTask

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_3.png)

Agregue y busque los reporting task requeridos de la misma manera que el paso anterior, haciendo clic en el ícono (+). Una vez agregados podrá tener una vista como la siguiente.

![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_task.png)

Configura los reporting task con la siguiente información:

- MonitorDiskUsage: Sistema de reporte interno que genera eventos a medida que se supera el umbral definido para la utilización del filesystem y capturados en un flujo especifico.

![image](/nifi-monitoring-splunk/assets/images/nifi/monitor_disk_usage.png)

- SiteToSiteBulletinReportingTask: Sistema de reporte interno que genera eventos a medida que se van generando errores del tipo bulletin y capturados en un flujo especifico. La configuración debe ser la siguiente:

    * Destination URL: http://${hostname(true)}:8080/nifi
    * Input Port Name: bulletin_report
    * Instance URL: http://${hostname(true)}:8080/nifi
    * Transport Protocol: HTTP
    * Record Writer: JsonRecordSetWriter

![image](/nifi-monitoring-splunk/assets/images/nifi/bulletin_reporting_task.png)

- SiteToSiteMetricsReportingTask: Sistema de reporte interno que genera eventos a medida que se van generando métricas del mismo ambiente y capturados en un flujo especifico. La configuración debe ser la siguiente:

    * Destination URL: http://${hostname(true)}:8080/nifi
    * Input Port Name: reporting_task
    * Instance URL: http://${hostname(true)}:8080/nifi
    * Transport Protocol: HTTP
    * Record Writer: JsonRecordSetWriter
    * Output Format: Record Formats

![image](/nifi-monitoring-splunk/assets/images/nifi/metrics_reporting_task.png)

Una vez configurados los reporting task deberá iniciar la ejecución haciendo click start (►) en cada uno de ellos.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_4.png)

## Habilitación del envío de datos

Luego de haber completado todo el proceso de configuración, inicie la ejecución del grupo de procesos. Haga clic derecho sobre el grupo de procesos y luego en Start.

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_1.png)

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_2.png)

Sí toda la configuración se ejecutó de manera correcta, se iniciará el envío de la información a Splunk. Para que los datos enviados a splunk estén accesibles desde la aplicación deberá haber configurado el [Lookup de Instancias](/nifi-monitoring-splunk/es/installation/#configuracion-de-lookup-nifi-instances)

## Configuración de Data Input NIFI

Para configurar el Data Input Nifi tiene que haber completado la carga y selección de template, Configuración de Variables y Configuración de Componentes.

Si finalizó el paso Habilitación del Envío de Datos o si el grupo de procesos está en ejecución, deberá detenerlo. Para ello, haz clic derecho sobre el grupo de procesos y luego en Stop. Esta acción detendrá el envío de información a Splunk

![image](/nifi-monitoring-splunk/assets/images/nifi/disable_sending_data.png)

### Deshabilitación del grupo de procesos Monitoring – API
Haz doble clic sobre el grupo y deberá ver la siguiente vista

![image](/nifi-monitoring-splunk/assets/images/nifi/disable_monitoring_api.png)

Para deshabilitar Monitoring API, haz clic derecho sobre la primera caja y luego clic en Disable, el componente deberá verse así:

![image](/nifi-monitoring-splunk/assets/images/nifi/disable_monitoring_api_2.png)

Una vez deshabilitado, regresa a la vista anterior. Haz clic derecho sobre una zona vacía y luego en leave group o en la banda inferior en NiFi Flow.


![image](/nifi-monitoring-splunk/assets/images/nifi/leave_group.png)

### Configuración del Data Input Nifi - Splunk

*Esta configuración debe ser aplicada cuando las instancias de NIFI cuenten con almenos autenticación básica*

En el splunk donde está instalada la aplicación Nifi Monitoring, accede al Home de la APP.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

Luego en Settings Data Inputs

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_1.png)

En los local data input, identifica NiFi y luego clic en + Add new

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_2.png)

Se desplegará el siguiente formulario. Marque la casilla More settings para habilitar otros campos de información relevantes en la configuración. 

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_3.png)

- NiFi Instance Name: Asigne un nombre a la instancia de NIFI
- NiFi API URL: Dirección de la API de NiFi. Ejemplo: http://<direccion:puerto\>/nifi-api/
- Auth Type: Tipo de autenticación:
    - none: Sin autenticación
    - basic: Acceso con credenciales usuario y contraseña
- Interval: Tiempo en segundos en el que se realizarán las peticiones para extraer la información.
- Host: Nombre del host de nifi, el cual debe corresponder a lo definido en el Lookup de Configuraciones. [Ver Lookup de Instancias](/nifi-monitoring-splunk/es/installation/#configuracion-de-lookup-nifi-instances)
- Index: Index de destinto para esta fuente de datos. Se recomienda un index dedicado, por ejemplo: nifi. Si no existe, deberá crearlo previamente.
