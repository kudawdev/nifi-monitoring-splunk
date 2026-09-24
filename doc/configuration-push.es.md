# Estrategia push: Envío Directo

Un flow que corre dentro de NiFi llama a la propia API de NiFi y envía el
resultado directo al HTTP Event Collector (HEC) de Splunk — del lado de
Splunk no hay que alcanzar a NiFi para nada. ¿No estás seguro de que esta
es la estrategia que necesitás? Ver
[Elegir una estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion).

## 1. Configura el HTTP Event Collector (HEC) en Splunk

Un HTTP Event Collector (HEC) recibe eventos de NiFi por HTTP o HTTPS.

Desde el menú de Splunk, ve a **Settings > Data Inputs > HTTP Event
Collector** y agrega uno nuevo:

- Asigna un nombre al data input.
- Establece el sourcetype en **Automatic**.
- Establece *App Context* en **NIFI Monitoring**.
- Selecciona el index — usa uno dedicado, y créalo primero si no existe.

Al terminar se crea un **Token Value**, necesario luego para configurar
el flow de NiFi.

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_1.png)
![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_2.png)
![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_3.png)

!!! warning "Iguala el TLS del HEC, no lo desactives"
    Splunk crea todo token de HEC nuevo con **Enable SSL** activado. Los
    procesadores `InvokeHTTP` de este flow envían HTTP plano, así que a
    menos que uno de los dos lados cambie, el desajuste falla como un
    "Connection reset" a nivel TCP — no como un error claro de
    certificado o autenticación.

    Deja el HEC en HTTPS y configura NiFi para eso en su lugar: pon
    `splunk_hec` (más abajo) en `https://<host>:8088/`, y agrégale a los
    procesadores `InvokeHTTP` de **SendHEC** un SSL Context Service que
    confíe en el certificado de Splunk — el mismo tipo de controller
    service que se usa en otras partes de esta página para el certificado
    del propio NiFi.

    Destildar **Enable SSL** en **Settings > Data Inputs > HTTP Event
    Collector > Global Settings** es un cambio a nivel de toda la
    instancia: afecta a todos los tokens de HEC de ese Splunk, no solo a
    este, y manda cada evento y cada token en texto plano. Considera esto
    solo en un entorno de prueba aislado que controles, nunca en una
    instancia de Splunk compartida o de producción.

## 2. Importa el Flow Definition en NiFi

Elige el archivo que corresponde a tu versión de NiFi. No son intercambiables:

| Tu NiFi | Importa |
|---|---|
| 1.16 – 1.28 | [`flow_definition/nifi-1.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-1.x/NiFiMonitoring.json) |
| 2.0 en adelante | [`flow_definition/nifi-2.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-2.x/NiFiMonitoring.json) |

!!! warning "No importes el flow de 1.x en NiFi 2.x"
    Se importa sin ningún error, pero queda mal configurado de una forma
    que no se nota a simple vista. NiFi 2.0 eliminó el Variable Registry,
    así que las seis variables de las que depende este flow desaparecen
    sin ningún aviso al importarlo. Cinco procesadores que dependen
    directamente de esas variables quedan inválidos de inmediato — pero
    no son los únicos afectados. Otros procesadores validan sin problema
    aunque también dependan de referencias como `${splunk_hec}` que ya no
    resuelven a nada; esos fallan recién al iniciar el flow, cuando
    intentan usar ese valor, ahora vacío.

Arrastra una caja de *process group* al lienzo, selecciona el ícono de
importación en la ventana emergente y elige el archivo. El grupo de
procesos importado contiene:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

## 3. Configura los ajustes del flow

El mecanismo cambia según la versión de NiFi, porque NiFi 2.0 eliminó el
Variable Registry.

### NiFi 2.x — parameter context

Al importar el flow de 2.x se crea un parameter context llamado **NiFi
Monitoring** y queda asignado al grupo de procesos. Ábrelo con clic
derecho sobre el grupo > *Parameters*, o desde el menú superior derecho >
*Parameter Contexts*.

Dos de sus parámetros se distribuyen vacíos a propósito, y hasta que
tengan valor los dos procesadores `GenerateFlowFile` quedan inválidos.
Es intencional: que NiFi se niegue a arrancar un procesador con una
propiedad requerida vacía es mejor que arrancarlo apuntando a los ids de
componentes de otra instalación.

### NiFi 1.x — variables

Clic derecho sobre la caja NiFiMonitoring > *Variables*.

En cualquiera de los dos casos, los ajustes son los mismos:

