# NIFI Monitoring for Splunk

## Overview

Nifi Monitoring is a solution that proposes to solve a great difficulty encountered
during the development of NIFI Projects and that corresponds to the complex process of monitoring the operation of different NIFI instances simultaneously.

This applications solves this problem centralizing all the information regarding the operation of the different components for various instances and has a set of panels that allow you to clearly and quickly view the operation of these instances.

## Requirements

- Splunk Enterprise or Splunk Cloud 9.0 – 10.x
- Apache NiFi 1.16 – 1.28.1 or 2.0 – 2.11
- NIFI TA Monitoring

And the following complements:

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/)
- [Status Indicator - Custom Visualization](https://splunkbase.splunk.com/app/3119/)

The exact versions covered by CI are in
[Compatibility](https://kudawdev.github.io/nifi-monitoring-splunk/compatibility/).

## Configuration

There are two ways to get data out of NiFi, and which one applies depends on
whether Splunk can reach NiFi and on how NiFi authenticates.

- **Pull** — the add-on's data input polls the NiFi REST API. This is the
  recommended path and the only one that works against an authenticated NiFi.
  No HEC needed.
- **Push** — a monitoring flow runs inside NiFi and sends to Splunk's HTTP
  Event Collector. Use it when Splunk cannot open a connection to NiFi. It
  **requires an unauthenticated NiFi**, because the flow calls NiFi's own API
  without credentials, so you need a HEC input enabled to receive it.

Both land on the same sourcetypes, so the dashboards do not care which one
you chose.

## Directories

### [nifi_monitoring]
Splunk application that mainly contains the visual features, plus other essential and configuration files for its operation.

### [nifi_TA_monitoring]
The technology add-on that processes and indexes the data coming from NiFi
servers. It is **generated**: `ucc-gen` builds it from `globalConfig.json` and
`package/` into `output/nifi_TA_monitoring/`, which is not versioned. Run
`./tests/build-ta.sh` before packaging or installing it.

### [flow_definition]
The monitoring flow that runs inside NiFi and pushes to Splunk's HEC,
versioned per NiFi line. `migrate_to_nifi2.py` generates the 2.x flow from the
1.x one, so edit the script rather than the JSON.

### [tests]
The test harness: unit tests with no dependencies, and an integration
environment that brings up NiFi and Splunk in Docker across ten scenarios.
See **Testing** below and [tests/README.md](tests/README.md).

### [doc]
Sources of the published documentation, built with mkdocs. Internal design
notes live in `docs/` and are not published.

## Testing

```
make build                            # generate the add-on into output/
make test                             # the unit suite
make validate                         # package both apps and run AppInspect
```

```
cd tests
./run.sh --list                       # the ten scenarios
./run.sh --list cluster               # everything about one of them
./run.sh nifi2-current                # bring it up, assert, tear down
./run.sh --bare cluster               # the environment only, to install by hand
```

A scenario is a NiFi version and architecture; a strategy is how the data
gets out of it, by the add-on pulling the REST API or by the flow pushing to
the HEC. Every scenario is covered against both. Full detail in
[tests/README.md](tests/README.md).

## Workflows

All four are manual (`workflow_dispatch`); none of them runs on push.

### dev.yml
AppInspect plus the unit tests.

### testing.yml
AppInspect plus the unit tests.

### main.yml
Version gate, AppInspect, unit tests, the integration matrix (one runner per
scenario) and a pre-release with both packages, tagged from `app.conf`.

### docs.yml
Builds the mkdocs site and publishes it.


## Splunkbase Apps

- [Nifi Monitoring for Splunk](https://splunkbase.splunk.com/app/6125)

- [Nifi Monitoring TA](https://splunkbase.splunk.com/app/6124)


## Full documentation
- [NIFI Monitoring for Splunk](https://kudawdev.github.io/nifi-monitoring-splunk/)

## Collaborate
NIFI Monitoring App is hosted in a Github repository where collaboration is always welcome.