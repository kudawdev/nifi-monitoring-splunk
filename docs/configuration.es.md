# Configuración de NiFi Monitoring Splunk

## Configuración
En esta etapa se detallarán los pasos necesarios para el correcto funcionamiento del aplicativo NiFi Monitoring Splunk

Hay dos vías de configuración que permiten el envío de eventos a Splunk y su elección dependerá de los mecanismos de autenticación que NIFI tenga habilitado.

- A. Envío directo: Esta configuración establecerá NIFI como la vía principal para el envío de datos a Splunk por medio de un conjunto de procesadores y debe ser utilizada cuando NIFI no tenga activado métodos de autenticación.

- B. Splunk Data Input NiFi: Splunk se encargará de realizar peticiones a las instancias de NIFI para rescatar la información del Monitoring API por medio de la habilitación y uso del Data Input NIFI. Esta configuración debe ser utilizada cuando NIFI cuente con autenticación basica.

[NOTA] Configura sólo una metodología (A o B), ambas en funcionamiento generarán información duplicada.

## A. Envío Directo

### 1. Configuración de HTTP Event Collector (HEC) en Splunk

Se necesita la configuración de un recopilador de eventos HTTP (HEC). Esto permite enviar eventos desde las instancias de nifi a una implementación de Splunk a través de los protocolos HTTP y HTTPS.

Para configurar, en el menú de Splunk selecciona Settings > Data Inputs. En el listado de Local Inputs identifica HTTP Event Collector y agrega uno nuevo.

En el proceso de configuración deberás:

- Asignar un nombre para el data input,
- Establecer el sourcetype en **automático**,
- Seleccionar el *App Context* **NIFI Monitoring** y finalmente
- Seleccionar el Index donde se almacenarán los datos.

Se recomienda utilizar un Index dedicado para este monitoreo. Si no existe, deberás crearlo previo a esta configuración.

Al finalizar la configuración de este Event Collector se creará un Token Value, el cual es necesario para luego configurar el envío de datos desde NIFI.

Proceso de configuración:

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_1.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_2.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_3.png)

### 2. Importar Flow Definition en NIFI

Descarga y utiliza el Flow Definition proporciado para la configuración de NiFi Monitoring a través de este link [NifiMonitoring](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/template/NifiMonitoring.json). También podrás encontrar este archivo dentro de la carpeta **flow_definition** del proyecto.

El archivo Flow Definition es la estructura de un grupo de procesos encargado de recolectar y ejecutar el envío de datos de NIFI al Splunk. Está en formato JSON el cual puede ser directamente importado. 

Para importar el Flow Definition, arrastra una caja de *process group* al lienzo de nifi

![image](/nifi-monitoring-splunk/assets/images/nifi/1_add_process_group.png)

En la ventana emergente, selecciona el ícono de importación, busca en tu equipo y selecciona el flow definition NiFiMonitoring.json para importar.

![image](/nifi-monitoring-splunk/assets/images/nifi/2_import_flow_definition.png)

Una vez importado, haz clic en "add" para finalizar la importación del flow definition.

![image](/nifi-monitoring-splunk/assets/images/nifi/3_load_flow_definition.png)

Finalmente, verás el grupo de procesadores y en su interior contiene la siguiente estructura:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

![image](/nifi-monitoring-splunk/assets/images/nifi/4_flow_definition_loaded.png)

### 3. Configuración de variables globales

Configura las variables globales ya que son indispensable para su funcionamiento. Para configurar los parámetros haz clic derecho sobre la caja NiFIMonitoring > Variables.

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable.png)

Se desplegará una ventana emergente donde tendrás que configurar los siguientes parámetros:

- nifi_api_url: Corresponde a la ruta del API Rest de NIFI, (Ej: http://127.0.0.1:8080/nifi-api)
- nifi_path: Corresponde a la ruta de instalación en el servidor nifi (en caso de cluster debe estar instalado en la misma ruta en cada nodo). (Ej: /home/nifi/nifi-1.10.0/)
- process_groups_list: Listado de **ID de grupos de procesos** que se necesitan monitorear, separados por coma.
- processors_list: Listado de **ID de procesadores** que se necesitan monitorear, separados por coma.
- splunk_hec: Es la dirección del servidor splunk donde se configuró el data input HTTP Event Collector. (Ej: http://splunk1:8088/)
- splunk_hec_token: Token obtenido al configurar [HTTP Event Collector](/nifi-monitoring-splunk/es/installation/#configuracion-de-http-event-collector-hec).

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable_2.png)


### 4. Configuración de componentes

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

Una vez configurados los reporting task deberás iniciar la ejecución haciendo click start (►) en cada uno de ellos.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_4.png)

### 5. Habilitación del envío de datos

Luego de haber completado todo el proceso de configuración, inicie la ejecución del grupo de procesos. Haga clic derecho sobre el grupo de procesos y luego en Start.

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_1.png)

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_2.png)

