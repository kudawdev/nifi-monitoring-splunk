# Plan: soporte de NiFi 2.x en NiFi Monitoring for Splunk

| | |
|---|---|
| **Fecha** | 2026-08-24 |
| **Autor** | Anibal Vasquez (Kudaw SA) |
| **Estado** | Propuesta — pendiente de aprobación |
| **Versión actual de las apps** | 1.2.3 (ambas) |
| **Versión objetivo** | 2.0.0 (breaking change) |
| **Apps afectadas** | `nifi_monitoring` (Splunkbase 6125), `nifi_TA_monitoring` (Splunkbase 6124) |

---

## 1. Objetivo y alcance

Extender las dos apps para monitorear instancias de **Apache NiFi 2.x** sin perder el soporte de **NiFi 1.x**, aprovechando la ventana para (a) reconsiderar el método de obtención de datos, (b) corregir los defectos acumulados y (c) convertir el harness de `tests/` en algo que realmente pruebe la app contra una matriz de versiones.

**En alcance**

- Soporte simultáneo de NiFi 1.16+ y 2.x en un único código.
- Revisión y consolidación del método de recolección.
- Corrección de los 24 defectos catalogados en §7.
- Rediseño de `tests/` como matriz parametrizable NiFi × Splunk con verificación automatizada.
- Actualización de la documentación pública bilingüe en `doc/`.

**Fuera de alcance**

- Soporte de NiFi Registry o de clusters NiFi multi-nodo (hoy tampoco está).
- Migración del flujo del cliente: entregamos el artefacto y la guía, no ejecutamos la migración.
- Reescritura de los dashboards a Dashboard Studio (queda como propuesta separada).

---

## 2. Línea base: cómo funciona hoy

Dos caminos de datos que convergen en los mismos sourcetypes:

```
NiFi sin auth   →  flow de NiFi (GetHTTP / TailFile / Reporting Tasks)  →  HEC        (push)
NiFi con basic  →  bin/nifi.py pollea la REST API                        →  EventWriter (pull)
```

| Sourcetype | Camino push | Camino pull | Consumido por la app |
|---|---|---|---|
| `nifi:api:flow_status` | GetHTTP | `/flow/status` | sí |
| `nifi:api:system_diagnostics` | GetHTTP | `/system-diagnostics` | sí |
| `nifi:api:site_to_site` | GetHTTP | `/site-to-site` | **no** |
| `nifi:api:processors_history` | InvokeHTTP | `/flow/processors/{id}/status/history` | sí |
| `nifi:api:process_groups_history` | InvokeHTTP | `/flow/process-groups/{id}/status/history` | sí |
| `nifi:api:controller_cluster` | — | — | **no (huérfano)** |
| `nifi:reporting:task` | SiteToSiteMetricsReportingTask | — | sí |
| `nifi:reporting:bulletin` | SiteToSiteBulletinReportingTask | — | sí |
| `nifi:log:{app,user,bootstrap}` | TailFile | — | sí |

El costo estructural de este diseño: **la lógica de recolección está duplicada** y el camino push obliga al cliente a mantener un flujo NiFi de 39 procesadores dentro de su propio NiFi, más tres Reporting Tasks y dos input ports Site-to-Site.

---

## 3. Investigación: qué cambia realmente en NiFi 2.x

### 3.1 Ciclo de vida de versiones

| | |
|---|---|
| NiFi 1.x — última release | **1.28.1** (2024-11-20) |
| NiFi 1.x — fin de soporte | **2024-12-08** (EOL) |
| NiFi 2.x — primera release | 2.0.0 (2024-11-04) |
| NiFi 2.x — última release | **2.11.0** (2026-08-03) |
| Ruta de migración soportada | 1.x → **1.27.0** → 2.0.0 → 2.x |
| Runtime requerido por 2.x | **Java 21** |

NiFi 1.x lleva **20 meses sin soporte**. Toda corrección de seguridad aterriza solo en la línea 2.x. Esto no es un "nice to have": es la razón por la que los clientes van a migrar y por la que la app tiene que estar lista.

### 3.2 Lo que se rompe: el camino push

Inventario real del flujo de `flow_definition/NiFiMonitoring.json` (39 procesadores) contra la rama `main` de `apache/nifi`:

| Componente | Uso en el flow | Estado en 2.x | Reemplazo |
|---|---|---|---|
| `GetHTTP` | **3×** (flow_status, system_diagnostics, site_to_site) | **REMOVIDO** | `InvokeHTTP` con method GET |
| Variable Registry (`variables` del PG) | **6 variables** | **REMOVIDO** | Parameter Context |
| Template XML (`NifiMonitoringTemplate.xml`) | artefacto distribuido | **REMOVIDO** | flow definition JSON |
| `InvokeHTTP` | 3× | vigente | — |
| `UpdateAttribute` | 10× | vigente | — |
| `LogMessage` | 6× | vigente | — |
| `TailFile`, `SplitText`, `ExtractText`, `EvaluateJsonPath`, `RouteText`, `RouteOnAttribute`, `JoltTransformJSON`, `ReplaceText`, `GenerateFlowFile`, `RetryFlowFile` | 1–2× cada uno | vigentes | — |
| `SiteToSiteMetricsReportingTask` | requerida por la doc | **vigente** | — |
| `SiteToSiteBulletinReportingTask` | requerida por la doc | **vigente** | — |
| `MonitorDiskUsage` | requerida por la doc | **vigente** | — |

**Conclusión:** el daño está acotado. De los 14 tipos de procesador que usa el flow, **solo `GetHTTP` desapareció**. Las tres Reporting Tasks sobreviven intactas. Los bloqueantes reales son tres: `GetHTTP` ×3, el bloque `variables`, y el template XML.

Además, el flow embarca `"flowEncodingVersion": "1.0"` y **cero** `parameterContexts`, así que tal como está no es importable en 2.x con su configuración.

### 3.3 Lo que NO se rompe: la REST API

Verificado contra la documentación oficial de la **REST API de NiFi 2.11.0** y el código de `nifi-web-api` en `main`:

| Endpoint que usa `bin/nifi.py` | 1.x | 2.11.0 |
|---|:---:|:---:|
| `POST /access/token` | ✅ | ✅ |
| `GET /flow/status` | ✅ | ✅ |
| `GET /system-diagnostics` | ✅ | ✅ |
| `GET /site-to-site` | ✅ | ✅ |
| `GET /flow/processors/{id}/status/history` | ✅ | ✅ |
| `GET /flow/process-groups/{id}/status/history` | ✅ | ✅ |

**Los cinco endpoints del modular input y el mecanismo de autenticación sobreviven sin un solo cambio.** `AccessResource.createAccessToken` sigue en `main`, delegando en el `LoginIdentityProvider` configurado — que es lo que provee `single-user-provider`, el default de NiFi desde 1.14.

Esto invierte la intuición: **el camino que envejece bien es el pull (el TA); el que se rompe es el push (el flow)**. El TA, que hoy es el camino secundario, es el que ya soporta NiFi 2.x.

### 3.4 Hallazgo: existe un endpoint de métricas unificado

> Lo que sigue es lo que prometen la documentación y el código. El spike de §3.5 corrigió parte de estas expectativas: leer las dos secciones juntas.

`GET /nifi-api/flow/metrics/{producer}` existe en **1.16+ y en todo 2.x**, con la misma firma:

| Parámetro | Valores | Nota |
|---|---|---|
| `producer` (path) | `prometheus` \| **`json`** | `json` devuelve `application/json` |
| `includedRegistries` | `NIFI`, `JVM`, `BULLETIN`, `CONNECTION`, `CLUSTER`, `VERSION_INFO` | repetible; `VERSION_INFO` solo en 2.x |
| `sampleName` | regex | filtra por nombre de métrica |
| `sampleLabelValue` | regex | filtra por valor de etiqueta |
| `rootFieldName` | string | solo producer `json` |
| `flowMetricsReportingStrategy` | `ALL_COMPONENTS` (default) \| `ALL_PROCESS_GROUPS` | control de cardinalidad |

