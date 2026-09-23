# Instalar NIFI Monitoring

Las dos apps son obligatorias en conjunto: **Nifi Monitoring** (los
dashboards) no tiene nada que mostrar sin **Nifi Monitoring TA** instalada
también — la TA es la que parsea e indexa los datos de NiFi, sin importar
qué [estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion)
uses.

Esta aplicación además requiere dos apps de terceros desde Splunkbase:

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/)
- [Status Indicator – Custom Visualization](https://splunkbase.splunk.com/app/3119/)

## Instalación de NIFI Monitoring APP

Instala `nifi_monitoring-<version>.tar.gz` — desde [Splunkbase](https://splunkbase.splunk.com/app/6125) o un [release de GitHub](https://github.com/kudawdev/nifi-monitoring-splunk/releases) — desde el administrador de aplicaciones de Splunk.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

## Instalación de NIFI Monitoring TA

El Technology Add-on (TA) contiene todo lo no visual: el parsing, la indexación y el input modular que consulta NiFi.

Instala `nifi_TA_monitoring-<version>.tar.gz` — desde [Splunkbase](https://splunkbase.splunk.com/app/6124) o un [release de GitHub](https://github.com/kudawdev/nifi-monitoring-splunk/releases) — desde el administrador de aplicaciones de Splunk.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

Luego de la instalación, todos los objetos que permiten la indexación de datos quedan disponibles.

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_objects.png)

Siguiente: [Configuración de NIFI](configuration.es.md).
