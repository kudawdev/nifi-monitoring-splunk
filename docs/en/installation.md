# Install and configure of NIFI Monitoring App

In this section the necessary steps required to install and configure the NIFI Monitoring application will be detailed.

## Install NIFI Monitoring APP

NIFI Monitoring is designed to be installed in Standalone or Cluster type environments.

The application contains all the visual features that allow the monitoring of the configured NIFI instances.

To install you must have the NIFI_Monitoring_(version).tar.gz file and install from the Splunk application manager.

![image](/assets/images/splunk/upload_app.png)

## Install NIFI Monitoring TA

The Technology Addon (TA) of NIFI Monitoring contains all the non-visual characteristics that allow the indexing of the different data sources received from the NIFI server 

To install you must have the NIFI_TA_Monitoring_(version).tar.gz file and install from the Splunk application manager.

![image](/assets/images/splunk/upload_app.png)

After installation, all the objects that allow data indexing will be available.

![image](/assets/images/splunk/ta_objects.png)

## Configure HTTP Event Collector (HEC)

It is fundamental to incorporate the configuration of an HTTP Event Collector (HEC). This allows event to be sent from NIFI instances to a Splunk implementation over the HTTP or HTTPS protocols.

To configure, from the Splunk menu select Settings > Data Inputs. In the Local Inputs list, identify the HTTP Event Collector and add a new one.

In the configuration process you must:

- Assign a name for the data input,
- Set the sourcetype to automatic,
- Select the App Context NIFI Monitoring and finally
- Select the Index where the data will be stored.

It is recommended to use a dedicated Index, for example nifi. If it does not exist, you must create it previous to this configuration.

At the end of the configuration of this Event Collector, a Token Value will be created, which is necessary to later configure the sending of data from NIFI.

Configuration process:

![image](/assets/images/splunk/add_hec_1.png)

![image](/assets/images/splunk/add_hec_2.png)

![image](/assets/images/splunk/add_hec_3.png)

## Lookup NIFI Instances Configuration

The configuration of the maintainer lookup of monitored instances is essential. The cluster tag is to associate a group of nodes and host is the name of the instance.
This step is very important for the correct operation of the application since if a new nifi node is not updated in the instance table the respective information will not be displayed.

![image](/assets/images/splunk/lookup_1.png)

To get the host name, you can run the following search with a time range of last 60 minutes. For this search to return results, the Nifi processes must be running correctly. [How to run a NIFI process?](/en/configuration/#enabling-the-sending-of-data)

```sourcetype=nifi* | dedup host | table host ```

The result of this search will return the list of hosts that must be configured in the lookup.

![image](/assets/images/splunk/sourcetype_search.png)

If the lookup is correctly configured, the information will be accessible from the Overview panel.

![image](/assets/images/splunk/nifi_overview_lookup.png)