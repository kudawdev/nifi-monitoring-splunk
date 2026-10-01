# Introduction

**Nifi Monitoring** centralizes, in Splunk, the operational visibility of
your Apache NiFi instances — a single one, several independent ones, or a
cluster. In one place you get:

- **Flow status**: running, stopped or invalid processors, and queued
  data.
- **System diagnostics**: heap, threads and repository disk usage, per
  node.
- **Bulletins**: the errors and warnings NiFi generates, traceable back
  to the component that raised them.
- **NiFi's logs** (optional, via a Universal Forwarder): app, bootstrap,
  user and request logs, searchable without a terminal on every host.
- **Flow metrics** (optional): throughput and per-component detail.
- **Cluster visibility**: each node's role and heap, without opening
  every node separately.

Data arrives one of two ways: Splunk polling NiFi's API (**pull**, the
recommended one), or NiFi sending straight to Splunk's HEC (**push**, for
when Splunk cannot reach NiFi). See
[Compatibility and collection strategy](compatibility.md) to pick the one
you need.

It ships as two apps:

- **Nifi Monitoring** — the dashboards (this guide).
- **Nifi Monitoring TA** — the add-on that gets NiFi's data into Splunk.

![image](/nifi-monitoring-splunk/assets/images/splunk/view_overview.png)

## Dependencies

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/), to edit the instance inventory.

Next: [Compatibility and collection strategy](compatibility.md) —
the first decision to make before installing anything.

## Support

Free and open source — [contribute or file issues on GitHub](https://github.com/kudawdev/nifi-monitoring-splunk), or write splunk.app@kudaw.com for an evaluation.
