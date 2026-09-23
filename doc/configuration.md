# Configuring NIFI Monitoring Splunk

## Configuration
At this stage, all the necessary steps that must be carried out by the side of our nifi instances that are to be monitored will be detailed.

There are two ways of configuration that allow the sending of events to Splunk and their choice depends on the authentication mechanisms that NIFI has enabled.

- Direct sending: This configuration will establish NIFI as the main way to send data to Splunk and should be used when NIFI does not have authentication methods enabled.

- Splunk Data Input NiFi: Splunk will be in charge of making requests to the NIFI instances to retrieve the information from the Monitoring API by enabling and using the Data Input NIFI. This configuration should be used when NIFI has basic authentication.

[NOTE] Configure only one methodology, both running will generate duplicate information.

## Direct Sending

### 1. Configuring HTTP Event Collector (HEC) in Splunk

Configuration of an HTTP Event Collector (HEC) is required. This allows events to be sent from nifi instances to a Splunk implementation via the HTTP and HTTPS protocols.

To configure, from the Splunk menu select Settings > Data Inputs. In the Local Inputs list, identify HTTP Event Collector and add a new one.

In the configuration process you must:

- Assign a name for the data input,
- Set the sourcetype to **automatic**,
- Select the *App Context* **NIFI Monitoring** and finally
- Select the Index where the data will be stored.

It is recommended to use a dedicated Index for this monitoring. If it does not exist, you must create it prior to this configuration.

At the end of the configuration of this Event Collector, a Token Value will be created, which is necessary to later configure the sending of data from NIFI.

Configuration process:

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_1.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_2.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/add_hec_3.png)

### 2. Import the Flow Definition into NiFi

Pick the file that matches your NiFi version. They are not interchangeable:

| Your NiFi | Import |
|---|---|
| 1.16 – 1.28 | [`flow_definition/nifi-1.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-1.x/NiFiMonitoring.json) |
| 2.0 and later | [`flow_definition/nifi-2.x/NiFiMonitoring.json`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/flow_definition/nifi-2.x/NiFiMonitoring.json) |

!!! warning "Do not import the 1.x flow into NiFi 2.x"
    It loads, which is the trap. Five processors come up invalid, and the six
    variables the flow depends on disappear without a single error: processors
    validate cleanly while holding `${splunk_hec}` references that resolve to
    nothing, and fail only at runtime.

The Flow Definition is a process group that collects NiFi data and sends it to
Splunk. To import it, drag a *process group* box onto the canvas, select the
import icon in the pop-up, and choose the file.

Once imported you will see the process group, containing:

-   Monitoring API
-   Monitoring Logs
-   Monitoring ReportingTask
-   SendHEC

### 3. Configure the flow's settings

The mechanism differs by NiFi version, because NiFi 2.0 removed the Variable
Registry.

#### NiFi 2.x — parameter context

Importing the 2.x flow creates a parameter context named **NiFi
Monitoring** and attaches it to the process group. Open it with
right-click on the process group > *Parameters*, or from the top-right
menu > *Parameter Contexts*.

Two of its parameters ship empty on purpose, and until they have values
the two `GenerateFlowFile` processors stay invalid. That is intended:
NiFi refusing to start a processor with an empty required property beats
starting one pointed at another installation's component ids.

#### NiFi 1.x — variables

Right-click on the NiFiMonitoring box > *Variables*.

Either way, the settings are the same:

| Setting | What it is |
|---|---|
| `nifi_api_url` | This instance's REST API, e.g. `http://127.0.0.1:8080/nifi-api/` |
| `nifi_path` | NiFi's install directory, used to tail its logs. On a cluster, the same path on every node |
| `process_groups_list` | Ids of the process groups to monitor, one per line |
| `processors_list` | Ids of the processors to monitor, one per line |
| `splunk_hec` | The Splunk server with the HEC input, e.g. `http://<host>:8088/` |
| `splunk_hec_token` | The token from [configuring the HEC](#1-configuring-http-event-collector-hec-in-splunk). On 2.x this is a **sensitive** parameter, so NiFi never writes it into an exported flow |

### 4. Components configuration

!!! note "The screenshots below are from NiFi 1.x"
    NiFi 2.x rebuilt its user interface, so these images no longer match what
    you see. The steps themselves are unchanged — the same controller service
    and the same three reporting tasks, reached from the same menus — but the
    screens look different. Recapturing them for 2.x is pending.


With the flow's settings in place (the parameter context on 2.x, variables on 1.x), create the following components. To configure access Nifi Settings from the menu > Controller Settings

![image](/nifi-monitoring-splunk/assets/images/nifi/controller_settings.png)

A pop-up window like the following will be displayed:

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings.png)

In the Reporting Task Controller Services tab, add the **JsonRecordSetWriter** controller service, which will allow parsing the results obtained from the Reporting Task service for later indexing in splunk. To add, click the (+) button

The window to add the controller will be displayed. Filter the list of options with the item to be added, select it and add it to the configuration.

![image](/nifi-monitoring-splunk/assets/images/nifi/add_controller_service.png)

Once added, you must enable its operation by clicking on the lightning bolt icon (ϟ) and in the pop-up window confirm. This will enable the controller and you should have a configuration like the following.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_2.png)

