# Configuración de NIFI

En esta etapa se detallarán todos los pasos necesarios que se deben realizar por el lado de nuestras instancias nifi que se quieren monitorear.

Hay dos vías de configuración que permiten el envío de eventos a Splunk y su elección dependerá de los mecanismos de autenticación que NIFI tenga habilitado.

- Envío directo: Esta configuración establecerá NIFI como la vía principal para el envío de datos a Splunk y debe ser utilizada cuando NIFI no tenga activado métodos de autenticación.

- Data Input NIFI: Splunk se encargará de realizar peticiones a las instancias de NIFI para rescatar la información del Monitoring API por medio de la habilitación y uso del Data Input NIFI. Esta configuración debe ser utilizada cuando NIFI cuente con autenticación basica.



## Carga de template

Podrá cargar el template desde la caja lateral Operate o haciendo clic derecho sobre una zona vacía y seleccionar la opción Upload template.

![image](/assets/images/nifi/add_template.png)

En la ventana emergente busque en su equipo y seleccione el template que utilizará.

![image](/assets/images/nifi/upload_template.png)

## Selección de Template

Para utilizar el template que fue previamente cargado, arrastre del menú la opción template a la hoja de trabajo. Se abrirá una ventana emergente y seleccione el template a utilizar.

![image](/assets/images/nifi/select_template.png)

![image](/assets/images/nifi/choose_template.png)

El template desplegado debe tener la siguiente estructura:

- La primera vista contiene Nifi_Monitoring_Splunk

![image](/assets/images/nifi/nifi_monitoring_process_group.png)

En su interior contiene la siguiente estructura:

-	Ingesta API
-	Ingesta Logs
-	Ingesta ReportingTask

![image](/assets/images/nifi/nifi_monitoring_process_group_2.png)


## Configuración de variables globales

Es fundamental configurar las variables globales ya que son indispensable para su funcionamiento. Para configurar los parámetros mencionados, haga clic derecho sobre la caja Nifi_Monitoring_Splunk > Variables.

![image](/assets/images/nifi/set_variable.png)

Se desplegará una ventana emergente donde tendrá que configurar los siguientes parámetros:

