# Vista General

La aplicación consta del siguiente árbol de navegación:

- App Nifi Monitoring
    - Home
    - Nifi Monitor Overview
    - Nifi Instance Panels
        - Flow's & Metrics Monitoring Panel
        - Bulletin Monitoring Panel
        - Logs Monitoring Panel
    - Configuration
        - Lookups
        - NiFi Instances
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
Con este panel podemos observar el comportamiento de los errores del sistema de bulletin en nifi, ya que es muy importante en el caso de ocurrir algún error poder realizar la correcta trazabilidad, con el fin de corregir la situación lo antes posible.

![image](/nifi-monitoring-splunk/assets/images/splunk/logs_panel.png)