### 3.5 Lo que el spike encontró (medido, no supuesto)

Se ejecutó el spike contra `apache/nifi:1.23.2` (HTTP sin auth) y `apache/nifi:2.11.0` (single-user, HTTPS). Las muestras están en `docs/plans/samples/`. Tres resultados cambian el diseño respecto de lo que la documentación sugería:

**(a) `producer=json` NO es JSON amigable para Splunk.** Es el modelo de datos de Prometheus serializado:

```json
{ "samples": [ {
    "name": "nifi_amount_items_queued",
    "labelNames":  ["instance","component_type","component_name","component_id","parent_id"],
    "labelValues": ["34228748-…","RootProcessGroup","NiFi Flow","34228740-…",""],
    "value": 0.0, "exemplar": null, "timestampMs": null
} ] }
```

`labelNames` y `labelValues` son **arrays paralelos**. `INDEXED_EXTRACTIONS = json` produciría `samples{}.labelNames{}` y `samples{}.labelValues{}` sin correlacionarlos: inservible para búsquedas. **El TA tiene que hacer el zip de labels y emitir un evento plano por muestra (o por componente).** No es un endpoint que se pueda enchufar y listo.

**(b) El endpoint de métricas NO reemplaza a `/flow/status`.** Ninguna de las dos versiones expone como métrica los 16 conteos de `controllerStatus` que el datamodel `Flow_Status` consume:

| Campo del datamodel | ¿Existe como métrica? |
|---|---|
| `activeThreadCount`, `terminatedThreadCount` | ✅ `nifi_amount_threads_active` / `_terminated` |
| `flowFilesQueued`, `bytesQueued` | ✅ `nifi_amount_items_queued`, `nifi_size_content_queued_total` |
| `runningCount`, `stoppedCount`, `invalidCount`, `disabledCount` | ❌ |
| `upToDateCount`, `locallyModifiedCount`, `staleCount`, `syncFailureCount`, `locallyModifiedAndStaleCount` | ❌ |
| `activeRemotePortCount`, `inactiveRemotePortCount` | ❌ |

**`/flow/status` es irreemplazable.** Son 364 bytes por llamada; no hay razón para intentar sustituirlo.

**(c) Las métricas de 2.x son un superconjunto estricto de las de 1.x.** 1.23.2 expone 38 métricas; 2.11.0 expone 56; **ninguna desapareció**. Las 18 nuevas son justamente las que faltaban:

- `nifi_{content,flow_file,provenance}_repo_{free,total,used}_space_bytes` (9) — en **2.x el endpoint de métricas sí cubre los repositorios** que el datamodel `System_Diagnostics` necesita; en 1.x hay que seguir usando `/system-diagnostics`.
- `nifi_processing_performance_{cpu,gc,content_read,content_write,session_commit}_duration` (5) — observabilidad que la app hoy no tiene.
- `nifi_jvm_heap_committed`, `nifi_jvm_non_heap_{used,committed}` (3), `nifi_version_info` (1).

**(d) Detalles operativos medidos:**

| Observación | Dato |
|---|---|
| Volumen en NiFi vacío | 1.23.2: 40 samples / 10.9 KB · 2.11.0: 56 samples / 17.3 KB |
| `includedRegistries` reduce de verdad | `JVM` → 11 samples / 1.9 KB · `NIFI` → 23 / 7.5 KB · `CONNECTION` → 2 / 0.8 KB |
| `sampleName` acepta regex | `nifi_amount.*` → 13 samples / 4.1 KB |
| `includedRegistries=VERSION_INFO` en 1.23.2 | **HTTP 404**, no respuesta vacía — el TA debe detectar versión antes de pedirlo, o tolerar el 404 |
| `POST /access/token` en 2.11.0 con `single-user-provider` | ✅ JWT válido, `exp - iat` = 8 h |
| Los 5 endpoints del TA en 2.11.0 | ✅ los 5 responden 200 con Bearer token |
| `GET /flow/bulletin-board` en 2.11.0 | ✅ 200 |
| Contenedor NiFi 2.x sin `NIFI_WEB_PROXY_HOST` | **HTTP 421 Misdirected Request** — hay que declararlo o nada funciona |

### 3.6 Lectura de los hallazgos

El endpoint de métricas es un **complemento de alto valor**, no un sustituto:

- **Aporta** estado por componente sin enumerar IDs a mano (hoy el cliente pega listas de UUIDs en el data input), predicciones de backpressure, analytics de conexión, y en 2.x el espacio de los tres repositorios y las métricas de performance.
- **No aporta** los conteos de estado y versionado del flujo (`/flow/status`) ni las series históricas (`/flow/.../status/history`).
- Requiere **transformación en el TA**, no es pass-through.
- Al ser 1.x ⊂ 2.x, **un solo parser sirve para ambas líneas**: las métricas nuevas simplemente aparecen cuando el NiFi es 2.x.

---

## 4. Decisión de arquitectura: el método de obtención

### 4.1 Comparación de los cuatro métodos disponibles

| Criterio | A. Flow NiFi → HEC (push, actual) | B. Modular input REST (pull, actual) | C. B + `/flow/metrics/json` (propuesto) | D. Prometheus scrape externo |
|---|---|---|---|---|
| Sobrevive NiFi 2.x | ❌ requiere reconstruir el flow | ✅ **medido: los 5 endpoints y el token dan 200 en 2.11** | ✅ | ✅ |
| Un solo código para 1.x y 2.x | ❌ dos flows | ✅ | ✅ (1.x ⊂ 2.x en métricas) | ✅ |
| Artefacto a mantener dentro de NiFi | 39 procesadores + 3 tasks + 2 puertos S2S | **ninguno** | **ninguno** | ninguno |
| Esfuerzo de configuración del cliente | alto (flow + tasks + variables) | bajo (un data input) | **muy bajo** | medio (otro stack) |
| Requiere que Splunk alcance a NiFi | no | **sí** | **sí** | sí |
| Cobertura de logs de NiFi | sí (TailFile) | no | no | no |
| Bulletins sin pérdida entre polls | ✅ (S2S es push) | n/a | ⚠️ conteos, no eventos | ⚠️ |
| Enumerar IDs de componentes a mano | sí | sí | **no** | no |
| Repositorios (content/flowfile/provenance) | vía `/system-diagnostics` | vía `/system-diagnostics` | métricas en 2.x, endpoint en 1.x | 2.x |
| Conteos de estado y versionado del flujo | `/flow/status` | `/flow/status` | **`/flow/status`, irreemplazable** | ❌ no disponible |
| Transformación necesaria antes de indexar | media (Jolt en el flow) | ninguna (pass-through) | **sí, zip de labels en el TA** | n/a |
| Control de intervalo/índice/reintento desde Splunk | no | ✅ | ✅ | no |
| Dependencias nuevas | ninguna | ninguna | ninguna | Prometheus + conector |

### 4.2 Decisión

**Adoptar C como camino primario y soportado, conservar A como camino alternativo reconstruido, y sacar los logs de ambos.**

1. **Primario — TA con REST pull (C).** `bin/nifi.py` mantiene `/flow/status` y los `status/history` como fuentes estructuradas —el spike probó que no son sustituibles— y **agrega** `/flow/metrics/json` como fuente complementaria, con el TA haciendo el zip de `labelNames`/`labelValues` y emitiendo un evento plano por muestra. En NiFi 2.x las métricas cubren además los tres repositorios, lo que permite espaciar o volver opcional el polling de `/system-diagnostics`; en 1.x ese endpoint sigue siendo necesario. Un solo código, mismo comportamiento en 1.16→2.11, cero artefactos dentro de NiFi.