- nifi_path: Corresponde a la ruta de instalación del servidor nifi (en caso de cluster debe estar instalado en la misma ruta en cada nodo). Ejemplo: /home/nifi/nifi-1.10.0/
- splunk_hec: Es la dirección del servidor splunk donde se configuró el data input HTTP Event Collector. Ejemplo: 127.0.0.1:8088
- splunk_hec_token: Token obtenido al configurar [HTTP Event Collector](/es/installation/#configuracion-de-http-event-collector-hec).

![image](/assets/images/nifi/set_variable_2.png)


## Configuración de componentes

Posterior a la configuración de las variables es necesario crear los siguientes componentes. Para configurar accede a Nifi Settings desde el menú > controller Settings

![image](/assets/images/nifi/controller_settings.png)

Se desplegará una ventana emergente como la siguiente:

![image](/assets/images/nifi/nifi_settings.png)

En la pestaña Reporting Task Controller Services, agrega el controller service JsonRecordSetWriter, el cual permitirá parsear los resultados obtenidos desde el servicio Reporting Task para su posterior indexación en splunk. Para añadir, click en el botón (+)

Se desplegará la ventana para agregar el controller. Filtra la lista de opciones con el elemento que se agregará, selecciónalo y añádelo a la configuración.

![image](/assets/images/nifi/add_controller_service.png)

Una vez agregado, deberás habilitar su funcionamiento haciendo clic sobre el ícono de rayo (ϟ) y en la ventana emergente confirmar. Esto habilitará el controller y deberás tener una configuración como la siguiente.

![image](/assets/images/nifi/nifi_settings_2.png)

En esta misma ventana, en la pestaña Reporting Task se deberá configurar los siguientes reportes.

- MonitorDiskUsage
- SitetoSiteBulletinReportingTask
- SitetoSiteMetricsReportingTask

![image](/assets/images/nifi/nifi_settings_3.png)

Agregue y busque los reporting task requeridos de la misma manera que el paso anterior, haciendo clic en el ícono (+). Una vez agregados podrá tener una vista como la siguiente.

![image](/assets/images/nifi/reporting_task.png)

Configura los reporting task con la siguiente información:

- MonitorDiskUsage: Sistema de reporte interno que genera eventos a medida que se supera el umbral definido para la utilización del filesystem y capturados en un flujo especifico.

![image](/assets/images/nifi/monitor_disk_usage.png)

- SiteToSiteBulletinReportingTask: Sistema de reporte interno que genera eventos a medida que se van generando errores del tipo bulletin y capturados en un flujo especifico. La configuración debe ser la siguiente:

![image](/assets/images/nifi/bulletin_reporting_task.png)

- SiteToSiteMetricsReportingTask: Sistema de reporte interno que genera eventos a medida que se van generando métricas del mismo ambiente y capturados en un flujo especifico. La configuración debe ser la siguiente:

![image](/assets/images/nifi/metrics_reporting_task.png)

Una vez configurados los reporting task deberá iniciar la ejecución haciendo click start (►) en cada uno de ellos.

![image](/assets/images/nifi/nifi_settings_4.png)

## Habilitación del envío de datos

Luego de haber completado todo el proceso de configuración, inicie la ejecución del grupo de procesos. Haga clic derecho sobre el grupo de procesos y luego en Start.

![image](/assets/images/nifi/enable_sending_1.png)

![image](/assets/images/nifi/enable_sending_2.png)

Sí toda la configuración se ejecutó de manera correcta, se iniciará el envío de la información a Splunk. Para que los datos enviados a splunk estén accesibles desde la aplicación deberá haber configurado el [Lookup de Instancias](/es/installation/#configuracion-de-lookup-nifi-instances)

## Configuración de Data Input NIFI

Para configurar el Data Input Nifi tiene que haber completado la carga y selección de template, Configuración de Variables y Configuración de Componentes.

Si finalizó el paso Habilitación del Envío de Datos o si el grupo de procesos está en ejecución, deberá detenerlo. Para ello, haz clic derecho sobre el grupo de procesos y luego en Stop. Esta acción detendrá el envío de información a Splunk

![image](/assets/images/nifi/disable_sending_data.png)

### Deshabilitación del grupo de procesos Monitoring – API
Haz doble clic sobre el grupo y deberá ver la siguiente vista

![image](/assets/images/nifi/disable_monitoring_api.png)

Para deshabilitar Monitoring API, haz clic derecho sobre la primera caja y luego clic en Disable, el componente deberá verse así:

![image](/assets/images/nifi/disable_monitoring_api_2.png)

Una vez deshabilitado, regresa a la vista anterior. Haz clic derecho sobre una zona vacía y luego en leave group o en la banda inferior en NiFi Flow.


![image](/assets/images/nifi/leave_group.png)

### Configuración del Data Input Nifi - Splunk
En el splunk donde está instalada la aplicación Nifi Monitoring, accede al Home de la APP.

![image](/assets/images/splunk/nifi_home.png)

Luego en Settings Data Inputs

![image](/assets/images/splunk/data_input_1.png)

En los local data input, identifica NiFi y luego clic en + Add new

![image](/assets/images/splunk/data_input_2.png)

Se desplegará el siguiente formulario. Marque la casilla More settings para habilitar otros campos de información relevantes en la configuración. 

![image](/assets/images/splunk/data_input_3.png)

- NiFi Instance Name: Asigne un nombre a la instancia de NIFI
- NiFi API URL: Dirección de la API de NiFi (Ej.: http://(direccion:puerto)/nifi-api/)
- Auth Type: Tipo de autenticación:
    - none: Sin autenticación
    - basic: Acceso con credenciales usuario y contraseña
- Interval: Tiempo en segundos en el que se realizarán las peticiones para extraer la información.
- Host: Nombre del host de nifi, el cual debe corresponder a lo definido en el Lookup de Configuraciones. [Ver Lookup de Instancias](/es/installation/#configuracion-de-lookup-nifi-instances)
- Index: Index de destinto para esta fuente de datos. Se recomienda un index dedicado, por ejemplo: nifi. Si no existe, deberá crearlo previamente.