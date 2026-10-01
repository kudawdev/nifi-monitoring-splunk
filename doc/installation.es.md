# Instalar NIFI Monitoring

Ambas apps son obligatorias: **Nifi Monitoring TA** parsea e indexa los
datos de NiFi; **Nifi Monitoring** (los dashboards) depende de ella, sin
importar la
[estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion)
que uses. Se necesitan tres apps en total, todas desde el administrador
de aplicaciones de Splunk (**Apps > Manage Apps > Install app from file**):

1. **Nifi Monitoring TA** — parsea e indexa los datos de NiFi. Instálala
   primero: los dashboards no tienen nada que leer sin ella.
   `nifi_TA_monitoring-<versión>.tar.gz`, desde
   [Splunkbase](https://splunkbase.splunk.com/app/6124) o un
   [release de GitHub](https://github.com/kudawdev/nifi-monitoring-splunk/releases).
2. **Nifi Monitoring** — los dashboards, vistas y lookups.
   `nifi_monitoring-<versión>.tar.gz`, desde
   [Splunkbase](https://splunkbase.splunk.com/app/6125) o la misma página
   de releases.
3. **[Lookup File Editor](https://splunkbase.splunk.com/app/1724/)** —
   necesaria para la pantalla de Instance Lookup. Desde 2.0.0 los dashboards
   son Dashboard Studio y no necesitan otra app de visualización; *Status
   Indicator* se puede desinstalar si nada más la usa.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

Después de instalar la TA, sus objetos de parseo e indexado quedan
disponibles:

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_objects.png)

Siguiente: [Lookup de Instancias](instance-lookup.es.md).
