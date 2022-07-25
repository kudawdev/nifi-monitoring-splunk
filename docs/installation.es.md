# Instalación y Configuración de NIFI Monitoring APP

Es esta sección se detallarán los pasos necesarios requeridos para instalar y configurar la aplicación NIFI Monitoring en Splunk

## Instalación de NIFI Monitoring APP

NIFI Monitoring está diseñado para ser instalado en ambientes de tipo Standalone o Cluster.

Esta aplicación requiere la implementación de las siguientes dependencias:

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/)
- [Status Indicator – Custom Visualization](https://splunkbase.splunk.com/app/3119/)

La aplicación contiene todas las características visuales que permiten el monitoreo de las instancias de NIFI configuradas.

Para instalar debe contar con el archivo NIFI_Monitoring_<version\>.tar.gz e instale desde el administrador de aplicaciones de Splunk.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

## Instalación de NIFI Monitoring TA

El Technology Addon (TA) de NIFI Monitoring contiene todas las características no visuales que permiten la indexación de las distintas fuentes de datos recibidas desde el o los servidores NIFI.

Para instalar debe contar con el archivo NIFI_TA_Monitoring_<version\>.tar.gz e instale desde el administrador de aplicaciones de Splunk.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

Luego de la instalación se dispondrá de todos los objetos que permiten la indexación de datos.

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_objects.png)

## Configuración de HTTP Event Collector (HEC)

Es fundamental incorporar la configuración de un recopilador de eventos HTTP (HEC). Esto permite enviar eventos desde las instancias de nifi a una implementación de Splunk a través de los protocolos HTTP y HTTPS.

Para configurar, en el menú de Splunk selecciona Settings > Data Inputs. En el listado de Local Inputs identifica HTTP Event Collector y agrega uno nuevo.

En el proceso de configuración deberás:

- Asignar un nombre para el data input,
- Establecer el sourcetype en **automático**,
- Seleccionar el *App Context* **NIFI Monitoring** y finalmente
- Seleccionar el Index donde se almacenarán los datos.

Se recomienda utilizar un Index dedicado, por ejemplo, nifi. Si no existe, deberás crearlo previo a esta configuración.

Al finalizar la configuración de este Event Collector se creará un Token Value, el cual es necesario para luego configurar el envío de datos desde NIFI.

Proceso de configuración:

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_1.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_2.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_3.png)

## Configuración de Lookup NIFI Instances

Es fundamental la configuración del lookup mantenedor de instancias monitoreadas. La etiqueta cluster es para asociar un grupo de nodos y host es el nombre de la instancia.
Este paso es muy importante para la correcta operación de la aplicación ya que si un nuevo nodo nifi no es actualizado en la tabla de instancias no se mostrará la información respectiva.

![image](/nifi-monitoring-splunk/assets/images/splunk/lookup_1.png)

Para obtener el nombre del host, puede ejecutar la siguiente búsqueda con un rango de tiempo de últimos 60 minutos. Para que esta búsqueda retorne resultados, los procesos de Nifi deben estar ejecutándose correctamente. [¿Cómo ejecutar un proceso NIFI?](/nifi-monitoring-splunk/es/configuration/#habilitacion-del-envio-de-datos)

**Splunk Query**  
```sourcetype=nifi* | dedup host | table host ```

El resultado de esta búsqueda retornará el listado de host que deben ser configurados en el lookup.

![image](/nifi-monitoring-splunk/assets/images/splunk/sourcetype_search.png)

Si el lookup está correctamente configurado la información podrá ser accesible desde el panel Overview.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview_lookup.png)