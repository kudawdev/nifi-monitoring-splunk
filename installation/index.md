# Install NIFI Monitoring

Both apps are required: **Nifi Monitoring TA** parses and indexes NiFi's data; **Nifi Monitoring** (the dashboards) depends on it, regardless of [collection strategy](https://kudawdev.github.io/nifi-monitoring-splunk/compatibility/#choosing-a-collection-strategy). Three apps are needed in total, all from the Splunk application manager (**Apps > Manage Apps > Install app from file**):

1. **Nifi Monitoring TA** — parses and indexes NiFi's data. Install this first: the dashboards have nothing to read without it. `nifi_TA_monitoring-<version>.tar.gz`, from [Splunkbase](https://splunkbase.splunk.com/app/6124) or a [GitHub release](https://github.com/kudawdev/nifi-monitoring-splunk/releases).
1. **Nifi Monitoring** — the dashboards, views, and lookups. `nifi_monitoring-<version>.tar.gz`, from [Splunkbase](https://splunkbase.splunk.com/app/6125) or the same GitHub releases page.
1. **[Lookup File Editor](https://splunkbase.splunk.com/app/1724/)** — required by the Instance Lookup screen. Since 2.0.0 the dashboards are Dashboard Studio and need no other visualization app; *Status Indicator* can be removed if nothing else uses it.

After installing the TA, its parsing and indexing objects are in place:

## Where to install, on a distributed deployment

On a single Splunk instance, install all three apps there and skip this section. On a distributed deployment, each piece goes where its configuration takes effect:

| Where                     | What                                                                            | Why                                                                                                                                                                                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Search head               | Nifi Monitoring, Nifi Monitoring TA, Lookup File Editor                         | The dashboards, alerts and lookups, and the TA's search-time fields.                                                                                                                                                                                      |
| Where the pull inputs run | Nifi Monitoring TA                                                              | The inputs live in the TA, and the API sourcetypes are parsed there (`INDEXED_EXTRACTIONS = json`), not on the indexers. That instance needs to reach NiFi's REST API.                                                                                    |
| Indexers                  | The `nifi` index; Nifi Monitoring TA if a Universal Forwarder sends NiFi's logs | The index is in the app's `default/indexes.conf`, which the search head does not pass on: deploy it to the indexers too. The log sourcetypes break lines and read timestamps where they are first parsed — the indexers, or a heavy forwarder in between. |
| NiFi hosts (optional)     | A Universal Forwarder with the same Nifi Monitoring TA package                  | Only for NiFi's log files — see [Setting up the Universal Forwarder](https://kudawdev.github.io/nifi-monitoring-splunk/compatibility/#setting-up-the-universal-forwarder).                                                                                |

Run the pull inputs on a heavy forwarder or a standalone search head. Not on a search head cluster: every member would run every input and index each NiFi's data more than once.

On **Splunk Cloud**, check that the `nifi` index exists (**Settings > Indexes**) and create it if it does not.

Next: [Instance Lookup](https://kudawdev.github.io/nifi-monitoring-splunk/instance-lookup/index.md).
