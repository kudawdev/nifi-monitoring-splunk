# Compatibility and collection strategy

This page answers two independent questions:

1. **Which NiFi and Splunk versions does this app support?** — [Version compatibility](#version-compatibility).
2. **How should data get from NiFi into Splunk?** — [Choosing a collection strategy](#choosing-a-collection-strategy): pull or push, and which one your deployment requires.

The collection strategy is independent of the NiFi version: decide it using the requirements below, not the version table above.

## Version compatibility

| | Supported | Tested in CI |
|---|---|---|
| Apache NiFi | 1.16 – 1.28.1, 2.0 – 2.11 | 1.23.2, 1.28.1, 2.0.0, 2.11.0 |
| Splunk Enterprise / Cloud | 9.0 – 10.x | 9.4, 10.4 |

- **NiFi 1.x reached end of life on 2024-12-08** (last release: 1.28.1). It still works with these apps, but new NiFi security fixes are published, from here on, only for the 2.x line.
- **The minimum supported version is NiFi 1.16**, because the `/flow/metrics/json` endpoint does not exist before it. Older 1.x instances still work, just without that flow-metrics endpoint; that combination is not covered by CI.

## Topology: standalone, multiple instances, or cluster

| Topology | Supported | What you configure |
|---|---|---|
| One instance | yes | One input. |
| Several independent instances | yes | One input per instance, one row per instance in the `instance` lookup. |
| A NiFi cluster | yes | **One input**, pointed at any node. |

A cluster counts as **one instance** to this app, not several: point the input at any node, and NiFi answers cluster-wide on its behalf. The add-on detects the cluster on its own and collects per-node data too — there is nothing to enable.

Events keep the `host` value you configured (the cluster's name) and add a `node` field naming the cluster member each event describes. On the **Nifi TA Monitoring** dashboard, the Cluster row breaks this down by member, role and per-node heap — the aggregate view alone would hide which node is actually running out of resources.

Two things exist only on a cluster:

- **Bulletins carry the node that raised them.** Framework bulletins (categories such as *Clustering* or *Primary Node*) describe the cluster itself rather than a component, so they have no source name.
- **On the push strategy, only the primary node polls the API.** A cluster does not send one copy of the same data per node. Log tailing still runs on every node, because log files are per node, not cluster-wide. This is handled by the flow automatically; there is nothing to configure.

## Choosing a collection strategy

Two mutually exclusive strategies get NiFi's data into Splunk.
**Pick exactly one per NiFi instance — running both on the same instance
duplicates every event.**

| | Pull | Push |
|---|---|---|
| What moves | Splunk's TA polls NiFi's REST API on an interval. | A flow inside NiFi calls its own API and sends the result to Splunk's HTTP Event Collector (HEC). |
| Network direction required | Splunk → NiFi | NiFi → Splunk |
| NiFi authentication supported | None, single-user, or LDAP | **None only** |
| What you install inside NiFi | Nothing | A process group (39 processors), 3 reporting tasks, 2 Site-to-Site input ports; one flow file per NiFi major version |
| Use when | Splunk can reach NiFi's API. **Default choice.** | Splunk cannot reach NiFi at all — NiFi in a DMZ, or on a network that only permits outbound connections from it |

!!! warning "Push requires an unauthenticated NiFi"
    The flow calls its own REST API without sending any credentials. If
    your NiFi has single-user, LDAP or any other login enabled, that call
    fails with 401 — and no setting fixes it, because the flow was never
    built to authenticate. Use pull instead.

### Feature comparison

| | Pull | Push |
|---|---|---|
| Flow status, diagnostics, status history | yes | yes |
| Flow metrics (`/flow/metrics`) | yes | no |
| NiFi version detection | yes | no |
| Individual bulletins | yes, by polling | yes, without loss |
| `bulletinGroupName` / `bulletinGroupPath` | no | yes |
| NiFi log files | via Universal Forwarder (see below) | via the flow |

Bulletins are the one place push is genuinely better: a reporting task
pushes each bulletin as it happens, while polling reads a board that only
holds a short window — an interval longer than that window loses events.
The input logs a warning when a poll comes back full, which is the sign
that this is happening.

## Collecting NiFi's log files

Independent of pull vs push: both strategies *can* collect NiFi's log
files, but the recommendation is neither of them. **Use a Universal
Forwarder on the NiFi host.** The TA ships the monitor inputs for this
already, disabled by default — enable the ones you need and correct the
path.

A forwarder handles log rotation and keeps its own checkpoint, and if
Splunk becomes unreachable it queues on disk instead of applying
backpressure to the same flow NiFi uses for real work.

`TailFile` inside the flow remains supported for when a forwarder is not
an option — NiFi running in a container you cannot add a sidecar to, for
example.

The TA defines five log sourcetypes. Enable `nifi:log:deprecation` before
moving to NiFi 2.x: it records which deprecated components the instance
is still using.
