# Overview

Inside Splunk, the app's own menu is:

- Home
- Nifi Monitor Overview
- Nifi Instance Panels
    - Flow's & Metrics Monitoring Panel
    - Bulletin Monitoring Panel
    - Logs Monitoring Panel
    - Status History
- Configuration
    - NiFi Instances
    - Internal Monitoring
- Alerts
- Search

## Home

A diagram of where the app's data comes from.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

## Nifi Monitor Overview

A summary across every monitored NiFi instance:

- Server status by node
- Repository status by node
- Bulletin error behavior by node

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview.png)

## Nifi Instance Panels

Per-node detail.

### Flow's & Metrics Monitoring Panel

Node performance and resource usage over time, with scale selectors for
different data volumes and per-node JVM metrics.

![image](/nifi-monitoring-splunk/assets/images/splunk/monitoring_panel.png)
![image](/nifi-monitoring-splunk/assets/images/splunk/behaviour_overtime_1.png)
![image](/nifi-monitoring-splunk/assets/images/splunk/behaviour_overtime_2.png)

### Bulletin Monitoring Panel

Bulletin errors raised by NiFi components, for traceability when something
breaks.

![image](/nifi-monitoring-splunk/assets/images/splunk/bulletin_panel.png)

### Logs Monitoring Panel

NiFi's application, bootstrap, user and request logs from every configured
instance, searchable without opening a terminal on each host.

![image](/nifi-monitoring-splunk/assets/images/splunk/logs_panel.png)

### Status History

Status history of the processors and process groups configured under
[Status history](configuration-pull.md#4-status-history) — throughput, queued
flow files and NiFi's other Status History counters, per instance over
time.

## Configuration

### NiFi Instances

Opens the [Instance Lookup](configuration.md#instance-lookup): every
monitored instance or cluster needs a row here before its data shows in
the panels above.

### Internal Monitoring

Labeled **Nifi TA Monitoring**. Reports on the add-on, not NiFi: event
counts per sourcetype and index — check here first when a panel is empty,
or when [upgrading](upgrading.md) requires changing `index_nifi` — plus,
on a cluster, member roles and per-node heap.
