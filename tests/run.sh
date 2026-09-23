#!/usr/bin/env bash
# Bring up one matrix profile, wait for it, run the assertions, tear it down.
#
#   ./run.sh                      # default profile (nifi2-current)
#   ./run.sh nifi1-legacy         # a named profile from matrix.yml
#   ./run.sh --list               # list profiles
#   ./run.sh --list cluster       # everything about one profile
#   ./run.sh --keep nifi2-current # leave the stack running afterwards
#   ./run.sh --bare cluster       # the environment only: install nothing
#
# Exits non-zero if the stack fails to come up or any assertion fails, so CI
# can call it directly.

set -euo pipefail

cd "$(dirname "$0")"

PROFILE="${DEFAULT_PROFILE:-nifi2-current}"
KEEP=0
# --bare gives you the scenario's machines and nothing else: no apps, no
# input, no lookup, no flow, and no assertions. Splunk extracts its own etc/
# into the empty volume on first boot, so what comes up is a virgin Splunk
# next to the NiFi topology the profile describes.
#
# It exists because the automated profiles cannot cover installation -- they
# exist precisely to remove that step, seeding /opt/splunk/etc before splunkd
# first starts. Uploading the .tar.gz, reading the setup screen and filling in
# the form is the one path nothing here exercises, and it is the first thing
# every user does.
BARE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --list)
            # With a profile name, everything known about that one; without,
            # a row each. The row now carries what the version and the auth
            # mode never answered: which strategy the profile covers and what
            # it actually starts.
            if [ -n "${2:-}" ]; then
                python3 matrix.py --describe "$2"
                exit 0
            fi
            python3 - <<'PY'
import sys
sys.path.insert(0, ".")
from matrix import load, strategy, topology
for name, p in load()["profiles"].items():
    print("  %-15s NiFi %-8s Splunk %-5s %-16s %-5s %s" % (
        name, p["nifi_version"], p["splunk_version"],
        "auth=" + p["nifi_auth"], strategy(name),
        " + ".join(topology(name))))
print()
print("  ./run.sh --list <profile>   everything about one of them")
PY
            exit 0
            ;;
        --keep) KEEP=1; shift ;;
        --bare) BARE=1; KEEP=1; shift ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \?//'; exit 0 ;;
        -*) echo "unknown option: $1" >&2; exit 2 ;;
        *) PROFILE="$1"; shift ;;
    esac
done

# The add-on is generated since the UCC migration: app.conf, inputs.conf, the
# spec and the whole configuration UI do not exist in the tree. Seeding from
# nifi_TA_monitoring/ would install something that has never been built, so
# the build comes first and the harness only ever sees output/ (UI-3).
# SKIP_TA_BUILD=1 reuses whatever is already there, for a quick re-run.
if [ "${SKIP_TA_BUILD:-0}" != "1" ]; then
    ./build-ta.sh
elif [ ! -d ../output/nifi_TA_monitoring ]; then
    echo "SKIP_TA_BUILD=1 but output/nifi_TA_monitoring does not exist" >&2
    exit 2
fi

echo "==> profile: $PROFILE${BARE:+ (bare: nothing will be installed)}"
python3 matrix.py "$PROFILE" > .env
if [ "$BARE" -eq 1 ]; then
    echo "BARE=1" >> .env
fi
cat .env | sed 's/^/    /'
set -a; . ./.env; set +a

cleanup() {
    status=$?
    if [ "$KEEP" -eq 1 ]; then
        echo "==> --keep given, leaving the stack up"
    else
        echo "==> tearing down"
        docker compose down -v --remove-orphans >/dev/null 2>&1 || true
    fi
    exit $status
}
trap cleanup EXIT

# Start from a clean slate. Running profiles back to back otherwise fails:
# the previous stack's containers and network are still going away while the
# next `up` claims the same published ports, and `up --wait` gives up. The
# CI matrix runs each profile on its own runner, but running them in
# sequence locally is the normal way to check the whole matrix.
echo "==> removing any previous stack"
docker compose down -v --remove-orphans >/dev/null 2>&1 || true

for port in "$SPLUNK_WEB_PORT" "$SPLUNK_MGMT_PORT" "$SPLUNK_HEC_PORT" \
            "$NIFI_HTTP_PORT" "$NIFI_HTTPS_PORT"; do
    for _ in $(seq 1 30); do
        if command -v ss >/dev/null 2>&1; then
            ss -ltn 2>/dev/null | grep -q ":${port} " || break
        else
            break
        fi
        sleep 1
    done
done

echo "==> starting (Splunk cold start can take several minutes)"
docker compose up -d --wait

echo "==> waiting for NiFi to answer"
python3 integration/wait_for_nifi.py

if [ "$BARE" -eq 1 ]; then
    cat <<BARE_NOTES

==> bare environment up. Nothing is installed.

    Splunk      http://localhost:${SPLUNK_WEB_PORT:-38000}   admin / ${SPLUNK_PASSWORD:-Password123}
    Splunk mgmt https://localhost:${SPLUNK_MGMT_PORT:-38089}
    NiFi        http://localhost:${NIFI_HTTP_PORT:-38080}/nifi
                https://localhost:${NIFI_HTTPS_PORT:-38443}/nifi  (single-user profiles;
                credentials in tests/${NIFI_ENV_FILE#./})

    The packages to install by hand:

      make package DEV=1  (from the repo root; the two .tar.gz land in dist/)

    The app also needs the two Splunkbase visualisations it depends on; they
    are in tests/additional_apps/. The push path additionally needs the flow
    from flow_definition/, imported through NiFi's own UI.

    Tear down with:  cd tests && docker compose down -v

BARE_NOTES
    exit 0
fi

echo "==> loading the instance kvstore collection"
python3 integration/seed_kvstore.py

if [ "${COLLECTION:-pull}" = "hec" ]; then
    echo "==> installing and starting the flow inside NiFi (push path)"
    python3 integration/provision_flow.py
fi

echo "==> running assertions"
(cd integration && python3 -m unittest discover -v)
