# Splunkbase 2.0.0 — material de publicación

Lo que lleva cada ficha de Splunkbase para la 2.0.0: los textos de cada campo,
listos para pegar, y las capturas, una carpeta por app. El prefijo numérico de
las capturas es el orden de subida: la primera es la portada de la ficha.

Todo sale de la doc pública (`doc/`); si cambia algo allí, revisar aquí.

- [Nifi Monitoring for Splunk (6125)](#nifi-monitoring-for-splunk--app-6125)
- [Nifi Monitoring TA (6124)](#nifi-monitoring-ta--app-6124)
- [Contact notes — las dos apps](#contact-notes--las-dos-apps)
- [Además de los textos](#además-de-los-textos)

---

## Nifi Monitoring for Splunk — app 6125

https://splunkbase.splunk.com/app/6125

### Capturas

Reemplazan **todas** las de la 1.2.3: eran de 2021 (Simple XML, menús que ya
no existen) y tres mostraban el host `nifi01.entelbd.local`, de un cliente.

| Archivo | Origen (`doc/assets/images/splunk/`) | Nota |
|---|---|---|
| `nifi_monitoring/01_overview.png` | `view_overview.png` | Portada |
| `nifi_monitoring/02_instance.png` | `view_instance.png` | Recortada a 1600×1080: estado, "Now" y "JVM and system" |
| `nifi_monitoring/03_components.png` | `view_components.png` | |
| `nifi_monitoring/04_bulletins.png` | `view_bulletins.png` | |
| `nifi_monitoring/05_cluster.png` | `view_cluster.png` | |
| `nifi_monitoring/06_logs.png` | `view_logs.png` | |
| `nifi_monitoring/07_alerts.png` | `view_alerts.png` | Recortada a 1600×875: sin el panel "Fired" vacío |

### Summary

```text
Nifi Monitoring centralizes, in Splunk, the operational visibility of your Apache NiFi instances — a single one, several independent ones, or a cluster — so you no longer have to open each NiFi UI to know whether it is healthy.

What you get:

* Overview: the whole fleet at a glance — healthy instances, ERROR bulletins, worst heap and repository, queued FlowFiles.
* Instance: heap, threads, load, GC, repository usage and throughput for one NiFi.
* Components: which processor, group or connection is the bottleneck, including connections near backpressure.
* Bulletins: NiFi's errors and warnings, traceable to the component that raised them.
* Logs (optional, via a Universal Forwarder): app, user, request and deprecation logs — including what to clear before moving to NiFi 2.x.
* Cluster: connected nodes, primary and coordinator, heap and queues per node.
* Alerts: 8 ready-made alerts (backpressure, disconnected node, ERROR spike, stale instance, repository filling up, sustained high heap, TA HTTP errors, versioned flow sync failure), with per-instance thresholds.
* Collection Health: whether data collection itself is working.

Data reaches Splunk by polling NiFi's REST API with the Nifi Monitoring TA (pull, recommended), or from a flow inside NiFi that sends to Splunk's HEC (push, for when Splunk cannot reach NiFi).

Compatibility:

* Splunk Enterprise / Splunk Cloud 9.4 – 10.x
* Apache NiFi 1.16 – 1.28.1 and 2.0 – 2.11

Requirements:

* Nifi Monitoring TA — https://splunkbase.splunk.com/app/6124
* Lookup File Editor — https://splunkbase.splunk.com/app/1724

Upgrading from 1.x? Status Indicator is no longer needed, and the upgrade guide covers what changed: https://kudawdev.github.io/nifi-monitoring-splunk/upgrading/

Documentation: https://kudawdev.github.io/nifi-monitoring-splunk/
Source and issues: https://github.com/kudawdev/nifi-monitoring-splunk
```

### Short description

```text
Monitor all your Apache NiFi instances and clusters from Splunk: flow status, heap and repositories, bulletins, logs and ready-made alerts. Supports NiFi 1.16–1.28 and 2.x.
```

Si el campo admite menos caracteres:

```text
Monitor every Apache NiFi instance and cluster from Splunk: health, bulletins, logs and alerts. NiFi 1.x and 2.x.
```

### Details

```text
Nifi Monitoring gives you, in Splunk, a single place to watch every Apache NiFi you run — one instance, several independent ones, or a cluster — from the whole fleet down to a single connection.

DASHBOARDS

* Overview — Is the fleet healthy right now? Healthy instances, ERROR bulletins, worst heap and repository, queued FlowFiles, and one row per instance sorted by severity.
* Instance — What is happening on this instance? Components, versioned process groups, heap, threads, load average, GC time, repository usage and throughput.
* Components — Which processor, group or connection is the bottleneck? Top 10 by the metric you pick, with trends, plus connections over or close to backpressure.
* Bulletins — What errors is NiFi reporting? By level, by component, with the full message.
* Logs — NiFi's application log, deprecations (what to clear before moving to NiFi 2.x) and API requests. Needs a Universal Forwarder on the NiFi host.
* Cluster — Is the cluster whole? Connected nodes, primary and coordinator, heap and queues per node.
* Alerts — 8 alerts shipped with the app: backpressure, cluster node disconnected, ERROR bulletin spike, instance without data, repository filling up, sustained high heap, TA HTTP errors and versioned flow sync failure. Thresholds can be set per instance.
* Collection Health — Is data collection working? Last data per instance and source, and TA HTTP errors.

HOW DATA GETS IN

Pick one per NiFi instance:

* Pull (recommended): the Nifi Monitoring TA polls NiFi's REST API on an interval. Works with NiFi unauthenticated or with username and password, over HTTP or HTTPS with certificate verification. Nothing runs inside NiFi.
* Push: a flow imported into NiFi calls NiFi's own API and sends the results to Splunk's HTTP Event Collector (HEC). Use it only when Splunk cannot reach NiFi; it requires a NiFi without authentication.

GETTING STARTED (PULL)

1. Install the Nifi Monitoring TA, then this app, then Lookup File Editor.
2. In the TA, go to Inputs > Create New Input: one input per NiFi instance (a cluster is one input, pointed at any node). Use Test connection to check it.
3. Under Advanced, set Index to "nifi". The app ships that index and every dashboard reads from it; leaving the default breaks every panel.
4. In this app, open Configuration > NiFi Instances and add each instance with its cluster and, optionally, its own thresholds.
5. Open Overview: each instance should show its NiFi version and recent data. If not, Configuration > Collection Health tells you which source is missing.

Optional: collect NiFi's log files with a Universal Forwarder, and accelerate the NIFI datamodel for faster panels.

Full step-by-step guide, push setup and data reference:
https://kudawdev.github.io/nifi-monitoring-splunk/

UPGRADING FROM 1.x

The dashboards are now Dashboard Studio, Status Indicator is no longer needed, and the app reads only from index=nifi. Read the upgrade guide before installing over 1.x:
https://kudawdev.github.io/nifi-monitoring-splunk/upgrading/

COLLABORATE

Source code, issues and contributions:
https://github.com/kudawdev/nifi-monitoring-splunk

Developed and supported by Küdaw.
```

### Installation

```text
REQUIREMENTS

* Splunk Enterprise or Splunk Cloud 9.4 – 10.x
* Apache NiFi 1.16 – 1.28.1 or 2.0 – 2.11
* Nifi Monitoring TA — https://splunkbase.splunk.com/app/6124
* Lookup File Editor — https://splunkbase.splunk.com/app/1724

INSTALL

Install the three apps in this order, from Apps > Manage Apps > Install app from file (or Browse more apps):

1. Nifi Monitoring TA — parses and indexes NiFi's data. Install it first: the dashboards have nothing to read without it.
2. Nifi Monitoring (this app) — dashboards, alerts, lookups and the "nifi" index.
3. Lookup File Editor — used by Configuration > NiFi Instances to edit the instance inventory.

Restart Splunk if prompted.

WHERE TO INSTALL (DISTRIBUTED DEPLOYMENTS)

* Search head: Nifi Monitoring, Nifi Monitoring TA and Lookup File Editor.
* Where the pull inputs run: Nifi Monitoring TA, with network access to NiFi's REST API. Use a heavy forwarder or a standalone search head, not a search head cluster: every member would run every input and index the data more than once.
* Indexers: the "nifi" index (deploy the app's indexes.conf); also the TA if a Universal Forwarder sends NiFi's logs.
* NiFi hosts (optional, for log files): a Universal Forwarder with the same Nifi Monitoring TA package.
* Splunk Cloud: check that the "nifi" index exists (Settings > Indexes) and create it if it does not.

CONFIGURE (PULL, RECOMMENDED)

1. Open the Nifi Monitoring TA > Inputs > Create New Input. Create one input per NiFi instance; a cluster is one input, pointed at any node.
2. Fill in the instance name, the NiFi API URL (e.g. https://<host>:8443/nifi-api/) and the authentication (None, or Username and password). Click Test connection.
3. For a self-signed certificate, keep TLS verification on and set the CA bundle path.
4. Under Advanced, set Index to "nifi". Every dashboard reads from it; leaving the default breaks every panel. On a cluster, also set Host field value to the cluster's name.
5. In Nifi Monitoring, open Configuration > NiFi Instances and add one row per instance: host (the input name, or the cluster name), its cluster and, optionally, its own thresholds.
6. Open Overview. Each instance should show its NiFi version and data from the last minute. If not, Configuration > Collection Health tells you which source is missing.

For push (NiFi sends to Splunk's HEC, when Splunk cannot reach NiFi), log collection with a Universal Forwarder, and datamodel acceleration, follow the guide:
https://kudawdev.github.io/nifi-monitoring-splunk/installation/

UPGRADING FROM 1.x

Read the upgrade guide before installing over 1.x. The app now reads only from index=nifi (it used index=*), TLS certificates are verified by default, and Status Indicator is no longer needed:
https://kudawdev.github.io/nifi-monitoring-splunk/upgrading/
```

### Troubleshooting

```text
Start at Configuration > Collection Health: it says whether the app sees any data, which instance or source is late or missing, and which index actually holds the NiFi data.

EVERY DASHBOARD IS EMPTY

* "Events the app can see" is 0: the data is not where the index_nifi macro looks (index=nifi by default). Either set the TA input's Index to "nifi", or point the macro at your index in nifi_monitoring/local/macros.conf:
    [index_nifi]
    definition = index=your_index
  "Where NiFi data is" on the same view shows which index holds it.
* On a distributed deployment, the "nifi" index has to exist on the indexers too, not only on the search head.
* Upgrading from 1.x: the macro used to be index=*, so data that worked before may now be outside index=nifi.

AN INSTANCE SHOWS "NO DATA" OR "STALE"

* Check that its TA input is enabled and look at "TA HTTP errors by status code" on Collection Health:
  - Login failure: wrong username or password.
  - 403: the NiFi user lacks permissions.
  - 404: a wrong component id in the Status History fields.
  - 5xx: a problem on NiFi's side.
* Certificate errors over HTTPS: keep TLS verification on and point the CA bundle path at NiFi's certificate. The guide shows how to get it.
* The host in Configuration > NiFi Instances must match the host the events carry: the input name, or its Host field value. Find it with:
    index=* sourcetype=nifi* | dedup host | table host
* On a cluster, set the input's Host field value to the cluster's name, the same host as its row in the inventory.

DUPLICATED DATA

* Use pull or push for each NiFi instance, never both.
* Do not run the pull inputs on a search head cluster: every member runs every input.

SOME PANELS ARE EMPTY

* Throughput, backpressure and busiest connections need Flow metrics enabled on the instance's TA input (off by default for volume).
* Logs needs a Universal Forwarder on the NiFi host with the TA's log monitors enabled.
* Cluster stays empty on a standalone NiFi, and on the push strategy.
* Components with history only covers the processor and process group ids set on the TA input.

ALERTS DO NOT FIRE

* The alerts ship disabled. Enable them in Settings > Searches, reports, and alerts (app nifi_monitoring), and set their recipients. Thresholds are the nifi_threshold_* macros, or per instance in the inventory.

PUSH: THE FLOW GETS 401 FROM NIFI

* The push flow calls NiFi's API without credentials, so it only works on a NiFi without authentication. Use pull instead.

More detail: https://kudawdev.github.io/nifi-monitoring-splunk/
Report an issue: https://github.com/kudawdev/nifi-monitoring-splunk/issues
```

### Release notes

```text
2.0.0 — NiFi 2.x support and rebuilt dashboards

Read the upgrade guide before installing over 1.x: https://kudawdev.github.io/nifi-monitoring-splunk/upgrading/

BREAKING CHANGES

* Splunk 9.4 is the minimum (Dashboard Studio features verified on 9.4 and 10.4).
* The dashboards were rebuilt in Dashboard Studio, and several views were renamed or merged: bookmarks to home, nifi_instances_detail, nifi_status_history, nifi_bulletin and nifi_internal_monitoring stop working.
* The index_nifi macro is now index=nifi instead of index=*, and the app ships that index. If your NiFi data lives elsewhere, override the macro in local/macros.conf; Configuration > Collection Health shows where the data is.
* NIFI datamodel: Reporting_Bulletin and Reporting_Task are now children of Bulletins and Throughput, and Status_History became Component_Status. Your own tstats searches on those datasets may need a change.
* Datamodel acceleration ships off. Turn it on for faster panels.
* Status Indicator is no longer a dependency.

NEW

* Eight views: Overview, Instance, Components, Bulletins, Logs, Cluster, Alerts and Collection Health.
* Eight alerts, shipped disabled: instance without data, repository filling up, sustained high heap, ERROR bulletin spike, backpressure, cluster node disconnected, versioned flow sync failure and add-on HTTP errors.
* Per-instance thresholds in the instance inventory (Configuration > NiFi Instances), shared by panels and alerts.
* One definition of health that respects each input's polling interval.
* NiFi 2.x support, clusters shown as one instance with named nodes, and several independent instances.
* Components view: the bottleneck processor, group or connection, with NiFi's own backpressure prediction.
* Logs view: application, deprecation and API request logs.

FIXES

* On a cluster, events from the push flow carry the instance's name instead of whichever node sent them, so the Overview no longer reports the cluster down and Bulletins is no longer empty. Set instance_name in the flow.

Requires Nifi Monitoring TA 2.0.0. Full notes: https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/CHANGELOG.md
```

---

## Nifi Monitoring TA — app 6124

https://splunkbase.splunk.com/app/6124

### Capturas

Reemplazan las de la 1.2.3: eran dos imágenes subidas dos veces cada una, del
formulario viejo de *Settings › Data inputs*.

| Archivo | Origen (`doc/assets/images/splunk/`) | Nota |
|---|---|---|
| `nifi_TA_monitoring/01_input_form.png` | `ta_input_form.png` | Portada |
| `nifi_TA_monitoring/02_inputs_created.png` | `ta_inputs_created.png` | |
| `nifi_TA_monitoring/03_collection_health.png` | `view_collection_health.png` | Vista de la app; responde "¿la recolección funciona?" |

### Summary

```text
The Nifi Monitoring TA gets Apache NiFi's data into Splunk and normalizes it for the Nifi Monitoring app (https://splunkbase.splunk.com/app/6125), which depends on it.

* A modular input polls NiFi's REST API — flow status, system diagnostics, bulletins, processor and process group status history, and optionally flow metrics — one input per NiFi instance or cluster.
* Authentication: none, or username and password (NiFi's token is kept in Splunk's credential store). TLS certificates are verified, with an optional CA bundle.
* Clusters are detected automatically, with per-node data.
* Parsing for NiFi's log files (app, bootstrap, user, request, deprecation) sent by a Universal Forwarder.
* Also parses the data sent by the NiFi flow (push), for when Splunk cannot reach NiFi.

Compatibility: Splunk Enterprise / Splunk Cloud 9.4 – 10.x; Apache NiFi 1.16 – 1.28.1 and 2.0 – 2.11.

Documentation: https://kudawdev.github.io/nifi-monitoring-splunk/
Source and issues: https://github.com/kudawdev/nifi-monitoring-splunk
```

### Short description

```text
Collects Apache NiFi status, diagnostics, bulletins and metrics through its REST API, and parses NiFi's logs, for the Nifi Monitoring app. NiFi 1.16–1.28 and 2.x.
```

### Details

```text
INPUT FORM

Inputs > Create New Input. One input per NiFi instance; a cluster is one input, pointed at any node.

* NiFi instance name and NiFi API URL (e.g. https://<host>:8443/nifi-api/).
* Authentication: None, or Username and password. Test connection checks it without saving.
* Endpoints: flow status, system diagnostics and bulletin board on by default; flow metrics (NiFi 1.16 or later) off by default for volume.
* Status History: the processor and process group ids whose history to collect.
* Custom endpoints: any other NiFi REST endpoint, as name,path, indexed as nifi:api:custom:<name>.
* TLS: certificate verification on by default, with an optional CA bundle path.
* Advanced: interval (60 s), index ("nifi" for the Nifi Monitoring app) and host field value (on a cluster, the cluster's name).

Configuration > Logging sets how much the add-on writes to splunkd.log.

SOURCETYPES

* nifi:api:* — data from NiFi's REST API.
* nifi:log:app, nifi:log:bootstrap, nifi:log:user, nifi:log:request, nifi:log:deprecation — NiFi's log files, through a Universal Forwarder.

Field reference: https://kudawdev.github.io/nifi-monitoring-splunk/references/
Input reference: https://kudawdev.github.io/nifi-monitoring-splunk/configuration-pull/
```

### Installation

```text
Install from Apps > Manage Apps > Install app from file, before the Nifi Monitoring app.

Where it goes on a distributed deployment:

* Search head: for search-time fields.
* Where the pull inputs run (heavy forwarder or standalone search head, not a search head cluster): it parses the API data there. That instance needs to reach NiFi's REST API.
* Indexers: only if a Universal Forwarder sends NiFi's logs; the log sourcetypes are parsed where they first arrive.
* NiFi hosts (optional): a Universal Forwarder with this same package, with the log monitors you need enabled in local/inputs.conf.

Then create one input per NiFi instance, with Index set to "nifi". Step-by-step guide:
https://kudawdev.github.io/nifi-monitoring-splunk/config-nifi-monitoring-2-0/

Upgrading from 1.x: existing inputs keep working; TLS certificates are now verified by default. See https://kudawdev.github.io/nifi-monitoring-splunk/upgrading/
```

### Release notes

```text
2.0.0 — NiFi 2.x support and a new configuration screen

Read the upgrade guide before installing over 1.x: https://kudawdev.github.io/nifi-monitoring-splunk/upgrading/

BREAKING CHANGES

* Splunk 9.4 is the minimum.
* TLS certificates are verified by default. Over HTTPS, set a CA bundle path, or turn verification off deliberately.
* Status history has new sourcetypes: nifi:api:processors_status and nifi:api:process_groups_status, one event per snapshot. nifi:api:*_history remains for the push path only.
* nifi:api:site_to_site and nifi:api:controller_cluster are no longer collected.
* Passwords are stored per input. A 1.x input keeps working, with a warning, until it is opened and saved again.
* The add-on now appears in the app menu, with its own configuration screen.

NEW

* NiFi 2.x support from the same input: the add-on detects the NiFi version per input and adapts.
* A configuration screen built with UCC: grouped form with validation, a Test connection button, and a Logging tab.
* Clusters detected automatically, with per-node diagnostics and bulletins that name their node.
* Custom endpoints: any NiFi REST path, indexed as nifi:api:custom:<name>.
* Flow metrics from /flow/metrics/json (NiFi 1.16 or later), off by default.
* Bulletins polled from the bulletin board with a cursor, without a reporting task.
* nifi:log:deprecation and nifi:log:request monitors for the Universal Forwarder.

FIXES

* The add-on logs in before its first request instead of a 401 per endpoint on every cold start.
* A failing custom endpoint writes no event; error bodies used to be indexed as data.
* The token and the bulletin cursor no longer live in a file inside the app, which was lost on reinstall and could be overwritten between two inputs.
* An input with no Host sends its events under the input's name instead of $decideOnStartup.

Full notes: https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/CHANGELOG.md
```

### Troubleshooting

```text
* No events from an input: check that it is enabled and look in splunkd.log (index=_internal). A request NiFi rejects indexes nothing: the error goes to the log, not to the index.
* Login failure: wrong username or password. 403: the NiFi user lacks permissions. 404: a wrong id in Status History. 5xx: a problem on NiFi's side.
* Certificate errors: keep verification on and point the CA bundle path at NiFi's certificate (the guide shows how to get it).
* Events in the wrong index: set the input's Index to "nifi", or override the index_nifi macro in the Nifi Monitoring app.
* Duplicated events: one input per instance or cluster, and pull or push per instance, never both. Do not run inputs on a search head cluster.
* Logs not arriving: check the monitor paths in the forwarder's local/inputs.conf against where NiFi writes its logs, and that the indexer receives on 9997.

Nifi Monitoring's Configuration > Collection Health view shows all of this per instance and source.

Report an issue: https://github.com/kudawdev/nifi-monitoring-splunk/issues
```

---

## Contact notes — las dos apps

El mismo texto en ambas fichas. Sale de `doc/about.md`: los bugs y pedidos
van a issues, donde todos los siguen; el correo, para lo demás.

```text
Bugs and feature requests: open a GitHub issue, where everyone can follow it.
https://github.com/kudawdev/nifi-monitoring-splunk/issues

Evaluation, deployment, help running the apps, or professional services for NiFi, data and AI projects: splunk.app@kudaw.com

Anything else: https://www.kudaw.com/contacto
LinkedIn: https://www.linkedin.com/company/kudaw-latam
```

---

## Además de los textos

- **Compatibilidad**: ambas fichas declaran plataformas 10.2–10.6; debe
  coincidir con `doc/compatibility.md` (Splunk 9.4–10.x).
- **Formato**: si los campos no interpretan las viñetas con `*`, usar guiones
  o un ítem por línea. Si admiten Markdown, los títulos en mayúsculas pueden
  pasar a `##`.
