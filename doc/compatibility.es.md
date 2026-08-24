# Compatibilidad y elección del método de recolección

## Versiones soportadas

| | Soportado | Probado en CI |
|---|---|---|
| Apache NiFi | 1.16 – 1.28.1, 2.0 – 2.11 | 1.23.2, 1.28.1, 2.0.0, 2.11.0 |
| Splunk Enterprise / Cloud | 9.0 – 10.x | 9.4, 10.4 |

NiFi 1.x llegó a fin de vida el 2024-12-08 con la 1.28.1. Sigue funcionando
con estas apps, pero toda corrección de seguridad del proyecto aterriza ahora
solo en la línea 2.x.

El piso es NiFi 1.16 porque es donde aparece `/flow/metrics/json`. Las
instancias 1.x anteriores funcionan sin el endpoint de métricas; esa
combinación no está cubierta por el CI.

## Dos formas de ingresar los datos

Elige una. Usar las dos duplica cada evento.

### Pull — el TA consulta la API REST de NiFi

Splunk le pide los datos a NiFi cada cierto intervalo. **Preferí esta.** No
hay nada que instalar ni mantener dentro de NiFi, un solo input cubre todas
las versiones soportadas, y Splunk controla el intervalo, el índice y los
reintentos.

Requiere que Splunk alcance la API de NiFi. Funciona con un NiFi sin
autenticación y con uno detrás de single-user o LDAP.

### Push — un flow dentro de NiFi envía al HEC

NiFi envía los datos al HTTP Event Collector de Splunk. Usá esta cuando
**Splunk no puede alcanzar a NiFi** — NiFi en una DMZ, o una red que solo
permite conexiones salientes desde él.

El costo es un grupo de 39 procesadores, tres reporting tasks y dos input
ports Site-to-Site que hay que mantener dentro de tu NiFi, además de un
archivo de flow distinto por cada versión mayor de NiFi.

### Qué da cada una

| | Pull (TA) | Push (flow) |
|---|---|---|
| Estado del flujo, diagnóstico, historial | sí | sí |
| Métricas de flujo (`/flow/metrics`) | sí | no |
| Detección de versión de NiFi | sí | no |
| Bulletins individuales | sí, por polling | sí, sin pérdida |
| `bulletinGroupName` / `bulletinGroupPath` | no | sí |
| Archivos de log de NiFi | vía Universal Forwarder | vía el flow |
| Qué instalar dentro de NiFi | nada | 39 procesadores + 3 reporting tasks |

Los bulletins son el único punto donde el camino push es genuinamente mejor:
una reporting task empuja cada bulletin, mientras que el polling lee un board
que solo retiene una ventana corta, así que un intervalo mayor que esa
ventana pierde eventos. El input avisa cuando un poll vuelve lleno, que es la
señal de que está pasando.

## Logs

Los dos caminos pueden recolectar los archivos de log de NiFi, y la
recomendación no es ninguno de los dos: usá un **Universal Forwarder** en el
host de NiFi. El TA ya trae los monitor inputs, deshabilitados; habilitá los
que necesites y corregí la ruta.

Un forwarder maneja la rotación y lleva su propio checkpoint, y si Splunk no
está disponible encola en disco en lugar de generar contrapresión sobre el
flujo que NiFi también usa para trabajo real.

`TailFile` dentro del flow sigue soportado para el caso donde un forwarder no
es opción — NiFi en un contenedor donde no podés agregar un sidecar.

El TA define cinco sourcetypes de log. `nifi:log:deprecation` conviene
habilitarlo antes de migrar a NiFi 2.x: registra qué componentes deprecados
sigue usando la instancia.
