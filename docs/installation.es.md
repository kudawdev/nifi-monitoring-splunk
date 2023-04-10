# Instalación de NIFI Monitoring APP

Es esta sección se detallarán los pasos necesarios requeridos para instalar la aplicación NIFI Monitoring en Splunk

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