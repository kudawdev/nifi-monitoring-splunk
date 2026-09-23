#!/usr/bin/env bash
# Run a set of integration scenarios and report how each one went.
#
# The argument is either a list named in matrix.yml's `ci` section
# (`pull_request`, `release`) or an explicit set of profile names. The add-on
# is built once and reused, which saves a pip install per scenario.
#
#   ./integration-matrix.sh                 # pull_request: one per axis
#   ./integration-matrix.sh release         # all ten
#   ./integration-matrix.sh cluster nifi2-hec
#
# Exits non-zero if any scenario fails, and never stops early: a run that
# takes this long should come back with the whole picture, not the first
# failure.

set -uo pipefail

cd "$(dirname "$0")"

WANTED=("${@:-pull_request}")

# A single word that names a CI list expands to it; anything else is taken as
# profile names.
if [[ ${#WANTED[@]} -eq 1 ]]; then
    case "${WANTED[0]}" in
        pull_request|release)
            mapfile -t WANTED < <(python3 matrix.py --ci "${WANTED[0]}") ;;
    esac
fi

# Every scenario publishes the same ports, so anything already holding one
# turns the whole run into guaranteed failures -- nine minutes of them, and
# the error arrives buried in a compose log. Ask first, and name the culprit:
# it is usually another project's stack, which is not ours to stop.
busy=""
for port in $(python3 matrix.py "${WANTED[0]}" | sed -n 's/^[A-Z_]*PORT=//p'); do
    holder="$(docker ps --format '{{.Names}}\t{{.Ports}}' 2>/dev/null \
              | grep -E "(^|:)$port->" | cut -f1 | head -1)"
    if [[ -n "$holder" ]]; then
        busy+="  port $port is held by $holder"$'\n'
    elif command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$port "; then
        busy+="  port $port is in use, by something outside Docker"$'\n'
    fi
done
if [[ -n "$busy" ]]; then
    echo "Cannot start: the scenarios need these ports and they are taken." >&2
    printf '%s' "$busy" >&2
    echo "Stop whatever holds them, or change the ports in tests/matrix.py." >&2
    exit 1
fi

echo "==> building the add-on once for ${#WANTED[@]} scenario(s)"
./build-ta.sh >/dev/null || { echo "build failed" >&2; exit 1; }
export SKIP_TA_BUILD=1

LOGS="$(mktemp -d)"
declare -a RESULTS=()
failures=0

for profile in "${WANTED[@]}"; do
    printf '==> %s' "$profile"
    started=$(date +%s)
    if ./run.sh "$profile" > "$LOGS/$profile.log" 2>&1; then
        status="ok"
    else
        status="FAILED"
        failures=$((failures + 1))
    fi
    took=$(( $(date +%s) - started ))
    summary="$(grep -E '^(OK|FAILED)' "$LOGS/$profile.log" | tail -1)"
    # No summary means the assertions never ran -- the stack did not come up.
    # Saying "FAILED" and nothing else is how a broken environment reads like
    # a broken test suite.
    if [[ -z "$summary" ]]; then
        summary="$(grep -m1 -iE 'error response from daemon|FATAL|Error:' \
                   "$LOGS/$profile.log" | cut -c1-110)"
        summary="${summary:-the stack never came up; see the log}"
    fi
    printf '  %s  %ss  %s\n' "$status" "$took" "$summary"
    RESULTS+=("$(printf '%-16s %-7s %5ss  %s' "$profile" "$status" "$took" "$summary")")
done

echo
echo "Scenarios:"
printf '  %s\n' "${RESULTS[@]}"
echo
echo "Logs: $LOGS"

if (( failures )); then
    echo "$failures of ${#WANTED[@]} failed."
    exit 1
fi
echo "${#WANTED[@]} of ${#WANTED[@]} passed."
