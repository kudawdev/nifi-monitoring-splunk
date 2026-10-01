# Compatibility and collection strategy

This page answers two independent questions:

1. **Which NiFi and Splunk versions does this app support?** — [Version compatibility](#version-compatibility).
2. **How should data get from NiFi into Splunk?** — [Choosing a collection strategy](#choosing-a-collection-strategy): pull or push, and which one your deployment requires.

The collection strategy is independent of the NiFi version: decide it using the requirements below, not the version table above.

## Version compatibility

| | Supported | Tested in CI |
|---|---|---|
| Apache NiFi | 1.16 – 1.28.1, 2.0 – 2.11 | 1.23.2, 1.28.1, 2.0.0, 2.11.0 |
| Splunk Enterprise / Cloud | 9.4 – 10.x | 9.4, 10.4 |

- **NiFi 1.x reached end of life on 2024-12-08** (last release: 1.28.1). It still works with these apps, but new NiFi security fixes are published, from here on, only for the 2.x line.
- **The minimum supported Splunk is 9.4.** The dashboards are Dashboard Studio and use features — sparklines in tables, an input that picks its first result, a click that sets a token — verified on 9.4 and 10.4 and not on anything older.
- **The minimum supported version is NiFi 1.16**, because the `/flow/metrics/json` endpoint does not exist before it. Older 1.x instances still work, just without that flow-metrics endpoint; that combination is not covered by CI.

## Topology: standalone, multiple instances, or cluster

| Topology | Supported | What you configure |
|---|---|---|
| One instance | yes | One input. |
| Several independent instances | yes | One input per instance, one row per instance in the `instance` lookup. |
| A NiFi cluster | yes | **One input**, pointed at any node. |

A cluster counts as **one instance** to this app, not several: point the input at any node, and NiFi answers cluster-wide on its behalf. The add-on detects the cluster on its own and collects per-node data too — there is nothing to enable.

Events keep the `host` value you configured (the cluster's name) and add a `node` field naming the cluster member each event describes. The **Cluster** view breaks this down by member, role and per-node heap — the aggregate view alone would hide which node is actually running out of resources.

Two things exist only on a cluster:

- **Bulletins carry the node that raised them.** Framework bulletins (categories such as *Clustering* or *Primary Node*) describe the cluster itself rather than a component, so they have no source name.
- **On the push strategy, only the primary node polls the API.** A cluster does not send one copy of the same data per node. Log tailing still runs on every node, because log files are per node, not cluster-wide. This is handled by the flow automatically; there is nothing to configure.

## Choosing a collection strategy

Two mutually exclusive ways get NiFi's data into Splunk:

- **Pull**: Splunk's TA calls NiFi's REST API on an interval and writes
  what it gets back. Nothing runs inside NiFi.
- **Push**: a flow running inside NiFi calls NiFi's own API and sends the
  result to Splunk's HTTP Event Collector (HEC). Nothing on Splunk's side
  has to reach NiFi.

**Pick exactly one per NiFi instance — running both on the same instance
duplicates every event.**

### Which one to use

**Use pull, unless both of the following are true:**

1. Splunk genuinely cannot reach NiFi's API — NiFi sits in a DMZ, or on a
   network that only allows outbound connections from it.
2. Your NiFi has **no authentication enabled at all**. Push calls NiFi's
   own API without sending any credentials. If NiFi requires a login
   (single-user, LDAP, or anything else), that call fails with 401, and
   no setting fixes it — the flow was never built to authenticate.

If either of those does not hold for your environment, use pull: it is
the default choice, it works whether or not NiFi has authentication
enabled, and it requires installing nothing inside NiFi.

| | Pull | Push |
|---|---|---|
| Network direction required | Splunk → NiFi | NiFi → Splunk |
| NiFi authentication supported | None, single-user, or LDAP | **None only** |
| What you install inside NiFi | Nothing | A process group (39 processors), 3 reporting tasks, 2 Site-to-Site input ports; one flow file per NiFi major version |

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

### Setting up the Universal Forwarder

1. **Install a Universal Forwarder on the NiFi host.** Standard Splunk
    install — see
    [Splunk's own Universal Forwarder documentation](https://docs.splunk.com/Documentation/Forwarder)
    if you have not done this before.

2. **Install `nifi_TA_monitoring` on that same forwarder** — the same
    package you installed on the indexer/search head, not a different one.
    Copy it into the forwarder's `$SPLUNK_HOME/etc/apps/`, or push it
    through a deployment server if you manage the forwarder that way.

3. **Enable the log monitors you need and confirm the path.** Do not
    edit the TA's `default/inputs.conf` — put the changes in
    `$SPLUNK_HOME/etc/apps/nifi_TA_monitoring/local/inputs.conf` instead
    (create the file if it does not exist yet), and set `disabled = false`
    for each monitor you want, for example:

    ```
    [monitor:///opt/nifi/nifi-current/logs/nifi-app*.log]
    disabled = false
    sourcetype = nifi:log:app
    index = nifi

    [monitor:///opt/nifi/nifi-current/logs/nifi-deprecation*.log]
    disabled = false
    sourcetype = nifi:log:deprecation
    index = nifi

    [monitor:///opt/nifi/nifi-current/logs/nifi-user*.log]
    disabled = false
    sourcetype = nifi:log:user
    index = nifi

    [monitor:///opt/nifi/nifi-current/logs/nifi-bootstrap*.log]
    disabled = false
    sourcetype = nifi:log:bootstrap
    index = nifi

    [monitor:///opt/nifi/nifi-current/logs/nifi-request*.log]
    disabled = false
    sourcetype = nifi:log:request
    index = nifi
    ```

    These are the five sourcetypes the TA defines. Comment out or delete
    the stanza for any you don't need.

    The path above matches the official NiFi container image. A package
    install keeps its logs wherever `NIFI_HOME` points instead — check
    `nifi.properties` (`org.apache.nifi.bootstrap.ConfigurableLogging`) or
    just look for `nifi-app.log` on disk, and correct the `monitor://`
    path for every stanza you enable if it differs.

4. **Point the forwarder at the indexer.** In
    `$SPLUNK_HOME/etc/system/local/outputs.conf`:

    ```
    [tcpout]
    defaultGroup = default-autolb-group

    [tcpout:default-autolb-group]
    server = <indexer-host>:9997
    ```

    The indexer also needs receiving enabled on 9997 — **Settings >
    Forwarding and receiving > Configure receiving > New Receiving Port**
    if it is not already.

5. **Restart the forwarder**: `$SPLUNK_HOME/bin/splunk restart`.

6. **Verify from the indexer or search head**:

    ```
    index=* sourcetype=nifi:log:* | stats count by sourcetype
    ```

    A sourcetype with zero events either has nothing to log yet (`nifi:log:deprecation`
    on a quiet instance, for example) or still has the wrong path — check
    step 3 again before assuming the forwarder itself is broken.
