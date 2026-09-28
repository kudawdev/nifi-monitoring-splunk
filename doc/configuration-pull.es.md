# Estrategia pull: Splunk Data Input NiFi

La TA consulta la API REST de NiFi en un intervalo y escribe lo que
recibe. **Con esta estrategia no se configura nada dentro de NiFi** — ni
procesadores, ni parameter context o variables, ni controller services,
ni reporting tasks. NiFi queda exactamente como está; todo lo de abajo
pasa del lado de Splunk. ¿No estás seguro de que esta es la estrategia
que necesitas? Ver
[Elegir una estrategia de recolección](compatibility.es.md#elegir-una-estrategia-de-recoleccion).

*Esta es la estrategia que deben usar las instancias de NiFi con al menos
autenticación básica.*

Requiere **Nifi Monitoring TA** ya instalada (ver
[Instalar NIFI Monitoring](installation.es.md)).

Ve a **Apps > NiFi TA Monitoring > Inputs** y haz clic en **Create New
Input**. Un input cubre una instancia de NiFi completa (o un cluster
entero, apuntado a cualquier nodo — ver
[Compatibilidad](compatibility.es.md#topologia-instancia-unica-multiples-instancias-o-cluster));
crea uno por cada instancia que quieras monitorear.

**Los pasos 1 a 3 alcanzan para un setup básico.** Los pasos 4 a 8 vienen
colapsados en el propio formulario — son opcionales, vuelve a ellos solo
si necesitas esa función puntual.

!!! note "La pantalla genérica de Splunk también funciona, pero conviene evitarla"
    *Settings > Data inputs > NiFi* escribe el mismo `inputs.conf`, pero
    no tiene el formulario agrupado, la validación de campos ni el Test
    connection del paso 2.

## 1. Instancia de NiFi

- **NiFi instance name**: un nombre único para este input. Se usa como el
  valor de `host` estampado en cada evento, salvo que definas uno
  explícitamente en *Advanced*.
- **NiFi API URL**: la API REST de la instancia, ej.
  `https://<direccion>:<puerto>/nifi-api/`.

## 2. Autenticación

- **Authentication**: `None`, o `Username and password` cuando NiFi tiene
  autenticación básica habilitada. `Username and password` ejecuta
  `POST /access/token` y envía el JWT recibido en cada request siguiente.
- **Username** / **Password**: requeridos salvo que Authentication sea
  `None`.
- **Test connection**: junto a las credenciales, hace las mismas dos
  llamadas que hace el input — el login y `GET /system-diagnostics` —
  con los valores que están en pantalla, y dice qué respondió, sin
  guardar nada.

## 3. Endpoints

Tres checkboxes, todos activados por defecto:

- **Flow status** — `GET /flow/status`. Los contadores resumen sobre los
  que se construye cada panel del dashboard.
- **System diagnostics** — `GET /system-diagnostics`. Heap, threads y uso
  de repositorios. Así detecta también el add-on la versión de NiFi, por lo
  que desactivarlo deshabilita el reporte de versión.
- **Bulletin board** — `GET /flow/bulletin-board`. Boletines individuales,
  consultados con un cursor para no contar dos veces. El board conserva
  solo una ventana corta, así que un intervalo mayor a esa ventana puede
  perder boletines.

## 4. Status history

Colapsado por defecto. Dos campos, separados por coma o salto de línea,
vacíos por defecto (no recolectan nada hasta completarlos):

- **Processor IDs**: UUID de los procesadores a los que recolectar status
  history.
- **Process group IDs**: UUID de los grupos de procesos a los que
  recolectar status history.

## 5. Flow metrics

Colapsado por defecto, y desactivado por defecto incluso una vez
desplegado:

- **Collect flow metrics** — `GET /flow/metrics/json`. Requiere NiFi 1.16
  o superior. Un NiFi inactivo emite alrededor de 60 muestras por consulta,
  y la estrategia `All components` de abajo escala eso con el tamaño del
  flow, así que revisa el volumen antes de activarlo.
- **Registries**: nombres de registries separados por coma, ej.
  `NIFI,JVM`. Vacío los recolecta todos.
- **Strategy**: `All process groups` o `All components`. `All components`
  emite una muestra por componente, que es lo que multiplica el volumen.
- **Sample filter**: una expresión regular comparada contra el nombre de la
  métrica. Vacío conserva todas las muestras.

## 6. Custom endpoints

Colapsado por defecto. Cubre cualquier ruta REST de NiFi que no esté en la
lista fija de *Endpoints* — ver [Endpoints personalizados](#endpoints-personalizados) más abajo.

## 7. TLS

Colapsado por defecto:

- **Verify the TLS certificate**: activado por defecto. Déjalo activado a
  menos que NiFi use un certificado que no se pueda confiar mediante un
  bundle de CA. Desactivarlo permite que cualquiera capaz de interceptar la
  conexión lea las credenciales y el token.
- **CA bundle path**: solo se muestra mientras *Verify the TLS certificate*
  está activado. Una ruta como
  `/opt/splunk/etc/apps/nifi_TA_monitoring/local/nifi-ca.pem`. Vacío usa el
  almacén de confianza del sistema.

### Cómo conseguir un certificado para el CA bundle

Salta esto si el certificado de NiFi ya está firmado por una CA que el
sistema operativo confía -- deja *CA bundle path* vacío y pasa a
[Advanced](#8-advanced).

Si no, exporta el certificado que presenta NiFi y entrégaselo a Splunk
como su propia CA, que es como se ve en la práctica una CA privada:

1. Consigue el certificado desde el propio NiFi, desde cualquier máquina
    que pueda alcanzarlo (reemplaza `<nifi-host>` y `<puerto>` por los
    valores del paso 1):

    ```
    openssl s_client -connect <nifi-host>:<puerto> -servername <nifi-host> \
      </dev/null 2>/dev/null | openssl x509 > nifi-ca.pem
    ```

2. Cópialo al servidor de Splunk, dentro del directorio `local` del TA,
    con el usuario con el que corre Splunk (habitualmente `splunk`) como
    dueño:

    ```
    sudo install -o splunk -g splunk -m 0644 nifi-ca.pem \
      /opt/splunk/etc/apps/nifi_TA_monitoring/local/nifi-ca.pem
    ```

    `install` crea el directorio que falte con el dueño correcto en un
    solo paso. Crear ese directorio primero por tu cuenta -- un `mkdir`
    simple, o cualquier cosa corrida como `root` -- lo deja en manos de
    `root`, y
    Splunk, que corre con su propio usuario, después no puede escribir
    nada más ahí tampoco, ni siquiera las credenciales de este mismo
    input: guardar el input falla con `Data could not be written ...
    passwords.conf: Permission denied`.

3. Pon **CA bundle path** en esa misma ruta,
    `/opt/splunk/etc/apps/nifi_TA_monitoring/local/nifi-ca.pem`.

## 8. Advanced

Colapsado por defecto:

- **Interval**: segundos entre consultas, `60` por defecto. Todo endpoint
  activado, incluidos los personalizados, se recolecta en este intervalo.
- **Index**: el index de destino. Se recomienda un index dedicado, por
  ejemplo `nifi`. Si no existe, créalo primero.
- **Host field value**: se estampa en cada evento de este input. Vacío usa
  el nombre de instancia de NiFi de arriba. **En un cluster, pon el
  nombre del cluster, no de un nodo** — el add-on nombra al nodo en un
  campo separado. Este es también el valor que debe coincidir con una fila
  del [lookup de instancias](installation.es.md#lookup-de-instancias).

Aparte de estos ocho grupos, **Configuration > Logging** (fuera del
input) define cuánto escribe el add-on en `splunkd.log` — `INFO` por
defecto, `WARNING` si solo te interesan los problemas.

## Endpoints personalizados

Opcional — solo si necesitas consultar un endpoint REST de NiFi que no
está en la lista fija de *Endpoints* del paso 3. Usa el apartado **Custom
endpoints**: una línea por endpoint, con el formato `nombre,path` (por
ejemplo `queue_stats,/flow/connections/1234-5678-90ab-cdef/status`). El
path es relativo a la NiFi API URL configurada arriba.

Tú le pones el nombre; el sourcetype lo pone el add-on. `queue_stats` se
indexa como `nifi:api:custom:queue_stats`, así que todo lo que declares se
busca con `nifi:api:custom:*` y nada de lo que declares puede caer en un
sourcetype que el add-on escribe por su cuenta. Splunk indexa la respuesta
cruda; si necesitas extracción de campos para ese sourcetype, agrega tu
propia stanza en `props.conf`.

Cuatro cosas que conviene saber antes de depender de uno:

- **Un nombre, no un sourcetype.** `nifi:api:flow_status` y cualquier otro
  fuera de `nifi:api:custom:` se rechaza al guardar: un endpoint custom
  escribiendo en un sourcetype del add-on mezclaría su respuesta con los
  datos que leen los dashboards, y nada aguas abajo podría distinguirlos.
  Escribir el `nifi:api:custom:queue_stats` completo se acepta y significa
  lo mismo que `queue_stats`.
- **No se admiten marcadores `{id}`.** A diferencia de los campos Status
  history de arriba, un path custom se pide literal. Escribe el UUID
  completo. El input se niega a guardar un path que contenga `{` o `}` en
  lugar de dejar que falle recién al consultar.
- **Una consulta fallida no indexa nada.** Si NiFi responde 4xx o 5xx, el
  add-on lo registra en `splunkd.log` y no escribe ningún evento, así que
  un sourcetype vacío significa que el endpoint no está funcionando — el
  cuerpo del error nunca se indexa como si fuera dato.
- **Editar `inputs.conf` a mano requiere un backslash al final.** El
  textarea acepta un endpoint por línea, pero un archivo `.conf` termina el
  valor en el primer salto de línea sin escapar. Cuando escribas la stanza
  tú mismo — por ejemplo desde un deployment server — continúa cada línea
  con `\`:

```
custom_endpoints = queue_stats,/flow/connections/1234-5678-90ab-cdef/status\
cluster,/controller/cluster
```

  Indentar la continuación en cambio se ignora en silencio: Splunk se queda
  con el primer endpoint y descarta el resto. `splunk btool inputs list`
  muestra qué quedó realmente en efecto.

Una vez completado el formulario, haz clic en **Next** y el input queda creado.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_success.png)

Repite este proceso por cada instancia de NiFi que quieras monitorear.

Una vez que un input esté corriendo, configura también el
[Lookup de Instancias](installation.es.md#lookup-de-instancias).
