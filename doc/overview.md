# Overview

Inside Splunk, the app's own menu is:

- Overview
- Instance
- Components
- Bulletins
- Logs
- Cluster
- Alerts
- Configuration
    - NiFi Instances
    - Collection Health
- Search

The views go from the fleet to a single component: **Overview** says which
instance needs attention, **Instance** says what is wrong with it, and
**Components** says which processor or connection is the cause. Every
drilldown keeps the instance and the time range you were looking at.

They work the same whichever way the data arrives — the TA polling NiFi
(pull) or the flow inside NiFi sending to the HEC (push). A panel that
needs a source you have not enabled says which one in its description.

## Overview

The landing page: is the fleet healthy right now? Six figures, then one row
per instance that is in the [inventory](instance-lookup.md) or has sent data,
worst first.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_overview.png)

- **Healthy instances**, **ERROR bulletins** in the last 15 minutes,
  **Worst heap**, **Worst repository**, **FlowFiles queued** and **Invalid
  components**. Heap and repository name the instance they belong to and
  are coloured by that instance's own [threshold](references.md#thresholds).
- **Instances**: each row has a health state and the reason for it —
  *Critical*, *Degraded*, *Stale* (no data for longer than its polling
  interval allows), *No data* or *Healthy*. An instance listed in the
  inventory that has never sent anything still gets its row; one that sends
  data but is not listed gets its row too, with cluster "—". Click a row
  to open it in **Instance**.
- Bulletins by level and FlowFiles queued per instance, over the selected
  time range.

## Instance

What is happening on one instance. It opens on the worst one of the
Overview list, and the selector at the top switches to another.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_instance.png)

- **Status**: health and its reason, NiFi and Java versions, uptime and
  when the last data arrived.
- **Now**: active threads, what is queued, components running, stopped,
  invalid and disabled, versioned process groups, and recent ERROR
  bulletins.
- **JVM and system**: heap (with this instance's threshold as a dashed
  line), threads, load average against the available cores, and time spent
  in each garbage collector.
- **Storage**: one row per repository — content and provenance can be
  several — and their use over time.
- **Throughput**: data and FlowFiles in, out and written by the whole
  flow. On the pull path it needs *Flow metrics* enabled on the TA input;
  on the push path it comes from the Reporting Task.
- **Recent bulletins**, with a link to **Bulletins** filtered to this
  instance.

## Components

Which processor, process group or connection is the bottleneck.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_components.png)

- Connections over their backpressure threshold, and those NiFi predicts
  will reach it soon.
- **Top 10** components by the metric you pick — task time, FlowFiles in
  and out, bytes read and written, and so on — with a trend line. Click one
  to plot it below.
- **Busiest connections**: how full each one is, by object count and by
  size, and NiFi's own estimate of the time left before backpressure.

The components listed are the ones whose status history is collected: the
processor and process group ids set on the TA input
([Status history](configuration-pull.md#4-status-history)), or in the push
flow's `processors_list` and `process_groups_list`. Connections need *Flow
metrics* on the TA input.

## Bulletins

The errors and warnings NiFi components raise, from either collection
path.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_bulletins.png)

Filter by instance, level, category or component. The detail table shows
each message whole; the process group comes as a name on the push path and
as an id on the pull path, which is all NiFi's bulletin board provides.

## Logs

NiFi's own log files, shipped by a Universal Forwarder (any of them) or by
the push flow (application, bootstrap and user logs only — Deprecations and
API requests need the forwarder).

![image](/nifi-monitoring-splunk/assets/images/splunk/view_logs.png)

- **Application**: events by level across NiFi's logs (all but the request
  log), and the `nifi-app.log` events. The search box applies to the
  events.
- **Deprecations**: what an instance uses that a later NiFi removes, from
  `nifi-deprecation.log` — the list to clear before moving to NiFi 2.x.
- **API requests**: `nifi-request.log` by status class, and the requests
  that fail most.

## Cluster

Whether a NiFi cluster is whole: nodes connected out of the total, which
node is primary and which coordinates, and heap and queue per node — the
aggregate hides the node that is running out.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_cluster.png)

A standalone NiFi has nothing to show here. The TA detects a cluster by
itself; there is nothing to enable.

## Alerts

The alerts the app ships, whether each is enabled, and which ones fired in
the selected range.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_alerts.png)

They ship **disabled**. Enable the ones you want in *Settings › Searches,
reports, and alerts* (app *nifi_monitoring*) and add the actions there —
email, webhook — since none come configured:

| Alert | Fires when |
|---|---|
| Instance without data | an instance in the inventory sends nothing for longer than its polling interval allows |
| Repository filling up | a repository reaches the instance's repository threshold |
| Sustained high heap | heap stays over the instance's heap threshold for several samples in a row |
| ERROR bulletin spike | an instance raises more ERROR bulletins than its bulletin threshold |
| Backpressure | a connection reaches the backpressure threshold, or NiFi predicts it will soon (needs *Flow metrics*) |
| Cluster node disconnected | a cluster member is not connected |
| Versioned flow sync failure | a versioned process group cannot sync with its registry |
| TA HTTP errors | the TA cannot log in to NiFi, is refused, or gets a server error |

Every alert uses the same thresholds as the panels; see
[Thresholds](references.md#thresholds).

## Configuration

### NiFi Instances

Opens the [Instance Lookup](instance-lookup.md): one row per monitored
instance or cluster, with its cluster name and, optionally, thresholds of
its own.

### Collection Health

Whether data collection is working — check here first when a panel is
empty.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_collection_health.png)

- How many events the app can see through the `index_nifi` macro, and in
  which index the NiFi data actually is: if they differ, point the macro
  at that index (see [Upgrading](upgrading.md)).
- **Instances behind**: how many instances are *Stale* or have *No data*.
- When each instance last sent each kind of data, marked late or missing
  against its polling interval. A blank cell is a source that is not
  enabled for that instance, not an error.
- The TA's HTTP errors by status code: a login failure means wrong
  credentials, 403 missing permissions, 404 a wrong component id, 5xx a
  problem on NiFi's side.
