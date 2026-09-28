# Estrategia push: Envío Directo (2.0)

!!! warning "Borrador, todavía no validado en vivo"
    A diferencia de [Estrategia pull](config-nifi-monitoring-2-0.md), nadie
    corrió esto de punta a punta contra un NiFi 2.x + Splunk real todavía.
    Está armado con las partes del walkthrough de push pre-2.0.0 que son
    independientes de la versión (configurar el HEC, iniciar el flow), más
    lo que se sabe que NiFi 2.x requiere en vez del Variable Registry
    (parameter context). Tratá cada paso acá como no verificado hasta que
    alguien lo corra y lo confirme.

Un flow que corre dentro de NiFi llama a la propia API de NiFi y envía el
resultado directo al HTTP Event Collector (HEC) de Splunk — del lado de
Splunk no hay que alcanzar a NiFi para nada. ¿No estás seguro de que esta
es la estrategia que necesitas? Ver
[Elegir una estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion).

Requiere las dos apps ya instaladas (ver
[Instalar NIFI Monitoring](installation.es.md)): **Nifi Monitoring TA**
parsea los eventos que manda este flow, aunque en esta estrategia no
configures ningún input dentro de ella.

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
    confíe en el certificado de Splunk.

    Destildar **Enable SSL** en **Settings > Data Inputs > HTTP Event
    Collector > Global Settings** es un cambio a nivel de toda la
    instancia: afecta a todos los tokens de HEC de ese Splunk, no solo a
    este, y manda cada evento y cada token en texto plano. Considera esto
    solo en un entorno de prueba aislado que controles, nunca en una
    instancia de Splunk compartida o de producción.

## 2. Importa el Flow Definition en NiFi

Importa [`flow_definition/nifi-2.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-2.x/NiFiMonitoring.json)
— no el de 1.x. NiFi 2.0 eliminó el Variable Registry del que depende el
flow de 1.x; ese archivo se importa sin error en una instancia 2.x, pero
varios procesadores quedan inválidos o fallan en silencio una vez
iniciado.

Arrastra una caja de *process group* al lienzo. En el diálogo **Create
Process Group**, ponele un nombre y hace clic en el ícono chico junto a
*Name* para subir el archivo del flow:

![image](/nifi-monitoring-splunk/assets/images/nifi/create_process_group_2x.png)

Una vez elegido el archivo, *Parameter Context* se reemplaza por un
aviso de que los parámetros van a venir del flow subido, y el nombre del
archivo aparece bajo *File to upload*:

![image](/nifi-monitoring-splunk/assets/images/nifi/create_process_group_2x_upload.png)

Hace clic en **Add**. El process group se crea con cada procesador que
necesita un parámetro todavía vacío marcado como inválido — esperable
hasta que los completes en el paso siguiente:

![image](/nifi-monitoring-splunk/assets/images/nifi/process_group_created_2x.png)

Contiene:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

## 3. Configura los ajustes del flow

Al importar el flow de 2.x se crea un parameter context llamado **NiFi
Monitoring** y queda asignado al grupo de procesos. Ábrelo con clic
derecho sobre el grupo > *Parameters*, o desde el menú superior derecho >
*Parameter Contexts*, y configura:

| Parámetro | Qué es |
|---|---|
| `instance_name` | El `host` con que se envían los eventos `nifi:api:*`: el `host` de la fila de este NiFi en la lookup `instance`. **Obligatorio en un cluster**, donde la API se consulta desde el nodo primario — si queda vacío, cada evento lleva el nombre del nodo que sea primario en ese momento, que cambia en cada failover y no coincide con la lookup, así que el overview muestra el cluster como Down. Vacío usa el hostname del nodo, que es lo correcto para un NiFi de un solo nodo. Los logs siempre llevan el nombre del nodo |
| `nifi_api_url` | La API REST de esta instancia, ej. `http://127.0.0.1:8080/nifi-api/` |
| `nifi_path` | Directorio de instalación de NiFi, para leer sus logs. En cluster, la misma ruta en cada nodo |
| `process_groups_list` | Ids de los grupos de procesos a monitorear, uno por línea |
| `processors_list` | Ids de los procesadores a monitorear, uno por línea |
| `splunk_hec` | El servidor Splunk con el input HEC, ej. `http://<host>:8088/` |
| `splunk_hec_token` | El token del [paso 1](#1-configura-el-http-event-collector-hec-en-splunk). Es un parámetro **sensible**, así que NiFi nunca lo escribe en un flow exportado |

Dos parámetros se distribuyen vacíos a propósito, y hasta que tengan
valor los dos procesadores `GenerateFlowFile` quedan inválidos. Es
intencional: que NiFi se niegue a arrancar un procesador con una
propiedad requerida vacía es mejor que arrancarlo apuntando a los ids de
componentes de otra instalación.

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

Con el parameter context ya cargado, crea los siguientes componentes
desde el menú > **Controller Settings**.

!!! warning "Capturas pendientes"
    La [página push de 1.2](configuration-push.es.md#4-configura-los-componentes-de-nifi)
    tiene capturas para este paso, pero NiFi 2.x rehizo su interfaz, así
    que no coinciden con lo que vas a ver acá. Los componentes y sus
    ajustes deberían ser los mismos — mismo controller service, mismas
    tres reporting tasks — pero falta confirmarlo contra un NiFi 2.x real.

En la pestaña **Reporting Task Controller Services**, agrega el
controller service **JsonRecordSetWriter** — parsea la salida de las
reporting tasks para indexarla en Splunk. Habilítalo.

En la pestaña **Reporting Task** de la misma ventana, agrega y configura
estas tres:

- **MonitorDiskUsage**: reporta cuando un filesystem supera el umbral de
  uso que definas.
- **SiteToSiteBulletinReportingTask**: envía cada bulletin en el momento
  en que ocurre.

    * Destination URL: `http://${hostname(true)}:8080/nifi` — mismo host
      y puerto que `nifi_api_url` de arriba, solo que sin `/nifi-api`
    * Input Port Name: `bulletin_report`
    * Instance URL: igual que Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`

- **SiteToSiteMetricsReportingTask**: envía métricas de flow y de JVM.

    * Destination URL: `http://${hostname(true)}:8080/nifi` — mismo host
      y puerto que `nifi_api_url` de arriba, solo que sin `/nifi-api`
    * Input Port Name: `reporting_task`
    * Instance URL: igual que Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`
    * Output Format: `Record Formats`

!!! note "Si tu NiFi es HTTPS"
    Que `nifi_api_url` sea `https://` hace que las URL de arriba también
    lo sean, lo que agrega una propiedad **SSL Context Service** en las
    dos reporting tasks. Asígnale un `StandardSSLContextService` con los
    mismos valores de Truststore del [paso 3](#3-configura-los-ajustes-del-flow).
    Crea este desde la misma ventana de **Controller Settings** donde
    están estas reporting tasks, no desde el diálogo *Configure* del
    process group: las reporting tasks son componentes a nivel de todo
    NiFi y no ven un controller service que esté dentro de un process
    group.

Inicia cada reporting task.

## 5. Inicia el flow

Haz clic derecho sobre el grupo de procesos y selecciona **Start**.

Los datos ya fluyen hacia Splunk. Para que aparezcan en los paneles de la
app, configura también el [Lookup de Instancias](instance-lookup.es.md).
