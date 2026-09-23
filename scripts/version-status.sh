#!/usr/bin/env bash
# kudaw-delivery: v1.8.0
# Drift report for a Splunk app — informational, never blocks.
#
# Three coordinates that should agree and drift apart quietly:
#   manifest   what <app>/default/app.conf says, across every stanza
#   artifact   the .tar.gz built into dist/, one per app the repo ships
#   release    the last published tag, and whether this version's release carries the file
#
# `--no-registry` skips the GitHub calls, so it runs offline.
set -euo pipefail

NEEDS_MANIFEST=1
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_app.sh"
cd "$PROJECT_ROOT"

NO_REGISTRY=0
[[ "${1:-}" == "--no-registry" ]] && NO_REGISTRY=1

VERSION="$(read_version)"

printf 'Version status — %s\n\n' "$PRODUCT_LABEL"
printf '  manifest    %s  (%s)\n' "$VERSION" "$MANIFEST"

# app.conf declares version in [id] and in [launcher]: if they diverge the app installs
# with inconsistent metadata and no gate looks at it.
mapfile -t declared < <(grep -E '^[[:space:]]*version[[:space:]]*=' "$MANIFEST" \
                        | awk -F= '{gsub(/[[:space:]\r]/,"");print $2}' | sort -u)
if (( ${#declared[@]} == 1 )); then
    printf '  stanzas     all at %s\n' "${declared[0]}"
else
    printf '  stanzas     DIVERGE: %s  <- bump with `make bump`, not by hand\n' "${declared[*]}"
fi

for name in "${APP_NAMES[@]}"; do
    TARBALL="$(artifact_path "$name" "$VERSION")"
    if [[ -f "$TARBALL" ]]; then
        printf '  artifact    %s  (%s)\n' "$TARBALL" "$(du -h "$TARBALL" | cut -f1)"
    else
        printf '  artifact    %s not built  <- `make package DRY_RUN=0`\n' "$name"
    fi
done

if (( NO_REGISTRY )); then
    printf '  release     (skipped: --no-registry)\n'
    exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
    printf '  release     (gh not installed)\n'
    exit 0
fi

LATEST="$(gh release list --limit 1 --json tagName -q '.[0].tagName' 2>/dev/null || true)"
printf '  release     %s\n' "${LATEST:-none}"

if gh release view "v${VERSION}" >/dev/null 2>&1; then
    ASSETS="$(gh release view "v${VERSION}" --json assets -q '.assets[].name' 2>/dev/null | paste -sd' ' - || true)"
    printf '  v%s        published, attached: %s\n' "$VERSION" "${ASSETS:-NONE — RELEASE_ASSETS not set?}"
else
    printf '  v%s        unpublished\n' "$VERSION"
fi
