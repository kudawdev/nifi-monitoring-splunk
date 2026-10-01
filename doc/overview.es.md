# Vista General

Dentro de Splunk, el menú propio de la app es:

- Overview
- Instance
- Components
- Bulletins
- Logs
- Cluster
- Alerts
- Configuration
    - NiFi Instances
    - Collection Health
- Search

Las vistas van de la flota a un único componente: **Overview** dice qué
instancia necesita atención, **Instance** dice qué le pasa, y
**Components** dice qué procesador o conexión es la causa. Cada drilldown
conserva la instancia y el rango de tiempo que se estaban mirando.

Funcionan igual sea cual sea el camino de los datos: la TA consultando a
NiFi (pull) o el flujo dentro de NiFi enviando al HEC (push). Un panel que
necesita una fuente que no habilitaste lo dice en su descripción.

## Overview

La página de inicio: ¿está bien la flota ahora? Seis cifras y, debajo, una
fila por instancia del [inventario](instance-lookup.es.md), de la peor a la
mejor.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_overview.png)

- **Healthy instances**, **ERROR bulletins** de los últimos 15 minutos,
  **Worst heap**, **Worst repository**, **FlowFiles queued** e **Invalid
  components**. Heap y repositorio nombran la instancia a la que
  pertenecen y se colorean con el [umbral](references.es.md#umbrales)
  propio de esa instancia.
- **Instances**: cada fila tiene un estado de salud y su motivo —
  *Critical*, *Degraded*, *Stale* (sin datos por más tiempo del que permite
  su intervalo de polling), *No data* o *Healthy*. Una instancia del
  inventario que nunca envió nada igual tiene su fila. Un clic en la fila
  la abre en **Instance**.
- Boletines por nivel y FlowFiles en cola por instancia, en el rango de
  tiempo elegido.

## Instance

Qué está pasando en una instancia. Abre en la primera del inventario, de
la peor a la mejor, y el selector de arriba cambia a otra.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_instance.png)

- **Estado**: salud y su motivo, versiones de NiFi y de Java, uptime y
  cuándo llegó el último dato.
- **Now**: threads activos, lo que está en cola, componentes en ejecución,
  detenidos, inválidos y deshabilitados, process groups versionados y
  boletines ERROR recientes.
- **JVM and system**: heap (con el umbral de esta instancia como línea
  punteada), threads, load average contra los cores disponibles y tiempo
  en cada garbage collector.
- **Storage**: una fila por repositorio —contenido y procedencia pueden
  ser varios— y su uso en el tiempo.
- **Throughput**: datos y FlowFiles que entran, salen y escribe el flujo
  completo. En el camino pull necesita *Flow metrics* habilitado en el
  input de la TA; en el camino push sale de la Reporting Task.
- **Recent bulletins**, con un enlace a **Bulletins** filtrado a esta
  instancia.

## Components

Qué procesador, process group o conexión es el cuello de botella.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_components.png)

- Conexiones sobre su umbral de backpressure, y las que NiFi predice que
  lo van a alcanzar pronto.
- **Top 10** de componentes según la métrica que elijas —tiempo de tarea,
  FlowFiles que entran y salen, bytes leídos y escritos, etc.— con una
  línea de tendencia. Un clic en uno lo grafica abajo.
- **Busiest connections**: qué tan llena está cada una, por cantidad de
  objetos y por tamaño, y la estimación de NiFi del tiempo que falta para
  el backpressure.

Los componentes listados son aquellos cuyo historial de estado se
recolecta: los ids de procesadores y process groups configurados en el
input de la TA ([Status history](configuration-pull.es.md#4-status-history)),
o en `processors_list` y `process_groups_list` del flujo push. Las
conexiones necesitan *Flow metrics* en el input de la TA.

## Bulletins

Los errores y advertencias que generan los componentes de NiFi, por
cualquiera de los dos caminos de recolección.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_bulletins.png)

Se filtra por instancia, nivel, categoría o componente. La tabla de
detalle muestra cada mensaje completo; el process group llega como nombre
en el camino push y como id en el camino pull, que es todo lo que entrega
el bulletin board de NiFi.

## Logs

Los archivos de log de NiFi, enviados por un Universal Forwarder o por el
flujo push.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_logs.png)

- **Application**: `nifi-app.log` por nivel, y sus eventos. El cuadro de
  búsqueda se aplica a los eventos.
- **Deprecations**: lo que una instancia usa y una versión posterior de
  NiFi elimina, desde `nifi-deprecation.log` — la lista a resolver antes de
  pasar a NiFi 2.x.
- **API requests**: `nifi-request.log` por clase de estado, y las
  peticiones que más fallan.

## Cluster

Si un cluster de NiFi está completo: nodos conectados sobre el total, qué
nodo es el primario y cuál coordina, y heap y cola por nodo — el agregado
oculta al nodo que se está quedando sin recursos.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_cluster.png)

Un NiFi standalone no tiene nada que mostrar aquí. La TA detecta el
cluster por sí sola; no hay nada que habilitar.

## Alerts

Las alertas que trae la app, si cada una está habilitada, y cuáles se
dispararon en el rango elegido.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_alerts.png)

Vienen **deshabilitadas**. Habilita las que quieras en *Settings ›
Searches, reports, and alerts* (app *nifi_monitoring*) y agrega ahí las
acciones —correo, webhook—, porque ninguna viene configurada:

| Alerta | Se dispara cuando |
|---|---|
| Instance without data | una instancia del inventario no envía nada por más tiempo del que permite su intervalo de polling |
| Repository filling up | un repositorio alcanza el umbral de repositorio de la instancia |
| Sustained high heap | el heap se mantiene sobre el umbral de heap de la instancia durante varias muestras seguidas |
| ERROR bulletin spike | una instancia genera más boletines ERROR que su umbral de boletines |
| Backpressure | una conexión alcanza el umbral de backpressure, o NiFi predice que lo hará pronto (necesita *Flow metrics*) |
| Cluster node disconnected | un miembro del cluster no está conectado |
| Versioned flow sync failure | un process group versionado no puede sincronizarse con su registry |
| TA HTTP errors | la TA no puede iniciar sesión en NiFi, es rechazada o recibe un error del servidor |

Todas las alertas usan los mismos umbrales que los paneles; ver
[Umbrales](references.es.md#umbrales).

## Configuration

### NiFi Instances

Abre el [Lookup de Instancias](instance-lookup.es.md): una fila por
instancia o cluster monitoreado, con el nombre de su cluster y,
opcionalmente, umbrales propios.

### Collection Health

Si la recolección de datos está funcionando — revisa aquí primero cuando
un panel está vacío.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_collection_health.png)

- Cuántos eventos ve la app a través del macro `index_nifi`, y en qué
  índice están realmente los datos de NiFi: si no coinciden, apunta el
  macro a ese índice (ver [Actualizar](upgrading.es.md)).
- Cuándo envió cada instancia cada tipo de dato por última vez, marcado
  como atrasado o faltante según su intervalo de polling. Una celda vacía
  es una fuente que no está habilitada para esa instancia, no un error.
- Los errores HTTP de la TA por código de estado: un fallo de login indica
  credenciales incorrectas, 403 permisos faltantes, 404 un id de
  componente equivocado, 5xx un problema del lado de NiFi.