2. **Alternativo — flow reconstruido (A').** Se mantiene porque es la **única** opción cuando Splunk no puede alcanzar la API de NiFi (NiFi en DMZ, red segmentada, NiFi que solo puede hacer egress). Se reconstruye una vez, nativo 2.x: `InvokeHTTP` en lugar de `GetHTTP`, Parameter Context en lugar de variables, y reducido a lo mínimo indispensable. Se versiona por línea de NiFi.

3. **Logs: UF como recomendación por defecto, `TailFile` conservado como alternativa.** Ver §4.3 — la rama de logs del flow **no se rompe** en NiFi 2.x, así que esto es una decisión de diseño, no una migración forzada.

4. **Bulletins: decisión explícita del trade-off.** El registry `BULLETIN` de `/flow/metrics` entrega **conteos**, no los bulletins individuales que hoy alimentan el dashboard `nifi_bulletin`. Para los eventos individuales hay dos opciones y ninguna es gratis:
   - polling de `GET /flow/bulletin-board` — simple, pero puede perder bulletins si el intervalo del input supera la retención del bulletin board (5 min por defecto en NiFi);
   - `SiteToSiteBulletinReportingTask` → HEC — no pierde eventos, pero reintroduce configuración dentro de NiFi.

   **Decidido (D-1, 2026-08-24): ambas, con el polling por defecto.** Implementado en TA-5, con tres cosas que la implementación aclaró:

   - `/flow/bulletin-board` acepta **`?after=<id>` en 1.x y en 2.x**, así que cada poll pide solo lo que no vio: no hay duplicados. El cursor vive en el `checkpoint_dir` de Splunk, que sobrevive reinicios — no en el `.env` (ver TA-7).
   - Lo que el `after` **no** puede hacer es recuperar un bulletin que NiFi ya descartó del board. Cuando una página vuelve llena, el input emite un WARN diciendo que pudo haber pérdida y qué hacer.
   - **Verificado contra un bulletin real**, no solo contra el DTO: `tests/integration/capture_bulletin.py` provoca uno a propósito (un `InvokeHTTP` apuntado a un puerto cerrado) y guarda la respuesta en `docs/plans/samples/nifi2.11-bulletin-board.json`. 7 de los 8 FIELDALIAS resuelven; el octavo, `nodeAddress`, solo lo puebla un cluster. Dos detalles que solo se vieron ahí: `bulletin.timestamp` es un reloj sin fecha (`"18:44:32 UTC"`) e inusable como tiempo de evento, y el `stackTrace` real pasa los 500 caracteres — la razón concreta del `TRUNCATE = 0`.
   - **El board da menos campos que la Reporting Task:** `bulletinGroupName` y `bulletinGroupPath` no existen ahí (el board lleva el id del grupo, nunca resuelve su nombre). `sourceType` y `stackTrace` existen solo desde NiFi 2.0. Eso es una razón adicional para conservar las dos vías.

### 4.3 Los logs de NiFi: análisis aparte

Hoy los logs llegan por el flow: el PG "Monitoring - Logs" hace `TailFile` sobre `${nifi_path}/logs/`, rutea con `RouteOnAttribute` y sale por el mismo `InvokeHTTP` al HEC, produciendo `nifi:log:{app,user,bootstrap}`.

**Lo primero: esto no se rompe en NiFi 2.x.** Verificado contra `apache/nifi:1.23.2` y `2.11.0`:

| Aspecto | 1.23.2 | 2.11.0 |
|---|---|---|
| Appenders en `logback.xml` | APP, USER, REQUEST, BOOTSTRAP, DEPRECATION | **idénticos** |
| Nombres de archivo | `nifi-{app,user,request,bootstrap,deprecation}.log` | **idénticos** |
| Patrón de línea | `%date %level [%thread] %logger{40} %msg%n` | **idéntico** |
| `TailFile` | disponible | disponible |

Una línea real de NiFi 2.11.0:

```
2026-08-24 14:32:51,640 INFO [main] org.apache.nifi.runtime.Application Starting NiFi 2.11.0 using Java 21.0.12+10-LTS with PID 83
```

El `TIME_FORMAT = %Y-%m-%d %H:%M:%S,%3N` y el `EXTRACT-level` que el TA ya tiene **parsean esa línea sin cambios**. Lo único que afecta a la rama de logs del cambio a 2.x es que usa la variable `nifi_path`, y las variables se removieron: es un renglón a mover al Parameter Context, no una reescritura.

**Entonces la decisión es de diseño, y tiene dos lados:**

| | `TailFile` en el flow (hoy) | Universal Forwarder |
|---|---|---|
| Rotación de archivos | la maneja `TailFile` | la maneja el UF (más probado) |
| Checkpoint tras reinicio | estado del procesador | fishbucket persistente |
| Si Splunk no responde | los FlowFiles se acumulan en la cola del flujo y pueden generar **backpressure en el propio NiFi** | el UF encola en disco, aislado de NiFi |
| Recursos | compite con el trabajo real dentro del JVM de NiFi | proceso aparte |
| Eventos multilínea (stack traces) | hay que reconstruirlos en el flujo | `props.conf` con `LINE_BREAKER` por timestamp |
| Dirección de la conexión | NiFi → Splunk (egress) | UF → Splunk (egress) — **también sirve si Splunk no alcanza a NiFi** |
| NiFi en contenedor / Kubernetes | funciona sin nada extra | requiere sidecar o imagen con UF: **incómodo** |
| Acceso al host de NiFi | no hace falta | hace falta instalar y gestionar un paquete |

**Propuesta:** UF como camino recomendado y documentado (el TA ya trae las stanzas `[monitor://...]` listas, solo deshabilitadas), y **conservar la rama `TailFile` del flow** para el caso real donde gana: NiFi containerizado donde meter un UF no es opción. No se elimina nada; se cambia cuál es el camino por defecto en la documentación.

**Tres brechas que aparecieron al revisar esto** (preexistentes, afectan igual a NiFi 1.x):

1. **`nifi-deprecation.log` no se recolecta, y es justo el log que importa en una migración.** Existe en ambas versiones y su razón de ser es avisar qué se está usando que va a desaparecer. Un sourcetype `nifi:log:deprecation` convierte a la app en herramienta de apoyo a la migración a 2.x: el cliente ve en un panel qué componentes deprecados usa antes de actualizar. Es el mayor aporte de valor que salió de este análisis.
2. **`nifi-request.log` tampoco se recolecta** (log de acceso HTTP a la API/UI, con formato propio).
3. **Los stack traces se fragmentan.** En un arranque limpio de NiFi 2.11, **1014 de 1311 líneas** de `nifi-app.log` (77%) son líneas de continuación sin timestamp. Con la config actual del TA eso se indexa mal — ver defecto B-20.

Tareas derivadas: TA-11 … TA-14 en §6.1.

### 4.4 Lo que explícitamente NO se hace

- **No se elimina el camino HEC.** Cubre topologías que el pull no puede.
- **No se adopta D (Prometheus externo).** Mete un stack nuevo en medio para resolver algo que la app ya resuelve; solo tendría sentido si el cliente ya tuviera Prometheus, y en ese caso no necesita esta app.
- **No se migra a métricas de Splunk (`mstats`).** Los `props.conf` traen la infraestructura comentada (`METRIC-SCHEMA-TRANSFORMS`). Es una mejora real de costo de almacenamiento, pero es un rediseño de los dashboards y del datamodel: propuesta separada.

---

## 5. Matriz de compatibilidad objetivo

| Producto | Versiones soportadas en 2.0.0 | Probadas en CI |
|---|---|---|
| Apache NiFi | 1.16 – 1.28.1, 2.0 – 2.11 | `1.23.2`, `1.28.1`, `2.11.0` |
| Splunk Enterprise / Cloud | 9.0 – 10.x | `9.4`, `10.4` |
| Python (modular input) | el de Splunk (3.7/3.9) | ambos |

Piso de NiFi en 1.16 porque es donde aparece `producer=json`. Para 1.12–1.15 el TA cae al modo legacy (endpoints individuales); se documenta, no se prueba en CI.

Splunk sube de 8.2–9.4 a 9.0–10.x: 8.x está fuera de soporte y Splunk 10 ya es la línea corriente. Requiere revalidar AppInspect (ver B-17).

---

## 6. Cambios por componente

### 6.1 `nifi_TA_monitoring`

| # | Cambio |
|---|---|
| TA-1 | Reescribir `NiFiScript.endpoints` como tabla declarativa con `min_version` / `max_version` por endpoint, en lugar de la lista plana actual. |
| TA-2 ✅ | **Hecho.** Agregar `/flow/metrics/json` con `includedRegistries`, `flowMetricsReportingStrategy` y `sampleName` expuestos como parámetros del input. **No es pass-through:** implementar el zip de `labelNames`/`labelValues` y emitir un evento plano por muestra (`{name, value, <labels…>}`). Ver §3.5(a). |
| TA-2b ✅ | **Hecho** (los registries se filtran por versión detectada). `includedRegistries=VERSION_INFO` responde **404 en 1.x**: pedirlo solo cuando la versión detectada sea ≥2.0, o tratar el 404 como "no soportado" sin marcarlo como error. |
| TA-3 ✅ | **Hecho.** Autodetección de versión leyendo `versionInfo.niFiVersion` de `/system-diagnostics`, que existe en **todas** las versiones soportadas — un solo camino, no la bifurcación que preveía este plan. `VERSION_INFO` del endpoint de métricas quedó descartado para esto: responde 404 antes de 2.0, así que no sirve para averiguar con qué versión se está hablando. La respuesta se reutiliza para el endpoint `system_diagnostics` (una sola llamada por ciclo) y la versión se emite como `nifi:api:version_info`. |
| TA-4 ✅ | **Hecho.** Nuevo sourcetype `nifi:api:flow_metrics` con su `props.conf` (`INDEXED_EXTRACTIONS = json`, **`TRUNCATE = 0`**, `SHOULD_LINEMERGE = false`, `LINE_BREAKER = ([\r\n]+)`) — un evento por línea. |
| TA-4b | En NiFi ≥2.0 los repositorios llegan por métricas (`nifi_*_repo_*_space_bytes`): hacer `/system-diagnostics` opcional o de intervalo mayor, sin romper 1.x. |
| TA-5 ✅ | **Hecho.** Polling de `/flow/bulletin-board` → `nifi:api:bulletin_board`, habilitado por defecto, con `?after=<id>` y cursor en el `checkpoint_dir`. `props.conf` mapea la forma del board a los nombres que ya usa el datamodel, para que ambas fuentes alimenten los mismos paneles. |
| TA-6 ◐ | **Parcial:** `nifi:api:controller_cluster` retirado (nada lo producía, ni el flow ni el TA). `nifi:api:site_to_site` sigue en pie a la espera de D-2. |
| TA-7 ◐ | **Parcial:** el cursor de bulletins ya usa el `checkpoint_dir` de Splunk. Falta mover el token. Sustituir el estado en `.env` por el KV store de Splunk o `storage/passwords` (B-14). **Medido en el run del 2026-08-24:** el `.env` vive dentro del directorio de la app, así que se pierde al reinstalarla o recrear el contenedor, y cada arranque en frío paga un 401 evitable. Al no haber token cacheado, pedirlo proactivamente antes de la primera request en lugar de provocar el 401. |
| TA-8 | Corregir B-4, B-5, B-15, B-16. |
| TA-9 | Extender `nifi_manager.xml` y `inputs.conf.spec` con los parámetros nuevos. |
| TA-10 ✅ | **Hecho.** `python.required` junto a `python.version`, que se conserva para Splunk 8.2–9.1. |
| TA-11 ✅ | **Hecho.** Nuevo sourcetype `nifi:log:deprecation` + su stanza `[monitor://…nifi-deprecation*.log]`. Es el insumo del panel de apoyo a la migración (§4.3). |
| TA-12 ✅ | **Hecho.** `nifi:log:request`. El formato se capturó de un NiFi real (`docs/plans/samples/nifi2.11-request.log`): es **NCSA combined**, idéntico al `access_combined` de Splunk, así que reutiliza `REPORT-access = access-extractions` del core en lugar de repetir el regex. Es el único log de NiFi con timestamp propio, así que el `_time` es el de la request, no el de recolección. |
| TA-13 ✅ | **Hecho.** Corregido el corte de eventos de los cuatro `nifi:log:*` para agrupar los stack traces (B-20): `LINE_BREAKER = ([\r\n]+)(?=\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})`, `SHOULD_LINEMERGE = false` explícito en las cuatro stanzas y `TRUNCATE` holgado. |
| TA-14 ✅ | **Hecho.** Rutas corregidas a `/opt/nifi/nifi-current/logs/` (B-21) y documentar que en el contenedor oficial es `/opt/nifi/nifi-current/logs/`, no `/opt/nifi/logs/`. |

### 6.2 `nifi_monitoring`

| # | Cambio |
|---|---|
| APP-1 | Reemplazar `index_nifi = index=*` por un macro con índice configurable vía lookup o argumento (B-6). |
| APP-2 | Decidir aceleración del datamodel `NIFI`: activarla, o dejar de consultarlo con `tstats` (B-7). |
| APP-3 | Nuevos objetos de datamodel para `nifi:api:flow_metrics` y `nifi:api:bulletin_board`. |
| APP-4 | Eliminar los `join` de `nifi_overview.xml` (B-8). |
| APP-5 | Verificar los nombres de campo de `System_Diagnostics` en `nifi_overview.xml` — referencian `freeSpace`/`usedSpace`/`utilization` sin prefijo de objeto, y el datamodel solo declara las variantes `*Bytes` (B-19). |
| APP-6 | Agregar stanza `[id]` en `app.conf` (B-17). |
| APP-7 | Panel de inventario que muestre versión de NiFi y método de recolección por instancia. |

### 6.3 `flow_definition`

| # | Cambio |
|---|---|
| FLOW-1 | Estructurar en `flow_definition/nifi-1.x/` y `flow_definition/nifi-2.x/`. |
| FLOW-2 | Reconstruir para 2.x: `GetHTTP` → `InvokeHTTP`, `variables` → Parameter Context. |
| FLOW-3 | **Purgar el token HEC y la IP del JSON** y reemplazarlos por placeholders (B-1). |
| FLOW-4 | Retirar `NifiMonitoringTemplate.xml` (formato removido en 2.x); dejar nota de migración. |
| FLOW-5 | **Conservar** la rama de logs (`TailFile`) — no se rompe en 2.x (§4.3); solo mover `nifi_path` al Parameter Context. Cambia la recomendación de la doc a UF por defecto, no el artefacto. |
| FLOW-6 | Validar que 2.x importa el flow con el `flowEncodingVersion` que exportemos. |

### 6.4 `doc/` (pública, bilingüe)

| # | Cambio |
|---|---|
| DOC-1 | `mkdocs.yml`: agregar `docs_dir: doc` tras el rename `docs/` → `doc/`, o `docs.yml` publica un sitio vacío (B-10). |
| DOC-2 | Reescribir §3 de `configuration.md` — "Global variables configuration" describe una UI que **no existe en NiFi 2.x**. |
| DOC-3 | Recapturar los screenshots: la UI de NiFi 2.x es un rediseño completo (Angular). ~25 imágenes en `doc/assets/images/nifi/`. |
| DOC-4 | Nueva página: matriz de compatibilidad y elección de método de recolección. |
| DOC-5 | Corregir el link roto a `template/NifiMonitoring.json` (la carpeta es `flow_definition/`). |
| DOC-6 | `mkdocs.yml`: `current_version: 1.0` → 2.0 (B-12). |
| DOC-7 | Actualizar los pares `*.es.md` de todo lo anterior. |

---

## 7. Defectos a corregir en el camino

Catalogados durante la lectura del repositorio del 2026-08-24. Severidad: **A** = corregir antes del release, **B** = incluir si entra, **C** = registrar.

| ID | Sev | Componente | Defecto |
|---|:---:|---|---|
| B-1 | **A** | `flow_definition/NiFiMonitoring.json` | Token HEC real e IP pública de un ambiente de desarrollo, hardcodeados en `flowContents.variables`, en repo público y en el historial. **Rotar el token, no solo borrarlo.** |
| B-2 | **A** | `.github/workflows/main.yml`, `testing.yml` | `check-apps-version` globea `ls -d allkun*` (heredado de otro repo). Sin coincidencias el gate pasa vacuamente: se puede publicar un release con las dos apps desalineadas. `dev.yml` está correcto (`nifi*`). |
| B-3 | **A** | `.github/workflows/testing.yml` | Usa `::set-output`, deshabilitado por GitHub en 2023 → `APP_VERSION` vacío → `slim validate` falla. El workflow está roto de punta a punta. |
| B-4 | **A** | `bin/nifi.py:validate_input` | Stub (`a=1; b=2; if a>=b: raise`) con `use_external_validation = True`. No valida nada: URL inválida o credenciales vacías se aceptan. |
| B-5 | **A** | `bin/nifi.py:__get_request` | En el reintento tras 401 se construye `headers` con el token nuevo pero **nunca se asigna a `req_args`**: el reintento reenvía el token viejo. La recuperación de sesión expirada no funciona. |
| B-6 | **A** | `nifi_monitoring/default/macros.conf` | `index_nifi = index=*` — base de todos los dashboards y de las constraints del datamodel. Busca en todos los índices, incluidos los internos. |
| B-7 | **B** | `datamodels.conf` + dashboards | `acceleration = false` mientras 6 paneles usan `tstats … from datamodel=NIFI.*`. Sin aceleración degrada a búsqueda cruda. |
| B-8 | **B** | `nifi_overview.xml` | Dos `join type=left` en la query principal. |
| B-9 ◐ | **B** | TA + app | `controller_cluster` retirado; `site_to_site` pendiente de D-2. | `nifi:api:site_to_site` se recolecta (habilitado por defecto) y **ningún** dashboard ni objeto de datamodel lo consume. `nifi:api:controller_cluster` tiene `props.conf` y no lo produce nadie. |
| B-10 | **A** | `mkdocs.yml` | No declara `docs_dir`; tras el rename `docs/` → `doc/` apunta a un directorio vacío. `docs.yml` publicaría un sitio vacío. |
| B-11 | C | `AGENTS.md` / `CLAUDE.md` | Dice versión 1.2.2; las apps están en 1.2.3. También afirma que `main.yml`/`testing.yml` corren por push — los tres son `workflow_dispatch`. |
| B-12 | C | `mkdocs.yml` | `current_version: 1.0`. |
| B-13 | **A** | `tests/nifi123-splunk91-nifi_login.yml` | `NIFI_WEB_PROXY_HOST: '<URL_BASE>:9443'` sin reemplazar → NiFi rechaza por host header. `SINGLE_USER_CREDENTIALS_PASSWORD: 'Password'` tiene 8 caracteres y NiFi exige 12: ignora las credenciales y genera aleatorias. **El modo login no funciona como está escrito.** Además mapea `443:9443` (puerto privilegiado) y no monta `../:/tmp/test` ni instala las apps auxiliares. |
| B-14 | **B** | `bin/nifi.py` | Persiste el token JWT en claro en un `.env` dentro de `bin/`. `dotenv.find_dotenv()` busca desde el CWD hacia arriba: en un modular input eso es `$SPLUNK_HOME`, y puede enganchar un `.env` ajeno. |
| B-15 | **B** | `bin/nifi.py` | `import requests` / `import urllib3` sin vendorizar en `lib/` — depende de que el Python de Splunk los traiga. Frágil entre versiones de Splunk. |
| B-16 | C | `bin/nifi.py:__get_password` | Devuelve `None` silenciosamente si no encuentra el usuario en `storage/passwords`. |
| B-17 ✅ | **B** | `app.conf` (ambas) | Falta la stanza `[id]` con `name`/`version`: agregarla baja 2 warnings de AppInspect (`check_for_valid_package_id`, `check_version_is_valid_semver`). Relevante porque el gate es `MAX_WARNING = 8` y AppInspect 4.2.x sumó `check_collections_conf` (+1, y `nifi_monitoring` tiene `collections.conf`). |
| B-18 | C | `doc/configuration.md` | Link a `blob/main/template/NifiMonitoring.json`; la carpeta es `flow_definition/`. |
| B-19 | **B** | `nifi_overview.xml` | El panel "Status Disk Space" pide `systemDiagnostics.…{}.freeSpace`/`usedSpace`/`utilization` dentro de un `tstats from datamodel=`, sin prefijo de objeto y con campos que el datamodel no declara (solo tiene las variantes `*Bytes`). Verificar si el panel devuelve datos. |
| B-20 ✅ | **B** | `nifi_TA_monitoring/default/props.conf` | El corte de eventos de los logs es inconsistente y fragmenta los stack traces. `nifi:log:app` **no declara `SHOULD_LINEMERGE`** (queda al default `true`) mientras `nifi:log:user` y `nifi:log:bootstrap` sí lo ponen en `false`; con `LINE_BREAKER = ([\r\n]+)` cada línea de un stack trace se convierte en un evento suelto, sin timestamp ni `level`. **Medido: 77% de las líneas de `nifi-app.log` en un arranque limpio de NiFi 2.11 son continuaciones sin timestamp** (1014 de 1311). Ninguna stanza declara `TRUNCATE`, así que aplica el default de 10.000 bytes, que además de mutilar el evento grande se lleva el siguiente. |
| B-21 ✅ | C | `nifi_TA_monitoring/default/inputs.conf` | Los monitor inputs apuntan a `/opt/nifi/logs/nifi-*.log`, pero en la imagen oficial de NiFi los logs están en `/opt/nifi/nifi-current/logs/`. La ruta por defecto no sirve para el despliegue más común. |
| B-22 ✅ | C | TA | `nifi-deprecation.log` y `nifi-request.log` existen en 1.x y 2.x y **no se recolectan**. El primero es el log que dice qué componentes deprecados está usando el cliente: el insumo natural de un panel de apoyo a la migración a 2.x. |
| B-23 | **A** ✅ | `bin/nifi.py` | **Resuelto.** Todas las llamadas a NiFi usaban `verify = False` (y se silencian los warnings de urllib3 con `disable_warnings`). Contra un NiFi con HTTPS eso acepta cualquier certificado: un atacante en la red puede interceptar la sesión y quedarse con el usuario, la contraseña y el JWT. En NiFi 2.x esto importa más que antes, porque HTTPS es el default y el modo sin auth dejó de ser práctico. Ahora es opcional (`verify_tls`, checkbox "Verify TLS certificate") con un `ca_bundle` opcional, y la verificación queda **activada** por defecto — incluido para los inputs guardados antes de que la opción existiera. Los warnings de urllib3 solo se silencian cuando el usuario apagó la verificación, y un fallo de certificado ahora dice qué hacer en lugar de mostrar solo el error de `requests`. Ver R-7 (breaking change) y R-8 (el harness cubre el camino sin verificar, no el default). |
| B-24 | C | `nifi_TA_monitoring/lib/splunklib` | `splunklib/results.py` hace `import deprecation`, un paquete de terceros que **no está vendorizado** junto a él, así que ese módulo lanza `ModuleNotFoundError` si alguien lo importa. Apareció al upgradear splunklib a 2.1.1 (`51f3ae6`). Hoy no rompe nada porque `bin/nifi.py` solo usa `splunklib.client` y `splunklib.modularinput`, que importan bien; queda como trampa para el próximo que necesite leer resultados de búsqueda. Vendorizar `deprecation` o retirar `results.py` del paquete. |

---

## 8. Rediseño del harness de `tests/`

### 8.1 Qué falla hoy

`tests/` no es una suite: es un par de composes de un solo punto de la matriz, con provisioning manual y sin una sola verificación.

- Una única combinación por archivo, con la versión en el **nombre del archivo** (`nifi123-splunk91-…`): agregar una versión significa copiar el archivo.
- NiFi 1.23.2 y Splunk 9.1, ambos desactualizados.
- Provisioning manual: `docker exec` + correr `init_splunk_nologin.sh` a mano, y "deshabilitar SSL en el HEC" a mano.
- El modo login está roto (B-13) y no tiene script de init.
- `nifi.csv` fija `host=nifi1`, así que solo sirve al modo nologin.
- `splunk_uf1` con `replicas: 0`, compartiendo los volúmenes de Splunk: frágil y desactivado.
- **Cero assertions.** Nada verifica que los eventos llegaron, que los campos se extrajeron o que los paneles devuelven datos.

### 8.2 Estructura propuesta

```
tests/
  docker-compose.yml            # único, parametrizado por variables de entorno
  .env.example                  # NIFI_VERSION, SPLUNK_VERSION, NIFI_AUTH, ...
  matrix.yml                    # combinaciones soportadas (fuente de verdad del CI)
  provision/
    splunk/                     # apps, inputs.conf, lookups, HEC — via volumen, sin exec manual
    nifi/                       # flow definition + parameter context por línea de versión
  assertions/
    test_ingest.py              # ¿llegaron eventos por sourcetype? ¿en cuántos segundos?
    test_fields.py              # ¿se extrajeron los campos que el datamodel declara?
    test_dashboards.py          # ¿cada panel devuelve filas?
    conftest.py                 # espera de readiness vía splunklib
  run.sh                        # levanta, provisiona, corre assertions, tira, devuelve exit code
```

### 8.3 Decisiones de diseño

| # | Decisión |
|---|---|
| T-1 | **Un solo compose parametrizado.** `image: apache/nifi:${NIFI_VERSION}` y `splunk/splunk:${SPLUNK_VERSION}`. La matriz vive en `matrix.yml`, no en nombres de archivo. |
| T-2 | **Provisioning declarativo.** Apps y `.conf` montados por volumen o precargados con un init container antes de que arranque `splunkd` — sin `docker exec` manual. `SPLUNK_HEC_TOKEN` y el HEC sin SSL se configuran por `SPLUNK_APPS_URL`/`default.yml`, no a mano. |
| T-3 | **Modo de auth como variable.** `NIFI_AUTH=none\|singleuser` selecciona el perfil de NiFi. Corrige B-13 de paso: password de ≥12 caracteres y `NIFI_WEB_PROXY_HOST` resuelto. |
| T-4 | **Perfil `nifi2-http` aparte.** En NiFi 2.x el `start.sh` del contenedor prioriza HTTPS con el hostname del contenedor sobre la configuración HTTP: el modo sin auth **no** sale con solo pasar `NIFI_WEB_HTTP_PORT`. Requiere override del entrypoint o de `nifi.properties`. Hay que resolverlo explícitamente y documentarlo. |
| T-5 | **Assertions en Python con `splunklib`,** ejecutadas contra la API de management. Es la única forma de que "test" signifique algo. |
| T-6 | **Healthchecks reales.** Splunk 10 arranca lento: `start_period` de 900 s (con 180 s el `up --wait` falla). Splunk 10 además exige `SPLUNK_GENERAL_TERMS: '--accept-sgt-current-at-splunk-com'` o el contenedor sale con código 1. |
| T-7 | **`run.sh` devuelve exit code** para que el job `unittest` del CI —hoy un `echo "TODO"`— pase a ejecutar la matriz de verdad. |
| T-8 | Quitar `version: '3.8'` (obsoleto) y el `splunk_uf1` con `replicas: 0`; si se prueban logs, un UF real en su propio perfil. |

### 8.4 Matriz propuesta para CI

| Perfil | NiFi | Splunk | Auth | Camino de datos |
|---|---|---|---|---|
| `nifi1-legacy` | 1.23.2 | 9.4 | none | pull (regresión) |
| `nifi1-last` | 1.28.1 | 10.4 | singleuser | pull + token |
| `nifi2-current` | 2.11.0 | 10.4 | singleuser | pull + token |
| `nifi2-hec` | 2.11.0 | 10.4 | singleuser | push (flow reconstruido) |

En PR corren `nifi1-legacy` y `nifi2-current`; la matriz completa en el workflow de release.

---

## 9. Fases de ejecución

### F0 — Spike de validación (parcialmente ejecutado el 2026-08-24)

| # | Tarea | Estado | Resultado |
|---|---|---|---|
| F0.1 | Levantar `1.23.2` y `2.11.0` | ✅ | 1.23.2 en HTTP sin auth; 2.11.0 en HTTPS single-user |
| F0.2 | Capturar `/flow/metrics/json` de ambas | ✅ | muestras en `docs/plans/samples/` |
| F0.3 | Medir cardinalidad y efecto de los filtros | ⚠️ parcial | medido en NiFi **vacío** (§3.5d). Falta medir con un flujo no trivial, que es donde `ALL_COMPONENTS` vs `ALL_PROCESS_GROUPS` importa |
| F0.4 | `POST /access/token` contra 2.11.0 | ✅ | JWT válido, 8 h de vida; los 5 endpoints del TA responden 200 |
| F0.5 | Importar el flow actual en 2.11.0 | ❌ pendiente | requiere UI; confirmar el modo de falla exacto |
| F0.6 | Modo HTTP sin auth en el contenedor 2.x | ⚠️ parcial | se reprodujo el **421** y se resolvió con `NIFI_WEB_PROXY_HOST`; falta la receta de HTTP puro sin auth |
| F0.7 | Mapeo métricas ↔ datamodel | ✅ | §3.5(b) y (c): `/flow/status` irreemplazable; repositorios cubiertos solo en 2.x |
| F0.8 | Levantar `1.28.1` y probar el TA real end-to-end contra Splunk | ❌ pendiente | se cubre en F2 con el harness nuevo |

**Lo que F0 ya cambió del plan:** §3.5 y §3.6 (nuevas), §4.1 (dos criterios agregados), §4.2.1 (reescrito), TA-2/TA-2b/TA-4/TA-4b. La decisión de §4.2 se sostiene, pero el rol del endpoint de métricas pasó de "sustituto" a "complemento con transformación en el TA".

**Lo que falta antes de F3:** F0.3 con un flujo real y F0.5. F0.8 se absorbe en F2.

### F1 — Saneamiento (independiente de NiFi 2.x)

Todo esto se puede mergear ya y liberar como **1.2.4**, sin esperar el resto.

- B-1 (rotar token + purgar), B-2, B-3, B-10, B-13.
- B-4, B-5, B-16 en `nifi.py`.
- B-11, B-12, B-18.
- **Aceptación:** los tres workflows verdes y con el gate de versión funcionando de verdad (probado con versiones desalineadas a propósito); ningún secreto en el HEAD.

### F2 — Harness de tests

- T-1 … T-8 y la matriz de §8.4.
- **Aceptación:** `run.sh` levanta los 4 perfiles y las assertions pasan contra la app 1.2.4 tal cual; el job `unittest` del CI ejecuta la matriz y falla si un perfil falla.
- **Estado 2026-08-24: F2 completa.** Los **cuatro perfiles** de la matriz corren de punta a punta en verde, `run.sh` devuelve exit 0 con teardown limpio, y el CI ejecuta la matriz (`integration` como job aparte, con `publish` dependiendo de él). Suite unit: 49 tests.

| Perfil | NiFi | Java | Splunk | Resultado |
|---|---|---|---|---|
| `nifi1-legacy` | 1.23.2 | 11.0.20 | 9.4 | 6 ok · 2 skip |
| `nifi1-last` | 1.28.1 | 11.0.25 | 10.4 | 7 ok · 1 skip |
| `nifi2-first` | 2.0.0 | 21.0.5 | 10.4 | 7 ok · 1 skip |
| `nifi2-current` | 2.11.0 | 21.0.12 | 10.4 | 7 ok · 1 skip |

Los skips son correctos: `VERSION_INFO` no existe en 1.x, la recolección de `/flow/metrics` todavía no está implementada (TA-2), y en `nifi1-legacy` no hubo errores de los que recuperarse porque el modo sin auth no paga el 401 de bootstrap.

**El resultado que importa: el TA actual, sin una línea de cambio en su lógica de recolección, indexa correctamente desde NiFi 1.23.2, 1.28.1, 2.0.0 y 2.11.0.** Es la confirmación empírica de la decisión de §4.2.

#### 9.1 Qué reveló la primera ejecución real

El harness no funcionó de entrada. Nueve defectos, ninguno visible leyendo el código:

| # | Defecto | Por qué importa |
|---|---|---|
| 1 | El seed instalaba siempre el `inputs.conf` sin auth (`http://nifi:8080`) incluso en un perfil `singleuser`, donde NiFi escucha HTTPS en 8443 | El TA habría consultado un puerto vacío: cero eventos, sin ningún error que lo explicara |
| 2 | El lookup `instance` es una colección **KV store** (`external_type = kvstore`), así que sembrar un CSV en `lookups/` no cargaba nada | El `LOOKUP-instance` de `props.conf` no habría enriquecido, y el agrupamiento por cluster de la app queda vacío |
| 3 | Los healthchecks usaban `curl -sfk`: Splunk y NiFi responden **401** en los endpoints sondeados, y `--fail` convierte eso en exit 22 | Los checks no podían pasar nunca; `up --wait` habría abandonado un stack que funcionaba |
| 4 | `wait_for_nifi.py` mandaba `Accept: application/json`, pero `/access/token` devuelve `text/plain` → **406 Not Acceptable** | El script reintentaba hasta agotar el timeout. `curl` no lo mostró porque no restringe `Accept` |
| 5 | La assertion "sin errores" trataba el 401 de bootstrap como fallo | Falso positivo sobre un comportamiento que es de diseño |
| 6 | `run.sh` sembraba el KV store en cuanto Splunk estaba *healthy*, pero el KV store sigue inicializando → `HTTP 503 KV Store is initializing` | Solo aparece cuando los pasos corren seguidos, que es justo lo que hace el CI. Resuelto con un gate sobre `/services/kvstore/status` |
| 7 | La assertion comparaba errores totales contra eventos totales: lo primero es un one-off del arranque, lo segundo crece con el uptime | Test flaky por construcción: el mismo stack sano pasaba si las assertions corrían tarde y fallaba si corrían temprano |
| 9 | `run.sh` no partía de un estado limpio: correr perfiles en secuencia fallaba en `up --wait` porque el stack anterior todavía se estaba yendo mientras el siguiente reclamaba los mismos puertos publicados | Cada perfil pasaba aislado, lo que lo hacía confuso. Correr la matriz en secuencia es la forma normal de verificarla localmente |
| 8 | **En el TA:** `__get_request` leía la credencial almacenada antes de ramificar por `auth_type`, así que el modo sin auth hacía una llamada inútil a `storage/passwords` por endpoint y por ciclo — y al hacer hablar a `__get_password`, un ERROR por request | 6 errores contra 2 eventos en `nifi1-legacy`. **Los unit tests no podían verlo porque mockean `__get_password`**: es el argumento más claro a favor de tener las dos capas |

**Lo que el run sí demostró**, y era el objetivo:

- El TA **funciona sin cambios contra NiFi 2.11.0 con autenticación**: 28 eventos en `nifi:api:{flow_status,system_diagnostics,site_to_site}`.
- `INDEXED_EXTRACTIONS` produce los campos que el datamodel declara (`controllerStatus.activeThreadCount`, `runningCount`, `flowFilesQueued`).
- El `LOOKUP-instance` enriquece con `cluster` desde el KV store.
- **El fix de B-5 quedó validado en producción real:** exactamente 2 errores, ambos 401 de arranque en frío, y el último evento 6 minutos posterior al último error. Sin ese fix el input se habría quedado atascado en 401 sin indexar nada.
- La autodetección de versión vía `VERSION_INFO` devuelve `NiFi 2.11.0 on Java 21.0.12`.

### F3 — TA multi-versión

- TA-1 … TA-10.
- **Aceptación:** un mismo input configurado contra NiFi 1.23.2, 1.28.1 y 2.11.0 produce eventos en los tres, con autodetección de versión visible en `nifi:api:version_info`; AppInspect sin errores y warnings ≤ el umbral.

### F4 — App visual

- APP-1 … APP-7.
- **Aceptación:** los 6 dashboards devuelven datos en los 4 perfiles de la matriz; ningún panel sobre `index=*`; tiempo del panel más lento medido y registrado antes/después.

### F5 — Flow reconstruido

- FLOW-1 … FLOW-6.
- **Aceptación:** el flow de `nifi-2.x/` importa y corre en 2.11.0 sin componentes inválidos, y el perfil `nifi2-hec` de la matriz pasa.

### F6 — Documentación y release 2.0.0

- DOC-1 … DOC-7.
- Bump coordinado a **2.0.0** en los dos `app.conf`.
- **Aceptación:** `mkdocs build` sin warnings de links; paridad `*.md` / `*.es.md`; release con los dos `.tar.gz` y AppInspect en verde.

**Dependencias:** F1 y F2 son paralelizables y no dependen de F0. F3 depende de F0. F4 depende de F3. F5 es independiente de F3/F4. F6 cierra.

---

## 10. Riesgos y decisiones abiertas

### Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| R-1 | `/flow/metrics/json` con `ALL_COMPONENTS` genera un volumen inmanejable en flujos grandes | medir en F0.3; exponer `flowMetricsReportingStrategy` y `sampleName` como parámetros del input; documentar el impacto en licencia |
| R-2 | El formato de `producer=json` cambia entre 1.16 y 2.11 y obliga a bifurcar el parsing | F0.2 compara las tres muestras antes de diseñar |
| R-3 | Recapturar ~25 screenshots de una UI nueva es más trabajo que el código | tratar DOC-3 como tarea propia con su estimación; considerar reducir el set de imágenes |
| R-4 | Cambiar sourcetypes rompe las búsquedas guardadas de los clientes actuales | 2.0.0 es major; **agregar** sourcetypes sin retirar los viejos en este release, y anunciar la deprecación para 2.1 |
| R-5 | El token de B-1 puede estar activo en un HEC de producción | rotarlo antes de tocar el repo, y verificar en qué instancia estaba |
| R-9 | **Volumen del endpoint de métricas.** Medido: un NiFi **ocioso** ya emite 60 muestras (~14 KB) por poll; con `ALL_COMPONENTS` eso escala con cada procesador del flujo. Un flujo de 500 procesadores puede rondar 1 GB/día solo de métricas | Por eso `endpoint_flow_metrics` viene **apagado** por defecto, el default de estrategia es `ALL_PROCESS_GROUPS` (más acotado que el `ALL_COMPONENTS` de NiFi) y se exponen `metrics_registries` y `metrics_sample_filter`. La doc de instalación debe traer el cálculo antes de recomendar habilitarlo |
| R-7 | **Activar la verificación TLS por defecto (B-23) es un breaking change.** Un input existente contra un NiFi con certificado autofirmado deja de conectar al actualizar | Es deliberado y corresponde a un major. El error dice qué hacer (apuntar `ca_bundle` a un bundle que lo valide, o destildar la verificación aceptando el riesgo). Debe ir en las notas de migración de 2.0.0, y hay que decidir si se acepta el default seguro o se invierte |
| R-8 | El harness prueba el camino con la verificación **desactivada** (`verify_tls = 0`), porque los contenedores usan certificados autofirmados. El camino por defecto, que es el seguro, no está cubierto por ningún perfil | Agregar un perfil que extraiga el certificado del contenedor de NiFi y lo pase como `ca_bundle`, para ejercitar la verificación real |
| R-6 | AppInspect nuevo sube warnings por encima de `MAX_WARNING = 8` y bloquea el release | B-17 baja 2; medir el conteo real en F1 y ajustar el umbral con justificación |

### Decisiones abiertas

| # | Decisión | Opciones |
|---|---|---|
| **D-1** ✅ | Bulletins individuales | **Decidido (c): ambas, con polling por defecto** (Anibal Vasquez, 2026-08-24). Implementado en TA-5. |
| **D-2** | `nifi:api:site_to_site` | (a) retirarlo; (b) construir el panel que hoy falta. **Recomendación: (a)** — se paga ingesta por dato que nadie mira. |
| **D-3** | Piso de NiFi soportado | (a) 1.16 (donde aparece `producer=json`); (b) 1.23 (lo que hoy se prueba); (c) solo 2.x + una 1.x de cortesía. **Recomendación: (a)**, con CI en 1.23.2 y 1.28.1. |
| **D-4** | Aceleración del datamodel | (a) activarla y asumir el costo de almacenamiento; (b) sacar `tstats` de los dashboards. **Recomendación: (a)**, es lo que los paneles ya suponen. |
| **D-5** | ¿1.2.4 de saneamiento antes de 2.0.0? | **Recomendación: sí.** F1 arregla un secreto expuesto y un gate de release roto; no debería esperar al resto del plan. |

---

## Anexo A — Fuentes

- [Apache NiFi — Migration Guidance](https://cwiki.apache.org/confluence/display/NIFI/Migration+Guidance)
- [Apache NiFi — Migrating Deprecated Components and Features for 2.0.0](https://cwiki.apache.org/confluence/spaces/NIFI/pages/240883792/Migrating+Deprecated+Components+and+Features+for+2.0.0)
- [Apache NiFi — Release Notes](https://cwiki.apache.org/confluence/display/NIFI/Release+Notes)
- [Apache NiFi REST API 2.11.0](https://nifi.apache.org/nifi-docs/rest-api.html)
- [NIFI-7273 — Add flow metrics REST endpoint for Prometheus scraping](https://issues.apache.org/jira/browse/NIFI-7273)
- [NIFI-8271 — Expansion of metrics in the REST API Prometheus endpoint](https://issues.apache.org/jira/browse/NIFI-8271)
- [Cloudera — Breaking changes in NiFi 2](https://docs.cloudera.com/cfm/4.10.0/release-notes/topics/cfm-nifi2-breaking-changes.html)
- [Apache NiFi 1.x End-of-Life](https://www.ksolves.com/blog/big-data/nifi/version-1-x-end-of-support)
- [apache/nifi — README (requisitos: Java 21)](https://github.com/apache/nifi/blob/main/README.md)
- [apache/nifi — docker README](https://github.com/apache/nifi/blob/main/nifi-docker/dockerhub/README.md)
- Código fuente de `apache/nifi@main`: `FlowResource.java`, `AccessResource.java`, `FlowMetricsProducer.java`, `FlowMetricsRegistry.java`, `FlowMetricsReportingStrategy.java`
- Tags de [apache/nifi en Docker Hub](https://hub.docker.com/r/apache/nifi/tags)

## Anexo B — Verificaciones ejecutadas para este plan

| Verificación | Método | Resultado |
|---|---|---|
| `GetHTTP` removido en 2.x | `curl` a `raw.githubusercontent.com/apache/nifi/main/…/GetHTTP.java` | HTTP 404 |
| `InvokeHTTP`, `TailFile`, `SplitText` vigentes | idem | HTTP 200 |
| 3× `SiteToSite*ReportingTask` y `MonitorDiskUsage` vigentes | idem | HTTP 200 |
| `POST /access/token` vigente en 2.x | lectura de `AccessResource.java@main` | `@Path("/access")` + `@Path("/token")`, `createAccessToken` presente |
| `producer=json` en 1.x y 2.x | `FlowMetricsProducer.java` en `main`, `support/nifi-1.x`, `support/nifi-1.23`, `support/nifi-1.16` | presente desde 1.16; ausente en 1.15 |
| Registries disponibles | `FlowMetricsRegistry.java` en `main` y `support/nifi-1.23` | 1.x: NIFI, JVM, BULLETIN, CONNECTION, CLUSTER · 2.x: + VERSION_INFO |
| Estrategias de reporte | `FlowMetricsReportingStrategy.java@main` | `ALL_PROCESS_GROUPS`, `ALL_COMPONENTS` |
| Java 21 en 2.x | `pom.xml@main` + README | `maven.compiler.release=21` |
| Endpoints del TA vigentes en 2.11.0 | doc oficial REST API 2.11.0 | los 6 presentes |
| Releases y tags disponibles | `gh api repos/apache/nifi/releases`, Docker Hub API | 2.11.0 (2026-08-03) es la última; 1.28.1 la última 1.x |
| Inventario del flow actual | parseo de `flow_definition/NiFiMonitoring.json` | 39 procesadores, 14 tipos, 6 variables legacy, 0 parameter contexts |

### Contra instancias reales (spike del 2026-08-24)

Contenedores `apache/nifi:1.23.2` (HTTP sin auth, puerto 18080) y `apache/nifi:2.11.0` (HTTPS single-user, puerto 18443), ambos efímeros y con flujo vacío.

| Verificación | Resultado |
|---|---|
| `POST /access/token` en 2.11.0 con `single-user-provider` | ✅ JWT de 462 chars, `sub=admin`, vida 8 h |
| `/flow/status`, `/system-diagnostics`, `/site-to-site`, `/flow/metrics/json`, `/flow/bulletin-board` en 2.11.0 con Bearer | ✅ los 5 responden **200** |
| Formato de `producer=json` | `{samples:[{name, labelNames[], labelValues[], value, …}]}` — arrays paralelos, requiere zip |
| Métricas en NiFi vacío | 1.23.2: 38 únicas / 40 samples / 10.9 KB · 2.11.0: 56 únicas / 17.3 KB |
| Diferencia 1.23.2 → 2.11.0 | +18 métricas, **0 removidas** (superconjunto estricto) |
| Repositorios como métrica | solo 2.x: `nifi_{content,flow_file,provenance}_repo_{free,total,used}_space_bytes` |
| Conteos de `controllerStatus` como métrica | ❌ ninguno en ninguna versión → `/flow/status` es irreemplazable |
| `includedRegistries=VERSION_INFO` en 1.23.2 | **HTTP 404** (no respuesta vacía) |
| `nifi_version_info` en 2.11.0 | `framework_version=2.11.0`, `java_version=21.0.12`, `build_tag=rel/nifi-2.11.0` |
| Filtros del endpoint | `includedRegistries` y `sampleName` (regex) reducen efectivamente: `JVM`→1.9 KB, `NIFI`→7.5 KB |
| Contenedor 2.x sin `NIFI_WEB_PROXY_HOST` | **HTTP 421 Misdirected Request** en todo el API |
| `logback.xml`: appenders y nombres de archivo 1.23.2 vs 2.11.0 | **idénticos** (APP, USER, REQUEST, BOOTSTRAP, DEPRECATION) |
| Patrón de línea de log en ambas | `%date %level [%thread] %logger{40} %msg%n` — idéntico |
| `TIME_FORMAT` y `EXTRACT-level` del TA contra `nifi-app.log` de 2.11.0 | ✅ parsean sin cambios las 297 líneas con timestamp |
| Líneas de continuación en `nifi-app.log` de 2.11.0 (arranque limpio) | **1014 de 1311 (77%)** sin timestamp → base del defecto B-20 |
| Archivos de log presentes en 2.11.0 | `nifi-{app,user,request,bootstrap,deprecation}.log`; el TA solo cubre 3 de 5 |
| Ruta real de logs en la imagen oficial | `/opt/nifi/nifi-current/logs/` (el TA monitorea `/opt/nifi/logs/`) |

Muestras versionadas en `docs/plans/samples/`: `nifi{1.23,2.11}-{metrics-all,flow-status,system-diagnostics}.json`.

> Sigue pendiente: medición con un flujo no trivial (F0.3), importación del flow actual en 2.11.0 (F0.5) y prueba end-to-end TA→Splunk (F0.8/F2).
