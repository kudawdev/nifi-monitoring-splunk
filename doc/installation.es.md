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

## Dónde instalar, en un despliegue distribuido

En una sola instancia de Splunk, instala las tres apps ahí y omite esta
sección. En un despliegue distribuido, cada pieza va donde su configuración
tiene efecto:

| Dónde | Qué | Por qué |
|---|---|---|
| Search head | Nifi Monitoring, Nifi Monitoring TA, Lookup File Editor | Los dashboards, alertas y lookups, y los campos de búsqueda de la TA. |
| Donde corren los inputs pull | Nifi Monitoring TA | Los inputs viven en la TA, y los sourcetypes de la API se parsean ahí (`INDEXED_EXTRACTIONS = json`), no en los indexers. Esa instancia necesita llegar a la API REST de NiFi. |
| Indexers | El índice `nifi`; Nifi Monitoring TA si un Universal Forwarder envía los logs de NiFi | El índice está en el `default/indexes.conf` de la app, que el search head no propaga: despliégalo también en los indexers. Los sourcetypes de logs cortan líneas y leen el timestamp donde se parsean por primera vez: los indexers, o un heavy forwarder intermedio. |
| Hosts de NiFi (opcional) | Un Universal Forwarder con el mismo paquete de Nifi Monitoring TA | Solo para los archivos de log de NiFi — ver [Configurar el Universal Forwarder](compatibility.es.md#configurar-el-universal-forwarder). |

Corre los inputs pull en un heavy forwarder o en un search head independiente.
No en un search head cluster: cada miembro correría todos los inputs e
indexaría los datos de cada NiFi más de una vez.

En **Splunk Cloud**, verifica que el índice `nifi` exista
(**Settings > Indexes**) y créalo si no está.

Siguiente: [Lookup de Instancias](instance-lookup.es.md).
