# Dashboards

Eight views, from the whole fleet down to a single connection. Each one
answers one question:

| View | The question it answers |
|---|---|
| [Overview](#overview) | Is the fleet healthy right now? |
| [Instance](#instance) | What is happening on this instance? |
| [Components](#components) | Which processor, group or connection is the bottleneck? |
| [Bulletins](#bulletins) | What errors is NiFi reporting? |
| [Logs](#logs) | What do NiFi's own log files say? |
| [Cluster](#cluster) | Is the cluster whole? |
| [Alerts](#alerts) | What can the app alert on, and what fired? |
| [Collection Health](#collection-health) | Is data collection working? |

**Overview** says which instance needs attention, **Instance** says what is
wrong with it, and **Components** says which processor or connection is the
cause. Every drilldown keeps the instance and the time range you were
looking at.

They work the same whichever way the data arrives — the TA polling NiFi
(pull) or the flow inside NiFi sending to the HEC (push). A panel that
needs a source you have not enabled says which one in its description.

In Splunk, the app's menu follows the same order, with **NiFi Instances**
and **Collection Health** under **Configuration**, and **Search** at the
end.

Every colour comes from a threshold, and every threshold can be set for
the whole app or for one instance — see [Thresholds](references.md#thresholds).

## Overview

The landing page: is the fleet healthy right now? Six figures, then one row
per instance that is in the [inventory](instance-lookup.md) or has sent data,
worst first.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_overview.png)

| Indicator | What it tells you |
|---|---|
| **Healthy instances** | Healthy instances out of all of them, heard from or not. |
| **ERROR bulletins · 15 min** | ERROR bulletins across the fleet in the last 15 minutes; red from the first one. |
| **Worst heap** | The highest heap use of any instance, and which one. Coloured by that instance's own heap threshold. |
| **Worst repository** | The fullest FlowFile, content or provenance repository of any instance, and which one. Coloured by that instance's repository threshold. |
| **FlowFiles queued** | Everything waiting in a queue, across every instance. |
| **Invalid components** | Processors and services NiFi will not start; amber from the first one. |
| **Instances** | One row per instance: health and its reason, cluster, NiFi version, when the last data arrived, component counts (running, stopped, invalid, disabled), queue, heap, worst repository and recent ERROR bulletins. Click a row to open it in **Instance**. |
| **Bulletins by level** | Bulletins in 10-minute buckets, over the selected range. |
| **FlowFiles queued by instance** | Queue over time for the four busiest instances; the rest fold into OTHER. |

The health of each instance is one of *Critical*, *Degraded*, *Stale* (no
data for longer than its polling interval allows), *No data* or *Healthy*,
and the reason column says which threshold decided it. An instance listed
in the inventory that has never sent anything still gets its row; one that
sends data but is not listed gets its row too, with cluster "—".

## Instance

What is happening on one instance. It opens on the worst one of the
Overview list, and the selector at the top switches to another.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_instance.png)

| Indicator | What it tells you |
|---|---|
| **Status** | Health and its reason, NiFi and Java versions, uptime and when the last data arrived. |
| **Active threads**, **FlowFiles queued**, **Bytes queued** | What the instance is doing right now. |
| **Components** | Running · stopped · invalid · disabled. |
| **Versioned process groups** | Up to date · locally modified · stale · failing to sync with their registry. |
| **ERROR bulletins · 15 min** | This instance's recent errors. |
| **Heap used** | % of max heap over time, with this instance's threshold as a dashed line. |
| **JVM threads** | Total and daemon threads. |
| **Load average** | 1-minute load against the available cores (dashed). |
| **GC time per collector** | Milliseconds spent in each garbage collector per 5 minutes. |
| **Repositories** | One row per repository — content and provenance can be several — with its latest use. |
| **Repository usage** | % used over time, with this instance's threshold dashed. |
| **Data in, out and processed** | MB per 5 minutes received, sent and written by the whole flow. |
| **FlowFiles received and sent** | FlowFiles per 5 minutes from and to outside NiFi. |
| **Recent bulletins** | The latest ten; a click opens **Bulletins** filtered to this instance. |

The two throughput charts need *Flow metrics* enabled on the TA input on
the pull path; on the push path they come from the Reporting Task.

## Components

Which processor, process group or connection is the bottleneck. The
selectors pick the instance, processors or process groups, the metric and
how it is aggregated.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_components.png)

| Indicator | What it tells you |
|---|---|
| **Connections over backpressure threshold** | Connections whose object count or size is at or over this instance's backpressure threshold. |
| **Reaching backpressure soon** | Connections NiFi itself predicts will reach backpressure within the hour. |
| **Components with history** | How many components have their status history collected. |
| **Top 10 by the selected metric** | The ten heaviest components by task time, FlowFiles in and out, bytes read and written, and so on, each with a trend line. Click one to plot it below. |
| **Busiest connections** | How full each connection is, by object count and by size, and NiFi's estimate of the time left before backpressure. |
| **Selected component** | The chosen metric per 5 minutes for the component clicked above. |

The components listed are the ones whose status history is collected: the
processor and process group ids set on the TA input
([Status history](configuration-pull.md#4-status-history)), or in the push
flow's `processors_list` and `process_groups_list`. Connections need *Flow
metrics* on the TA input.

## Bulletins

The errors and warnings NiFi components raise, from either collection
path. Filter by instance, level, category or component.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_bulletins.png)

| Indicator | What it tells you |
|---|---|
| **Bulletins**, **ERROR**, **WARNING** | How many in the selected range, and of which level. |
| **Components affected** | How many distinct components raised them. |
| **Bulletins over time** | Hourly, by level. |
| **Components with most bulletins** | Where to look first. |
| **Bulletin details** | Each message whole, with its instance, level, category, component and group. |

The process group comes as a name on the push path and as an id on the
pull path, which is all NiFi's bulletin board provides.

## Logs

NiFi's own log files, shipped by a Universal Forwarder (any of them) or by
the push flow (application, bootstrap and user logs only — Deprecations and
API requests need the forwarder). Filter by instance and severity, and
search the events.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_logs.png)

| Indicator | What it tells you |
|---|---|
| **Events by level** | Events by level across NiFi's logs, all but the request log. |
| **Events** | The `nifi-app.log` events, newest first, matching the search box. |
| **Deprecated usage · last 7 days** | What an instance uses that a later NiFi removes, from `nifi-deprecation.log` — the list to clear before moving to NiFi 2.x. |
| **Requests by status class** | `nifi-request.log` in 5-minute buckets, by 2xx, 3xx, 4xx and 5xx. |
| **Top failing requests** | The 4xx and 5xx requests that fail most. |

## Cluster

Whether a NiFi cluster is whole.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_cluster.png)

| Indicator | What it tells you |
|---|---|
| **Connected nodes** | Nodes connected out of the total. |
| **Primary node**, **Cluster coordinator** | Which node holds each role. |
| **Nodes** | One row per node: status, roles, last heartbeat, active threads, queue and heap. |
| **Heap used by node** | Heap per node — the aggregate hides the node that is running out. |
| **FlowFiles queued by node** | Queue per node. |

A standalone NiFi has nothing to show here. The TA detects a cluster by
itself; there is nothing to enable.

## Alerts

The alerts the app ships, whether each is enabled, and which ones fired in
the selected range.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_alerts.png)

| Indicator | What it tells you |
|---|---|
| **Alerts enabled** | How many of the shipped alerts are on. |
| **Fired in range** | How many times any of them fired; red from the first one. |
| **Alerts shipped with the app** | Each alert, whether it is enabled, its condition and its schedule. |
| **Fired** | Each firing: when, which alert, and its severity. |

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

| Indicator | What it tells you |
|---|---|
| **Events the app can see** | Events reachable through the `index_nifi` macro; zero means the macro points at the wrong index. |
| **Instances behind** | Instances that are *Stale* or have *No data*. |
| **TA HTTP errors** | Requests the TA could not complete. |
| **Last data per instance and source** | When each instance last sent each kind of data: on time, late or missing against its polling interval. A blank cell is a source that is not enabled for that instance, not an error. |
| **TA HTTP errors by status code** | A login failure means wrong credentials, 403 missing permissions, 404 a wrong component id, 5xx a problem on NiFi's side. |
| **Where NiFi data is** | Which index actually holds the NiFi data: if it is not the one the macro points at, change the macro (see [Upgrading](upgrading.md)). |
