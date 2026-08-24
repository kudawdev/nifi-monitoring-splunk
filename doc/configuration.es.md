# Configuración de NiFi Monitoring Splunk

## Configuración
En esta etapa se detallarán los pasos necesarios para el correcto funcionamiento del aplicativo NiFi Monitoring Splunk

Hay dos vías de configuración que permiten el envío de eventos a Splunk y su elección dependerá de los mecanismos de autenticación que NIFI tenga habilitado.

- Envío directo: Esta configuración establecerá NIFI como la vía principal para el envío de datos a Splunk por medio de un conjunto de procesadores y debe ser utilizada cuando NIFI no tenga activado métodos de autenticación.

- Splunk Data Input NiFi: Splunk se encargará de realizar peticiones a las instancias de NIFI para rescatar la información del Monitoring API por medio de la habilitación y uso del Data Input NIFI. Esta configuración debe ser utilizada cuando NIFI cuente con autenticación basica.

[NOTA] Configura sólo una metodología, ambas en funcionamiento generarán información duplicada.

## Envío Directo

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

### 2. Importar el Flow Definition en NiFi

Elige el archivo que corresponde a tu versión de NiFi. No son intercambiables:

| Tu NiFi | Importa |
|---|---|
| 1.16 – 1.28 | [`flow_definition/nifi-1.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-1.x/NiFiMonitoring.json) |
| 2.0 en adelante | [`flow_definition/nifi-2.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-2.x/NiFiMonitoring.json) |

!!! warning "No importes el flow de 1.x en NiFi 2.x"
    Carga, y ahí está la trampa. Cinco procesadores quedan inválidos, y las
    seis variables de las que depende el flow desaparecen sin un solo error:
    hay procesadores que validan sin problema mientras sostienen referencias
    `${splunk_hec}` que ya no resuelven a nada, y que fallan recién en
    tiempo de ejecución.

El Flow Definition es un grupo de procesos que recolecta los datos de NiFi y
los envía a Splunk. Para importarlo, arrastra una caja de *process group* al
lienzo, selecciona el ícono de importación en la ventana emergente y elige el
archivo.

Una vez importado verás el grupo de procesos, que contiene:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

### 3. Configurar los ajustes del flow

El mecanismo cambia según la versión de NiFi, porque NiFi 2.0 eliminó el
Variable Registry.

#### NiFi 2.x — parameter context

Al importar el flow de 2.x se crea un parameter context llamado **NiFi
Monitoring** y queda asignado al grupo de procesos. Ábrelo con clic
derecho sobre el grupo > *Parameters*, o desde el menú superior derecho >
*Parameter Contexts*.

Dos de sus parámetros se distribuyen vacíos a propósito, y hasta que
tengan valor los dos procesadores `GenerateFlowFile` quedan inválidos.
Es intencional: que NiFi se niegue a arrancar un procesador con una
propiedad requerida vacía es mejor que arrancarlo apuntando a los ids de
componentes de otra instalación.

#### NiFi 1.x — variables

Clic derecho sobre la caja NiFiMonitoring > *Variables*.

En cualquiera de los dos casos, los ajustes son los mismos:

| Ajuste | Qué es |
|---|---|
| `nifi_api_url` | La API REST de esta instancia, ej. `http://127.0.0.1:8080/nifi-api/` |
| `nifi_path` | Directorio de instalación de NiFi, para leer sus logs. En cluster, la misma ruta en cada nodo |
| `process_groups_list` | Ids de los grupos de procesos a monitorear, uno por línea |
| `processors_list` | Ids de los procesadores a monitorear, uno por línea |
| `splunk_hec` | El servidor Splunk con el input HEC, ej. `http://<host>:8088/` |
| `splunk_hec_token` | El token de [configurar el HEC](#1-configuracion-de-http-event-collector-hec-en-splunk). En 2.x es un parámetro **sensible**, así que NiFi nunca lo escribe en un flow exportado |

### 4. Configuración de componentes

!!! note "Las capturas de abajo son de NiFi 1.x"
    NiFi 2.x rehizo su interfaz, así que estas imágenes ya no coinciden con lo
    que vas a ver. Los pasos en sí no cambian — el mismo controller service y
    las mismas tres reporting tasks, desde los mismos menús — pero las
    pantallas se ven distintas. Recapturarlas para 2.x está pendiente.


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

## Configuración del Data Input Nifi en Splunk

*Esta configuración debe ser aplicada cuando las instancias de NIFI cuenten con almenos autenticación básica*

En en los data input de Splunk puedes configurar varios recursos, como: NIFI Endpoints para el monitoreo de System Diagnostics, Flow Status y Site to Site y el NIFI Status History para monitoreo específico de procesadores y grupos de procesos en base a los ID de éstos.

Para configurar, en el splunk donde está instalada la aplicación Nifi Monitoring, accede al Home de la APP.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

Luego en Settings Data Inputs

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_1.png)

En los local data input, identifica NiFi y luego clic en + Add new

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_2.png)

Se desplegará una ventana como la siguiente:

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_3.jpeg)

**Te recomendamos configurar de manera independiente cada uno de los recursos de monitoreo para eventuales modificaciones en la configuración y debido a los tiempos de ejecución para obtención de datos.**

Los recursos son:

- a. NIFI Endpoints
- b. NIFI Status History para Procesadores
- c. NIFI Status History para Grupos de Procesos

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

### a. NIFI Endpoints
En el apartado NIFI Endpoints, selecciona los elementos a monitorear de la lista existente.

- System Diagnostics
- Flow Status
- Site to Site

### b. NIFI Status History para Procesadores
En el apartado NIFI Status History > List Processors ID especifica los ID de procesadores que serán monitorieados y separados por coma en caso de ser varios.

### c. NIFI Status History para Grupos de Procesos
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
 2. Splunk Data Input NiFi: Los data inputs configurados deben estar habilitados.