# Pull strategy: Splunk Data Input NiFi

The TA polls NiFi's REST API on an interval and writes what it gets back
— nothing runs inside NiFi. Not sure this is the strategy you need? See
[Choosing a collection strategy](compatibility.md#choosing-a-collection-strategy).

*This strategy is what NiFi instances with at least basic authentication
must use.*

Requires **Nifi Monitoring TA** already installed (see
[Install NIFI Monitoring](installation.md)) — that is the app this
whole page configures.

Go to **Apps > NiFi TA Monitoring > Inputs** and click **Create New
Input**. There you fill in the eight field groups described below — one
input per NiFi instance you want to monitor.

**One input covers a whole NiFi instance** (or a whole cluster, pointed
at any node — see [Compatibility](compatibility.md#topology-standalone-multiple-instances-or-cluster)).
You don't need a separate input per endpoint: everything for that
instance — which endpoints to poll, which processors and process groups
to track, TLS, the interval — lives on the same form.

!!! note "Splunk's generic screen also works, but avoid it"
    *Settings > Data inputs > NiFi* writes the same `inputs.conf`, but has
    none of the grouped form, the field validation or the **Test
    connection** described below.

Two more things worth knowing, outside the eight groups:

- **Configuration > Logging**, outside the input itself, sets how much the
  add-on writes to `splunkd.log`. It is `INFO` by default, which is one line
  per request per endpoint per interval. On an instance polling several
  NiFis that is most of what the add-on puts in `_internal`; `WARNING` keeps
  the problems and drops the rest.
- **Test connection**, inside the input form next to the credentials,
  performs the same two calls the input performs -- the login and
  `GET /system-diagnostics` -- with the values currently on screen, and says
  what came back. It saves nothing. Getting a NiFi input right means getting
  the URL, the scheme, the certificate and the credentials right at the same
  time; without this they all fail the same way, some minutes later, in a
  log.

## 1. NiFi instance

- **NiFi instance name**: a unique name for this input. Used as the `host`
  value stamped on every event unless you set one explicitly under
  *Advanced*.
- **NiFi API URL**: the instance's REST API, e.g.
  `https://<address>:<port>/nifi-api/`.

## 2. Authentication

- **Authentication**: `None`, or `Username and password` when NiFi has
  basic authentication enabled. `Username and password` performs
  `POST /access/token` and sends the JWT it gets back on every following
  request.
- **Username** / **Password**: required unless Authentication is `None`.
- **Test connection**: see above.

## 3. Endpoints

Three checkboxes, all on by default:

- **Flow status** — `GET /flow/status`. The summary counters every
  dashboard panel is built on.
- **System diagnostics** — `GET /system-diagnostics`. Heap, threads and
  repository usage. This is also how the add-on detects the NiFi version,
  so turning it off disables version reporting.
- **Bulletin board** — `GET /flow/bulletin-board`. Individual bulletins,
  polled with a cursor so nothing is counted twice. The board only keeps a
  short window, so an interval longer than that window can miss bulletins.

## 4. Status history

Collapsed by default. Two fields, each comma- or newline-separated and
empty by default (collecting nothing until filled in):

- **Processor IDs**: UUIDs of the processors to collect status history for.
- **Process group IDs**: UUIDs of the process groups to collect status
  history for.

## 5. Flow metrics

Collapsed by default, and off by default even once expanded:

- **Collect flow metrics** — `GET /flow/metrics/json`. Requires NiFi 1.16
  or later. An idle NiFi emits around 60 samples per poll, and the
  `All components` strategy below scales that with the size of the flow, so
  review the volume before turning it on.
- **Registries**: comma-separated registry names to collect, e.g.
  `NIFI,JVM`. Empty collects all of them.
- **Strategy**: `All process groups` or `All components`. `All components`
  emits one sample per component, which is what multiplies the volume.
- **Sample filter**: a regular expression matched against the metric name.
  Empty keeps every sample.

## 6. Custom endpoints

Collapsed by default. Covers any NiFi REST path that is not on the fixed
list under *Endpoints* — see [Custom endpoints](#custom-endpoints) below.

## 7. TLS

Collapsed by default:

- **Verify the TLS certificate**: on by default. Leave it on unless NiFi
  uses a certificate that cannot be trusted through a CA bundle. Turning it
  off lets anyone able to intercept the connection read the credentials and
  the token.
- **CA bundle path**: only shown while *Verify the TLS certificate* is on.
  A path such as
  `/opt/splunk/etc/apps/nifi_TA_monitoring/local/nifi-ca.pem`. Empty uses
  the system trust store.

## 8. Advanced

Collapsed by default:

- **Interval**: seconds between polls, `60` by default. Every enabled
  endpoint, including the custom ones, is collected on this interval.
- **Index**: the destination index. A dedicated index is recommended, for
  example `nifi`. If it does not exist, create it first.
- **Host field value**: stamped on every event from this input. Empty uses
  the NiFi instance name above. **On a cluster, set this to the cluster,
  not a node** — the add-on names the node in a separate field. This is
  also the value that must match a row in the
  [instance lookup](configuration.md#instance-lookup).

## Custom endpoints

The fixed list under *Endpoints* covers what the app ships with. If you need
to poll a NiFi REST endpoint that is not on that list, use the **Custom
endpoints** section instead: one line per endpoint, as `name,path` (e.g.
`queue_stats,/flow/connections/1234-5678-90ab-cdef/status`). The path is
relative to the NiFi API URL configured above.

You name the endpoint; the add-on gives it the sourcetype. `queue_stats` is
indexed as `nifi:api:custom:queue_stats`, so everything you declare is
searchable as `nifi:api:custom:*` and nothing you declare can land in a
sourcetype the add-on itself writes. Splunk indexes the raw response; if you
need field extraction for it, add your own `props.conf` stanza for that
sourcetype.

Four things worth knowing before you rely on one:

- **A name, not a sourcetype.** `nifi:api:flow_status` and anything else
  outside `nifi:api:custom:` is refused at save time: a custom endpoint
  writing into a shipped sourcetype would mix its response into the data
  the dashboards read, and nothing downstream could tell the two apart.
  Writing the full `nifi:api:custom:queue_stats` is accepted and means the
  same as `queue_stats`.
- **`{id}` placeholders are not supported.** Unlike the Status History
  fields above, a custom path is requested literally. Write the UUID out.
  The input refuses to save a path containing `{` or `}` rather than
  letting it fail at poll time.
- **A failed request indexes nothing.** If NiFi answers 4xx or 5xx, the
  add-on logs it to `splunkd.log` and writes no event, so an empty
  sourcetype means the endpoint is not working — the error body is never
  indexed as if it were data.
- **Editing `inputs.conf` by hand needs a trailing backslash.** The
  textarea takes one endpoint per line, but a `.conf` file ends a value at
  the first unescaped newline. When you write the stanza yourself — a
  deployment server, for instance — continue each line with `\`:

```
custom_endpoints = queue_stats,/flow/connections/1234-5678-90ab-cdef/status\
cluster,/controller/cluster
```

  Indenting the continuation instead is silently ignored: Splunk keeps the
  first endpoint and drops the rest. `splunk btool inputs list` shows what
  actually took effect.

After completing the form, click **Next** and the input is created.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_success.png)

Repeat this once for every NiFi instance you want to monitor.

!!! note "The screenshot below is from before 2.0.0"
    It shows the three separate inputs the add-on used to require —
    endpoints, processor status history and process-group status history —
    instead of the single grouped input described above. Recapturing it is
    pending; what to expect today is one row per NiFi instance under
    **Data Inputs > NiFi**, not three.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_4.png)

Once an input is running, also configure the
[Instance Lookup](configuration.md#instance-lookup).
