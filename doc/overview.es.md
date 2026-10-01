# Dashboards

Ocho vistas, desde la flota completa hasta una sola conexión. Cada una
responde una pregunta:

| Vista | La pregunta que responde |
|---|---|
| [Overview](#overview) | ¿Está bien la flota ahora? |
| [Instance](#instance) | ¿Qué está pasando en esta instancia? |
| [Components](#components) | ¿Qué procesador, grupo o conexión es el cuello de botella? |
| [Bulletins](#bulletins) | ¿Qué errores está reportando NiFi? |
| [Logs](#logs) | ¿Qué dicen los archivos de log de NiFi? |
| [Cluster](#cluster) | ¿Está completo el cluster? |
| [Alerts](#alerts) | ¿Sobre qué puede alertar la app, y qué se disparó? |
| [Collection Health](#collection-health) | ¿Funciona la recolección de datos? |

**Overview** dice qué instancia necesita atención, **Instance** dice qué le
pasa, y **Components** dice qué procesador o conexión es la causa. Cada
drilldown conserva la instancia y el rango de tiempo que se estaban
mirando.

Funcionan igual sea cual sea el camino de los datos: la TA consultando a
NiFi (pull) o el flujo dentro de NiFi enviando al HEC (push). Un panel que
necesita una fuente que no habilitaste lo dice en su descripción.

En Splunk, el menú de la app sigue el mismo orden, con **NiFi Instances** y
**Collection Health** bajo **Configuration**, y **Search** al final.

Cada color sale de un umbral, y cada umbral se puede definir para toda la
app o para una instancia — ver [Umbrales](references.es.md#umbrales).

## Overview

La página de inicio: ¿está bien la flota ahora? Seis cifras y, debajo, una
fila por instancia que está en el [inventario](instance-lookup.es.md) o que
envió datos, de la peor a la mejor.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_overview.png)

| Indicador | Qué te dice |
|---|---|
| **Healthy instances** | Las instancias sanas sobre el total, hayan enviado datos o no. |
| **ERROR bulletins · 15 min** | Boletines ERROR de toda la flota en los últimos 15 minutos; rojo desde el primero. |
| **Worst heap** | El mayor uso de heap de cualquier instancia, y de cuál. Se colorea con el umbral de heap propio de esa instancia. |
| **Worst repository** | El repositorio de FlowFiles, contenido o procedencia más lleno de cualquier instancia, y de cuál. Se colorea con el umbral de repositorio de esa instancia. |
| **FlowFiles queued** | Todo lo que espera en una cola, en todas las instancias. |
| **Invalid components** | Procesadores y servicios que NiFi no va a iniciar; ámbar desde el primero. |
| **Instances** | Una fila por instancia: salud y su motivo, cluster, versión de NiFi, cuándo llegó el último dato, componentes (corriendo, detenidos, inválidos, deshabilitados), cola, heap, peor repositorio y boletines ERROR recientes. Un clic en la fila la abre en **Instance**. |
| **Bulletins by level** | Boletines en intervalos de 10 minutos, en el rango elegido. |
| **FlowFiles queued by instance** | La cola en el tiempo de las cuatro instancias con más carga; el resto se agrupa en OTHER. |

La salud de cada instancia es *Critical*, *Degraded*, *Stale* (sin datos por
más tiempo del que permite su intervalo de polling), *No data* o *Healthy*,
y la columna del motivo dice qué umbral la decidió. Una instancia del
inventario que nunca envió nada igual tiene su fila; una que envía datos
pero no está en el inventario también, con cluster "—".

## Instance

Qué está pasando en una instancia. Abre en la peor de la lista del
Overview, y el selector de arriba cambia a otra.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_instance.png)

| Indicador | Qué te dice |
|---|---|
| **Estado** | Salud y su motivo, versiones de NiFi y de Java, uptime y cuándo llegó el último dato. |
| **Active threads**, **FlowFiles queued**, **Bytes queued** | Qué está haciendo la instancia en este momento. |
| **Components** | Corriendo · detenidos · inválidos · deshabilitados. |
| **Versioned process groups** | Al día · modificados localmente · desactualizados · sin poder sincronizar con su registry. |
| **ERROR bulletins · 15 min** | Los errores recientes de esta instancia. |
| **Heap used** | % del heap máximo en el tiempo, con el umbral de esta instancia como línea punteada. |
| **JVM threads** | Threads totales y daemon. |
| **Load average** | Load de 1 minuto contra los cores disponibles (punteado). |
| **GC time per collector** | Milisegundos en cada garbage collector cada 5 minutos. |
| **Repositories** | Una fila por repositorio —contenido y procedencia pueden ser varios— con su uso actual. |
| **Repository usage** | % usado en el tiempo, con el umbral de esta instancia punteado. |
| **Data in, out and processed** | MB cada 5 minutos recibidos, enviados y escritos por el flujo completo. |
| **FlowFiles received and sent** | FlowFiles cada 5 minutos desde y hacia fuera de NiFi. |
| **Recent bulletins** | Los diez más recientes; un clic abre **Bulletins** filtrado a esta instancia. |

Los dos gráficos de throughput necesitan *Flow metrics* habilitado en el
input de la TA en el camino pull; en el camino push salen de la Reporting
Task.

## Components

Qué procesador, process group o conexión es el cuello de botella. Los
selectores eligen la instancia, procesadores o process groups, la métrica y
cómo se agrega.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_components.png)

| Indicador | Qué te dice |
|---|---|
| **Connections over backpressure threshold** | Conexiones cuya cantidad de objetos o tamaño está en el umbral de backpressure de esta instancia o sobre él. |
| **Reaching backpressure soon** | Conexiones que el propio NiFi predice que alcanzarán el backpressure dentro de la hora. |
| **Components with history** | Cuántos componentes tienen su historial de estado recolectado. |
| **Top 10 by the selected metric** | Los diez componentes con más carga según tiempo de tarea, FlowFiles que entran y salen, bytes leídos y escritos, etc., cada uno con su línea de tendencia. Un clic en uno lo grafica abajo. |
| **Busiest connections** | Qué tan llena está cada conexión, por cantidad de objetos y por tamaño, y la estimación de NiFi del tiempo que falta para el backpressure. |
| **Selected component** | La métrica elegida cada 5 minutos para el componente seleccionado arriba. |

Los componentes listados son aquellos cuyo historial de estado se
recolecta: los ids de procesadores y process groups configurados en el
input de la TA ([Status history](configuration-pull.es.md#4-status-history)),
o en `processors_list` y `process_groups_list` del flujo push. Las
conexiones necesitan *Flow metrics* en el input de la TA.

## Bulletins

Los errores y advertencias que generan los componentes de NiFi, por
cualquiera de los dos caminos de recolección. Se filtra por instancia,
nivel, categoría o componente.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_bulletins.png)

| Indicador | Qué te dice |
|---|---|
| **Bulletins**, **ERROR**, **WARNING** | Cuántos hubo en el rango elegido, y de qué nivel. |
| **Components affected** | Cuántos componentes distintos los generaron. |
| **Bulletins over time** | Por hora, por nivel. |
| **Components with most bulletins** | Dónde mirar primero. |
| **Bulletin details** | Cada mensaje completo, con su instancia, nivel, categoría, componente y grupo. |

El process group llega como nombre en el camino push y como id en el camino
pull, que es todo lo que entrega el bulletin board de NiFi.

## Logs

Los archivos de log de NiFi, enviados por un Universal Forwarder
(cualquiera de ellos) o por el flujo push (solo los logs de aplicación,
bootstrap y user — Deprecations y API requests necesitan el forwarder). Se
filtra por instancia y severidad, y se buscan los eventos.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_logs.png)

| Indicador | Qué te dice |
|---|---|
| **Events by level** | Eventos por nivel en los logs de NiFi, todos menos el de requests. |
| **Events** | Los eventos de `nifi-app.log`, del más nuevo al más viejo, que coinciden con la búsqueda. |
| **Deprecated usage · last 7 days** | Lo que una instancia usa y una versión posterior de NiFi elimina, desde `nifi-deprecation.log` — la lista a resolver antes de pasar a NiFi 2.x. |
| **Requests by status class** | `nifi-request.log` en intervalos de 5 minutos, por 2xx, 3xx, 4xx y 5xx. |
| **Top failing requests** | Las peticiones 4xx y 5xx que más fallan. |

## Cluster

Si un cluster de NiFi está completo.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_cluster.png)

| Indicador | Qué te dice |
|---|---|
| **Connected nodes** | Nodos conectados sobre el total. |
| **Primary node**, **Cluster coordinator** | Qué nodo tiene cada rol. |
| **Nodes** | Una fila por nodo: estado, roles, último heartbeat, threads activos, cola y heap. |
| **Heap used by node** | Heap por nodo — el agregado oculta al nodo que se está quedando sin recursos. |
| **FlowFiles queued by node** | Cola por nodo. |

Un NiFi standalone no tiene nada que mostrar aquí. La TA detecta el
cluster por sí sola; no hay nada que habilitar.

## Alerts

Las alertas que trae la app, si cada una está habilitada, y cuáles se
dispararon en el rango elegido.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_alerts.png)

| Indicador | Qué te dice |
|---|---|
| **Alerts enabled** | Cuántas de las alertas incluidas están activas. |
| **Fired in range** | Cuántas veces se disparó alguna; rojo desde la primera. |
| **Alerts shipped with the app** | Cada alerta, si está habilitada, su condición y su programación. |
| **Fired** | Cada disparo: cuándo, qué alerta y su severidad. |

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

| Indicador | Qué te dice |
|---|---|
| **Events the app can see** | Eventos alcanzables a través del macro `index_nifi`; cero significa que el macro apunta al índice equivocado. |
| **Instances behind** | Instancias que están *Stale* o en *No data*. |
| **TA HTTP errors** | Peticiones que la TA no pudo completar. |
| **Last data per instance and source** | Cuándo envió cada instancia cada tipo de dato por última vez: a tiempo, atrasado o faltante según su intervalo de polling. Una celda vacía es una fuente que no está habilitada para esa instancia, no un error. |
| **TA HTTP errors by status code** | Un fallo de login indica credenciales incorrectas, 403 permisos faltantes, 404 un id de componente equivocado, 5xx un problema del lado de NiFi. |
| **Where NiFi data is** | En qué índice están realmente los datos de NiFi: si no es al que apunta el macro, cambia el macro (ver [Actualizar](upgrading.es.md)). |