In this same window, in the Reporting Task tab, the following reports must be configured.

- MonitorDiskUsage
- SitetoSiteBulletinReportingTask
- SitetoSiteMetricsReportingTask

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_3.png)

Add and find the required reporting tasks in the same way as the previous step, by clicking the (+) icon. Once added you can have a view like the following.

![image](/nifi-monitoring-splunk/assets/images/nifi/reporting_task.png)

Configure task reports with the following information:

- MonitorDiskUsage: Internal reporting system that generates events as the threshold defined for the use of the filesystem is exceeded and captured in a specific flow.

![image](/nifi-monitoring-splunk/assets/images/nifi/monitor_disk_usage.png)

- SiteToSiteBulletinReportingTask: Internal reporting system that generates events as bulletin type errors are generated and captured in a specific flow. The configuration should be as follows:

    * Destination URL: http://${hostname(true)}:8080/nifi
    * Input Port Name: bulletin_report
    * Instance URL: http://${hostname(true)}:8080/nifi
    * Transport Protocol: HTTP
    * Record Writer: JsonRecordSetWriter

![image](/nifi-monitoring-splunk/assets/images/nifi/bulletin_reporting_task.png)

- SiteToSiteMetricsReportingTask: Internal reporting system that generates events as metrics are generated from the same environment and captured in a specific flow. The configuration should be as follows:

    * Destination URL: http://${hostname(true)}:8080/nifi
    * Input Port Name: reporting_task
    * Instance URL: http://${hostname(true)}:8080/nifi
    * Transport Protocol: HTTP
    * Record Writer: JsonRecordSetWriter
    * Output Format: Record Formats

![image](/nifi-monitoring-splunk/assets/images/nifi/metrics_reporting_task.png)

Once the reporting tasks have been configured, you must start the execution by clicking start (►) on each of them.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_4.png)

### 5. Enabling the sending of data

After completing the entire configuration process, start the process group execution. Right click on the process group and then Start.

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_1.png)

