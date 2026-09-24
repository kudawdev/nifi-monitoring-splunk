# Push strategy: Direct Sending

A flow running inside NiFi calls NiFi's own API and sends the result
straight to Splunk's HTTP Event Collector (HEC) — nothing on Splunk's
side has to reach NiFi. Not sure this is the strategy you need? See
[Choosing a collection strategy](compatibility.md#choosing-a-collection-strategy).

Requires both apps already installed (see
[Install NIFI Monitoring](installation.md)): **Nifi Monitoring TA**
parses the events this flow sends, even though you configure no input
inside it for this strategy.

## 1. Configure the HTTP Event Collector (HEC) in Splunk

An HTTP Event Collector (HEC) receives events from NiFi over HTTP or HTTPS.

From the Splunk menu, go to **Settings > Data Inputs > HTTP Event
Collector** and add a new one:

- Name the data input.
- Set the sourcetype to **Automatic**.
- Set *App Context* to **NIFI Monitoring**.
- Select the index — use a dedicated one, and create it first if it does
  not exist.

Finishing this creates a **Token Value**, needed later to configure
NiFi's flow.

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_1.png)
![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_2.png)
![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_3.png)

!!! warning "Match the HEC's TLS setting, don't turn it off"
    Splunk ships every new HEC token with **Enable SSL** on. The flow's
    `InvokeHTTP` processors send plain HTTP, so unless one side changes,
    the mismatch fails as a TCP-level "Connection reset" -- not a clear
    certificate or authentication error.

    Keep the HEC on HTTPS and configure NiFi for it instead: set
    `splunk_hec` (below) to `https://<host>:8088/`, and give the
    `InvokeHTTP` processors under **SendHEC** an SSL Context Service that
    trusts Splunk's certificate -- the same kind of controller service
    used elsewhere on this page for NiFi's own certificate.

    Turning **Enable SSL** off under **Settings > Data Inputs > HTTP
    Event Collector > Global Settings** is an instance-wide change: it
    affects every HEC token on this Splunk instance, not only this one,
    and sends every event and every token in plain text. Only consider it
    in an isolated test environment you control, never on a shared or
    production Splunk instance.

## 2. Import the Flow Definition into NiFi

Pick the file that matches your NiFi version. They are not interchangeable:

| Your NiFi | Import |
|---|---|
| 1.16 – 1.28 | [`flow_definition/nifi-1.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-1.x/NiFiMonitoring.json) |
| 2.0 and later | [`flow_definition/nifi-2.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-2.x/NiFiMonitoring.json) |

!!! warning "Do not import the 1.x flow into NiFi 2.x"
    It loads without a single error, which is the trap. NiFi 2.0 removed the
    Variable Registry, so the six variables this flow depends on disappear
    silently on import. Five processors that need those variables come up
    invalid right away — but they are not the only ones affected. Others
    keep validating cleanly even though they hold `${splunk_hec}` and
    similar references that no longer resolve to anything; those fail only
    once you start the flow and it actually tries to use the now-empty
    value.

Drag a *process group* box onto the canvas, select the import icon in the
pop-up, and choose the file. The imported process group contains:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

## 3. Configure the flow's settings

The mechanism differs by NiFi version, because NiFi 2.0 removed the Variable
Registry.

### NiFi 2.x — parameter context

Importing the 2.x flow creates a parameter context named **NiFi
Monitoring** and attaches it to the process group. Open it with
right-click on the process group > *Parameters*, or from the top-right
menu > *Parameter Contexts*.

Two of its parameters ship empty on purpose, and until they have values
the two `GenerateFlowFile` processors stay invalid. That is intended:
NiFi refusing to start a processor with an empty required property beats
starting one pointed at another installation's component ids.

### NiFi 1.x — variables

Right-click on the NiFiMonitoring box > *Variables*.

Either way, the settings are the same:

