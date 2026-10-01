# Plan: rediseño de los dashboards de NiFi Monitoring for Splunk

| ||
|---|---|
| **Fecha** | 2026-10-01 |
| **Autor** | Anibal Vasquez (Kudaw SA) |
| **Estado** | **Implementado y verificado** el 2026-10-01 en la rama `nifi-2`, sin commit. Ver §12 |
| **Versión** | **2.0.0** (ambas apps). 2.0.0 todavía no se publicó, así que el rediseño entra en ella en lugar de abrir 2.1 |
| **Rama** | `nifi-2` |
| **Mockups** | [`mockups/dashboards-2.0.html`](mockups/dashboards-2.0.html) — abrir en un navegador; un solo archivo, sin dependencias |
| **Antecedente** | [`2026-08-24-soporte-nifi-2.md`](2026-08-24-soporte-nifi-2.md), §12 (hallazgos D-A a D-K) |

---

## 1. Por qué

2.0.0 movió el camino primario de recolección a **pull** y la capa visual
siguió pensada para **push**. §12 del plan anterior lo documentó panel por
panel (D-A a D-K); el resumen es que en un despliegue pull, el recomendado:

- **Los bulletins no se ven en ninguna parte** (D-C). Todos los paneles leen
  `Reporting_Bulletin`, que solo alimenta el flow push; el TA escribe en
  `Bulletin_Board`, que no consulta nadie. El overview muestra `0` en la
  columna "Bulletin Errors", que se lee como "sano".
- **La mitad inferior de `nifi_instances_detail` está vacía** (D-A): los 12
  gráficos de "Behaviour Over Time" leen `Reporting_Task`, también solo push.
  El heap está en el índice con otro nombre (D-B).
- **Cuatro datasets y dos sourcetypes nuevos no tienen panel** (D-D, D-E),
  incluido `nifi:log:deprecation`, que el plan anterior llamó el mayor aporte
  de valor del análisis.

El análisis del 2026-10-01 encontró además:

| # | Hallazgo | Dónde |
|---|---|---|
| **D-L** | El drilldown del contador de bulletins apunta a `bulletin_monitor_panel`, una vista que no existe (la real es `nifi_bulletin`) | `nifi_instances_detail.xml:119` |
| **D-M** | `baseSearch2` agrega `max(ReadLast5Minutes_max)` cuando el campo es `BytesReadLast5Minutes_max`, y define `TotalTaskDurationSecond_*` pero lee `…Seconds_*`: "Max Read" y "Total Task Duration" salen vacíos **aun con push** | `nifi_instances_detail.xml:12-13` |
| **D-N** | "JVM Heap Usage $LabelName$" grafica **non-heap**, multiplicado por `-1` y dividido por la unidad de bytes, aunque el campo es un ratio | `nifi_instances_detail.xml:590-595` |
| **D-O** | En Logs, `$customsearch$` se aplica como post-proceso sobre un `tstats`: cualquier término de texto libre deja el contador y el gráfico en 0 | `nifi_logs.xml:93`, `:108` |
| **D-P** | El panel de estado HTTP del TA solo cuenta `404` como error (401, 403 y 5xx no) y conserva un `"No Aplica"`; la página entera se recarga cada 60 s, incluido un `tstats index=*` | `nifi_internal_monitoring.xml:1`, `:167` |
| **D-Q** | Up/Down es "hubo eventos en los últimos 5 minutos", sin mirar el intervalo de la instancia: con `interval > 300` una instancia sana sale **Down** | `nifi_overview.xml` |
| **D-R** | El repositorio de contenido y el de procedencia son **arreglos** (NiFi admite varios). `latest()` sobre el alias multivalor muestra uno, sin decir cuál | `nifi_overview.xml`, `nifi_instances_detail.xml:19` |
| **D-S** | La app no trae ninguna alerta, pero el menú enlaza `alerts` (ya en §12.4) | `default/` sin `savedsearches.conf` |
| **D-T** | `DashboardPanelTest` ejecuta 3 paneles de ~45. Ninguno de bulletins ni de `Reporting_Task`, por eso la matriz pasa en verde con D-A y D-C | `tests/integration/test_ingest.py:628` |

