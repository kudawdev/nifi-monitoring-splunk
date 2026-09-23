#!/usr/bin/env bash
# kudaw-delivery: v1.8.0
# Confirm the artifacts for this version exist and are what they claim to be — every app
# the repo ships, since a release attaches them together.
#
# In the libreria profile, verify asks the registry. A Splunk app has no intermediate
# registry: what verify checks is that the .tar.gz was built, that the version INSIDE the
# package matches the manifest, and that the AppInspect gate came out green. That is what
# plays the part of staging — the rule that only verified code reaches main.
#
# Post-release it also confirms the GitHub Release carries the .tar.gz.
set -euo pipefail

NEEDS_MANIFEST=1
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_app.sh"
cd "$PROJECT_ROOT"

VERSION="$(read_version)"
failures=0
ok()  { printf '  \xe2\x9c\x93 %s\n' "$1"; }
bad() { printf '  \xe2\x9c\x97 %s\n' "$1"; failures=$((failures + 1)); }

printf 'verify — %s v%s\n' "$PRODUCT_LABEL" "$VERSION"

for i in "${!APP_NAMES[@]}"; do
    name="${APP_NAMES[$i]}" budget="${APP_BUDGETS[$i]}"
    TARBALL="$(artifact_path "$name" "$VERSION")"
    REPORT="$(appinspect_file "$name")"
    echo
    echo "$name:"

    if [[ ! -f "$TARBALL" ]]; then
        bad "missing $TARBALL — run: make package DRY_RUN=0"
        continue
    fi
    ok "artifact present: $TARBALL"

    # The version of the PACKAGED manifest, not the tree's: an old tarball under a new
    # name passes any check that only looks at the filename. Every stanza has to agree,
    # too — that is the failure `bump` exists to prevent, and it belongs in the gate. For
    # a generated add-on this is also what proves PRE_PACKAGE saw the bumped version.
    INNER="$(tar -xzOf "$TARBALL" "$name/default/app.conf" 2>/dev/null \
             | grep -E '^[[:space:]]*version[[:space:]]*=' \
             | awk -F= '{gsub(/[[:space:]\r]/,"");print $2}' | sort -u | tr '\n' ' ' | sed 's/ $//')"
    if [[ "$INNER" == "$VERSION" ]]; then
        ok "packaged app.conf: $INNER (every stanza agrees)"
    else
        bad "packaged app.conf says '${INNER:-nothing}', the manifest says '$VERSION'"
    fi

    if [[ -f "$REPORT" ]]; then
        read -r E F W <<<"$(jq -r '.summary | "\(.error) \(.failure) \(.warning)"' "$REPORT")"
        if (( E == 0 && F == 0 && W <= budget )); then
            ok "AppInspect: error=$E failure=$F warning=$W (budget $budget)"
        else
            bad "AppInspect outside budget: error=$E failure=$F warning=$W (budget $budget)"
        fi
    else
        bad "missing $REPORT — the artifact never went through the gate"
    fi
done

if command -v gh >/dev/null 2>&1 && gh release view "v${VERSION}" >/dev/null 2>&1; then
    echo
    attached="$(gh release view "v${VERSION}" --json assets -q '.assets[].name' 2>/dev/null || true)"
    for name in "${APP_NAMES[@]}"; do
        if grep -qxF "${name}-${VERSION}.tar.gz" <<< "$attached"; then
            ok "GitHub Release v$VERSION carries ${name}-${VERSION}.tar.gz"
        else
            bad "GitHub Release v$VERSION exists without ${name}-${VERSION}.tar.gz attached"
        fi
    done
fi

echo
if (( failures )); then
    echo "$failures problem(s). Do not promote until they are resolved."
    exit 1
fi
echo "OK — the v$VERSION artifacts are publishable."
