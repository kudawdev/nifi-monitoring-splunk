# Install NIFI Monitoring

Both apps are required together: **Nifi Monitoring** (the dashboards) has
nothing to show without **Nifi Monitoring TA** installed as well — the TA
is what parses and indexes NiFi's data, regardless of which
[collection strategy](compatibility.md#choosing-a-collection-strategy) you
use.

This application also requires two third-party Splunkbase apps:

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/)
- [Status Indicator - Custom Visualization](https://splunkbase.splunk.com/app/3119/)

## Install NIFI Monitoring APP

Install `nifi_monitoring-<version>.tar.gz` — from [Splunkbase](https://splunkbase.splunk.com/app/6125) or a [GitHub release](https://github.com/kudawdev/nifi-monitoring-splunk/releases) — from the Splunk application manager.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

## Install NIFI Monitoring TA

The Technology Add-on (TA) contains everything non-visual: parsing, indexing, and the modular input that polls NiFi.

Install `nifi_TA_monitoring-<version>.tar.gz` — from [Splunkbase](https://splunkbase.splunk.com/app/6124) or a [GitHub release](https://github.com/kudawdev/nifi-monitoring-splunk/releases) — from the Splunk application manager.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

After installation, all the objects that allow data indexing will be available.

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_objects.png)

Next: [NIFI Configuration](configuration.md).
