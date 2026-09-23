# Introducción

Nifi Monitoring centraliza la visibilidad operacional de múltiples instancias de Apache NiFi en Splunk — standalone o en cluster — para que no tengas que vigilar cada una por separado. Se distribuye como dos apps: **Nifi Monitoring**, los dashboards que describe esta guía, y **Nifi Monitoring TA**, el add-on que trae los datos de NiFi a Splunk.

![image1](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

## Sobre este producto

- Soporta múltiples instancias de NiFi, ya sea standalone o en cluster.
- Recolecta datos de los logs de NiFi, su API REST y sus reporting tasks.
- Dos formas de traer esos datos: consultando la API, o un flow dentro de
  NiFi que envía al HTTP Event Collector de Splunk. Ver
  [Compatibilidad y métodos de recolección](compatibility.es.md) para elegir una.

Esta aplicación requiere las siguientes dependencias:

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/)
- [Status Indicator – Custom Visualization](https://splunkbase.splunk.com/app/3119/)

## Por dónde seguir

- [Compatibilidad y métodos de recolección](compatibility.es.md) — versiones de NiFi y Splunk soportadas, y cuál de las dos rutas de recolección corresponde a tu ambiente.
- [Instalación y configuración de NIFI Monitoring en Splunk](installation.es.md) — instalar ambas apps.
- [Configuración de NIFI](configuration.es.md) — configurar NiFi y el data input según la ruta elegida.
- [Referencia de Datos](references.es.md) — qué contiene cada sourcetype.

## Soporte

Su funcionamiento es completamente gratuito y puedes contribuir a través del [repositorio de GitHub](https://github.com/kudawdev/nifi-monitoring-splunk).

Escríbanos a splunk.app@kudaw.com para una evaluación, o a través de nuestro sitio [kudaw.com](https://www.kudaw.com/).