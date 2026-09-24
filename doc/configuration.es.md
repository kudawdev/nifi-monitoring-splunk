# Configuración de NIFI

Esta página detalla la configuración del lado de NiFi para la estrategia
de recolección que ya elegiste en
[Elegir una estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion):

- ¿Elegiste **push**? Ve a [Estrategia push: Envío Directo](configuration-push.es.md).
- ¿Elegiste **pull**? Ve a [Estrategia pull: Splunk Data Input NiFi](configuration-pull.es.md).

Configura solo una — usar las dos duplica cada evento.

## Común a ambas estrategias

Configura esto sin importar qué estrategia uses — sin esto, ninguna de las
dos muestra datos en los paneles de la app.

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
