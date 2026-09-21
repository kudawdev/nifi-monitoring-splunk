# Tests

Two layers:

| | What it checks | Needs Docker |
|---|---|---|
| `unit/` | The TA's Python: token refresh, input validation, credential handling, and the matrix reader | no |
| `integration/` | That data actually reaches Splunk and the fields come out, against a real NiFi + Splunk pair | yes |

## Building the add-on

`nifi_TA_monitoring` is generated. `app.conf`, `inputs.conf`, the spec,
`restmap.conf`, `lib/` and the whole configuration UI come out of `ucc-gen`
and land in `output/nifi_TA_monitoring/`, which is gitignored:

```
./build-ta.sh
```

The first run creates `.venv-ucc` and installs `ucc-gen` into it; after that
it takes a few seconds. Both layers below need it, and `run.sh` calls it for
you.

## Unit tests

Standard library only, but the build has to have run -- `splunklib` is no
longer versioned, it is installed into the built add-on's `lib/`:

```
./build-ta.sh
cd unit && python3 -m unittest discover -v
```

Without a build they skip, with a message saying to run it. `REQUIRE_BUILT_TA=1`
turns those skips into failures; CI sets it, because a green run where the
generated half of the add-on was never looked at is worse than a red one.

These run in CI (the `unittest` job of `dev.yml`, `testing.yml` and
`main.yml`).

## Integration environment

One compose file covers every supported combination. Pick one by name from
`matrix.yml` instead of copying compose files:

```
cd tests
./run.sh --list            # show the profiles
./run.sh                   # default: nifi2-current
./run.sh nifi1-legacy      # NiFi 1.23.2 + Splunk 9.4, unsecured
./run.sh --keep nifi2-current   # leave the stack up to poke at it
```

`run.sh` builds the add-on, writes `.env` from the profile, brings the stack
up, waits for NiFi to answer, runs the assertions, and tears down. It exits
non-zero if anything fails, so CI can call it directly. `SKIP_TA_BUILD=1`
reuses the last build, for a quick re-run against unchanged add-on code.

While a stack is up:

| | |
|---|---|
| Splunk Web | http://localhost:38000 (`admin` / `Password123`) |
| Splunk management | https://localhost:38089 |
| Splunk HEC | http://localhost:38088 (token in `.env`) |
| NiFi (unsecured profiles) | http://localhost:38080/nifi |
| NiFi (single-user profiles) | https://localhost:38443/nifi (`admin` / see `env/nifi-singleuser.env`) |

Run the assertions against a stack you started yourself:

```
cd tests/integration && python3 -m unittest discover -v
```

They skip, rather than fail, when no stack is reachable.

### Profiles

`matrix.yml` holds the supported combinations and which ones CI runs.

There are two recommended ways to get data out of NiFi, and each one is
covered **whole** -- API *and* logs -- by one profile:

| Strategy | API | Logs | Profile |
|---|---|---|---|
| **Push** | the flow's `InvokeHTTP` → HEC | the flow's `TailFile` → HEC | `nifi2-hec` |
| **Pull + forwarder** | the TA's modular input | a Universal Forwarder | `nifi2-current` |

The remaining profiles (`nifi1-legacy`, `nifi1-last`, `nifi2-first`) are
version regression: their job is to prove the TA still talks to every
supported NiFi, not to cover a strategy.

`nifi_auth` selects an environment file from `env/`:

- `none` — plain HTTP, no authentication. The TA's `auth_type = none` path.
- `singleuser` — HTTPS with NiFi's single-user provider. Exercises
  `POST /access/token`, the same login the TA performs.

`forwarder: true` brings up the `universalforwarder` service. `matrix.py`
turns it into `COMPOSE_PROFILES=forwarder` in `.env`, which Compose reads by
itself -- `run.sh` needs no flag for it.

### Provisioning

There is no manual setup step. The `provision` service seeds
`/opt/splunk/etc` before `splunkd` first starts (the Splunk image extracts
its own `etc/` additively, so seeded files survive), which installs both
apps plus the two bundled third-party visualizations, enables the HEC
without SSL, loads the `instance` lookup, and installs the TA input
matching the profile's auth mode (`provision/splunk/inputs.conf.<mode>`).

The **TA comes from `output/`, not from the tree** -- seeding the tree would
install an add-on with no `app.conf`, no `inputs.conf` and no UI, which looks
like it installed and then does nothing. The seed script refuses rather than
doing that. The app, which is not generated, still comes from the tree.

This replaces the old procedure of `docker exec`-ing into the container,
running `init_splunk_nologin.sh` by hand, and then turning off SSL on the
HEC in the UI on every start.

### Notes

- **Splunk cold start is slow.** The healthcheck allows 15 minutes
  (`start_period: 900s`); with less, `docker compose up --wait` gives up
  before `splunkd` is listening. Splunk 10 also requires
  `SPLUNK_GENERAL_TERMS`, which the compose file sets.
- **NiFi 2.x needs `NIFI_WEB_PROXY_HOST`.** Without it NiFi answers HTTP
  421 Misdirected Request to every API call, because it rejects Host
  headers it does not recognise.
- **A single-user password must be at least 12 characters.** NiFi silently
  ignores shorter ones and generates random credentials instead.
- **Unsecured NiFi 2.x is awkward.** The container's `start.sh` applies the
  container hostname to the HTTPS host, which takes precedence over the HTTP
  settings. The `none` profile is verified on 1.x; for 2.x prefer
  `singleuser`, which is also closer to a real deployment.
- **The forwarder has no management port.** Its image sets the management
  mode to "auto (Allows UDS)", so splunkd listens on a Unix socket and TCP
  8089 answers nothing at all -- `curl` returns 000, not 401. Its healthcheck
  therefore looks for the process, unlike Splunk's and NiFi's.
- **The forwarder gets the real TA**, not a bespoke `inputs.conf`. The
  seeded `local/inputs.conf` only flips `disabled` and sets the index, so the
  profile tests the monitor paths and sourcetypes exactly as shipped -- which
  is how defect B-21 (the stanzas pointed at `/opt/nifi/logs/`, not where the
  official image keeps them) would be caught next time.
- **`nifi-deprecation.log` is created empty** and stays that way until
  something deprecated runs, so its assertion skips rather than fails on a
  clean instance.
