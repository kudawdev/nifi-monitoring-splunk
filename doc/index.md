# Introduction

Nifi Monitoring centralizes operational visibility across multiple Apache
NiFi instances in Splunk — standalone or clustered — so you do not have to
watch each one separately. It ships as two apps: **Nifi Monitoring**, the
dashboards described in this guide, and **Nifi Monitoring TA**, the add-on
that gets NiFi's data into Splunk.

![image1](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

## About this product

- Supports multiple NiFi instances, either standalone or cluster nodes.
- Collects data from NiFi's logs, its REST API, and its reporting tasks.
- Two ways to get that data in — polling the API, or a flow inside NiFi
  pushing to Splunk's HTTP Event Collector. See
  [Compatibility and choosing a collection path](compatibility.md) to pick
  one.

This application requires the following dependencies:

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/)
- [Status Indicator - Custom Visualization](https://splunkbase.splunk.com/app/3119/)

## Where to go next

- [Compatibility and choosing a collection path](compatibility.md) — supported NiFi and Splunk versions, and which of the two collection paths fits your environment.
- [Install and configure NIFI Monitoring on Splunk](installation.md) — install both apps.
- [NIFI Configuration](configuration.md) — configure NiFi and the data input for the path you chose.
- [Data Reference](references.md) — what each sourcetype contains.

## Support

Its operation is completely free and you can contribute through the [GitHub repository](https://github.com/kudawdev/nifi-monitoring-splunk).

Write us at splunk.app@kudaw.com for an evaluation, or through our site [kudaw.com](https://www.kudaw.com/).