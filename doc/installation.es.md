# Instalar NIFI Monitoring

Ambas apps son obligatorias: **Nifi Monitoring TA** parsea e indexa los
datos de NiFi; **Nifi Monitoring** (los dashboards) depende de ella, sin
importar la
[estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion)
que uses. Se necesitan cuatro apps en total, todas desde el administrador
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
   necesaria para la pantalla de Instance Lookup.
4. **[Status Indicator - Custom Visualization](https://splunkbase.splunk.com/app/3119/)** —
   necesaria para los paneles de estado de los dashboards.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

Después de instalar la TA, sus objetos de parseo e indexado quedan
disponibles:

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_objects.png)

## Lookup de Instancias

Configura esto sin importar qué estrategia de recolección uses — sin
esto, ningún panel del dashboard muestra datos.

Ve a Configuration > NiFi Instances para acceder a la vista de
configuración de Lookups.

![image](/nifi-monitoring-splunk/assets/images/splunk/1_configure_instances.png)

Completa la información de los campos, donde la etiqueta cluster es para
asociar un grupo de nodos y host es el nombre de la instancia.

![image](/nifi-monitoring-splunk/assets/images/splunk/2_configure_instances.png)

Para obtener el nombre del host, ejecuta la siguiente búsqueda con un
rango de tiempo de últimos 60 minutos.

**Splunk Query**  
```index=* sourcetype=nifi* | dedup host | table host ```

![image](/nifi-monitoring-splunk/assets/images/splunk/sourcetype_search.png)

El resultado de esta búsqueda retornará el listado de host que deben ser
configurados en el lookup.

!!! note "¿No hay resultados en esa búsqueda?"
    Los procesos de NiFi ya tienen que estar mandando datos para que esta
    búsqueda devuelva algo:

    1. Estrategia push: inicia el flow de NiFi — ver [Inicia el flow](configuration-push.es.md#5-inicia-el-flow).
    2. Estrategia pull: los data inputs configurados deben estar habilitados.

    ![image](/nifi-monitoring-splunk/assets/images/splunk/4_configure_instances.png)

Una vez que el lookup tiene una fila por cada host, la información queda
accesible desde el panel Overview.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview_lookup.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/3_configure_instances.png)

Siguiente: elige tu versión y estrategia de recolección en la barra
lateral, bajo **Configurar Nifi Monitoring 1.2** o
**Configurar Nifi Monitoring 2.0**.