| Setting | What it is |
|---|---|
| `nifi_api_url` | This instance's REST API, e.g. `http://127.0.0.1:8080/nifi-api/` |
| `nifi_path` | NiFi's install directory, used to tail its logs. On a cluster, the same path on every node |
| `process_groups_list` | Ids of the process groups to monitor, one per line |
| `processors_list` | Ids of the processors to monitor, one per line |
| `splunk_hec` | The Splunk server with the HEC input, e.g. `http://<host>:8088/` |
| `splunk_hec_token` | The token from [step 1](#1-configure-the-http-event-collector-hec-in-splunk). On 2.x this is a **sensitive** parameter, so NiFi never writes it into an exported flow |

!!! note "If NiFi serves HTTPS"
    Setting `nifi_api_url` to `https://...` makes the `GetHTTP` processors
    inside **Monitoring API** invalid, with "SSL context is invalid"
    warnings, until they have one to trust NiFi's own certificate. Add a
    **StandardSSLContextService** inside that process group's own
    Controller Services (right-click the process group > *Configure* >
    *Controller Services*), filling in only **Truststore Filename**,
    **Truststore Password** and **Truststore Type** — it only needs to
    trust NiFi's certificate, not present one of its own. Enable it, then
    set it on each invalid `GetHTTP`.

## 4. Configure the NiFi components

!!! note "The screenshots below are from NiFi 1.x"
    NiFi 2.x rebuilt its user interface, so these images no longer match what
    you see. The steps themselves are unchanged — the same controller service
    and the same three reporting tasks, reached from the same menus — but the
    screens look different. Recapturing them for 2.x is pending.

With the flow's settings in place (the parameter context on 2.x,
variables on 1.x), create the following components from the menu >
**Controller Settings**.

![image](/nifi-monitoring-splunk/assets/images/nifi/controller_settings.png)
![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings.png)

In the **Reporting Task Controller Services** tab, add the
**JsonRecordSetWriter** controller service — it parses the reporting
tasks' output for indexing in Splunk. Click **(+)**, filter for it,
select it, and add it.

![image](/nifi-monitoring-splunk/assets/images/nifi/add_controller_service.png)

Enable it: click the lightning bolt icon (ϟ) and confirm.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_2.png)

In the **Reporting Task** tab of the same window, add these three:

- MonitorDiskUsage
- SiteToSiteBulletinReportingTask
- SiteToSiteMetricsReportingTask

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_3.png)
![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_task.png)

Configure each one:

- **MonitorDiskUsage**: reports when a filesystem crosses the usage
  threshold you set.

![image](/nifi-monitoring-splunk/assets/images/nifi/monitor_disk_usage.png)

- **SiteToSiteBulletinReportingTask**: sends every bulletin as it
  happens.

    * Destination URL: `http://${hostname(true)}:8080/nifi` — same host
      and port as `nifi_api_url` above, just without `/nifi-api`
    * Input Port Name: `bulletin_report`
    * Instance URL: same as Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`

![image](/nifi-monitoring-splunk/assets/images/nifi/bulletin_reporting_task.png)

- **SiteToSiteMetricsReportingTask**: sends flow and JVM metrics.

    * Destination URL: `http://${hostname(true)}:8080/nifi` — same host
      and port as `nifi_api_url` above, just without `/nifi-api`
    * Input Port Name: `reporting_task`
    * Instance URL: same as Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`
    * Output Format: `Record Formats`

![image](/nifi-monitoring-splunk/assets/images/nifi/metrics_reporting_task.png)

!!! note "If NiFi serves HTTPS"
    `nifi_api_url` being `https://` makes the URLs above `https://` too,
    which adds an **SSL Context Service** property to both reporting
    tasks. Set it to a `StandardSSLContextService` with the same
    Truststore values as [step 3](#3-configure-the-flows-settings).
    Create this one from the **Controller Settings** window these
    reporting tasks are already in, not from the process group's
    *Configure* dialog: reporting tasks are NiFi-wide components and
    cannot see a controller service scoped to a process group, even
    though it is the same NiFi and the same certificate.

Start each reporting task: click **►** on each of them.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_4.png)

## 5. Start the flow

Right-click the process group and select **Start**.

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_1.png)

Data now flows to Splunk. For it to appear in the app's panels, also
configure the [Instance Lookup](configuration.md#instance-lookup).
