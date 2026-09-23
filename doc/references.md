# Sourcetypes

The different sourcetypes used by the application provide a corresponding type of information. Most come from the TA's modular input polling the NiFi REST API (the **pull** path); `nifi:reporting:task` and `nifi:reporting:bulletin` come from NiFi's own reporting tasks pushing to Splunk's HEC (the **push** path) — see [Configuration](configuration.md).

### Logs

- **nifi:log:app** / **nifi:log:bootstrap**

The record of NiFi's own activity — file uploads, execution times, bulletins raised by components — from `nifi-app.log` and `nifi-bootstrap.log`.

- **nifi:log:user**

The record of web activity where users interact with NiFi and the actions they carry out (`nifi-user.log`).

- **nifi:log:request**

NiFi's request log (`nifi-request.log`), in the same NCSA combined format as Splunk's own `access_combined`. Unlike the other logs, each event carries its own timestamp — the request time, not the collection time.

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

- **nifi:api:process_groups_history**

Historical status of the monitored process groups, from `/flow/process-groups/{id}/status/history`.

- **nifi:api:processors_history**

Historical status of the monitored processors, from `/flow/processors/{id}/status/history`.

- **nifi:api:flow_metrics**

Prometheus-style metric samples, from `/flow/metrics/json`. Requires NiFi 1.16 or later and is off by default for volume reasons.

- **nifi:api:bulletin_board**

Bulletins — errors and warnings raised by components — from `/flow/bulletin-board`, mapped onto the same field names as `nifi:reporting:bulletin` so both sources feed the same dashboards.

- **nifi:api:version_info**

The polled NiFi instance's version, used to gate version-dependent endpoints and fields.

### Reporting tasks (push)

- **nifi:reporting:task**

Internal reports of status and metrics at a more detailed level than flow status, sent by NiFi's `SiteToSiteMetricsReportingTask`.

- **nifi:reporting:bulletin**

Internal bulletins where errors during operation are specified, sent by NiFi's `SiteToSiteBulletinReportingTask`.
