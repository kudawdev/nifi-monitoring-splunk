---
title: Push strategy (1.2)
---

# Push strategy: Direct Sending (1.2)

!!! note "For version 1.2.x of both apps"
    This is the setup as it was in release 1.2.3, with the flow that release
    shipped. On 2.0, see
    [Push strategy (2.0)](config-nifi-monitoring-2-0-push.md), which covers
    both NiFi 1.x and 2.x.

This configuration makes NiFi the main way data is sent to Splunk, and it
should be used when NiFi has no authentication enabled.

Configure only one strategy: running both generates duplicate data.

## 1. Configuring the HTTP Event Collector (HEC) in Splunk

An HTTP Event Collector (HEC) is required. It lets NiFi instances send
events to Splunk over HTTP and HTTPS.

From the Splunk menu, select **Settings > Data Inputs**. In the Local Inputs
list, find **HTTP Event Collector** and add a new one. In the process you
must:

- assign a name to the data input,
- set the sourcetype to **automatic**,
- select the *App Context* **NIFI Monitoring**, and
- select the index where the data will be stored.

A dedicated index is recommended for this monitoring. If it does not exist,
create it before this configuration.

When the HEC is created you get a **Token Value**, needed later to configure
the sending of data from NiFi.

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_1.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_2.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_3.png)

## 2. Import the Flow Definition into NiFi

Download the Flow Definition for the 1.2 setup,
[`flow_definition/NiFiMonitoring.json` at 1.2.3](https://github.com/kudawdev/nifi-monitoring-splunk/blob/1.2.3/flow_definition/NiFiMonitoring.json).

The Flow Definition is the structure of a process group that collects NiFi's
data and sends it to Splunk. It is a JSON file that can be imported
directly.

To import it, drag a *process group* box onto the NiFi canvas.

![image](/nifi-monitoring-splunk/assets/images/nifi/1_add_process_group.png)

In the pop-up window, select the import icon, browse your computer and pick
the `NiFiMonitoring.json` flow definition.

![image](/nifi-monitoring-splunk/assets/images/nifi/2_import_flow_definition.png)

Once imported, click **Add** to finish.

![image](/nifi-monitoring-splunk/assets/images/nifi/3_load_flow_definition.png)

You will see the process group, which contains:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

![image](/nifi-monitoring-splunk/assets/images/nifi/4_flow_definition_loaded.png)

## 3. Global variables configuration

The global variables are required for the flow to work. To set them,
right-click on the NiFiMonitoring box > **Variables**.

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable.png)

A pop-up window opens where you set:

- `nifi_api_url`: the route of the NiFi REST API (e.g. `http://127.0.0.1:8080/nifi-api/`).
- `nifi_path`: the NiFi installation path on the server (on a cluster, it
  must be installed in the same path on every node), e.g.
  `/home/nifi/nifi-1.10.0/`.
- `process_groups_list`: the **IDs of the process groups** to monitor, one
  per line.
- `processors_list`: the **IDs of the processors** to monitor, one per line.
- `splunk_hec`: the address of the Splunk server where the HTTP Event
  Collector was configured (e.g. `http://<host>:8088/`).
- `splunk_hec_token`: the token from
  [configuring the HTTP Event Collector](#1-configuring-the-http-event-collector-hec-in-splunk).

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable_2.png)

## 4. Components configuration

With the variables set, create the following components. Open NiFi's
settings from the menu > **Controller Settings**.

![image](/nifi-monitoring-splunk/assets/images/nifi/controller_settings.png)

A pop-up window like the following opens:

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings.png)

In the **Reporting Task Controller Services** tab, add the
**JsonRecordSetWriter** controller service, which parses the results of the
reporting tasks for indexing in Splunk. To add it, click the (+) button.

Filter the list with the name of the item to add, select it and add it.

![image](/nifi-monitoring-splunk/assets/images/nifi/add_controller_service.png)

Once added, enable it: click the lightning bolt icon (ϟ) and confirm in the
pop-up window. You should then have a configuration like the following.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_2.png)

In the same window, in the **Reporting Task** tab, add these reporting
tasks:

- MonitorDiskUsage
- SiteToSiteBulletinReportingTask
- SiteToSiteMetricsReportingTask

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_3.png)

Add them the same way as in the previous step, with the (+) icon. Once
added you will see something like:

![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_task.png)

Configure them as follows:

- **MonitorDiskUsage**: an internal reporting task that raises events when
  the filesystem usage threshold is exceeded, captured in a specific flow.

![image](/nifi-monitoring-splunk/assets/images/nifi/monitor_disk_usage.png)

- **SiteToSiteBulletinReportingTask**: an internal reporting task that
  raises events as bulletins are generated, captured in a specific flow:

    * Destination URL: `http://${hostname(true)}:8080/nifi`
    * Input Port Name: `bulletin_report`
    * Instance URL: `http://${hostname(true)}:8080/nifi`
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`

![image](/nifi-monitoring-splunk/assets/images/nifi/bulletin_reporting_task.png)

- **SiteToSiteMetricsReportingTask**: an internal reporting task that
  raises events as metrics are generated by the same environment, captured
  in a specific flow:

    * Destination URL: `http://${hostname(true)}:8080/nifi`
    * Input Port Name: `reporting_task`
    * Instance URL: `http://${hostname(true)}:8080/nifi`
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`
    * Output Format: `Record Format`

![image](/nifi-monitoring-splunk/assets/images/nifi/metrics_reporting_task.png)

Once configured, start each reporting task by clicking start (►).

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_4.png)

## 5. Enabling the sending of data

With all of the above done, start the process group: right-click on it, then
**Start**.

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_1.png)

If everything is configured correctly, the data starts being sent to
Splunk. For it to show in the app, configure the
[Instance Lookup](instance-lookup.md).
