# Upgrading to 2.0.0

2.0.0 adds NiFi 2.x support. It is a major release and it changes defaults
that an existing installation depends on. Read this before upgrading.

## Breaking changes

### The app looks in one index, not every index

The `index_nifi` macro was `index=*`, which made every panel and the
datamodel acceleration scan every event index on the instance. It now points
at `index=nifi`, and the app ships that index.

**If your NiFi data is somewhere else, every dashboard will be empty.** Do
not guess where: open **Internal Monitoring**, which reports how many events
the macro can see and which indexes actually hold NiFi data. Then override
the macro in `local/macros.conf`:

```
[index_nifi]
definition = index=your_index
```

### TLS certificates are verified

Every request the TA made used to accept any certificate presented by NiFi.
Over HTTPS that lets anyone able to intercept the connection read the
username, the password and the bearer token — and NiFi 2.x serves HTTPS by
default.

Verification is now on, including for inputs saved before the option
existed. **An input pointing at a NiFi with a self-signed certificate will
stop connecting.** The error says what to do; you have two options:

- point **CA bundle path** at a bundle that trusts the certificate, or
- clear **Verify TLS certificate**, accepting an unverified connection.

### `nifi:api:site_to_site` is no longer collected

It was polled on every cycle and no dashboard, datamodel object or saved
search ever read it. If you built something on that sourcetype, it stops
receiving new events; already-indexed data is unaffected. The input logs a
warning once if it finds the old setting still in `inputs.conf`.

### Datamodel acceleration ships off -- turn it on

Splunkbase does not accept an app that distributes an accelerated datamodel,
so the NIFI model ships with `acceleration = false`. The dashboards still
return the right numbers, because `tstats ... from datamodel=NIFI.*` falls
back to a raw search, but they get slower as the index grows.

Turning acceleration on is the single biggest thing you can do for panel
latency:

1. Go to **Settings > Data models**.
2. Select **NIFI**, then **Edit > Edit Acceleration**.
3. Tick **Accelerate** and pick a summary range. The app ships
   `acceleration.earliest_time = -7d`, which is the range the panels were
   designed around.

The cost is one tsidx summary per bucket in that range. Shorten the range if
storage matters more to you than history.

### The flow definition is split by NiFi version

`flow_definition/` now holds `nifi-1.x/` and `nifi-2.x/`. If you use the push
path, import the one matching your NiFi. See
[Compatibility](compatibility.md).

The XML template moved to `nifi-1.x/`. NiFi 2.x removed template support.

## What to do, in order

1. Note which index your NiFi data is in, from **Internal Monitoring** on the
   current version, or `| tstats count where index=* sourcetype=nifi:* by index`.
2. Upgrade both apps. They must be on the same version.
3. If your index is not `nifi`, override `index_nifi` as above.
4. Check each NiFi input: if it targets an HTTPS NiFi, set the CA bundle or
   turn verification off.
5. Remove `endpoint_site_to_site` from your inputs if it is there.
6. Only if you use the push path: re-import the flow for your NiFi version
   and move the settings into the parameter context (2.x) or variables (1.x).

## New in this release

- **NiFi 2.x support**, from one input. The TA detects the version and adapts.
- **Flow metrics** from `/flow/metrics/json`, off by default — an idle NiFi
  emits around 60 samples per poll and `ALL_COMPONENTS` scales that with the
  flow, so review the volume before enabling it.
- **Bulletins without a reporting task**, by polling the bulletin board.
- **`nifi:log:deprecation`**, which records the deprecated components an
  instance still uses. Enable it before planning a move to NiFi 2.x.
- **`nifi:log:request`**, NiFi's HTTP access log.
- An **inventory panel** showing each instance's NiFi version, Java version
  and which collection path its data arrived by.
