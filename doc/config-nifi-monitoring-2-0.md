# Installation and Configuration v2.0.0

Step-by-step setup on the Splunk side, from the apps already installed to
working dashboards. This page assumes the **pull** strategy (the TA
polling NiFi's REST API) — the default and recommended one. For **push**,
see [Push strategy: Direct Sending](configuration-push.md) instead.

Not sure which strategy you need? See
[Choosing a collection strategy](compatibility.md#choosing-a-collection-strategy)
before you start.

**Requirement**: all four apps installed — see
[Install NIFI Monitoring](installation.md).

## 1. Create the TA input

Go to **Apps > NiFi TA Monitoring > Inputs**.

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_inputs_empty.png)

Click **Create New Input**. One input covers a whole NiFi instance, or a
whole cluster pointed at any node — see
[Topology](compatibility.md#topology-standalone-multiple-instances-or-cluster).
Create one per instance you monitor.

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_input_form.png)

Fill in, at minimum:

- **NiFi instance name** — a unique name, used as the `host` value on every
  event from this input.
- **NiFi API URL** — e.g. `https://<address>:<port>/nifi-api/`.
- **Authentication** — `None`, or `Username and password` if NiFi has basic
  authentication enabled. Use **Test connection** to check the credentials
  before saving.
- **TLS** (collapsed section, only matters over HTTPS) — leave **Verify the
  TLS certificate** on unless NiFi's certificate cannot be trusted through a
  CA bundle. If it's self-signed, get it and point **CA bundle path** at it —
  see [Getting a certificate for the CA bundle](configuration-pull.md#getting-a-certificate-for-the-ca-bundle).

Then, under **Advanced**, set:

- **Index** — `nifi`, not the default. The app ships a dedicated `nifi`
  index (`nifi_monitoring/default/indexes.conf`), and every dashboard
  reads through the `index_nifi` macro, which points at `index=nifi` by
  default. Leaving this field at its default value breaks every panel.

Leave every other section (Endpoints, Status History, Flow metrics, Custom
endpoints) at its default for a first setup — see
[Pull strategy: Splunk Data Input NiFi](configuration-pull.md) for what each
one does.

Click **Next** to create the input.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_success.png)

It now shows up as a row under **Inputs**:

![image](/nifi-monitoring-splunk/assets/images/splunk/ta_inputs_created.png)

Repeat for every NiFi instance you want to monitor.

## 2. Configure the Instance Lookup

Same for any version — see
[Instance Lookup](instance-lookup.md).

Then go to **Nifi Monitor Overview**, in the **Nifi Monitoring** app, and
check that the configuration worked:

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_overview_check.png)

## 3. (Optional) Collect NiFi's log files

Everything above gets you flow status, diagnostics, and bulletins. NiFi's
own text log files (`nifi-app.log` and friends) are a separate, optional
step: install a Universal Forwarder on the NiFi host and point it at your
indexer. Full procedure:
[Setting up the Universal Forwarder](compatibility.md#setting-up-the-universal-forwarder).

## 4. (Optional) Accelerate the datamodel

Dashboards work without this — `tstats` falls back to a raw search when the
datamodel isn't accelerated. Turning acceleration on is the single biggest
thing you can do for panel latency, at the cost of a summary index:

1. **Settings > Data models > NIFI > Edit > Edit Acceleration**.
2. Check **Accelerate**, and pick a summary range. `-7d` is what the panels
   were designed around.

## Next

- Your collection strategy has fields not covered here (custom endpoints,
  flow metrics, log sourcetypes): [Pull strategy](configuration-pull.md) /
  [Push strategy](configuration-push.md).
- Sourcetype and field reference: [Data Reference](references.md).