**Lectura.** No se arregla panel por panel. Faltan tres cosas en la base, y
los paneles se reconstruyen sobre ellas: **datasets por concepto** (los paneles
no saben por qué vía llegó el dato), **una sola definición de salud** (la usan
el overview, el detalle y las alertas) y **un test por panel y por perfil**.

---

## 2. Decisiones

Tomadas el 2026-10-01.

| # | Decisión | Por qué | Alternativa descartada |
|---|---|---|---|
| **R-1** | **Dashboard Studio** para todas las vistas | Quita la dependencia de *Status Indicator* (app 3119) y los dos JS propios (`nifi_monitor_overview.js`, `nifi_instance_panels.js`); es la capa que Splunk sigue desarrollando; corre en 9.0+, que es el piso de la matriz | Simple XML corregido: más barato hoy, pero mantiene las dependencias y el JS custom, que Splunk Cloud restringe cada vez más |
| **R-2** | **Unificar las fuentes en el datamodel**, con un dataset padre por concepto | Un panel consulta `Bulletins` y le da igual si el dato vino del board o de la Reporting Task; se puede acelerar | Macros por concepto: no tocan `NIFI.json`, pero no se aceleran y duplican la lógica en cada búsqueda |
| **R-3** | **El TA emite un evento plano por snapshot** del status history, con su propio `_time` | Elimina el `spath` + `mvexpand` sobre JSON anidado que hoy corre en cada carga (la vista más cara de la app); `_time` pasa a ser el del snapshot, no el de recolección | Mantener el JSON y aplanar en búsqueda: es lo que hay y es lo que no escala |
| **R-4** | **Se queda en 2.0.0** | 2.0.0 no se publicó; el rediseño es parte de lo que 2.0.0 promete (pull como camino primario) | Abrir 2.1.0: dejaría salir una 2.0.0 cuyo camino recomendado no muestra bulletins |

---

## 3. Principios

1. **Por concepto, no por sourcetype.** Bulletins, throughput, JVM,
   repositorios y componentes son conceptos; cada uno tiene un dataset que
   junta todas las fuentes que lo alimentan.
2. **Una definición de salud.** Un macro la calcula y la usan todas las vistas
   y todas las alertas. Ningún panel decide por su cuenta qué es "Down".
3. **De la flota al componente, con contexto.** Overview → Instance →
   Components. Cada drilldown lleva `host`, `cluster` y el rango de tiempo.
4. **La primera pantalla responde "¿algo está mal ahora?"** sin elegir nada.
   Ninguna vista abre en *waiting for input* (D-J): toda vista tiene valores
   por defecto que muestran datos.
5. **El color sale del valor, nunca de la fila** (D-G). Salud con ícono +
   texto, no solo color. Una medida por gráfico: sin doble eje Y.
6. **Un panel vacío dice por qué.** Si un panel depende de una fuente que está
   apagada (`flow_metrics`, history sin ids configurados, cluster), muestra
   qué habilitar en lugar de *No results found*.

---

## 4. Modelo de datos

### 4.1 Datasets por concepto (R-2)

| Dataset padre | Hijos | Constraint del padre | Para |
|---|---|---|---|
| **`Bulletins`** | `Bulletin_Board` (pull), `Reporting_Bulletin` (push) | `` `index_nifi` sourcetype IN ("nifi:api:bulletin_board", "nifi:reporting:bulletin") `` | Overview, Instance, Bulletins, alerta de bulletins |
| **`Throughput`** | `Reporting_Task` (push), `Flow_Metrics_Root` (pull, `component_type=RootProcessGroup`) | ambos sourcetypes | Instance › Throughput |
| **`Component_Status`** | `Processors`, `Process_Groups` | `sourcetype IN ("nifi:api:processors_status", "nifi:api:process_groups_status")` (§5) | Components |

Los campos del padre son la **intersección normalizada**: `bulletinLevel`,
`bulletinCategory`, `bulletinSourceName`, `bulletinSourceId`,
`bulletinGroupId`, `bulletinMessage`, `cluster`, `host`. Los que solo tiene
una fuente (`bulletinGroupName`, `bulletinGroupPath`, `bulletinNodeAddress`)
quedan en el hijo.

