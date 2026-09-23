#!/usr/bin/env bash
# `make verify` for the app-splunk profile: is what we are about to release
# actually there, and is it the right thing?
#
# For a library this asks a registry. Here the deliverable is local until the
# release attaches it, so verification is about the packages themselves --
# they exist, they carry the version the manifest claims, and the add-on
# inside is the generated one rather than the tree. That last check is the
# reason this exists: packaging nifi_TA_monitoring/ straight from the tree
# produces an add-on with no app.conf and no UI, and slim does not complain.
#
#   ARGS=--no-registry   skip the GitHub Release lookup
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
cd "$REPO"

NO_REGISTRY=0
[[ "${1:-}" == "--no-registry" ]] && NO_REGISTRY=1

VERSION="$(bash "$HERE/version.sh" get)"
failures=0
note() { printf '  %s %s\n' "$1" "$2"; }

echo "Verify $VERSION"
echo

for app in nifi_monitoring nifi_TA_monitoring; do
    tarball="$app-$VERSION.tar.gz"
    if [[ ! -f "$tarball" ]]; then
        note "✗" "$tarball is missing — run \`make publish\`"
        failures=$((failures + 1))
        continue
    fi
    declared="$(tar -xzOf "$tarball" "$app/default/app.conf" 2>/dev/null \
                | grep -m1 '^version' | tr -d ' \r' | cut -d= -f2)"
    if [[ "$declared" == "$VERSION" ]]; then
        note "✓" "$tarball declares $declared"
    else
        note "✗" "$tarball declares '$declared', expected $VERSION"
        failures=$((failures + 1))
    fi
done

# The add-on is generated. These three exist only after ucc-gen has run, so
# their absence means the tree was packaged instead of output/.
echo
echo "The add-on is the generated one:"
tarball="nifi_TA_monitoring-$VERSION.tar.gz"
if [[ -f "$tarball" ]]; then
    # Listed once into a variable rather than piped per member: `grep -q` exits
    # on the first match, tar takes SIGPIPE, and under `set -o pipefail` the
    # pipeline then reports failure for a member that is present. This script
    # said the add-on had been packaged from the tree when it had not.
    members="$(tar -tzf "$tarball")"
    for member in default/restmap.conf README/inputs.conf.spec appserver/static/openapi.json; do
        if grep -q "nifi_TA_monitoring/$member" <<< "$members"; then
            note "✓" "$member"
        else
            note "✗" "$member is missing — the tree was packaged, not output/"
            failures=$((failures + 1))
        fi
    done
fi

if (( ! NO_REGISTRY )) && command -v gh >/dev/null 2>&1; then
    echo
    echo "Release:"
    if gh release view "$VERSION" >/dev/null 2>&1; then
        note "✓" "$VERSION is published"
    else
        note "·" "$VERSION is not released yet (expected before \`make release\`)"
    fi
fi

echo
if (( failures )); then
    echo "$failures problem(s)."
    exit 1
fi
echo "OK — the packages are what they claim to be."
