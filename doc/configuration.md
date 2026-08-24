# Configuring NIFI Monotoring Splunk

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

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_2.png)

If all the configuration was successful, the information will be sent to Splunk. For the data sent to splunk to be accessible from the application, you must have configured the [NIFI Instances Lookup](/nifi-monitoring-splunk/installation/#lookup-nifi-instances-configuration)

## Configuration of Nifi Data Input in Splunk 

*This configuration must be applied when the NIFI instances have at least basic authentication*

In the Splunk data inputs you can configure several resources, such as: NIFI Endpoints for monitoring System Diagnostics, Flow Status and Site to Site and the NIFI Status History for specific monitoring of processors and process groups based on their IDs.
To configure, in the splunk where the Nifi Monitoring application is installed, access the Home of the APP.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

Then in Settings Data Inputs

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_1.png)

In the local data input, identify NiFi and then click on + Add new

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_2.png)

A window like the following will be displayed:

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_3.jpeg)

**We recommend that you configure each of the monitoring resources independently for eventual changes in the configuration and due to execution times to obtain data.**

The resources are:

- a. NIFI Endpoints
- b. NIFI Status History for Processors
- c. NIFI Status History for Process Groups

### 1. Basic resource configuration
For each of the resources you must configure all the required fields:

- NIFI Instance name: Assigns a name to the NIFI instance
- NIFI API URL: NIFI Rest API address. (eg. http://<address:port\>/nifi-api/)
- Auth Type: Authentication type:
    - none: No authentication
    - basic: Access with username and password credentials
- Interval: Time in seconds in which the requests will be executed to extract the information, by default, 60 seconds.
- Host: Name of the nifi host, which must correspond to what is defined in the Configuration Lookup.
- Index: Destination index for this data source. A dedicated index is recommended, for example: nifi. If it does not exist, you must create it first.

### a. NIFI Endpoints
In the NIFI Endpoints section, select the elements to monitor from the existing list.

- System Diagnostics
- Flow Status
- Site to Site

### b. NIFI Status History for Processors
In the NIFI Status History > List Processors ID section, specify the processor IDs that will be monitored and separated by commas if there are several.

### c. NIFI Status History for Process Groups
In the NIFI Status History > Process Groups ID section, specify the IDs of the process groups that will be monitored and separated by a comma if there are several.

After the configuration is complete, click next and the creation will finish successfully
![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_success.png)

Repeat the configuration process for each resource you need to monitor.

Example of the 3 resources created independently
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

1. Direct sending: You must start the NIFI processes [How to enable data sending?](#Enabling-the-sending-of-data)
2. Splunk Data Input NiFi: The configured data inputs must be enabled.