Para `Throughput`, los dos orígenes miden lo mismo con nombres distintos
(`BytesReceivedLast5Minutes` vs `nifi_amount_bytes_received`). Se normalizan
en el `props.conf` del TA con `FIELDALIAS`/`EVAL` a `bytes_in`, `bytes_out`,
`flowfiles_in`, `flowfiles_out`, `bytes_queued`, `flowfiles_queued`. Es el
mismo mecanismo que ya usa TA-5 para los bulletins.

Los datasets actuales siguen existiendo como hijos, con el mismo nombre. **A
verificar en F1 (V-2):** si `tstats … from datamodel=NIFI.Reporting_Bulletin`
sigue resolviendo cuando el objeto pasa a ser hijo, o si exige
`NIFI.Bulletins.Reporting_Bulletin`. Si cambia, es un breaking change para
búsquedas de usuarios de 1.x y se documenta en `doc/upgrading.md`.

### 4.2 Macros

| Macro | Qué es | Default |
|---|---|---|
| `nifi_health` | Recibe `last_seen` e `interval` por host y devuelve `health` = `ok` · `degraded` · `critical` · `stale` · `no_data`, más `health_reason` (texto corto, p. ej. *"Heap 93% ≥ 85% for 25 min"*) | — |
| `nifi_stale_factor` | Cuántos intervalos sin datos convierten una instancia en `stale` | `3` |
| `nifi_threshold_heap` | % de heap que marca `degraded` | `85` (crítico `95`) |
| `nifi_threshold_repo` | % de uso de un repositorio que marca `degraded` | `80` (crítico `90`) |
| `nifi_threshold_backpressure` | % de ocupación de una conexión | `80` |

`degraded` sale de: repositorio o heap sobre umbral, componentes inválidos,
`syncFailureCount > 0`, o bulletins `ERROR` en los últimos 15 min.
`critical`, de heap o repositorio sobre el umbral crítico, o heap sobre umbral
sostenido en 3 muestras seguidas. El
intervalo de cada host se toma del input del TA (`| rest` sobre
`data/inputs/nifi`); si no se puede leer (push, o permisos), se usa
`nifi_default_interval` = `60`.

**Umbrales por instancia (propuesto, confirmar en F1).** La colección KV
`instance` gana columnas opcionales `heap_threshold`, `repo_threshold`,
`backpressure_threshold`. Vacías, rige el macro. Se editan desde el mismo
Lookup File Editor que ya se usa para el inventario. Es lo que §12.4 del plan
anterior pedía.

### 4.3 Repositorios uno por fila (D-R)

`system_diagnostics` trae `contentRepositoryStorageUsage{}` y
`provenanceRepositoryStorageUsage{}` como arreglos con `identifier`. Los
paneles de almacenamiento usan `mvzip`/`mvexpand` sobre el `identifier` para
mostrar **un repositorio por fila**, y "peor repositorio" toma el máximo, no
el `latest()` de un multivalor.

---

## 5. Cambio en el TA: status history plano (R-3)

**Hoy** (`bin/nifi.py:992-1036`): por cada id configurado, el TA pide
`/flow/{processors,process-groups}/{id}/status/history`, recorta
`aggregateSnapshots` al último y escribe **el JSON completo** —con
`fieldDescriptors` y `componentDetails` repetidos— como un evento con
`DATETIME_CONFIG = CURRENT`.

**Propuesto:**

- Un evento por snapshot, plano:
  ```json
  {"component_id": "…", "component_name": "PutDatabaseRecord",
   "component_type": "processor", "group_id": "…",
   "timestamp": 1790859420000,
   "bytesRead": 0, "bytesWritten": 1048576, "flowFilesIn": 120,
   "flowFilesOut": 118, "taskMillis": 5321, "queuedCount": 40, …}
  ```
- `_time` = `timestamp` del snapshot (`TIME_PREFIX`/`TIME_FORMAT=%s%3N`).
- **Cursor por componente** en el `checkpoint_dir`, como el del bulletin
  board: se emiten todos los snapshots más nuevos que el último escrito. Con
  `interval` mayor que la granularidad del history (1 min por defecto en NiFi)
  hoy se pierden puntos; con el cursor no.
