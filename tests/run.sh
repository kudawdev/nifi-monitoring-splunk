#!/usr/bin/env bash
# Bring up one matrix profile, wait for it, run the assertions, tear it down.
#
#   ./run.sh                      # default profile (nifi2-current)
#   ./run.sh nifi1-legacy         # a named profile from matrix.yml
#   ./run.sh --list               # list profiles
#   ./run.sh --keep nifi2-current # leave the stack running afterwards
#
# Exits non-zero if the stack fails to come up or any assertion fails, so CI
# can call it directly.

set -euo pipefail

cd "$(dirname "$0")"

PROFILE="${DEFAULT_PROFILE:-nifi2-current}"
KEEP=0

while [ $# -gt 0 ]; do
    case "$1" in
        --list)
            python3 - <<'PY'
import sys
sys.path.insert(0, ".")
from matrix import load
for name, p in load()["profiles"].items():
    print(f"  {name:<16} NiFi {p['nifi_version']:<8} Splunk {p['splunk_version']:<6} auth={p['nifi_auth']}")
PY
            exit 0
            ;;
        --keep) KEEP=1; shift ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \?//'; exit 0 ;;
        -*) echo "unknown option: $1" >&2; exit 2 ;;
        *) PROFILE="$1"; shift ;;
    esac
done

echo "==> profile: $PROFILE"
python3 matrix.py "$PROFILE" > .env
cat .env | sed 's/^/    /'

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

echo "==> starting (Splunk cold start can take several minutes)"
docker compose up -d --wait

echo "==> waiting for NiFi to answer"
python3 integration/wait_for_nifi.py

echo "==> loading the instance kvstore collection"
python3 integration/seed_kvstore.py

echo "==> running assertions"
(cd integration && python3 -m unittest discover -v)
