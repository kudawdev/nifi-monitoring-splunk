# Sourcetypes

The different sourcetypes used by the application provide a corresponding type of information. Most come from the TA's modular input polling the NiFi REST API (the **pull** path); on the **push** path the flow inside NiFi sends the same `nifi:api:*` sourcetypes to Splunk's HEC, plus `nifi:reporting:task` and `nifi:reporting:bulletin` from NiFi's own reporting tasks — see [Compatibility and collection strategy](compatibility.md#choosing-a-collection-strategy).

### Logs

Read from NiFi's log files by a Universal Forwarder, with the monitors the TA ships disabled. The push flow also sends the app, bootstrap and user logs, but not the request or deprecation logs.

- **nifi:log:app** / **nifi:log:bootstrap**

The record of NiFi's own activity — file uploads, execution times, bulletins raised by components — from `nifi-app.log` and `nifi-bootstrap.log`.

- **nifi:log:user**

The record of web activity where users interact with NiFi and the actions they carry out (`nifi-user.log`).

- **nifi:log:request**

NiFi's request log (`nifi-request.log`), in the same NCSA combined format as Splunk's own `access_combined`. As with the other logs, each event's time is the one written in the line — here, the request time.

- **nifi:log:deprecation**

Names the deprecated components an instance still uses (`nifi-deprecation.log`); the input for migration reporting when moving between NiFi versions.

### REST API (pull)

- **nifi:api:flow_status**

Basic information on the status and processing of the NiFi instance, from `/flow/status`.

- **nifi:api:system_diagnostics**

System resources in use and available, from `/system-diagnostics`. On a cluster this is the aggregate across all nodes.

- **nifi:api:node_diagnostics**

Per-node system diagnostics on a cluster, one event per member, from `/system-diagnostics?nodewise=true`.

- **nifi:api:cluster_nodes**

One event per cluster member from `/controller/cluster`: status, roles (Primary Node / Cluster Coordinator), heartbeat and the node's own queue and thread counts. Only populated on a cluster.

- **nifi:api:process_groups_status**

Status history of the monitored process groups, from `/flow/process-groups/{id}/status/history`: one flat event per snapshot (one a minute, by default), stamped with the snapshot's own time, with the group's id and name and each metric as a field. The input resumes from the newest snapshot it wrote, so a snapshot is indexed once; a group configured for the first time brings only its latest hour.

- **nifi:api:processors_status**

The same for the monitored processors, from `/flow/processors/{id}/status/history`.

- **nifi:api:process_groups_history**, **nifi:api:processors_history**

The nested status history as the push flow sends it: the whole response in one event. The TA no longer writes these; the `Component_Status` dataset reads both shapes.

- **nifi:api:flow_metrics**

Prometheus-style metric samples, from `/flow/metrics/json`. Requires NiFi 1.16 or later and is off by default for volume reasons.

- **nifi:api:bulletin_board**

Bulletins — errors and warnings raised by components — from `/flow/bulletin-board`, mapped onto the same field names as `nifi:reporting:bulletin` so both sources feed the same dashboards.

- **nifi:api:version_info**

A record of the polled instance's NiFi, Java and operating system versions and build, written whenever `/system-diagnostics` is polled. The TA itself reads the version from `/system-diagnostics` to choose its endpoints.

### Reporting tasks (push)

- **nifi:reporting:task**

Internal reports of status and metrics at a more detailed level than flow status, sent by NiFi's `SiteToSiteMetricsReportingTask`.

- **nifi:reporting:bulletin**

Internal bulletins where errors during operation are specified, sent by NiFi's `SiteToSiteBulletinReportingTask`.

## Datamodel

The `NIFI` datamodel groups the sourcetypes by concept, so a panel does not need to know which collection path an event came by:

| Dataset | What it holds | Fed by |
|---|---|---|
| `Bulletins` | Every bulletin; children `Bulletin_Board` (pull) and `Reporting_Bulletin` (push) | `nifi:api:bulletin_board`, `nifi:reporting:bulletin` |
| `Throughput` | Data in, out and written by the whole flow, as `bytes_in`, `bytes_out`, `bytes_written`, `flowfiles_in`, `flowfiles_out`; children `Reporting_Task` (push) and `Flow_Metrics_Root` (pull) | `nifi:reporting:task`, the root group's `nifi:api:flow_metrics` |
| `Component_Status` | One row per component status snapshot, as `component_label`, `component_kind` and the metrics in the `nifi_status_metrics` lookup; children `Processors` and `Process_Groups` | `nifi:api:*_status`, and the push flow's `nifi:api:*_history` |
| `Flow_Status`, `System_Diagnostics`, `Node_Diagnostics`, `Cluster_Nodes`, `Flow_Metrics`, `Version_Info`, `Request_Log` | One sourcetype each | as named |
| `Logs` | The app, bootstrap, user and deprecation logs, with `level` | `nifi:log:*` except `nifi:log:request` |

## Thresholds

Every view and every alert reads the same thresholds, at two levels:

1. **Per instance**, in the instance's row of the inventory (*Configuration > NiFi Instances*). An empty column means the macro applies.
2. **For every instance**, in the macros. Override them in `local/macros.conf` of `nifi_monitoring`.

| Inventory column | Macro | Default | Meaning |
|---|---|---|---|
| `heap_threshold` / `heap_threshold_critical` | `nifi_threshold_heap` / `nifi_threshold_heap_critical` | 85 / 95 | % of max heap that makes an instance degraded / critical |
| `repo_threshold` / `repo_threshold_critical` | `nifi_threshold_repo` / `nifi_threshold_repo_critical` | 80 / 90 | % of a repository's volume |
| `backpressure_threshold` | `nifi_threshold_backpressure` | 80 | % of a connection's object or size limit |
| `bulletin_threshold` | `nifi_threshold_bulletins` | 5 | ERROR bulletins in `nifi_recent_window` that fire the bulletin alert |

These apply to every instance and have no inventory column:

| Macro | Default | Meaning |
|---|---|---|
| `nifi_threshold_bulletins_degraded` | 1 | ERROR bulletins in `nifi_recent_window` that make an instance degraded; raise it for a NiFi whose flows log errors routinely |
| `nifi_recent_window` | `-15m` | What "now" means for health and bulletin counts |
| `nifi_backpressure_horizon` | 3600 | Seconds ahead NiFi's backpressure prediction counts as imminent |
| `nifi_heap_sustained_samples` | 3 | Consecutive samples over the heap threshold the sustained-heap alert waits for |
| `nifi_stale_factor` | 3 | Polling intervals without data that make an instance stale |
| `nifi_default_interval` | 60 | Seconds between polls, when the input's own interval cannot be read |

`nifi_fleet` builds one row per instance with the thresholds that apply to it, and `nifi_health` turns that row into `ok`, `degraded`, `critical`, `stale` or `no_data` with a reason. The heap and repository numbers on the Overview are coloured by the threshold of the instance they belong to.