- `fieldDescriptors` sale del evento y pasa a un **lookup CSV** que distribuye
  la app (`nifi_status_metrics.csv`: `field, label, description, unit,
  component_type`). Alimenta el selector de métrica sin una búsqueda cruda de
  24 h (que es lo que hace hoy el dropdown).
- **Sourcetypes nuevos:** `nifi:api:processors_status` y
  `nifi:api:process_groups_status`. No se reutilizan los actuales: un mismo
  sourcetype con dos formas de evento es la trampa que el datamodel no puede
  resolver.

**Pregunta abierta P-1 — el camino push.** El flow push (1.x y 2.x) también
emite `nifi:api:{processors,process_groups}_history` con la forma anidada.
Opciones:

| | Qué | Costo |
|---|---|---|
| **a** | El flow aplana con un `JoltTransformJSON` y emite los sourcetypes nuevos | Editar `migrate_to_nifi2.py` (2.x) y el JSON + template de 1.x, que es un artefacto distribuido y frágil de tocar |
| **b** | El push conserva los sourcetypes viejos; `Component_Status` tiene un tercer hijo `Status_History_Legacy` que aplana en búsqueda | La vista Components queda cara solo para usuarios push |
| **c** | Components se declara **solo pull** y lo dice su estado vacío | Cero trabajo; el push pierde la vista |

**Recomendación: (b)** — no toca el flow, y el costo recae en el camino que ya
es secundario.

---

## 6. Vistas

Navegación nueva (`default/data/ui/nav/default.xml`):

```
Overview · Instance · Components · Bulletins · Logs · Cluster · Alerts · Configuración ▾
                                                                        ├ Instancias (Lookup File Editor)
                                                                        └ Salud de la recolección
```

Cada vista está dibujada en los mockups. Lo que sigue es qué responde y de
dónde sale cada panel.

### 6.1 Overview — `nifi_overview` (landing)

Reemplaza `home` (el splash con GIF, D-H) y el overview actual.
**Responde:** ¿está bien la flota ahora?

| Panel | Fuente | Notas |
|---|---|---|
| 6 KPIs: instancias OK/total, bulletins ERROR (15 min), peor heap %, peor repositorio %, FlowFiles en cola, componentes inválidos | `nifi_health`, `Bulletins`, `System_Diagnostics`, `Flow_Status` | Cada KPI nombra la instancia peor y lleva a ella |
| Tabla de instancias: salud (ícono + texto + razón), instancia, cluster, versión, último dato, componentes ▶/■/⚠, cola con sparkline, heap %, peor repositorio %, bulletins ERROR | ídem + `Version_Info` | Encabezados legibles (D-F); color por valor (D-G). Clic en la fila → Instance |
| Bulletins por nivel en el tiempo | `Bulletins` | Barras apiladas ERROR / WARNING / INFO |
| FlowFiles en cola por instancia | `Flow_Status` | Top 4 + "Otras" |

### 6.2 Instance — `nifi_instance`

Reemplaza `nifi_instances_detail`. **Responde:** ¿qué le pasa a esta
instancia? Abre con la primera instancia del inventario seleccionada (D-J).

| Sección | Paneles | Fuente |
|---|---|---|
| Encabezado | Salud + razón, versión de NiFi y Java, uptime, cluster, último dato | `nifi_health`, `Version_Info`, `System_Diagnostics` |
| Ahora | Threads activos, en cola (FlowFiles + bytes), componentes ▶/■/⚠/⏻, flows versionados (al día / modificados / desactualizados / sync failure), bulletins ERROR | `Flow_Status`, `Bulletins` |
| JVM y sistema | Heap % con línea de umbral; threads (total y daemon); load average con referencia en el nº de cores; tiempo de GC por colector | `System_Diagnostics` — **funciona con pull** (D-B) |
| Almacenamiento | Tabla un repositorio por fila (tipo, identifier, usado, total, % con barra); % usado por repositorio en el tiempo con umbral | `System_Diagnostics` (§4.3) |
| Throughput | Bytes in/out; FlowFiles in/out | `Throughput`. Vacío → *"Habilita `endpoint_flow_metrics` en el input del TA"* |
| Bulletins recientes | Últimos 10, con enlace a Bulletins filtrado | `Bulletins` |

