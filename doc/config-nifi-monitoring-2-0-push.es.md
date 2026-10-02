---
title: Estrategia push (2.0)
---

# Estrategia push: Envío Directo (2.0)

Un flow que corre dentro de NiFi llama a la propia API de NiFi y envía el
resultado directo al HTTP Event Collector (HEC) de Splunk — del lado de
Splunk no hay que alcanzar a NiFi para nada. ¿No estás seguro de que esta
es la estrategia que necesitas? Ver
[Elegir una estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion),
donde también está dibujada la arquitectura de las dos.

Requiere las dos apps ya instaladas (ver
[Instalar NIFI Monitoring](installation.es.md)): **Nifi Monitoring TA**
parsea los eventos que manda este flow, aunque en esta estrategia no
configures ningún input dentro de ella.

El flow viene en dos archivos, uno por línea de **NiFi**, porque NiFi 2.0
eliminó las variables con que se configura el flow 1.x. Los pasos son los
mismos para los dos; donde cambian, elige la pestaña del NiFi que
monitoreas. Para la versión 1.2 de las apps, ver
[Estrategia push (1.2)](configuration-push-1-2.es.md).

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
    `splunk_hec` (más abajo) en `https://<host>:8088`, y agrégale al
    procesador `Send2Splunk-HEC` (un `InvokeHTTP`) de **SendHEC** un SSL
    Context Service que confíe en el certificado de Splunk: un
    **StandardSSLContextService** con solo **Truststore Filename**,
    **Truststore Password** y **Truststore Type** completados.

    Destildar **Enable SSL** en **Settings > Data Inputs > HTTP Event
    Collector > Global Settings** es un cambio a nivel de toda la
    instancia: afecta a todos los tokens de HEC de ese Splunk, no solo a
    este, y manda cada evento y cada token en texto plano. Considera esto
    solo en un entorno de prueba aislado que controles, nunca en una
    instancia de Splunk compartida o de producción.

## 2. Importa el Flow Definition en NiFi

=== "NiFi 2.x"

    Importa [`flow_definition/nifi-2.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-2.x/NiFiMonitoring.json)
    — no el de 1.x: ese se importa sin error en una instancia 2.x, pero
    varios procesadores quedan inválidos o fallan en silencio una vez
    iniciado.

    Arrastra una caja de *process group* al lienzo. En el diálogo **Create
    Process Group**, asígnale un nombre y haz clic en el ícono chico junto
    a *Name* para subir el archivo del flow:

    ![image](/nifi-monitoring-splunk/assets/images/nifi/create_process_group_2x.png)

    Una vez elegido el archivo, *Parameter Context* se reemplaza por un
    aviso de que los parámetros van a venir del flow subido, y el nombre
    del archivo aparece bajo *File to upload*:

    ![image](/nifi-monitoring-splunk/assets/images/nifi/create_process_group_2x_upload.png)

    Haz clic en **Add**. El process group se crea con cada procesador que
    necesita un parámetro todavía vacío marcado como inválido — esperable
    hasta que los completes en el paso siguiente:

    ![image](/nifi-monitoring-splunk/assets/images/nifi/process_group_created_2x.png)

=== "NiFi 1.x"

    Importa [`flow_definition/nifi-1.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-1.x/NiFiMonitoring.json).

    Arrastra una caja de *process group* al lienzo, selecciona el ícono de
    importación en la ventana emergente y elige el archivo.

    ![image](/nifi-monitoring-splunk/assets/images/nifi/2_import_flow_definition.png)

En los dos casos, el process group contiene:

-   Monitoring - API
-   Monitoring - Logs
-   Monitoring - ReportingTask
-   SendHEC

## 3. Configura los ajustes del flow

Los dos flows usan los mismos ajustes:

