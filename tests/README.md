# Tests

Two layers:

| | What it checks | Needs Docker |
|---|---|---|
| `unit/` | The TA's Python: token refresh, input validation, credential handling, and the matrix reader | no |
| `integration/` | That data actually reaches Splunk and the fields come out, against a real NiFi + Splunk pair | yes |

## Unit tests

Standard library only, nothing to install:

```
cd tests/unit && python3 -m unittest discover -v
```

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

`run.sh` writes `.env` from the profile, brings the stack up, waits for NiFi
to answer, runs the assertions, and tears down. It exits non-zero if
anything fails, so CI can call it directly.

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
`nifi_auth` selects an environment file from `env/`:

- `none` — plain HTTP, no authentication. The TA's `auth_type = none` path.
- `singleuser` — HTTPS with NiFi's single-user provider. Exercises
  `POST /access/token`, the same login the TA performs.

### Provisioning

There is no manual setup step. The `provision` service seeds
`/opt/splunk/etc` before `splunkd` first starts (the Splunk image extracts
its own `etc/` additively, so seeded files survive), which installs both
apps plus the two bundled third-party visualizations, enables the HEC
without SSL, loads the `instance` lookup, and installs the TA input
matching the profile's auth mode (`provision/splunk/inputs.conf.<mode>`).

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
- **Log forwarding** is off by default. Bring up the Universal Forwarder
  with `docker compose --profile forwarder up -d`.