Corrige de paso D-L, D-M y D-N, porque esos paneles se reescriben.

### 6.3 Components — `nifi_components`

Reemplaza `nifi_status_history`. **Responde:** ¿qué procesador, grupo o
conexión es el cuello de botella?

| Panel | Fuente | Notas |
|---|---|---|
| KPIs: conexiones sobre umbral de backpressure, conexiones que llegan a backpressure en < 1 h, componentes con history recolectado | `Flow_Metrics`, `Component_Status` | |
| Top 10 componentes por la métrica elegida, con sparkline | `Component_Status` | Métrica por defecto: tiempo de tarea; el selector sale del lookup (§5) |
| Conexiones más cargadas: origen → destino, % por cantidad y por bytes, predicción a backpressure | `Flow_Metrics` (`nifi_percent_used_*`, `nifi_time_to_*_backpressure_prediction`) | Vacío → habilitar `endpoint_flow_metrics` |
| Serie del componente seleccionado | `Component_Status` | Aparece al hacer clic en el top 10 |

### 6.4 Bulletins — `nifi_bulletins`

Reemplaza `nifi_bulletin`. Mismos filtros que hoy, pero sobre `Bulletins`
(D-C). KPIs (total, ERROR, WARNING, componentes afectados), barras por nivel,
componentes con más bulletins y el detalle con el mensaje completo.

### 6.5 Logs — `nifi_logs`

Tres secciones apiladas en la misma vista:

- **Aplicación:** eventos por nivel y visor de eventos. La búsqueda libre va al
  `search` crudo, no al post-proceso del `tstats` (D-O).
- **Deprecaciones** (D-E): uso deprecado agrupado por clase y componente, con
  ocurrencias, último visto e instancia. Es la lista de lo que hay que resolver
  antes de pasar a NiFi 2.x.
- **Requests** (D-E): códigos 2xx/4xx/5xx en el tiempo; usuarios y URIs con
  más 4xx/5xx.

### 6.6 Cluster — `nifi_cluster`

Sale de "Internal Monitoring", donde está escondido hoy. KPIs (nodos
conectados/total, primary, coordinator), tabla de nodos (estado, roles,
heartbeat, threads, cola, heap %) y heap % por nodo. En una instancia
standalone la vista lo dice en lugar de quedar vacía.

### 6.7 Alerts — `nifi_alerts`

Lista las alertas que trae la app (estado, condición, umbral, frecuencia) y
las disparadas en 24 h (`index=_audit action=alert_fired`). El enlace al
`alerts` nativo de Splunk se mantiene para administrarlas.

### 6.8 Salud de la recolección — `nifi_collection_health`

Reemplaza `nifi_internal_monitoring`. **Responde:** ¿la recolección está
funcionando? Matriz instancia × sourcetype con el último dato (ícono de
estado por celda), errores HTTP del TA **por código** (401, 403, 404, 5xx —
D-P), y el diagnóstico del macro `index_nifi` (cuántos eventos ve y en qué
índices hay datos de NiFi). Sin `refresh` de página entera.

### 6.9 Lo que se elimina

- `home.xml` (splash) — el overview pasa a ser la vista por defecto.
- `appserver/static/nifi_monitor_overview.{js,css}`,
  `nifi_instance_panels.{js,css}`, `nifi_monitoring.gif`.
- El footer "Developed by Kudaw" copiado en 6 vistas: queda uno, en Overview.
- La dependencia de **Status Indicator** (app 3119): `README.md`,
  `doc/index{,.es}.md`, `doc/installation{,.es}.md`. **Lookup File Editor** se
  queda: es como se edita el inventario.

---

## 7. Alertas

Se distribuyen en `default/savedsearches.conf`, **deshabilitadas** (AppInspect
exige que una app no active alertas al instalarse). Todas consultan
`nifi_health` o los mismos macros de umbral que los paneles, así que una
alerta y un panel nunca discrepan.

