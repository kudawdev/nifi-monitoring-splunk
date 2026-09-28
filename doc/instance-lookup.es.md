# Lookup de Instancias

Configura esto sin importar la versión de la app o la estrategia de
recolección que uses — sin esto, ningún panel del dashboard muestra
datos.

Requiere [NIFI Monitoring instalado](installation.es.md).

Abre la app **Nifi Monitoring** (no la TA):

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_monitoring_home.png)

En la barra lateral izquierda, ve a **Configuration > NiFi Instances**.
Esto abre el editor de lookups sobre el lookup `instance`:

![image](/nifi-monitoring-splunk/assets/images/splunk/instance_lookup_editor.png)

Para encontrar los valores exactos de host a ingresar, ejecuta (últimos
60 minutos):

```
index=* sourcetype=nifi* | dedup host | table host
```

![image](/nifi-monitoring-splunk/assets/images/splunk/sourcetype_search.png)

!!! note "¿No hay resultados en esa búsqueda?"
    Los procesos de NiFi ya tienen que estar mandando datos para que esta
    búsqueda devuelva algo:

    1. Estrategia push: inicia el flow de NiFi — ver [Inicia el flow](configuration-push.es.md#5-inicia-el-flow).
    2. Estrategia pull: los data inputs configurados deben estar habilitados.

Agrega una fila por host, con el cluster al que pertenece. Una vez que
cada host tiene su fila, el panel Overview lo toma:

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview_lookup.png)

Siguiente: elige tu versión y estrategia de recolección en la barra
lateral, bajo **Configurar Nifi Monitoring 1.2** o
**Configurar Nifi Monitoring 2.0**.
