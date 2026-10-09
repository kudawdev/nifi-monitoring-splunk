# Instance Lookup

Configure this regardless of app version or collection strategy. The
inventory gives each instance its cluster and, optionally, thresholds of its
own, and it is what makes an instance that has never sent data show as
*No data* instead of missing. Without it, instances that send data still
show up, with cluster "—" and the app-wide thresholds.

Requires [NIFI Monitoring installed](installation.md).

Open the **Nifi Monitoring** app (not the TA). In the app menu, go to **Configuration > NiFi Instances**. This opens
the lookup editor on the `instance` lookup:

![image](/nifi-monitoring-splunk/assets/images/splunk/instance_lookup_editor.png)

To find the exact host values to enter, run (last 60 minutes):

```
index=* sourcetype=nifi* | dedup host | table host
```

![image](/nifi-monitoring-splunk/assets/images/splunk/sourcetype_search.png)

!!! note "No results in that search?"
    The NiFi processes have to already be sending data for this search to
    return anything:

    1. Push strategy: start the NiFi flow — see [Start the flow](config-nifi-monitoring-2-0-push.md#5-start-the-flow).
    2. Pull strategy: the configured data inputs must be enabled.

Add one row per host, with the cluster it belongs to. The Overview picks a
new row up on its next refresh.

The other columns are optional thresholds for that instance alone — leave
them empty to use the app-wide default:

| Column | Default | Meaning |
|---|---|---|
| `heap_threshold`, `heap_threshold_critical` | 85, 95 | % of max heap for degraded, critical |
| `repo_threshold`, `repo_threshold_critical` | 80, 90 | % of a repository's volume for degraded, critical |
| `backpressure_threshold` | 80 | % of a connection's limit |
| `bulletin_threshold` | 5 | ERROR bulletins in 15 minutes that fire the bulletin alert |

A NiFi whose content repository sits at 85% by design, for example, gets
`repo_threshold` 92 and stops showing as degraded, while the rest keep
the default. The defaults themselves are macros; see
[Thresholds](references.md#thresholds).

The [Overview](overview.md#overview) then lists every row — an instance
that has not sent anything yet shows as *No data* rather than missing.

Next: pick your version and collection strategy in the sidebar, under
**Configure Nifi Monitoring 1.2** or **Configure Nifi Monitoring 2.0**.
