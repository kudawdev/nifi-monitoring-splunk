---
title: Pull input reference
---

# Pull input reference

Every field of the TA's input form, one section per group in the order the
form shows them, plus the custom endpoints. For a first setup you need only
a few of them — [Pull strategy (2.0)](config-nifi-monitoring-2-0.md) walks
through those; come here for the rest.

The TA polls NiFi's REST API on an interval and writes what it gets
back. **Nothing gets configured inside NiFi for this strategy** — no
processors, no parameter context or variables, no controller services,
no reporting tasks. NiFi stays exactly as it is; everything below
happens on the Splunk side. Not sure this is the strategy you need? See
[Choosing a collection strategy](compatibility.md#choosing-a-collection-strategy).

*This strategy is what NiFi instances with at least basic authentication
must use.*

Requires **Nifi Monitoring TA** already installed (see
[Install NIFI Monitoring](installation.md)).

Go to **Apps > NiFi TA Monitoring > Inputs** and click **Create New
Input**. One input covers a whole NiFi instance (or a whole cluster,
pointed at any node — see
[Compatibility](compatibility.md#topology-standalone-multiple-instances-or-cluster));
create one per instance you want to monitor.

**Steps 1 through 3 are enough for a basic setup.** Steps 4 through 8
are collapsed in the form itself — optional, come back to them only if
you need that specific feature.

!!! note "Splunk's generic screen also works, but avoid it"
    *Settings > Data inputs > NiFi* writes the same `inputs.conf` and runs
    the same validation on save, but has neither the grouped form nor the
    Test connection from step 2, and it stores the password in clear text
    in `inputs.conf` instead of in Splunk's password storage.

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
- **Test connection**: next to the credentials, performs the same two
  calls the input performs -- the login and `GET /system-diagnostics` --
  with the values currently on screen, and says what came back, without
  saving anything.

## 3. Endpoints

Three checkboxes, all on by default:

- **Flow status** — `GET /flow/status`. The summary counters every
  dashboard panel is built on.
- **System diagnostics** — `GET /system-diagnostics`. Heap, threads,
  repository usage and the NiFi and Java versions the views show. Turning
  it off leaves those columns empty. The add-on still reads the NiFi
  version now and then to choose its endpoints, without indexing it.
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
  `NIFI,JVM`. Empty collects all of them. The known names are `NIFI`,
  `JVM`, `BULLETIN`, `CONNECTION` and `CLUSTER`, plus `VERSION_INFO`, which
  is only requested from NiFi 2.x; any other name is refused at save.
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

### Getting a certificate for the CA bundle

Skip this if NiFi's certificate is already signed by a CA the operating
system trusts -- leave *CA bundle path* empty and go to
[Advanced](#8-advanced).

Otherwise, export the certificate NiFi presents and hand it to Splunk as
its own CA, which is what a private CA setup looks like in practice:

1. Get the certificate from NiFi itself, from any machine that can reach
    it (replace `<nifi-host>` and `<port>` with the values from step 1):

    ```
    openssl s_client -connect <nifi-host>:<port> -servername <nifi-host> \
      </dev/null 2>/dev/null | openssl x509 > nifi-ca.pem
    ```

2. Copy it onto the Splunk server, into the TA's `local` directory, owned
    by the user Splunk runs as (commonly `splunk`):

    ```
    sudo install -o splunk -g splunk -m 0644 nifi-ca.pem \
      /opt/splunk/etc/apps/nifi_TA_monitoring/local/nifi-ca.pem
    ```

    `install` creates any missing directory with the right owner in one
    step. Creating that directory yourself first -- a plain `mkdir`, or
    anything run as `root` -- leaves it owned by `root`, and Splunk, which
    runs as its own user, then cannot write anything else into it either,
    including this input's own credentials: saving the input fails with
    `Data could not be written ... passwords.conf: Permission denied`.

3. Set **CA bundle path** to that same path,
    `/opt/splunk/etc/apps/nifi_TA_monitoring/local/nifi-ca.pem`.

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
  [instance lookup](instance-lookup.md).

Besides these eight groups, **Configuration > Logging** (outside the
input) sets how much the add-on writes to `splunkd.log` — `INFO` by
default, `WARNING` if you only care about problems.

## Custom endpoints

Optional — only if you need to poll a NiFi REST endpoint that is not on
the fixed list from step 3. Use the **Custom endpoints** section: one
line per endpoint, as `name,path` (e.g.
`queue_stats,/flow/connections/1234-5678-90ab-cdef/status`). The name takes
only letters, digits, `_`, `.` and `-`; the path starts with `/`, is
relative to the NiFi API URL configured above — not a full URL — and has
no whitespace. Anything else is refused at save.

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

After completing the form, click **Add** and the input is created.

Repeat this once for every NiFi instance you want to monitor.

Once an input is running, also configure the
[Instance Lookup](instance-lookup.md).
