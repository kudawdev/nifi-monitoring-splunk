# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repo is the source for two **published Splunkbase apps** (publisher: Kudaw SA, both currently at version **1.2.2**, compatible with Splunk Enterprise / Splunk Cloud 8.2–9.4):

- **Nifi Monitoring for Splunk** — https://splunkbase.splunk.com/app/6125 — built from `nifi_monitoring/`. The user-facing Splunk **app** (dashboards, views, datamodels, lookups, macros) that centralizes operational visibility across multiple NiFi instances. `app.conf` → `id = nifi_monitoring`, `is_visible = true`. Depends on two third-party visualizations from Splunkbase: **Lookup File Editor** (app 1724) and **Status Indicator - Custom Visualization** (app 3119).
- **Nifi Monitoring TA** — https://splunkbase.splunk.com/app/6124 — built from `nifi_TA_monitoring/`. The **technology add-on** that normalizes and indexes NiFi data. `app.conf` → `id = nifi_TA_monitoring`, `is_visible = false`. Contains `bin/nifi.py`, a Splunk *modular input* (subclass of `splunklib.modularinput.Script`) that polls the NiFi REST API and emits events.

Also in this repo:

- `flow_definition/` — the NiFi template (`NifiMonitoringTemplate.xml`) / flow JSON that runs inside NiFi and pushes metrics to Splunk's HEC.

The two deployment modes reflect NiFi authentication:

- **No-auth NiFi**: NiFi pushes to Splunk HEC (the flow template is the data path; the TA's modular input is unused).
- **Basic-auth NiFi**: the TA's `nifi.py` modular input pulls from NiFi's REST API (`/flow/status`, `/system-diagnostics`, `/site-to-site`, `/flow/processors/{id}/status/history`, `/flow/process-groups/{id}/status/history`) and writes events via Splunk's EventWriter.

**Versions must match.** `check-apps-version` in `main.yml` fails the build if `version =` in `nifi_monitoring/default/app.conf` and `nifi_TA_monitoring/default/app.conf` differ — bump both together.

## Common commands

Packaging & validation (run inside the `kudaw/appinspect:latest` container used by CI, or with equivalent local tooling):

```
slim package nifi_monitoring
slim package nifi_TA_monitoring
slim validate nifi_monitoring-<version>.tar.gz
splunk-appinspect inspect nifi_monitoring-<version>.tar.gz --output-file appinspect_result.json --mode precert
```

AppInspect is the gate. `main.yml` fails if `summary.error > 0`, `failure > 0`, or `warning > MAX_WARNING` (currently `8`).

Local integration test environments (see `tests/README.md`):

```
# no-auth mode
docker compose -f tests/nifi123-splunk91-nifi_nologin.yml -p nifi_nologin up
# then inside the splunk container:
bash /tmp/test/tests/script/init_splunk_nologin.sh --all   # or --copy-apps | --config

# basic-auth mode
docker compose -f tests/nifi123-splunk91-nifi_login.yml -p nifi_login up
```

After starting Splunk, **disable SSL on HEC global config** (documented workaround).

Docs (MkDocs, see `mkdocs.yml` + `docs/`):

```
pip install -r docs/requirements.txt
mkdocs serve     # local preview
mkdocs build
```

## Workflows

- `dev.yml` — manual; AppInspect + unit tests.
- `testing.yml` — on push to `testing`; AppInspect + unit tests.
- `main.yml` — manual (`workflow_dispatch`); AppInspect + unit tests + **pre-release** GitHub release with both `.tar.gz` artifacts, tagged with `APP_VERSION` pulled from `app.conf`.
- `docs.yml` — manual; builds and publishes MkDocs.

The `unittest` job currently just echoes TODO — there is no real test suite yet; "tests" in this repo means the docker-compose integration harness under `tests/`.

## Editing conventions specific to this repo

- Splunk artifact layout is fixed (`default/`, `metadata/`, `static/`, `appserver/`, `bin/`, `lib/`). Do not reorganize — AppInspect and `slim` rely on it.
- `nifi_TA_monitoring/lib/` vendors `splunklib` (Splunk SDK for Python). `bin/nifi.py` adds it to `sys.path` at import time; keep that shim.
- `bin/nifi.py` uses `python-dotenv` to persist state in a sibling `.env` file (auto-created on first run). Treat that file as runtime state, not config.
- When adding a new NiFi endpoint, extend the `endpoints` list at the top of `NiFiScript` in `bin/nifi.py` and add the matching `sourcetype` routing in `default/props.conf` / `default/transforms.conf`.
- Docs are bilingual: every `*.md` has an `*.es.md` counterpart. Update both when changing user-facing docs.
