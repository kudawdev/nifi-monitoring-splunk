# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repo is the source for two **published Splunkbase apps** (publisher: Kudaw SA, both currently at version **2.0.0**, compatible with Splunk Enterprise / Splunk Cloud **9.0–10.x** and Apache NiFi **1.16–1.28.1 and 2.0–2.11** — see `doc/compatibility.md`):

- **Nifi Monitoring for Splunk** — https://splunkbase.splunk.com/app/6125 — built from `nifi_monitoring/`. The user-facing Splunk **app** (dashboards, views, datamodels, lookups, macros) that centralizes operational visibility across multiple NiFi instances. `app.conf` → `id = nifi_monitoring`, `is_visible = true`. Depends on two third-party visualizations from Splunkbase: **Lookup File Editor** (app 1724) and **Status Indicator - Custom Visualization** (app 3119).
- **Nifi Monitoring TA** — https://splunkbase.splunk.com/app/6124 — **generated** from `nifi_TA_monitoring/` by [UCC](https://splunk.github.io/addonfactory-ucc-generator/). The **technology add-on** that normalizes and indexes NiFi data. Contains `package/bin/nifi.py`, a Splunk *modular input* (subclass of `splunklib.modularinput.Script`) that polls the NiFi REST API and emits events.

  **The TA is not installable from the tree.** `app.conf`, `inputs.conf`, `README/inputs.conf.spec`, `restmap.conf`, `metadata/default.meta`, `lib/` and the whole configuration UI are produced by `ucc-gen build` and land in `output/nifi_TA_monitoring/`, which is gitignored. Run `tests/build-ta.sh` before packaging, before the harness, and before the unit suite. Its layout:

  | | |
  |---|---|
  | `globalConfig.json` | The single source for the input form, the table, `inputs.conf` defaults and the spec. **Generated** by `nifi_TA_monitoring/gen_globalconfig.py` — edit the script and re-run it; a unit test fails if the JSON drifts. |
  | `package/` | Everything handwritten that ships verbatim: `bin/`, `default/props.conf`, `default/transforms.conf`, `static/`, `app.manifest`, `lib/requirements.txt`, `lib/exclude.txt`. |
  | `appended/inputs.conf` | The file monitors. Separate because ucc-gen owns `default/inputs.conf` and a file of ours there would replace its defaults rather than add to them. |
  | `additional_packaging.py` | Post-build hook: appends those monitors and writes `python.required = 3.13` into the `[nifi]` stanza and the three `[admin_external:*]` stanzas, none of which ucc-gen emits. |

Also in this repo:

- `flow_definition/` — the NiFi flow that runs inside NiFi and pushes to Splunk's HEC, versioned per NiFi line: `nifi-2.x/NiFiMonitoring.json` (flow definition, native 2.x), `nifi-1.x/NiFiMonitoring.json` + `nifi-1.x/NifiMonitoringTemplate.xml` (templates were removed in NiFi 2.x). `migrate_to_nifi2.py` generates the 2.x flow from the 1.x one; a unit test fails if the distributed file drifts from a clean run of the script, so **edit the script, not the JSON**.
- `docs/plans/` — internal design docs, **not** published. `2026-08-24-soporte-nifi-2.md` is the plan behind the 2.0.0 release and records what is still deferred to 2.1.

**Two data paths**, both landing on the same sourcetypes:

- **Pull (primary, supported).** The TA's `nifi.py` modular input polls the NiFi REST API — `/flow/status`, `/system-diagnostics`, `/flow/processors/{id}/status/history`, `/flow/process-groups/{id}/status/history`, `/flow/bulletin-board`, and `/flow/metrics/json` (NiFi ≥ 1.16, off by default for volume reasons) — plus any `custom_endpoints` the input declares, and writes events via Splunk's EventWriter. Works with `auth_type = none` or `basic`; TLS verification is on by default (`verify_tls`, with an optional `ca_bundle`).
- **Push (alternative).** The NiFi flow calls its own API and sends to the HEC. It is the only option when Splunk cannot reach NiFi, but it **requires an unauthenticated NiFi**: the flow calls its own API without credentials.

`nifi:api:site_to_site` and `nifi:api:controller_cluster` were **retired in 2.0.0** — nothing consumed them.