| Alerta | Condición | Frecuencia |
|---|---|---|
| Instancia sin datos | `health = stale` o `no_data` | 5 min |
| Repositorio por llenarse | Algún repositorio ≥ `nifi_threshold_repo` | 15 min |
| Heap alto sostenido | Heap ≥ `nifi_threshold_heap` en 3 muestras seguidas | 5 min |
| Pico de bulletins ERROR | ERROR en 15 min > N (macro) | 5 min |
| Backpressure | Conexión ≥ `nifi_threshold_backpressure` o predicción < 1 h | 5 min (requiere `flow_metrics`) |
| Nodo de cluster desconectado | `Cluster_Nodes.status != CONNECTED` | 5 min |
| Sync failure de flow versionado | `syncFailureCount > 0` | 15 min |
| Errores HTTP del TA | 401/403/5xx del modular input en 15 min | 15 min |

---

## 8. Tests

La regla es D-T: **ningún panel queda sin ejecutar en CI.**

**Unitarios** (stdlib, sin Docker; `tests/unit/`):

- Leer las vistas Studio: el JSON va dentro de `<definition><![CDATA[…]]>`.
  Un helper reemplaza al `re.findall("<query>")` de hoy.
- Toda `dataSource` usa `` `index_nifi` `` o `datamodel=NIFI.*`; ninguna usa
  `index=*` salvo el diagnóstico de Salud de la recolección (se mantiene el
  test actual).
- Todo drilldown a otra vista apunta a una vista que existe (habría detectado
  D-L) y todo token que se usa está definido por un input o un default.
- Ninguna vista abre esperando input: todos los inputs tienen default (D-J).
- Cada alerta de `savedsearches.conf` está `disabled = 1` y usa los macros.
- El lookup de métricas cubre los campos que el TA emite.
- Ningún `join` (se mantiene el test actual).

**Integración** (`tests/integration/test_ingest.py`):

- `DashboardPanelTest` pasa a recorrer **todas** las `dataSources` de todas
  las vistas, en cada perfil. Cada fuente declara en un manifiesto qué perfiles
  deben darle filas (`pull`, `push`, `cluster`); una fuente vacía en un perfil
  donde debería tener datos falla.
- Test del TA nuevo: los snapshots salen planos, con `_time` del snapshot, y
  el cursor no duplica ni pierde puntos entre dos corridas.

---

## 9. Documentación

Bilingüe, como siempre (`*.md` y `*.es.md`):

- `doc/overview`, `doc/references` y las páginas de configuración: capturas
  nuevas y la lista de vistas.
- `doc/installation`, `doc/index`, `README.md`: sacar Status Indicator.
- `doc/references`: sourcetypes nuevos (`*_status`), datasets padre y macros.
- `doc/upgrading`: datasets renombrados (si V-2 lo confirma), sourcetypes de
  history reemplazados, alertas disponibles.

---

## 10. Fases

| Fase | Qué | Criterio de cierre |
|---|---|---|
| **F0** | Este plan y los mockups aprobados | Aprobación explícita |
| **F1 — Base** | Datasets padre (§4.1), normalización de `Throughput`, macros de salud y umbrales (§4.2), cambio del TA (§5), helper de tests Studio, manifiesto de fuentes por perfil, verificaciones V-1 a V-4 | Unitarios verdes; `tstats` sobre cada padre devuelve filas en `nifi2-current` y en un perfil push |
| **F2 — Overview + Instance** | Las dos vistas más usadas | Todos sus paneles con filas en los perfiles que les corresponden |
| **F3 — Bulletins, Logs, Cluster, alertas** | Tres vistas + `savedsearches.conf` + Alerts | Ídem; las alertas disparan en un perfil con la condición forzada |
| **F4 — Components + Salud de la recolección** | Las dos restantes | Ídem |
| **F5 — Limpieza y docs** | §6.9, §9, AppInspect | `make check` verde con `MAX_WARNING` sin subir; matriz `release` completa |

---

## 11. Riesgos y verificaciones

