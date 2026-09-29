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

1. Anota en qué índice están tus datos de NiFi, desde **Internal Monitoring**
   en la versión actual, o con
   `| tstats count where index=* sourcetype=nifi:* by index`.
2. Actualiza las dos apps. Tienen que quedar en la misma versión.
3. Si tu índice no es `nifi`, sobrescribe `index_nifi` como se indica arriba.
4. Revisa cada input de NiFi: si apunta a un NiFi con HTTPS, configura el CA
   bundle o desactiva la verificación.
5. Saca `endpoint_site_to_site` de tus inputs si está.
6. Abre cada input que use usuario y contraseña, escribe la contraseña y
   guárdalo.
7. Solo si usas la estrategia push: reimporta el flow de tu versión de NiFi
   y pasa los ajustes al parameter context (2.x) o a las variables (1.x).
8. (Opcional) Borra `bin/.env` y `bin/dotenv/` dentro de `nifi_TA_monitoring`
   una vez que la actualización funcione -- 2.0.0 no usa ninguno de los dos.

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