**Versions must match.** `check-apps-version` in `main.yml` fails the build if `version =` differs between `nifi_monitoring/default/app.conf` and `nifi_TA_monitoring/default/app.conf`, or between the `[launcher]` and `[id]` stanzas within one app — bump all four together.

## Common commands

Build the add-on first — everything below needs `output/nifi_TA_monitoring/`:

```
./tests/build-ta.sh          # creates .venv-ucc on first run, then ucc-gen build
```

Packaging & validation (run inside the `kudaw/appinspect:latest` container used by CI, or with equivalent local tooling). Note the TA is packaged from `output/`, the app from the tree:

```
slim package nifi_monitoring
slim package output/nifi_TA_monitoring
slim validate nifi_monitoring-<version>.tar.gz
splunk-appinspect inspect nifi_monitoring-<version>.tar.gz --output-file appinspect_result.json --mode precert
```

AppInspect is the gate. `main.yml` fails if `summary.error > 0`, `failure > 0`, or `warning > MAX_WARNING` (currently `13`; measured per app, 5 for the app and 12 for the TA).

Unit tests — standard library only, no Docker, but the build has to have run: `lib/` and the generated `.conf` files live in `output/`. Without it the checks that read them skip with a message saying so; `REQUIRE_BUILT_TA=1` turns those skips into failures, which is what CI sets.

```
./tests/build-ta.sh
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

`run.sh` builds the TA, writes `.env` from the profile, brings the stack up, waits for NiFi, runs the assertions and tears down, exiting non-zero on any failure. It seeds the container from `output/`, never from the tree — what is tested is what ships. `SKIP_TA_BUILD=1` reuses the last build. Provisioning is declarative — **no `docker exec` step, and no turning off HEC SSL by hand**; the `provision` service seeds `/opt/splunk/etc` before `splunkd` first starts.

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
- **Dependencies are declared, not vendored.** `package/lib/requirements.txt` holds what Splunk does not ship (`splunktaucclib`, `splunk-sdk>=2.1,<3`, `solnlib>=7,<8`) and `package/lib/exclude.txt` holds what it does (`requests`, `urllib3`, `certifi`, ...). Both pins exist for the same reason: `splunk-sdk` 3.x ships a `splunklib/ai/` package AppInspect cannot parse, and `solnlib` 8.x pulls in grpcio, whose compiled extension is built for one CPU architecture and one Python minor version. A unit test fails if any `.so` reaches `lib/`. `bin/nifi.py` starts with `import import_declare_test`, ucc-gen's `sys.path` shim; keep it.
- Note `splunklib/results.py` imports `deprecation`, which is not installed — importing that module raises `ModuleNotFoundError` (tracked as B-24).
- Runtime state does not live on the app's own disk. The JWT goes to `storage/passwords` under the realm `nifi_TA_monitoring:token`, keyed by input name and cached in memory for the life of the process; the bulletin cursor goes to Splunk's `checkpoint_dir`. Both used to be a `.env` inside `bin/`, which was lost on reinstall and — because the modular input sets `use_single_instance = false` — was rewritten non-atomically by one process per input, so two instances could clobber each other's token (defect B-14).
- When adding a new NiFi endpoint, extend the `endpoints` list at the top of `NiFiScript` in `package/bin/nifi.py` — with `min_version` if it is not available in every supported NiFi — add the matching `sourcetype` routing in `package/default/props.conf` / `transforms.conf`, and declare the input field in `nifi_TA_monitoring/gen_globalconfig.py`. A unit test fails if the code reads a field the form does not offer, which is how four flow-metrics fields came to be implemented and specified but unreachable from the UI (UI-4). For a one-off endpoint a user needs, the `custom_endpoints` input field already covers it without a release.
- `bin/nifi.py` logs through `self._log(ew, level, message)`, not `EventWriter.log`, so **Configuration > Logging** can quieten it. Calling `EventWriter.log` directly bypasses the level.
- Public docs live in `doc/` (published by mkdocs; `docs_dir: doc`). Internal development docs
  (plans, design notes) live in `docs/` and are NOT published.
- Public docs are bilingual: every `*.md` has an `*.es.md` counterpart. Update both when changing user-facing docs.