| Ajuste | Qué es |
|---|---|
| `instance_name` | El `host` con que se envían los eventos `nifi:api:*`: el `host` de la fila de este NiFi en la lookup `instance`. Vacío usa el hostname del nodo, que es lo correcto para un NiFi de un solo nodo. **En un cluster, pon el `host` del cluster**: la API se consulta desde un solo nodo, el primario, así que si queda vacío cada evento lleva el nombre del nodo que sea primario en ese momento, que cambia en cada failover y no coincide con la lookup. Los logs siempre llevan el nombre del nodo |
| `nifi_api_url` | La API REST de esta instancia, ej. `http://127.0.0.1:8080/nifi-api`, sin barra final. En cluster, una dirección en la que escuche el servidor web del nodo (`nifi.web.http.host`), que a menudo no es `127.0.0.1` |
| `nifi_path` | Directorio de instalación de NiFi, para leer sus logs. Debe terminar en `/`, ej. `/opt/nifi/nifi-current/`: el flow le agrega `logs`. En cluster, la misma ruta en cada nodo |
| `process_groups_list` | Ids de los grupos de procesos a monitorear, uno por línea |
| `processors_list` | Ids de los procesadores a monitorear, uno por línea |
| `splunk_hec` | El servidor Splunk con el input HEC, ej. `http://<host>:8088`, sin barra final |
| `splunk_hec_token` | El token del [paso 1](#1-configura-el-http-event-collector-hec-en-splunk) |

Lo que cambia es dónde se configuran:

=== "NiFi 2.x"

    Al importar el flow 2.x se crea un parameter context llamado **NiFi
    Monitoring** y queda asignado al process group. Ábrelo con clic
    derecho sobre el process group > *Parameters*, o desde el menú
    superior derecho > *Parameter Contexts*. `splunk_hec_token` es un
    parámetro **sensible**, así que NiFi nunca lo escribe en un flow
    exportado.

    `processors_list` y `process_groups_list` se distribuyen vacíos a
    propósito, y hasta que tengan valor los dos procesadores
    `GenerateFlowFile` quedan inválidos. Es intencional: que NiFi se niegue
    a arrancar un procesador con una propiedad requerida vacía es mejor que
    arrancarlo apuntando a los ids de componentes de otra instalación.

=== "NiFi 1.x"

    Clic derecho sobre la caja NiFiMonitoring > *Variables*.

    ![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable_2.png)

    !!! warning "En cluster, deja las fuentes de la API solo en el primario"
        El flow 2.x consulta la API desde el nodo primario por sí solo; el
        flow 1.x ejecuta cada procesador en todos los nodos, así que cada
        nodo consulta la API del cluster y envía su propia copia: N nodos
        son N veces los eventos `nifi:api:*` y N veces la licencia. Abre
        **Monitoring - API** y pon *Execution* en **Primary node** en
        `GetHTTP-flow_status`, `GetHTTP-system_diagnostics` y el
        `GenerateFlowFile` de cada grupo `GetHTTP-*_history` — solo esas
        fuentes, porque un procesador alimentado por una conexión dejaría
        varado lo que está en cola en los demás nodos. Deja la rama de logs
        en todos los nodos.

!!! note "Si tu NiFi es HTTPS"
    Usa la estrategia pull. Un NiFi con HTTPS siempre exige que sus
    usuarios se autentiquen, y este flow llama a la API de NiFi sin
    credenciales, así que cada llamada es rechazada — ver
    [Elegir una estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion).

## 4. Configura los componentes de NiFi

Desde el menú > **Controller Settings**, agrega el controller service
**JsonRecordSetWriter** — parsea la salida de las reporting tasks para
indexarla en Splunk — y habilítalo. Después agrega tres reporting tasks:
**MonitorDiskUsage**, **SiteToSiteBulletinReportingTask** y
**SiteToSiteMetricsReportingTask**.

=== "NiFi 2.x"

    ![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_2x.png)

    El servicio va en la pestaña **Management Controller Services**. Queda
    **Disabled** — habilítalo:

    ![image](/nifi-monitoring-splunk/assets/images/nifi/json_record_set_writer_added_2x.png)

    Las reporting tasks van en la pestaña **Reporting Tasks** de la misma
    ventana:

    ![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_tasks_empty_2x.png)

=== "NiFi 1.x"

    ![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings.png)

    El servicio va en la pestaña **Reporting Task Controller Services**:
    haz clic en **(+)**, fíltralo, selecciónalo y agrégalo.

    ![image](/nifi-monitoring-splunk/assets/images/nifi/add_controller_service.png)

    Habilítalo: haz clic en el ícono de rayo (ϟ) y confirma.

    ![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_2.png)

    Las reporting tasks van en la pestaña **Reporting Task** de la misma
    ventana:

    ![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_3.png)

Configura cada reporting task igual en las dos líneas:

- **MonitorDiskUsage**: reporta cuando un filesystem supera el umbral de
  uso que definas.

    * Threshold: ej. `80%`
    * Directory Location: el filesystem a monitorear, ej. `/`
    * Directory Display Name: una etiqueta para identificarlo, ej. `NifiFileSystem`

- **SiteToSiteBulletinReportingTask**: envía cada bulletin en el momento
  en que ocurre.

    * Destination URL: `http://${hostname(true)}:8080/nifi`
    * Input Port Name: `bulletin_report`
    * Instance URL: igual que Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`

- **SiteToSiteMetricsReportingTask**: envía métricas de flow y de JVM.

    * Destination URL: `http://${hostname(true)}:8080/nifi`
    * Input Port Name: `reporting_task`
    * Instance URL: igual que Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`
    * Output Format: `Record Format`

Después inicia cada una (**►**):

=== "NiFi 2.x"

    ![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_tasks_running_2x.png)

=== "NiFi 1.x"

    ![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_4.png)

## 5. Inicia el flow

Haz clic derecho sobre el process group y selecciona **Start**. Todos
los componentes de adentro quedan corriendo, sin ninguno inválido:

=== "NiFi 2.x"

    ![image](/nifi-monitoring-splunk/assets/images/nifi/process_group_running_2x.png)

=== "NiFi 1.x"

    ![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_1.png)

Los datos ya fluyen hacia Splunk. Para que aparezcan en los paneles de la
app, configura también el [Lookup de Instancias](instance-lookup.es.md).
