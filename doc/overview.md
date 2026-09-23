# Overview

The application consists of the following navigation tree:

- App Nifi Monitoring
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

The main page of NIFI Monitoring App where you can see a small diagram that shows the type of information obtained from the NIFI servers to be analyzed by Splunk

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

## NIFI Monitor Overview

In the overview panel can see a summary of the different monitored NIFI servers, very similar to the top bar that we find in the initial application. The indicators are the following:

- Server status by node
- Repository status by node
- Bulletin error behavior by node

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview.png)

## Nifi Instance Panels

In the next group of panels we will obtain details of different data sources, but analyzing the nodes individually.

### Flow's & Metrics Monitoring Panel

The following panel shows details of the node's operation, analyzing different performance metrics, as well as availability of use of some of the node's resources.

![image](/nifi-monitoring-splunk/assets/images/splunk/monitoring_panel.png)

To make the data visualization more user-friendly, the panels have a series of scale selectors understanding the volume variability that a server can handle.

![image](/nifi-monitoring-splunk/assets/images/splunk/behaviour_overtime_1.png)

Additionally, information on the operational JVM is available in each node, and in this way have a complete view of the operation of the platform.

![image](/nifi-monitoring-splunk/assets/images/splunk/behaviour_overtime_2.png)

### Bulletin Monitoring Panel

In the next panel, we can mainly observe the behavior of the errors of the bulletin system in NiFi, since it is very important in the event of an error to be able to carry out the correct traceability, in order to correct the situation as soon as possible.

![image](/nifi-monitoring-splunk/assets/images/splunk/bulletin_panel.png)

### Logs Monitoring Panel

In the next panel, we can observe the NiFi application, bootstrap, user and request logs collected from every configured instance, to search and correlate log activity without opening a terminal on each NiFi host.

![image](/nifi-monitoring-splunk/assets/images/splunk/logs_panel.png)

### Status History

This panel plots the status history of the specific processors and process groups configured under [Status history](configuration.md#4-status-history) on the data input — throughput, queued flow files and the other counters NiFi's own Status History view shows, over time and per instance.

## Configuration

### NiFi Instances

Opens the [Instance Lookup](configuration.md#instance-lookup) editor, where every monitored NiFi instance (or cluster) must have a row before its data is accessible from the panels above.

### Internal Monitoring

Labeled **Nifi TA Monitoring** in the app. Reports on the add-on itself rather than on NiFi: how many events each sourcetype and index actually holds — the first place to look when a panel is empty or when [upgrading](upgrading.md) and the `index_nifi` macro needs to change — and, on a cluster, the members, their roles and their per-node heap.
