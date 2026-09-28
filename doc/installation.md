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

## Instance Lookup

Configure this regardless of collection strategy — without it, no
dashboard panel shows data.

Go to Configuration > NiFi Instances to access the Lookups configuration
view.

![image](/nifi-monitoring-splunk/assets/images/splunk/1_configure_instances.png)

Complete the information in the fields, where the cluster label is to
associate a group of nodes and host is the name of the instance.

![image](/nifi-monitoring-splunk/assets/images/splunk/2_configure_instances.png)

To obtain the name of the host, execute the following search with a time
range of the last 60 minutes.

**Splunk Query**  
```index=* sourcetype=nifi* | dedup host | table host ```

![image](/nifi-monitoring-splunk/assets/images/splunk/sourcetype_search.png)

The result of this query will return the list of hosts that must be
configured in the lookup.

!!! note "No results in that search?"
    The NiFi processes have to already be sending data for this search to
    return anything:

    1. Push strategy: start the NiFi flow — see [Start the flow](configuration-push.md#5-start-the-flow).
    2. Pull strategy: the configured data inputs must be enabled.

    ![image](/nifi-monitoring-splunk/assets/images/splunk/4_configure_instances.png)

Once the lookup has a row for each host, the information becomes
accessible from the Overview panel.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview_lookup.png)

![image](/nifi-monitoring-splunk/assets/images/splunk/3_configure_instances.png)

Next: pick your version and collection strategy in the sidebar, under
**Configure Nifi Monitoring 1.2** or **Configure Nifi Monitoring 2.0**.
