# Compatibilidad y estrategia de recolección

Esta página responde dos preguntas independientes:

1. **¿Qué versiones de NiFi y Splunk soporta esta app?** — [Compatibilidad de versiones](#compatibilidad-de-versiones).
2. **¿Cómo debe llegar la información desde NiFi hasta Splunk?** — [Elegir una estrategia de recolección](#elegir-una-estrategia-de-recoleccion): pull o push, y cuál corresponde a tu entorno.

La estrategia de recolección es independiente de la versión de NiFi:
decídela con los requisitos de abajo, no con la tabla de versiones de
arriba.

## Compatibilidad de versiones

| | Soportado | Probado en CI |
|---|---|---|
| Apache NiFi | 1.16 – 1.28.1, 2.0 – 2.11 | 1.23.2, 1.28.1, 2.0.0, 2.11.0 |
| Splunk Enterprise / Cloud | 9.0 – 10.x | 9.4, 10.4 |

- **NiFi 1.x llegó a su fin de vida el 2024-12-08** (último release: 1.28.1). Sigue funcionando con estas apps, pero las correcciones de seguridad nuevas del proyecto NiFi se publican, de aquí en adelante, únicamente para la línea 2.x.
- **La versión mínima soportada es NiFi 1.16**, porque el endpoint `/flow/metrics/json` no existe en versiones anteriores. Las instancias 1.x más antiguas siguen funcionando, solo que sin ese endpoint de métricas de flujo; esa combinación no está cubierta por el CI.

## Topología: instancia única, múltiples instancias o cluster

| Topología | Soportado | Qué se configura |
|---|---|---|
| Una instancia | sí | Un input. |
| Varias instancias independientes | sí | Un input por instancia, una fila por instancia en el lookup `instance`. |
| Un cluster de NiFi | sí | **Un input**, apuntado a cualquier nodo. |

Un cluster cuenta como **una sola instancia** para esta app, no como
varias: apunta el input a cualquier nodo, y NiFi responde en nombre de
todo el cluster. El add-on detecta el cluster por su cuenta y recolecta
también los datos por nodo — no hay nada que habilitar.

Los eventos conservan el valor de `host` que configuraste (el nombre del
cluster) y agregan un campo `node` que identifica a qué miembro del
cluster corresponde cada evento. En el dashboard **Nifi TA Monitoring**,
la fila Cluster desglosa esto por miembro, rol y heap por nodo — la vista
agregada por sí sola ocultaría cuál nodo se está quedando sin recursos.

Dos cosas existen solo en un cluster:

- **Los bulletins llevan el nodo que los generó.** Los bulletins de
  framework (categorías como *Clustering* o *Primary Node*) describen al
  cluster mismo, no a un componente, así que no tienen nombre de origen.
- **En la estrategia push, solo el nodo primario consulta la API.** Un
  cluster no envía una copia de los mismos datos por cada nodo. El tail de
  logs sí corre en todos los nodos, porque los archivos de log son por
  nodo, no por cluster. Esto lo maneja el flow de forma automática; no hay
  nada que configurar.

## Elegir una estrategia de recolección

Dos estrategias mutuamente excluyentes llevan los datos de NiFi a Splunk.
**Elige exactamente una por instancia de NiFi — usar las dos en la misma
instancia duplica cada evento.**

| | Pull | Push |
|---|---|---|
| Qué ocurre | La TA de Splunk consulta la API REST de NiFi en un intervalo. | Un flow dentro de NiFi llama a su propia API y envía el resultado al HTTP Event Collector (HEC) de Splunk. |
| Dirección de red requerida | Splunk → NiFi | NiFi → Splunk |
| Autenticación de NiFi soportada | Ninguna, single-user o LDAP | **Únicamente ninguna** |
| Qué se instala dentro de NiFi | Nada | Un process group (39 procesadores), 3 reporting tasks, 2 puertos de entrada Site-to-Site; un archivo de flow distinto por versión mayor de NiFi |
| Cuándo usarla | Cuando Splunk puede alcanzar la API de NiFi. **Opción por defecto.** | Cuando Splunk no puede alcanzar NiFi en absoluto — NiFi en una DMZ, o en una red que solo permite conexiones salientes desde NiFi |

!!! warning "Push requiere un NiFi sin autenticación"
    El flow llama a su propia API REST sin enviar ninguna credencial. Si
    tu NiFi tiene single-user, LDAP o cualquier otro inicio de sesión
    habilitado, esa llamada falla con 401 — y no hay ningún ajuste que lo
    resuelva, porque el flow nunca fue diseñado para autenticarse. Usa
    pull en su lugar.

### Comparación de funcionalidades

| | Pull | Push |
|---|---|---|
| Flow status, diagnostics, status history | sí | sí |
| Flow metrics (`/flow/metrics`) | sí | no |
| Detección de versión de NiFi | sí | no |
| Bulletins individuales | sí, por polling | sí, sin pérdida |
| `bulletinGroupName` / `bulletinGroupPath` | no | sí |
| Archivos de log de NiFi | vía Universal Forwarder (ver abajo) | vía el flow |

Los bulletins son el único punto donde push es realmente mejor: una
reporting task envía cada bulletin en el momento en que ocurre, mientras
que el polling lee un tablero que solo conserva una ventana corta de
tiempo — un intervalo más largo que esa ventana pierde eventos. El input
registra una advertencia cuando un poll vuelve lleno, que es la señal de
que esto está pasando.

## Recolectar los archivos de log de NiFi

Independiente de pull o push: ambas estrategias *pueden* recolectar los
archivos de log de NiFi, pero la recomendación no es ninguna de las dos.
**Usa un Universal Forwarder en el host de NiFi.** La TA ya trae los
monitor inputs para esto, desactivados por defecto — activa los que
necesites y corrige la ruta.

Un forwarder maneja la rotación de logs y mantiene su propio checkpoint,
y si Splunk queda inalcanzable encola en disco en lugar de generar
presión sobre el mismo flow que NiFi usa para su trabajo real.

`TailFile` dentro del flow sigue soportado para cuando un forwarder no es
una opción — por ejemplo, NiFi corriendo en un contenedor al que no se le
puede agregar un sidecar.

La TA define cinco sourcetypes de log. Activa `nifi:log:deprecation`
antes de migrar a NiFi 2.x: registra qué componentes deprecados sigue
usando la instancia.
