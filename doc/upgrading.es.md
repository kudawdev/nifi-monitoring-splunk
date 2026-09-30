# Actualizar a 2.0.0

La 2.0.0 agrega soporte de NiFi 2.x. Es un release mayor y cambia defaults de
los que depende una instalación existente. Lee esto antes de actualizar.

La pantalla de configuración del TA también se reconstruyó desde cero: 1.x
tenía un formulario único escrito a mano, 2.0.0 lo genera UCC con tabs
agrupadas (Endpoints, TLS, Advanced). La página **Inputs** en **Apps > NiFi
TA Monitoring** no se parece en nada a la que conocías -- ver
[Estrategia pull](config-nifi-monitoring-2-0.es.md#1-crear-el-input-de-la-ta)
para ver cómo es ahora. Los inputs existentes siguen funcionando tal cual;
el formulario nuevo solo aparece cuando abres uno.

## Cambios que rompen

### La app busca en un índice, no en todos

El macro `index_nifi` era `index=*`, lo que hacía que cada panel y la
aceleración del datamodel escanearan todos los índices de eventos de la
instancia. Ahora apunta a `index=nifi`, y la app trae ese índice.

**Si tus datos de NiFi están en otro lado, todos los dashboards van a quedar
vacíos.** No adivines dónde: abre **Internal Monitoring**, que informa
cuántos eventos ve el macro y en qué índices hay datos de NiFi realmente.
Después sobrescribe el macro en `local/macros.conf`:

```
[index_nifi]
definition = index=tu_indice
```

### Se verifican los certificados TLS

Cada request del TA aceptaba cualquier certificado que presentara NiFi. Sobre
HTTPS eso permite que cualquiera capaz de interceptar la conexión lea el
usuario, la contraseña y el bearer token — y NiFi 2.x sirve HTTPS por
defecto.

La verificación queda activada, incluso para inputs guardados antes de que la
opción existiera. **Un input que apunte a un NiFi con certificado autofirmado
va a dejar de conectar.** El error dice qué hacer; tienes dos opciones:

- apuntar **CA bundle path** a un bundle que valide el certificado, o
- destildar **Verify TLS certificate**, aceptando una conexión sin verificar.

### `nifi:api:site_to_site` deja de recolectarse

Se consultaba en cada ciclo y ningún dashboard, objeto del datamodel ni
búsqueda guardada lo leía nunca. Si construiste algo sobre ese sourcetype,
deja de recibir eventos nuevos; los datos ya indexados no se ven afectados.
Si `inputs.conf` todavía tiene el ajuste viejo, el input avisa en cada poll --
bórralo para silenciar el log.

El formulario nuevo no tiene campo para esto, y guardar un input desde ahí no
borra los campos viejos que el formulario no conoce -- volver a guardar la
contraseña ([más abajo](#las-contrasenas-se-guardan-por-input)) no limpia
este. Borra la línea `endpoint_site_to_site` a mano de cada stanza
`[nifi://...]` en `local/inputs.conf`, dentro de `nifi_TA_monitoring`.

### La aceleración del datamodel viene apagada -- cómo activarla

Splunkbase no acepta una app que distribuya un datamodel acelerado, así que
el modelo NIFI se entrega con `acceleration = false`. Los dashboards siguen
devolviendo los números correctos, porque `tstats ... from datamodel=NIFI.*`
cae en una búsqueda cruda, pero se vuelven más lentos a medida que crece el
índice.

Activar la aceleración es lo que más mejora la latencia de los paneles:

1. Ve a **Settings > Data models**.
2. Elige **NIFI** y después **Edit > Edit Acceleration**.
3. Marca **Accelerate** y elige un rango de summary. La app trae
   `acceleration.earliest_time = -7d`, que es el rango con el que se
   diseñaron los paneles.

El costo es un summary tsidx por bucket dentro de ese rango. Acorta el rango
si el almacenamiento te importa más que la historia.

### Las contraseñas se guardan por input

El add-on 1.x guardaba cada contraseña de NiFi bajo el **usuario** de NiFi,
así que dos inputs con el mismo usuario compartían una contraseña. La
pantalla de configuración ahora la guarda por **input**, cifrada, al guardar
el input.

Un input que viene de 1.x sigue funcionando con la contraseña que guardó
1.x, y deja un aviso en el log que lo dice. Ábrelo en la página **Inputs**,
escribe la contraseña y guárdalo: desde ahí tiene la suya.

### 1.x deja archivos que 2.0.0 no usa

Instalar 2.0.0 sobre un add-on 1.x solo sobrescribe los archivos que trae el
paquete nuevo -- no borra los que traía el viejo y que 2.0.0 ya no necesita.
Vale la pena borrar dos a mano de `nifi_TA_monitoring/bin/`:

- `.env` -- el token de la API de NiFi que 1.x cacheaba ahí, casi en texto
  plano. 2.0.0 cachea ese mismo tipo de token en `storage/passwords` y nunca
  vuelve a leer este archivo.
- `dotenv/` -- la librería que 1.x usaba para leerlo.

Ninguno de los dos rompe nada si se dejan, pero son una credencial vieja y
código muerto ocupando espacio sin ningún motivo.

### El flow definition se divide por versión de NiFi

`flow_definition/` ahora tiene `nifi-1.x/` y `nifi-2.x/`. Si usas la
estrategia push, importa el que corresponde a tu NiFi. Ver
[Compatibilidad](compatibility.es.md).

El template XML se movió a `nifi-1.x/`. NiFi 2.x eliminó el soporte de
templates.

## Qué hacer, en orden

1. **Averigua dónde están tus datos, en la versión actual.** Ve a
   **NiFi Monitoring > Configuration > Internal Monitoring**, o corre:

   ```
   | tstats count where index=* sourcetype=nifi:* by index
   ```

   Anota el índice. Lo necesitas en el paso 3.

2. **Instala los dos paquetes como actualización, primero la TA.** Para cada
   app -- **Nifi Monitoring TA**, después **Nifi Monitoring** -- ve a
   **Apps > Manage Apps > Install app from file**, elige el `.tar.gz` nuevo,
   y marca **Upgrade app. Checking this will overwrite the existing version
   of this app.** Las dos tienen que quedar en el mismo número de versión.
   Después reinicia Splunk (**Settings > Server controls > Restart
   Splunk**): las dos apps agregan o cambian endpoints REST (`restmap.conf`,
   `web.conf`), que solo toman efecto después de reiniciar.

3. **Si el índice del paso 1 no es `nifi`, sobrescribe el macro.** Edita
   `local/macros.conf` dentro de `nifi_monitoring` (o usa
   **Settings > Advanced search > Search macros**):

   ```
   [index_nifi]
   definition = index=tu_indice
   ```

4. **Arregla el TLS en cada input que apunte a un NiFi con HTTPS.** Ve a
   **Apps > NiFi TA Monitoring > Inputs**, abre el input, expande **TLS**, y
   apunta **CA bundle path** a un bundle que valide el certificado de NiFi, o
   destilda **Verify the TLS certificate**. Guarda.

5. **Borra `endpoint_site_to_site` de `local/inputs.conf`.** El formulario no
   tiene campo para esto y guardar un input no lo borra (ver
   [arriba](#nifiapisite_to_site-deja-de-recolectarse)) -- abre
   `nifi_TA_monitoring/local/inputs.conf` en el filesystem del search head y
   quita la línea de cada stanza `[nifi://...]` a mano.

6. **Vuelve a guardar la contraseña en cada input que autentica.** Ábrelo,
   sobrescribe el campo de contraseña -- se muestra como una máscara,
   escribir encima es lo que realmente la mueve -- y guarda. Revisa
   **Settings > Server settings > Logging**, o `index=_internal
   nifi_TA_monitoring "1.x add-on"`, para ver qué inputs todavía dicen
   `Input <name> is using the credential the 1.x add-on stored...`: esos son
   los que faltan.

7. **Solo si usas la estrategia push.** Reimporta
   [`flow_definition/nifi-2.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-2.x/NiFiMonitoring.json)
   (o `nifi-1.x/` si este NiFi se queda en 1.x) como un process group nuevo,
   y pasa lo que el flow viejo guardaba en variables al Parameter Context
   nuevo. Ver [Estrategia push](config-nifi-monitoring-2-0-push.es.md).

8. **(Opcional) Limpia.** Una vez que todos los inputs de arriba estén
   corriendo, borra `nifi_TA_monitoring/bin/.env` y
   `nifi_TA_monitoring/bin/dotenv/` -- 2.0.0 no usa ninguno de los dos.

## Novedades de este release

- **Soporte de NiFi 2.x**, desde un solo input. El TA detecta la versión y se
  adapta.
- **Métricas de flujo** desde `/flow/metrics/json`, apagadas por defecto — un
  NiFi ocioso emite unas 60 muestras por poll y `ALL_COMPONENTS` escala eso
  con el flujo, así que revisa el volumen antes de habilitarlo.
- **Bulletins sin reporting task**, consultando el bulletin board.
- **`nifi:log:deprecation`**, que registra los componentes deprecados que la
  instancia sigue usando. Habilítalo antes de planificar la migración a NiFi
  2.x.
- **`nifi:log:request`**, el log de acceso HTTP de NiFi.
- Un **panel de inventario** con la versión de NiFi y de Java de cada
  instancia, y con qué estrategia llegaron sus datos.
