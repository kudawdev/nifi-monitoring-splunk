#!/usr/bin/env bash
# kudaw-delivery: v1.3.0
# Level 1 of the contract's validation: does this repo expose the surface its profile
# requires?
#
# Usage:
#   scripts/contract-check.sh          Report, exit non-zero on a missing target
#   scripts/contract-check.sh --warn   Report, always exit 0 (🟡 baseline mode)
#
# This is the check that a prose contract could never have: you cannot assert that a
# paragraph was followed, but you can assert that `make release` exists.
#
# What it deliberately does NOT do is tell you whether the facade is up to date. It has no
# way to know the latest version — the plugin is not installed on a CI runner. It reports
# the seal it finds, and `/cicd audit` (which does have the plugin) compares.

set -euo pipefail

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
cd "$PROJECT_ROOT"

WARN_ONLY=0
[[ "${1:-}" == "--warn" ]] && WARN_ONLY=1

# Every profile owes these.
COMMON="help check status version baseline suggest-level bump set-version manifest
        changelog release-notes release contract-check self-test"
case "$PROFILE" in
    servicio)            EXTRA="image image-status promote-staging promote-prod" ;;
    libreria|app-splunk) EXTRA="publish verify promote-main" ;;
    *) echo "Error: unknown PROFILE '$PROFILE' in delivery.conf" >&2; exit 2 ;;
esac

failures=0
note() { printf '  %s %s\n' "$1" "$2"; }

echo "Contract check — profile: $PROFILE"
echo

echo "Targets:"
for t in $COMMON $EXTRA; do
    if make -n "$t" >/dev/null 2>&1; then
        note "✓" "$t"
    else
        note "✗" "$t  — required by the '$PROFILE' profile, not defined"
        failures=$((failures + 1))
    fi
done

echo
echo "Facade seal:"
mapfile -t sealed < <(grep -rl '^# kudaw-delivery: v' delivery.mk scripts/ 2>/dev/null | sort)
if (( ${#sealed[@]} == 0 )); then
    note "✗" "no sealed files found — is the facade installed?"
    failures=$((failures + 1))
else
    mapfile -t versions < <(grep -h '^# kudaw-delivery: v' "${sealed[@]}" \
                            | sed 's/^# kudaw-delivery: //' | sort -u)
    if (( ${#versions[@]} == 1 )); then
        note "✓" "${#sealed[@]} file(s) at ${versions[0]}"
    else
        note "✗" "mixed versions across the facade: ${versions[*]} — a sync stopped halfway"
        failures=$((failures + 1))
    fi
fi

echo
if (( failures == 0 )); then
    echo "OK — the surface matches the contract."
    exit 0
fi
echo "$failures problem(s). The contract lives in kudaw-tecnica/tech-cicd,"
echo "references/comandos-proceso.md; \`/cicd audit\` explains how to close them."
(( WARN_ONLY )) && exit 0
exit 1
