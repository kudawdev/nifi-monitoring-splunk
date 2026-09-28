# Install NIFI Monitoring

Both apps are required: **Nifi Monitoring TA** parses and indexes NiFi's
data; **Nifi Monitoring** (the dashboards) depends on it, regardless of
[collection strategy](compatibility.md#choosing-a-collection-strategy).
Four apps are needed in total, all from the Splunk application manager
(**Apps > Manage Apps > Install app from file**):

1. **Nifi Monitoring TA** — parses and indexes NiFi's data. Install this
   first: the dashboards have nothing to read without it.
   `nifi_TA_monitoring-<version>.tar.gz`, from
   [Splunkbase](https://splunkbase.splunk.com/app/6124) or a
   [GitHub release](https://github.com/kudawdev/nifi-monitoring-splunk/releases).
2. **Nifi Monitoring** — the dashboards, views, and lookups.
   `nifi_monitoring-<version>.tar.gz`, from
   [Splunkbase](https://splunkbase.splunk.com/app/6125) or the same
   GitHub releases page.
3. **[Lookup File Editor](https://splunkbase.splunk.com/app/1724/)** —
   required by the Instance Lookup screen.
4. **[Status Indicator - Custom Visualization](https://splunkbase.splunk.com/app/3119/)** —
   required by the status panels on the dashboards.

![image](/nifi-monitoring-splunk/assets/images/splunk/upload_app.png)

After installing the TA, its parsing and indexing objects are in place:

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_objects.png)

Next: [Instance Lookup](instance-lookup.md).
