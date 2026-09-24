# Actualizar a 2.0.0

La 2.0.0 agrega soporte de NiFi 2.x. Es un release mayor y cambia defaults de
los que depende una instalación existente. Leé esto antes de actualizar.

## Cambios que rompen

### La app busca en un índice, no en todos

El macro `index_nifi` era `index=*`, lo que hacía que cada panel y la
aceleración del datamodel escanearan todos los índices de eventos de la
instancia. Ahora apunta a `index=nifi`, y la app trae ese índice.

**Si tus datos de NiFi están en otro lado, todos los dashboards van a quedar
vacíos.** No adivines dónde: abrí **Internal Monitoring**, que informa
cuántos eventos ve el macro y en qué índices hay datos de NiFi realmente.
Después sobreescribí el macro en `local/macros.conf`:

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
va a dejar de conectar.** El error dice qué hacer; tenés dos opciones:

- apuntar **CA bundle path** a un bundle que valide el certificado, o
- destildar **Verify TLS certificate**, aceptando una conexión sin verificar.

### `nifi:api:site_to_site` deja de recolectarse

Se consultaba en cada ciclo y ningún dashboard, objeto del datamodel ni
búsqueda guardada lo leía nunca. Si construiste algo sobre ese sourcetype,
deja de recibir eventos nuevos; los datos ya indexados no se ven afectados.
El input avisa una vez si encuentra el ajuste viejo en `inputs.conf`.

### La aceleración del datamodel viene apagada -- cómo activarla

Splunkbase no acepta una app que distribuya un datamodel acelerado, así que
el modelo NIFI se entrega con `acceleration = false`. Los dashboards siguen
devolviendo los números correctos, porque `tstats ... from datamodel=NIFI.*`
cae en una búsqueda cruda, pero se vuelven más lentos a medida que crece el
índice.

Activar la aceleración es lo que más mejora la latencia de los paneles:

1. Andá a **Settings > Data models**.
2. Elegí **NIFI** y después **Edit > Edit Acceleration**.
3. Marcá **Accelerate** y elegí un rango de summary. La app trae
   `acceleration.earliest_time = -7d`, que es el rango con el que se
   diseñaron los paneles.

El costo es un summary tsidx por bucket dentro de ese rango. Acortá el rango
si el almacenamiento te importa más que la historia.

### Las contraseñas se guardan por input

El add-on 1.x guardaba cada contraseña de NiFi bajo el **usuario** de NiFi,
así que dos inputs con el mismo usuario compartían una contraseña. La
pantalla de configuración ahora la guarda por **input**, cifrada, al guardar
el input.

Un input que viene de 1.x sigue funcionando con la contraseña que guardó
1.x, y deja un aviso en el log que lo dice. Abrilo en la página **Inputs**,
escribí la contraseña y guardalo: desde ahí tiene la suya.

### El flow definition se divide por versión de NiFi

`flow_definition/` ahora tiene `nifi-1.x/` y `nifi-2.x/`. Si usás el camino
push, importá el que corresponde a tu NiFi. Ver
[Compatibilidad](compatibility.md).

El template XML se movió a `nifi-1.x/`. NiFi 2.x eliminó el soporte de
templates.

## Qué hacer, en orden

1. Anotá en qué índice están tus datos de NiFi, desde **Internal Monitoring**
   en la versión actual, o con
   `| tstats count where index=* sourcetype=nifi:* by index`.
2. Actualizá las dos apps. Tienen que quedar en la misma versión.
3. Si tu índice no es `nifi`, sobreescribí `index_nifi` como se indica arriba.
4. Revisá cada input de NiFi: si apunta a un NiFi con HTTPS, configurá el CA
   bundle o desactivá la verificación.
5. Sacá `endpoint_site_to_site` de tus inputs si está.
6. Abrí cada input que use usuario y contraseña, escribí la contraseña y
   guardalo.
7. Solo si usás el camino push: reimportá el flow de tu versión de NiFi y
   pasá los ajustes al parameter context (2.x) o a las variables (1.x).

## Novedades de este release

- **Soporte de NiFi 2.x**, desde un solo input. El TA detecta la versión y se
  adapta.
- **Métricas de flujo** desde `/flow/metrics/json`, apagadas por defecto — un
  NiFi ocioso emite unas 60 muestras por poll y `ALL_COMPONENTS` escala eso
  con el flujo, así que revisá el volumen antes de habilitarlo.
- **Bulletins sin reporting task**, consultando el bulletin board.
- **`nifi:log:deprecation`**, que registra los componentes deprecados que la
  instancia sigue usando. Habilitalo antes de planificar la migración a NiFi
  2.x.
- **`nifi:log:request`**, el log de acceso HTTP de NiFi.
- Un **panel de inventario** con la versión de NiFi y de Java de cada
  instancia, y por qué camino llegaron sus datos.
