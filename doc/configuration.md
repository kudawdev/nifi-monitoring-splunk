# NIFI Configuration

This page details the setup on the NiFi side, for the collection strategy
you already chose in [Choosing a collection strategy](compatibility.md#choosing-a-collection-strategy):

- Chose **push**? Go to [Push strategy: Direct Sending](configuration-push.md).
- Chose **pull**? Go to [Pull strategy: Splunk Data Input NiFi](configuration-pull.md).

Configure only one — running both duplicates every event.

## Common to both strategies

Configure this regardless of which strategy you use — without it, neither
one shows data in the app's panels.

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

No results in that search?

![image](/nifi-monitoring-splunk/assets/images/splunk/4_configure_instances.png)

For it to return any, the NiFi processes must be running correctly:

1. Push strategy: start the NiFi flow — see [Start the flow](configuration-push.md#5-start-the-flow).
2. Pull strategy: the configured data inputs must be enabled.
