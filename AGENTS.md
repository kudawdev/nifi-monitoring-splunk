# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repo is the source for two **published Splunkbase apps** (publisher: Kudaw SA, both currently at version **2.0.0**, compatible with Splunk Enterprise / Splunk Cloud **9.0–10.x** and Apache NiFi **1.16–1.28.1 and 2.0–2.11** — see `doc/compatibility.md`):

- **Nifi Monitoring for Splunk** — https://splunkbase.splunk.com/app/6125 — built from `nifi_monitoring/`. The user-facing Splunk **app** (dashboards, views, datamodels, lookups, macros) that centralizes operational visibility across multiple NiFi instances. `app.conf` → `id = nifi_monitoring`, `is_visible = true`. Depends on two third-party visualizations from Splunkbase: **Lookup File Editor** (app 1724) and **Status Indicator - Custom Visualization** (app 3119).
- **Nifi Monitoring TA** — https://splunkbase.splunk.com/app/6124 — built from `nifi_TA_monitoring/`. The **technology add-on** that normalizes and indexes NiFi data. `app.conf` → `id = nifi_TA_monitoring`, `is_visible = false`. Contains `bin/nifi.py`, a Splunk *modular input* (subclass of `splunklib.modularinput.Script`) that polls the NiFi REST API and emits events.

Also in this repo:

- `flow_definition/` — the NiFi flow that runs inside NiFi and pushes to Splunk's HEC, versioned per NiFi line: `nifi-2.x/NiFiMonitoring.json` (flow definition, native 2.x), `nifi-1.x/NiFiMonitoring.json` + `nifi-1.x/NifiMonitoringTemplate.xml` (templates were removed in NiFi 2.x). `migrate_to_nifi2.py` generates the 2.x flow from the 1.x one; a unit test fails if the distributed file drifts from a clean run of the script, so **edit the script, not the JSON**.
- `docs/plans/` — internal design docs, **not** published. `2026-08-24-soporte-nifi-2.md` is the plan behind the 2.0.0 release and records what is still deferred to 2.1.

**Two data paths**, both landing on the same sourcetypes:

- **Pull (primary, supported).** The TA's `nifi.py` modular input polls the NiFi REST API — `/flow/status`, `/system-diagnostics`, `/flow/processors/{id}/status/history`, `/flow/process-groups/{id}/status/history`, `/flow/bulletin-board`, and `/flow/metrics/json` (NiFi ≥ 1.16, off by default for volume reasons) — plus any `custom_endpoints` the input declares, and writes events via Splunk's EventWriter. Works with `auth_type = none` or `basic`; TLS verification is on by default (`verify_tls`, with an optional `ca_bundle`).
- **Push (alternative).** The NiFi flow calls its own API and sends to the HEC. It is the only option when Splunk cannot reach NiFi, but it **requires an unauthenticated NiFi**: the flow calls its own API without credentials.

`nifi:api:site_to_site` and `nifi:api:controller_cluster` were **retired in 2.0.0** — nothing consumed them.

**Versions must match.** `check-apps-version` in `main.yml` fails the build if `version =` differs between `nifi_monitoring/default/app.conf` and `nifi_TA_monitoring/default/app.conf`, or between the `[launcher]` and `[id]` stanzas within one app — bump all four together.

## Common commands

Packaging & validation (run inside the `kudaw/appinspect:latest` container used by CI, or with equivalent local tooling):

```
slim package nifi_monitoring
slim package nifi_TA_monitoring
slim validate nifi_monitoring-<version>.tar.gz
splunk-appinspect inspect nifi_monitoring-<version>.tar.gz --output-file appinspect_result.json --mode precert
```

AppInspect is the gate. `main.yml` fails if `summary.error > 0`, `failure > 0`, or `warning > MAX_WARNING` (currently `8`).

Unit tests — standard library only, no Docker:

```
cd tests/unit && python3 -m unittest discover -v
```

Integration — one parameterized compose file, profiles named in `tests/matrix.yml` (see `tests/README.md`):

```
cd tests
./run.sh --list             # show the profiles
./run.sh                    # default: nifi2-current
./run.sh nifi1-legacy       # NiFi 1.23.2 + Splunk 9.4, unsecured
./run.sh --keep nifi2-current
```

`run.sh` writes `.env` from the profile, brings the stack up, waits for NiFi, runs the assertions and tears down, exiting non-zero on any failure. Provisioning is declarative — **no `docker exec` step, and no turning off HEC SSL by hand**; the `provision` service seeds `/opt/splunk/etc` before `splunkd` first starts.

Public docs (MkDocs, see `mkdocs.yml` + `doc/`):

```
pip install -r doc/requirements.txt
mkdocs serve     # local preview
mkdocs build
```

## Workflows

- `dev.yml` — manual; AppInspect + unit tests.
- `testing.yml` — manual (`workflow_dispatch`); AppInspect + unit tests.
- `main.yml` — manual (`workflow_dispatch`); version gate + AppInspect + unit tests + the **integration matrix** (`integration` job, one runner per profile in `matrix.yml`'s `ci.release`) + **pre-release** GitHub release with both `.tar.gz` artifacts, tagged with `APP_VERSION` pulled from `app.conf`. `publish` depends on `integration`.
- `docs.yml` — manual; builds and publishes MkDocs.

## Editing conventions specific to this repo

- Splunk artifact layout is fixed (`default/`, `metadata/`, `static/`, `appserver/`, `bin/`, `lib/`). Do not reorganize — AppInspect and `slim` rely on it.
- `nifi_TA_monitoring/lib/` vendors `splunklib` (Splunk SDK for Python). `bin/nifi.py` adds it to `sys.path` at import time; keep that shim. Note `splunklib/results.py` imports `deprecation`, which is **not** vendored — importing that module raises `ModuleNotFoundError` (tracked as B-24).
- `bin/nifi.py` uses `python-dotenv` to persist the JWT in a sibling `.env` file (auto-created on first run). Treat that file as runtime state, not config. It is a known defect (B-14): the file lives inside the app directory, so it is lost on reinstall. The bulletin cursor already uses Splunk's `checkpoint_dir` instead.
- When adding a new NiFi endpoint, extend the `endpoints` list at the top of `NiFiScript` in `bin/nifi.py` — with `min_version` if it is not available in every supported NiFi — and add the matching `sourcetype` routing in `default/props.conf` / `default/transforms.conf`. For a one-off endpoint a user needs, the `custom_endpoints` input field already covers it without a release.
- Public docs live in `doc/` (published by mkdocs; `docs_dir: doc`). Internal development docs
  (plans, design notes) live in `docs/` and are NOT published.
- Public docs are bilingual: every `*.md` has an `*.es.md` counterpart. Update both when changing user-facing docs.