| # | Qué verificar | Por qué importa | Si falla |
|---|---|---|---|
| **V-1** | Que en **Splunk 9.0** Studio tenga lo que usan los mockups: sparklines en celdas de tabla, visor de eventos, drilldown a otro dashboard pasando tokens, formato condicional por valor | La matriz soporta 9.0–10.x y Studio ganó varias de esas capacidades después de 9.0 | Degradar ese panel en 9.0 (sin sparkline, enlace a búsqueda) o subir el piso a la versión que lo tenga — decisión del usuario |
| **V-2** | Cómo resuelve `tstats` un dataset que pasa a ser hijo | Si cambia el nombre, rompe búsquedas de usuarios 1.x | Documentarlo en `upgrading.md` |
| **V-3** | Que AppInspect acepte las vistas Studio sin subir `MAX_WARNING` | Es el gate de publicación | Ajustar las vistas, no el umbral |
| **V-4** | Volumen de `flow_metrics` con el flow de 37 procesadores | Components y Throughput dependen de él y está apagado por defecto por volumen | Recomendar un intervalo mayor para ese endpoint en lugar de encenderlo por defecto |
| **P-1** | Formato del status history en el camino push | §5 | Recomendación (b) |

**Sin tabs.** Los mockups apilan secciones en lugar de usar pestañas de Studio,
porque no están en 9.0. Si V-1 muestra que sí, Logs e Instance pueden pasar a
pestañas sin cambiar su contenido.

---

## 12. Implementación y verificación

Hecho el 2026-10-01, F1 a F5 en una sola pasada.

### 12.1 Qué se hizo

| Pieza | Dónde |
|---|---|
| 8 vistas Dashboard Studio, generadas | `tools/gen_dashboards.py` → `nifi_monitoring/default/data/ui/views/` (un test falla si el XML difiere de una corrida limpia) |
| Datasets padre `Bulletins`, `Throughput`, `Component_Status` | `NIFI.json`; los campos normalizados son calculados del padre, los hijos solo aportan su constraint |
| Macros de salud, umbrales, repositorios y flota | `macros.conf`: `nifi_fleet`, `nifi_health`, `nifi_repositories`, `nifi_threshold_*` |
| 8 alertas, deshabilitadas | `savedsearches.conf` |
| Status history plano con cursor (R-3) | `bin/nifi.py`, sourcetypes `nifi:api:{processors,process_groups}_status`, lookup `nifi_status_metrics.csv` |
| Flujo de carga del harness | `tests/integration/provision_workload.py`: tráfico, una cola al límite de backpressure, un procesador que falla, uno inválido y uno deshabilitado |
| Tests | `tests/unit/test_dashboards.py`, `test_status_history.py`; `DashboardPanelTest` ejecuta **todas** las fuentes de datos de todas las vistas en cada perfil |
| Eliminado | `home`, las 4 vistas Simple XML viejas, los 2 JS y 2 CSS propios, el GIF, la dependencia de Status Indicator (también del harness) |

### 12.2 Verificación

| Perfil | Splunk | NiFi | Resultado | En Chrome |
|---|---|---|---|---|
| `nifi2-current` | 10.4.3 | 2.11.0 | verde | las 8 vistas; alertas despachadas: disparan *Backpressure* y *ERROR bulletin spike*, no *Instance without data* ni *Repository* |
| `cluster` | 10.4.3 | 2.11.0 ×2 | verde | Cluster: 2/2, roles, heap y cola por nodo |
| `nifi2-hec` (push) | 10.4.3 | 2.11.0 | verde | Instance (throughput desde la Reporting Task), Bulletins (con ruta del grupo) |
| `multi-instance` | 10.4.3 | 2.11.0 + 1.28.1 | verde | — (ventana del navegador minimizada) |
| `nifi1-legacy` | **9.4.15** | 1.23.2 | verde | Overview, Components (sparklines, `selectFirstSearchResult`, clic que fija token), drilldown con host y tiempo |

