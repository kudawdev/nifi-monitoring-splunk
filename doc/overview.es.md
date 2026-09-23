# Vista General

La aplicación consta del siguiente árbol de navegación:

- App Nifi Monitoring
    - Home
    - Nifi Monitor Overview
    - Nifi Instance Panels
        - Flow's & Metrics Monitoring Panel
        - Bulletin Monitoring Panel
        - Logs Monitoring Panel
        - Status History
    - Configuration
        - NiFi Instances
        - Internal Monitoring
    - Alerts
    - Search

## Home

La página principal de la aplicación de Nifi Monitoring donde se observa un pequeño diagrama que muestra el tipo de información obtenida desde los servidores NIFI para ser analizada por SPLUNK.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

## NIFI Monitor Overview

En el panel de overview se puede observar un resumen de los distintos servidores NIFI monitoreados, muy similar a la barra superior que encontramos en el aplicativo inicial. Los indicadores son los siguientes:

- Estado del servidor por nodo
- Estado de repositorios por nodo
- Comportamiento de errores de bulletin por nodo

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview.png)

## Nifi Instance Panels

En el siguiente grupo de paneles obtendremos detalles de distintas fuentes de datos, pero analizando los nodos de manera individual.

### Flow's & Metrics Monitoring Panel
El siguiente panel muestra detalle de la operación del nodo, analizando distintas métricas del funcionamiento, así como también disponibilidad de uso de algunos de los recursos del nodo.

![image](/nifi-monitoring-splunk/assets/images/splunk/monitoring_panel.png)

Para hacer mas amigable la visualizacion de los datos, los paneles cuentan con una serie de selectores de escala entendiendo la variabilidad de volumenes que puede manejar un servidor.

![image](/nifi-monitoring-splunk/assets/images/splunk/behaviour_overtime_1.png)

Adicionalmente se dispone información de la JVM operativa en cada nodo, y así de esta manera tener una vista completa del funcionamiento de la plataforma.

![image](/nifi-monitoring-splunk/assets/images/splunk/behaviour_overtime_2.png)

### Bulletin Monitoring Panel
En el siguiente panel podemos observar principalmente el comportamiento de los errores del sistema de bulletin en nifi, ya que es muy importante en el caso de ocurrir algún error poder realizar la correcta trazabilidad, con el fin de corregir la situación lo antes posible.

![image](/nifi-monitoring-splunk/assets/images/splunk/bulletin_panel.png)

### Logs Monitoring Panel
En el siguiente panel podemos observar los logs de aplicación, bootstrap, usuario y request de NiFi recolectados desde cada instancia configurada, para buscar y correlacionar la actividad de logs sin abrir una terminal en cada host de NiFi.

![image](/nifi-monitoring-splunk/assets/images/splunk/logs_panel.png)

### Status History

Este panel grafica el status history de los procesadores y grupos de procesos específicos configurados en [Status history](configuration.es.md#4-status-history) del data input — throughput, flow files en cola y los demás contadores que muestra la propia vista Status History de NiFi, a lo largo del tiempo y por instancia.

## Configuration

### NiFi Instances

Abre el editor del [Lookup de Instancias](configuration.es.md#lookup-de-instancias), donde toda instancia de NiFi monitoreada (o cluster) debe tener una fila antes de que sus datos sean accesibles desde los paneles anteriores.

### Internal Monitoring

Etiquetado **Nifi TA Monitoring** en la app. Reporta sobre el propio add-on en lugar de sobre NiFi: cuántos eventos tiene realmente cada sourcetype e index — el primer lugar donde mirar cuando un panel está vacío o al [actualizar](upgrading.es.md) y hay que cambiar la macro `index_nifi` — y, en un cluster, los miembros, sus roles y su heap por nodo.
