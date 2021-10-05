# NIFI Configuration

At this stage, all the necessary steps that must be carried out by the side of our nifi instances that are to be monitored will be detailed.

There are two ways of configuration that allow the sending of events to Splunk and their choice depends on the authentication mechanisms that NIFI has enabled.

- Direct sending: This configuration will establish NIFI as the main way to send data to Splunk and should be used when NIFI does not have authentication methods enabled.

- Data Input NIFI: Splunk will be in charge of making requests to the NIFI instances to retrieve the information from the Monitoring API by enabling and using the Data Input NIFI. This configuration should be used when NIFI has basic authentication.


## Load Template

You can upload the template from the Operate side box or by right clicking on an empty area and selecting the Upload template option.

![image](/nifi-monitoring-splunk/assets/images/nifi/add_template.png)

In the pop-up window, search on your computer and select the template to use.

![image](/nifi-monitoring-splunk/assets/images/nifi/upload_template.png)

## Select Template

To use the template that was previously loaded, drag the template option from the menu to the work space. A pop-up window will open and select the template to use.

![image](/nifi-monitoring-splunk/assets/images/nifi/select_template.png)

![image](/nifi-monitoring-splunk/assets/images/nifi/choose_template.png)

The displayed template must have the following structure:

- The first view contains the process group Nifi_Monitoring_Splunk 

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_monitoring_process_group.png)

Inside it contains the following structure:

- API ingest
- Ingest Logs
- Ingest ReportingTask

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_monitoring_process_group_2.png)


## Global variables configuration

It is essential to configure global variables as they are imprescindible for their operation. To configure the parameters, right click on the Nifi_Monitoring_Splunk box > Variables.

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable.png)

A pop-up window will be displayed where you will have to configure the following parameters:

- nifi_path: Corresponds to the nifi server installation path (in case of a cluster, it must be installed in the same path on each node). Example: /home/nifi/nifi-1.10.0/
- splunk_hec: It is the address of the splunk server where the data input HTTP Event Collector was configured. Example: <splunk_host\>:8088
- splunk_hec_token: Token obtained when configuring [HTTP Event Collector](/en/installation/#configure-http-event-collector-hec).

![image](/nifi-monitoring-splunk/assets/images/nifi/set_variable_2.png)


## Components configuration

After configuring the variables, it is necessary to create the following components. To configure access Nifi Settings from the menu > Controller Settings

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

![image](/nifi-monitoring-splunk/assets/images/nifi/bulletin_reporting_task.png)

- SiteToSiteMetricsReportingTask: Internal reporting system that generates events as metrics are generated from the same environment and captured in a specific flow. The configuration should be as follows:

![image](/nifi-monitoring-splunk/assets/images/nifi/metrics_reporting_task.png)

Once the reporting tasks have been configured, you must start the execution by clicking start (►) on each of them.

![image](/nifi-monitoring-splunk/assets/images/nifi/nifi_settings_4.png)

## Enabling the sending of data

After completing the entire configuration process, start the process group execution. Right click on the process group and then Start.

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_1.png)

![image](/nifi-monitoring-splunk/assets/images/nifi/enable_sending_2.png)

If all the configuration was successful, the information will be sent to Splunk. For the data sent to splunk to be accessible from the application, you must have configured the [NIFI Instances Lookup](/en/installation/#lookup-nifi-instances-configuration)

## Data Input NIFI configuration

To configure the Data Input Nifi you must have completed the loading and selection of template, Configuration of Variables and Configuration of Components.

If you have completed the Enabling Data Sending step or if the process group is running, you will need to stop it. To do this, right click on the process group and then on Stop. This action will stop sending information to Splunk.

![image](/nifi-monitoring-splunk/assets/images/nifi/disable_sending_data.png)

### Disabling the Monitoring - API process group

Double click on the group and you should see the following view

![image](/nifi-monitoring-splunk/assets/images/nifi/disable_monitoring_api.png)

To disable Monitoring API, right click on the first box and then click Disable, the component should look like this:

![image](/nifi-monitoring-splunk/assets/images/nifi/disable_monitoring_api_2.png)

Once disabled, return to the previous view. Right click on an empty zone and then on leave group or on the bottom band in NiFi Flow.

![image](/nifi-monitoring-splunk/assets/images/nifi/leave_group.png)

### Data Input Nifi Configuration - Splunk

*This configuration should be applied when NIFI instances has at least basic authentication method*

In the splunk where the Nifi Monitoring application is installed, access the Home of the APP.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

Then go Settings > Data Inputs

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_1.png)

In the local data inputs, identify NiFi and then click + Add new

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_2.png)

The following form will be displayed. Check the More settings box to enable other relevant information fields in the settings.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_3.png)

- NiFi Instance Name: Set the NiFi instance name
- NiFi API URL: NiFi API Adress. Example: http://<host:port\>/nifi-api/
- Auth Type: Authentication type:
    - none: Without authentication
    - basic: Access with username and password credentials
- Interval: Time in seconds in which the requests to extract the information will be made.
- Host: Name of the nifi host, which must correspond to what is defined in the Settings Lookup. [See Instances Lookup](/en/installation/#lookup-nifi-instances-configuration)
- Index: Destination index for this data source. A dedicated index is recommended, for example: nifi. If it does not exist, you must create it beforehand.