**V-1, resuelto en parte.** Todo lo que usan las vistas funciona en 9.4.15 y 10.4.3: grid, sparklines en tablas, `selectFirstSearchResult`, `drilldown.setToken`, `drilldown.customUrl`, color por valor. **9.0–9.3 no se probó** y, decidido el 2026-10-01, **9.4 pasa a ser la versión mínima** de Splunk (`doc/compatibility.md`, `README.md`).
**V-2, resuelto.** Un hijo no se consulta como raíz: `datamodel=NIFI.Bulletin_Board` falla con *Invalid or unaccelerable root object*; la forma es `datamodel=NIFI.Bulletins where nodename=Bulletins.Bulletin_Board`. Es un cambio que rompe búsquedas propias de usuarios 1.x sobre `Reporting_Bulletin`/`Reporting_Task`, documentado en `doc/upgrading.md` con esa sintaxis.
**P-1, decidido (b).** El push conserva `nifi:api:*_history`; `Component_Status` lo lee con campos calculados desde el último snapshot.
**Umbrales por instancia (§4.2): implementados el 2026-10-01.** El KV `instance` tiene seis columnas opcionales (`heap_threshold`, `heap_threshold_critical`, `repo_threshold`, `repo_threshold_critical`, `backpressure_threshold`, `bulletin_threshold`) que sobrescriben el macro de igual sentido solo para esa instancia; vacías, rige el macro. `nifi_thresholds` resuelve el umbral efectivo con `coalesce(tonumber(columna), macro)`: el `tonumber` es necesario porque el `default_match = standalone` del lookup llena cada columna de un host desconocido con "standalone". Por la misma razón el `LOOKUP-instance` automático pasó a `OUTPUT cluster`. Verificado en vivo: `repo_threshold = 10` en una fila deja esa instancia degradada y su KPI en amarillo con el mismo 14 %.
**Valores que habían quedado fijos, ahora configurables:** el color de los KPI de heap y repositorio (estaba en 85/95 y 80/90 dentro de la vista; ahora sale de `heap_severity`/`repo_severity`, calculados con el umbral de la instancia); cualquier ERROR degradaba la salud (`nifi_threshold_bulletins_degraded`, 1); el horizonte de predicción de backpressure (`nifi_backpressure_horizon`, 3600 s); las muestras de heap sostenido (`nifi_heap_sustained_samples`, 3); la ventana de "ahora" (`nifi_recent_window`, `-15m`).
**`critical` en `nifi_health`** sale de los umbrales críticos; el "sostenido N muestras" lo hace la alerta *Sustained high heap*, no el macro.
**Splunk 9.4 es la versión mínima** desde el 2026-10-01.

### 12.3 Defectos que apareció la verificación

Ninguno era del rediseño; los expuso que por primera vez los paneles se ejecutaran con datos en todos los perfiles.

| # | Defecto | Arreglo |
|---|---|---|
| **D-U** | El TA leía `endpoint_flow_status`, `endpoint_system_diagnostics` y `endpoint_bulletin_board` comparando contra `'1'`: con `true`/`True` —válidos para Splunk, y lo que escribe su API REST— el endpoint se apagaba sin aviso | `_is_enabled()` para todos; test `EndpointFlagTest` |
| **D-V** | Las dos `InvokeHTTP` del status history del flujo push (1.x, 2.x y la plantilla) armaban la URL con `http://${hostname(true)}:8080` en lugar de `nifi_api_url`. Nunca se vio porque las listas de ids venían vacías | URL desde `nifi_api_url`; test `FlowApiUrlTest` |
| **D-W** | El harness push no instalaba las reporting tasks que la doc pide (paso 4): en push nunca llegaron `nifi:reporting:*`, y `test_the_flow_reports_no_bulletins_at_error_level` pasaba contando nada | `provision_flow.py` instala `JsonRecordSetWriter` y las dos `SiteToSite*ReportingTask`; el test ahora exige los bulletins del workload |
| **D-X** | `run.sh` bajaba solo los servicios del perfil actual: tras `cluster`, un `nifi2-hec` convivía con el segundo nodo, ZooKeeper y dos forwarders que seguían mandando logs | `docker compose --profile '*' down` |
| **D-Y** | La doc push decía `Output Format: Record Formats`; la opción es `Record Format` | doc en ambos idiomas |
| **D-Z** | `test_conf_consistency` no leía `.conf` con continuación de línea ni el `mkdocs.yml` del PR #47 (tags `!!python/name`, nav anidada) | tests |

### 12.4 Lo que queda

- AppInspect sobre los dos paquetes (`make validate`).
- Capturas nuevas para `doc/` (las de los dashboards son de 1.x).