| Ajuste | Qué es |
|---|---|
| `nifi_api_url` | La API REST de esta instancia, ej. `http://127.0.0.1:8080/nifi-api/` |
| `nifi_path` | Directorio de instalación de NiFi, para leer sus logs. En cluster, la misma ruta en cada nodo |
| `process_groups_list` | Ids de los grupos de procesos a monitorear, uno por línea |
| `processors_list` | Ids de los procesadores a monitorear, uno por línea |
| `splunk_hec` | El servidor Splunk con el input HEC, ej. `http://<host>:8088/` |
| `splunk_hec_token` | El token del [paso 1](#1-configura-el-http-event-collector-hec-en-splunk). En 2.x es un parámetro **sensible**, así que NiFi nunca lo escribe en un flow exportado |

!!! note "Si tu NiFi es HTTPS"
    Poner `nifi_api_url` en `https://...` deja inválidos a los
    procesadores `GetHTTP` de **Monitoring API**, con warnings de "SSL
    context is invalid", hasta que tengan uno que confíe en el
    certificado de tu propio NiFi. Agrega un **StandardSSLContextService**
    dentro de los Controller Services de ese process group (clic derecho
    sobre el process group > *Configure* > *Controller Services*),
    completando solo **Truststore Filename**, **Truststore Password** y
    **Truststore Type** — solo necesita confiar en el certificado de NiFi,
    no presentar uno propio. Habilítalo, y asignalo en cada `GetHTTP`
    inválido.

## 4. Configura los componentes de NiFi

!!! note "Las capturas de abajo son de NiFi 1.x"
    NiFi 2.x rehizo su interfaz, así que estas imágenes ya no coinciden con lo
    que vas a ver. Los pasos en sí no cambian — el mismo controller service y
    las mismas tres reporting tasks, desde los mismos menús — pero las
    pantallas se ven distintas. Recapturarlas para 2.x está pendiente.

Con los ajustes del flow ya cargados (el parameter context en 2.x, las
variables en 1.x), crea los siguientes componentes desde el menú >
**Controller Settings**.

![image](/nifi-monitoring-splunk/assets/images/nifi/controller_settings.png)
![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings.png)

En la pestaña **Reporting Task Controller Services**, agrega el
controller service **JsonRecordSetWriter** — parsea la salida de las
reporting tasks para indexarla en Splunk. Haz clic en **(+)**, fíltralo,
selecciónalo y agrégalo.

![image](/nifi-monitoring-splunk/assets/images/nifi/add_controller_service.png)

Habilítalo: haz clic en el ícono de rayo (ϟ) y confirma.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_2.png)

En la pestaña **Reporting Task** de la misma ventana, agrega estas tres:

- MonitorDiskUsage
- SiteToSiteBulletinReportingTask
- SiteToSiteMetricsReportingTask

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_3.png)
![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_task.png)

Configura cada una:

- **MonitorDiskUsage**: reporta cuando un filesystem supera el umbral de
  uso que definas.

![image](/nifi-monitoring-splunk/assets/images/nifi/monitor_disk_usage.png)

- **SiteToSiteBulletinReportingTask**: envía cada bulletin en el momento
  en que ocurre.

    * Destination URL: `http://${hostname(true)}:8080/nifi` — mismo host
      y puerto que `nifi_api_url` de arriba, solo que sin `/nifi-api`
    * Input Port Name: `bulletin_report`
    * Instance URL: igual que Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`

![image](/nifi-monitoring-splunk/assets/images/nifi/bulletin_reporting_task.png)

- **SiteToSiteMetricsReportingTask**: envía métricas de flow y de JVM.

    * Destination URL: `http://${hostname(true)}:8080/nifi` — mismo host
      y puerto que `nifi_api_url` de arriba, solo que sin `/nifi-api`
    * Input Port Name: `reporting_task`
    * Instance URL: igual que Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`
    * Output Format: `Record Formats`

![image](/nifi-monitoring-splunk/assets/images/nifi/metrics_reporting_task.png)

!!! note "Si tu NiFi es HTTPS"
    Que `nifi_api_url` sea `https://` hace que las URL de arriba también
    lo sean, lo que agrega una propiedad **SSL Context Service** en las
    dos reporting tasks. Asígnale un `StandardSSLContextService` con los
    mismos valores de Truststore del [paso 3](#3-configura-los-ajustes-del-flow).
    Crea este desde la misma ventana de **Controller Settings** donde
    están estas reporting tasks, no desde el diálogo *Configure* del
    process group: las reporting tasks son componentes a nivel de todo
    NiFi y no ven un controller service que esté dentro de un process
    group, aunque sea el mismo NiFi y el mismo certificado.

Inicia cada reporting task: haz clic en **►** en cada una.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_4.png)

## 5. Inicia el flow

Haz clic derecho sobre el grupo de procesos y selecciona **Start**.

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_1.png)

Los datos ya fluyen hacia Splunk. Para que aparezcan en los paneles de la
app, configura también el [Lookup de Instancias](configuration.es.md#lookup-de-instancias).
