# Compatibility and choosing a collection path

## Supported versions

| | Supported | Tested in CI |
|---|---|---|
| Apache NiFi | 1.16 – 1.28.1, 2.0 – 2.11 | 1.23.2, 1.28.1, 2.0.0, 2.11.0 |
| Splunk Enterprise / Cloud | 9.0 – 10.x | 9.4, 10.4 |

NiFi 1.x reached end of life on 2024-12-08 with 1.28.1. It still works with
these apps, but every security fix from the project now lands only on the 2.x
line.

The floor is NiFi 1.16 because that is where `/flow/metrics/json` appears.
Older 1.x instances work without the flow-metrics endpoint; that combination
is not covered by CI.

## Cluster and multiple instances

| Topology | Supported | What you configure |
|---|---|---|
| One instance | yes | one input |
| Several independent instances | yes | one input each, one row each in the `instance` lookup |
| A NiFi cluster | yes | **one input**, pointed at any node |

A cluster is one instance to the app, not several. Point the input at any
node: NiFi answers cluster-wide from all of them. The add-on works out on its
own that it is talking to a cluster and collects the per-node data as well --
there is nothing to enable.

That means events keep the `host` you configured, which is the cluster, and
carry a `node` field saying which member they describe. Existing searches and
panels are unaffected; the Cluster row of the **Nifi TA Monitoring** dashboard
shows members, roles and per-node heap, because the aggregate hides the node
that is running out of it.

Two things only a cluster has:

- **Bulletins carry the node that raised them**, and framework bulletins
  (categories like *Clustering* or *Primary Node*) describe the cluster rather
  than a component, so they have no source name.
- **On the push path the flow runs on the primary node only** for the parts
  that poll the API, so a cluster does not send one copy per node. Log tailing
  still runs everywhere, because log files are per node. This is handled by
  the flow as distributed; nothing to configure.

## Two ways to get data in

Pick one. Running both duplicates every event.

### Pull — the TA polls NiFi's REST API

Splunk asks NiFi for data on an interval. **Prefer this one.** There is
nothing to install or maintain inside NiFi, one input covers every supported
version, and Splunk controls the interval, the index and the retries.

Requires Splunk to reach NiFi's API. Works with an unauthenticated NiFi and
with one behind single-user or LDAP authentication.

### Push — a flow inside NiFi sends to the HEC

NiFi sends data to Splunk's HTTP Event Collector. Use this when **Splunk
cannot reach NiFi** — NiFi in a DMZ, or a network that only allows outbound
connections from it.

The cost is a process group of 39 processors, three reporting tasks and two
Site-to-Site input ports to maintain inside your NiFi, and a separate flow
file per NiFi major version.

### What each one gives you

| | Pull (TA) | Push (flow) |
|---|---|---|
| Flow status, diagnostics, status history | yes | yes |
| Flow metrics (`/flow/metrics`) | yes | no |
| NiFi version detection | yes | no |
| Individual bulletins | yes, by polling | yes, without loss |
| `bulletinGroupName` / `bulletinGroupPath` | no | yes |
| NiFi log files | via Universal Forwarder | via the flow |
| To install inside NiFi | nothing | 39 processors + 3 reporting tasks |

Bulletins are the one place the push path is genuinely better: a reporting
task pushes each bulletin, while polling reads a board that only holds a
short window, so an interval longer than that window loses events. The input
warns when a poll comes back full, which is the sign that is happening.

## Logs

Both paths can collect NiFi's log files, and the recommendation is neither of
them: use a **Universal Forwarder** on the NiFi host. The TA already ships
the monitor inputs, disabled; enable the ones you need and correct the path.

A forwarder handles rotation and keeps its own checkpoint, and if Splunk is
unreachable it queues on disk instead of backing pressure up into the flow
that NiFi is also using for real work.

`TailFile` inside the flow stays supported for the case where a forwarder is
not an option — NiFi in a container where you cannot add a sidecar.

The TA defines five log sourcetypes. `nifi:log:deprecation` is worth enabling
before a move to NiFi 2.x: it records which deprecated components the
instance is still using.