Sí toda la configuración se ejecutó de manera correcta, se iniciará el envío de la información a Splunk. Para que los datos enviados a splunk estén accesibles desde la aplicación deberá haber configurado el [Lookup de Instancias](/nifi-monitoring-splunk/es/installation/#configuracion-transversal)

## B. Configuración del Data Input Nifi en Splunk

*Esta configuración debe ser aplicada cuando las instancias de NIFI cuenten con almenos autenticación básica*

En en los data input de Splunk puedes configurar varios recursos, como: NIFI Endpoints para el monitoreo de System Diagnostics, Flow Status y Site to Site y el NIFI Status History para monitoreo específico de procesadores y grupos de procesos en base a los ID de éstos.

Para configurar, en el splunk donde está instalada la aplicación Nifi Monitoring, accede al Home de la APP.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

Luego en Settings Data Inputs

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_1.png)

En los local data input, identifica NiFi y luego clic en + Add new

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_2.png)

Se desplegará una ventana como la siguiente:

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_3.pjeg)

**Te recomendamos configurar de manera independiente cada uno de los recursos de monitoreo para eventuales modificaciones en la configuración.**

Los recursos son:

- NIFI Endpoints
- NIFI Status History para Procesadores
- NIFI Status History para Grupos de Procesos

### 1. Configuración básica de los recursos
Para cada una de los recursos debes configurar todos los campos requeridos:

- NIFI Instance name: Asigna un nombre a la instancia de NIFI
- NIFI API URL: Dirección del API Rest de NIFI. (Ej. http://<direccion:puerto\>/nifi-api/)
- Auth Type: Tipo de autenticación:
    - none: Sin autenticación
    - basic: Acceso con credenciales usuario y contraseña
- Interval: Tiempo en segundos en el que se realizarán las peticiones para extraer la información, por defecto, 60 segundos.
- Host: Nombre del host de nifi, el cual debe corresponder a lo definido en el Lookup de Configuraciones.
- Index: Index de destinto para esta fuente de datos. Se recomienda un index dedicado, por ejemplo: nifi. Si no existe, deberá crearlo previamente.

### 2. NIFI Endpoints
En el apartado NIFI Endpoints, selecciona los elementos a monitorear de la lista existente.

- System Diagnostics
- Flow Status
- Site to Site

### 3. NIFI Status History para Procesadores
En el apartado NIFI Status History > List Processors ID especifica los ID de procesadores que serán monitorieados y separados por coma en caso de ser varios.

### 4. NIFI Status History para Grupos de Procesos
En el apartado NIFI Status History > Process Groups ID especifica los ID de los grupos de procesos que serán monitorieados y separados por coma en caso de ser varios.

Una vez completada la configuración, haz clic en siguiente y la creación finalizará correctamente
![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_success.png)

Repite el proceso de configuración por cada recurso que necesites monitorear.

Ejemplo de los 3 recursos creados de manera independiente
![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_4.png)

## Configuración transversal

Independiente de la metodología de envío adoptada, este paso de configuración es requerido para el despliegue de datos en la aplicación de NIFI Monitoring Splunk.

### Lookup de Instancias

Ve a Configuration > NiFi Instances para acceder a la vista de configuración de Lookups

![image](/nifi-monitoring-splunk/assets/images/splunk/1_configure_instances.png)

Completa la información de los campos, en donde, la etiqueta cluster es para asociar un grupo de nodos y host es el nombre de la instancia.

![image](/nifi-monitoring-splunk/assets/images/splunk/2_configure_instances.png)

Para obtener el nombre del host, ejecuta la siguiente búsqueda con un rango de tiempo de últimos 60 minutos.

**Splunk Query**  
```sourcetype=nifi* | dedup host | table host ```

El resultado de esta búsqueda retornará el listado de host que deben ser configurados en el lookup.

![image](/nifi-monitoring-splunk/assets/images/splunk/sourcetype_search.png)

Si el lookup está correctamente configurado la información podrá ser accesible desde el panel Overview.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview_lookup.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/3_configure_instances.png)

¿No hay resultados en la búsqueda ejecutada?

![image](/nifi-monitoring-splunk/assets/images/splunk/4_configure_instances.png)

 Para que esta búsqueda retorne resultados, los procesos de Nifi deben estar ejecutándose correctamente.
 Según la metodología de configuración deberás:
 1. Envío directo: Debes iniciar los procesos de NIFI [¿Cómo habilitar envío de datos?](#habilitacion-del-envio-de-datos)
 2. Splunk Data Input NiFi: Los data inputs configurados deben estar habilitados. [¿Cómo habilitar los data input?](La URL)
