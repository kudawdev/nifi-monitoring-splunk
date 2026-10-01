---
title: Push strategy (2.0)
---

# Push strategy: Direct Sending (2.0)

A flow running inside NiFi calls NiFi's own API and sends the result
straight to Splunk's HTTP Event Collector (HEC) — nothing on Splunk's
side has to reach NiFi. Not sure this is the strategy you need? See
[Choosing a collection strategy](compatibility.md#choosing-a-collection-strategy),
which also draws the architecture of both.

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
    trusts Splunk's certificate.

    Turning **Enable SSL** off under **Settings > Data Inputs > HTTP
    Event Collector > Global Settings** is an instance-wide change: it
    affects every HEC token on this Splunk instance, not only this one,
    and sends every event and every token in plain text. Only consider it
    in an isolated test environment you control, never on a shared or
    production Splunk instance.

## 2. Import the Flow Definition into NiFi

Import [`flow_definition/nifi-2.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-2.x/NiFiMonitoring.json)
— not the 1.x one. NiFi 2.0 removed the Variable Registry the 1.x flow
depends on; the 1.x file loads into a 2.x instance without an error, but
several processors come up invalid or fail silently once started.

Drag a *process group* box onto the canvas. In the **Create Process
Group** dialog, name it and click the small icon next to *Name* to
upload the flow file:

![image](/nifi-monitoring-splunk/assets/images/nifi/create_process_group_2x.png)

Once a file is selected, *Parameter Context* is replaced by a note that
parameters will come from the uploaded flow, and the filename shows
under *File to upload*:

![image](/nifi-monitoring-splunk/assets/images/nifi/create_process_group_2x_upload.png)

Click **Add**. The process group is created with every processor that
needs a still-empty parameter showing invalid — expected until you set
them in the next step:

![image](/nifi-monitoring-splunk/assets/images/nifi/process_group_created_2x.png)

It contains:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

## 3. Configure the flow's settings

Importing the 2.x flow creates a parameter context named **NiFi
Monitoring** and attaches it to the process group. Open it with
right-click on the process group > *Parameters*, or from the top-right
menu > *Parameter Contexts*, and set:

| Parameter | What it is |
|---|---|
| `instance_name` | The `host` the `nifi:api:*` events are sent with: the `host` of this NiFi's row in the `instance` lookup. **Required on a cluster**, where the API is polled from the primary node — left empty, each event carries the name of whichever node is primary, which changes on every failover and does not match the lookup, so the overview reports the cluster Down. Empty uses the node's hostname, which is right for a single NiFi. Logs always carry the node's name |
| `nifi_api_url` | This instance's REST API, e.g. `http://127.0.0.1:8080/nifi-api/` |
| `nifi_path` | NiFi's install directory, used to tail its logs. On a cluster, the same path on every node |
| `process_groups_list` | Ids of the process groups to monitor, one per line |
| `processors_list` | Ids of the processors to monitor, one per line |
| `splunk_hec` | The Splunk server with the HEC input, e.g. `http://<host>:8088/` |
| `splunk_hec_token` | The token from [step 1](#1-configure-the-http-event-collector-hec-in-splunk). This is a **sensitive** parameter, so NiFi never writes it into an exported flow |

Two parameters ship empty on purpose, and until they have values the two
`GenerateFlowFile` processors stay invalid. That's intended: NiFi
refusing to start a processor with an empty required property beats
starting one pointed at another installation's component ids.

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

With the parameter context in place, create the following components
from the menu > **Controller Settings**.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_2x.png)

In the **Management Controller Services** tab, add the
**JsonRecordSetWriter** controller service — it parses the reporting
tasks' output for indexing in Splunk. It comes in **Disabled** — enable
it:

![image](/nifi-monitoring-splunk/assets/images/nifi/json_record_set_writer_added_2x.png)

In the **Reporting Tasks** tab of the same window:

![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_tasks_empty_2x.png)

Add and configure these three:

- **MonitorDiskUsage**: reports when a filesystem crosses the usage
  threshold you set.

    * Threshold: e.g. `80%`
    * Directory Location: the filesystem to watch, e.g. `/`
    * Directory Display Name: a label for it, e.g. `NifiFileSystem`

- **SiteToSiteBulletinReportingTask**: sends every bulletin as it
  happens.

    * Destination URL: `http://${hostname(true)}:8080/nifi`
    * Input Port Name: `bulletin_report`
    * Instance URL: same as Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`

- **SiteToSiteMetricsReportingTask**: sends flow and JVM metrics.

    * Destination URL: `http://${hostname(true)}:8080/nifi`
    * Input Port Name: `reporting_task`
    * Instance URL: same as Destination URL
    * Transport Protocol: `HTTP`
    * Record Writer: `JsonRecordSetWriter`
    * Output Format: `Record Format`

!!! note "If NiFi serves HTTPS"
    `nifi_api_url` being `https://` makes the URLs above `https://` too,
    which adds an **SSL Context Service** property to both reporting
    tasks. Set it to a `StandardSSLContextService` with the same
    Truststore values as [step 3](#3-configure-the-flows-settings).
    Create this one from the **Controller Settings** window these
    reporting tasks are already in, not from the process group's
    *Configure* dialog: reporting tasks are NiFi-wide components and
    cannot see a controller service scoped to a process group.

Start each reporting task:

![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_tasks_running_2x.png)

## 5. Start the flow

Right-click the process group and select **Start**. Every component
inside comes up running, with no invalid ones left:

![image](/nifi-monitoring-splunk/assets/images/nifi/process_group_running_2x.png)

Data now flows to Splunk. For it to appear in the app's panels, also
configure the [Instance Lookup](instance-lookup.md).
