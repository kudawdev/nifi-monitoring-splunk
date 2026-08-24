# Install and configure of NIFI Monitoring App

In this section the necessary steps required to install and configure the NIFI Monitoring application will be detailed.

## Install NIFI Monitoring APP

NIFI Monitoring is designed to be installed in Standalone or Cluster type environments.

The application contains all the visual features that allow the monitoring of the configured NIFI instances.

This application requieres the implementation of the following dependencies;

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/)
- [Status Indicator - Custom Visualization](https://splunkbase.splunk.com/app/3119/)

To install you must have the NIFI_Monitoring_<version\>.tar.gz file and install from the Splunk application manager.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

## Install NIFI Monitoring TA

The Technology Addon (TA) of NIFI Monitoring contains all the non-visual characteristics that allow the indexing of the different data sources received from the NIFI server 

To install you must have the NIFI_TA_Monitoring_<version\>.tar.gz file and install from the Splunk application manager.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

After installation, all the objects that allow data indexing will be available.

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_objects.png)