If all the configuration was successful, the information will be sent to Splunk. For the data sent to splunk to be accessible from the application, you must have configured the [Instance Lookup](#instance-lookup) below.

## Configuration of Nifi Data Input in Splunk

*This configuration must be applied when the NIFI instances have at least basic authentication.*

As of 2.0.0 the add-on has its own configuration page. Open **Apps > NiFi TA
Monitoring > Inputs** and click **Create New Input**. Splunk's generic
*Settings > Data inputs > NiFi* screen still works and writes the same
`inputs.conf`, but it does not offer the grouped form, the field validation
or the connection test described below.

**One input covers one NiFi instance** (or one cluster, pointed at any
node — see [Compatibility](compatibility.md#cluster-and-multiple-instances)).
Everything for that instance — which endpoints to poll, which processors and
process groups to track, TLS, the interval — lives on the same form,
organized into the groups described below. Create one input per NiFi
instance you want to monitor.

Two more things worth knowing:

- **Configuration > Logging**, outside the input itself, sets how much the
  add-on writes to `splunkd.log`. It is `INFO` by default, which is one line
  per request per endpoint per interval. On an instance polling several
  NiFis that is most of what the add-on puts in `_internal`; `WARNING` keeps
  the problems and drops the rest.
- **Test connection**, inside the input form next to the credentials,
  performs the same two calls the input performs -- the login and
  `GET /system-diagnostics` -- with the values currently on screen, and says
  what came back. It saves nothing. Getting a NiFi input right means getting
  the URL, the scheme, the certificate and the credentials right at the same
  time; without this they all fail the same way, some minutes later, in a
  log.

### 1. NiFi instance

- **NiFi instance name**: a unique name for this input. Used as the `host`
  value stamped on every event unless you set one explicitly under
  *Advanced*.
- **NiFi API URL**: the instance's REST API, e.g.
  `https://<address>:<port>/nifi-api/`.

### 2. Authentication

- **Authentication**: `None`, or `Username and password` when NiFi has
  basic authentication enabled. `Username and password` performs
  `POST /access/token` and sends the JWT it gets back on every following
  request.
- **Username** / **Password**: required unless Authentication is `None`.
- **Test connection**: see above.

### 3. Endpoints

Three checkboxes, all on by default:

- **Flow status** — `GET /flow/status`. The summary counters every
  dashboard panel is built on.
- **System diagnostics** — `GET /system-diagnostics`. Heap, threads and
  repository usage. This is also how the add-on detects the NiFi version,
  so turning it off disables version reporting.
- **Bulletin board** — `GET /flow/bulletin-board`. Individual bulletins,
  polled with a cursor so nothing is counted twice. The board only keeps a
  short window, so an interval longer than that window can miss bulletins.

### 4. Status history

Collapsed by default. Two fields, each comma- or newline-separated and
empty by default (collecting nothing until filled in):

- **Processor IDs**: UUIDs of the processors to collect status history for.
- **Process group IDs**: UUIDs of the process groups to collect status
  history for.

### 5. Flow metrics

Collapsed by default, and off by default even once expanded:

- **Collect flow metrics** — `GET /flow/metrics/json`. Requires NiFi 1.16
  or later. An idle NiFi emits around 60 samples per poll, and the
  `All components` strategy below scales that with the size of the flow, so
  review the volume before turning it on.
- **Registries**: comma-separated registry names to collect, e.g.
  `NIFI,JVM`. Empty collects all of them.
- **Strategy**: `All process groups` or `All components`. `All components`
  emits one sample per component, which is what multiplies the volume.
- **Sample filter**: a regular expression matched against the metric name.
  Empty keeps every sample.

### 6. Custom endpoints

Collapsed by default. Covers any NiFi REST path that is not on the fixed
list under *Endpoints* — see [Custom endpoints](#custom-endpoints) below.

### 7. TLS

Collapsed by default:

- **Verify the TLS certificate**: on by default. Leave it on unless NiFi
  uses a certificate that cannot be trusted through a CA bundle. Turning it
  off lets anyone able to intercept the connection read the credentials and
  the token.
- **CA bundle path**: only shown while *Verify the TLS certificate* is on.
  A path such as
  `/opt/splunk/etc/apps/nifi_TA_monitoring/local/nifi-ca.pem`. Empty uses
  the system trust store.

### 8. Advanced

Collapsed by default:

- **Interval**: seconds between polls, `60` by default. Every enabled
  endpoint, including the custom ones, is collected on this interval.
- **Index**: the destination index. A dedicated index is recommended, for
  example `nifi`. If it does not exist, create it first.
- **Host field value**: stamped on every event from this input. Empty uses
  the NiFi instance name above. **On a cluster, set this to the cluster,
  not a node** — the add-on names the node in a separate field. This is
  also the value that must match a row in the
  [instance lookup](#instance-lookup) below.

### Custom endpoints

The fixed list under *Endpoints* covers what the app ships with. If you need
to poll a NiFi REST endpoint that is not on that list, use the **Custom
endpoints** section instead: one line per endpoint, as `name,path` (e.g.
`queue_stats,/flow/connections/1234-5678-90ab-cdef/status`). The path is
relative to the NiFi API URL configured above.

You name the endpoint; the add-on gives it the sourcetype. `queue_stats` is
indexed as `nifi:api:custom:queue_stats`, so everything you declare is
searchable as `nifi:api:custom:*` and nothing you declare can land in a
sourcetype the add-on itself writes. Splunk indexes the raw response; if you
need field extraction for it, add your own `props.conf` stanza for that
sourcetype.

Four things worth knowing before you rely on one:

- **A name, not a sourcetype.** `nifi:api:flow_status` and anything else
  outside `nifi:api:custom:` is refused at save time: a custom endpoint
  writing into a shipped sourcetype would mix its response into the data
  the dashboards read, and nothing downstream could tell the two apart.
  Writing the full `nifi:api:custom:queue_stats` is accepted and means the
  same as `queue_stats`.
- **`{id}` placeholders are not supported.** Unlike the Status History
  fields above, a custom path is requested literally. Write the UUID out.
  The input refuses to save a path containing `{` or `}` rather than
  letting it fail at poll time.
- **A failed request indexes nothing.** If NiFi answers 4xx or 5xx, the
  add-on logs it to `splunkd.log` and writes no event, so an empty
  sourcetype means the endpoint is not working — the error body is never
  indexed as if it were data.
- **Editing `inputs.conf` by hand needs a trailing backslash.** The
  textarea takes one endpoint per line, but a `.conf` file ends a value at
  the first unescaped newline. When you write the stanza yourself — a
  deployment server, for instance — continue each line with `\`:

```
custom_endpoints = queue_stats,/flow/connections/1234-5678-90ab-cdef/status\
cluster,/controller/cluster
```

  Indenting the continuation instead is silently ignored: Splunk keeps the
  first endpoint and drops the rest. `splunk btool inputs list` shows what
  actually took effect.

After completing the form, click **Next** and the input is created.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_success.png)

Repeat this once for every NiFi instance you want to monitor.

!!! note "The screenshot below is from before 2.0.0"
    It shows the three separate inputs the add-on used to require —
    endpoints, processor status history and process-group status history —
    instead of the single grouped input described above. Recapturing it is
    pending; what to expect today is one row per NiFi instance under
    **Data Inputs > NiFi**, not three.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_4.png)

## Transverse configuration

Regardless of the shipping methodology adopted, this configuration step is required for data display in the NIFI Monitoring Splunk application.

### Instance Lookup

Go to Configuration > NiFi Instances to access the Lookups configuration view

![image](/nifi-monitoring-splunk/assets/images/splunk/1_configure_instances.png)

Complete the information in the fields, where the cluster label is to associate a group of nodes and host is the name of the instance.

![image](/nifi-monitoring-splunk/assets/images/splunk/2_configure_instances.png)

To obtain the name of the host, execute the following search with a time range of the last 60 minutes.

**Splunk Query**  
```sourcetype=nifi* | dedup host | table host ```

The result of this query will return the list of hosts that must be configured in the lookup.

![image](/nifi-monitoring-splunk/assets/images/splunk/sourcetype_search.png)

If the lookup is correctly configured, the information can be accessed from the Overview panel.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview_lookup.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/3_configure_instances.png)

There are no results in the executed search?

![image](/nifi-monitoring-splunk/assets/images/splunk/4_configure_instances.png)

For this search to return results, the Nifi processes must be running correctly.
 According to the configuration methodology you must:

1. Direct sending: You must start the NIFI processes [How to enable data sending?](#5-enabling-the-sending-of-data)
2. Splunk Data Input NiFi: The configured data inputs must be enabled.
