#!/usr/bin/env bash
# Version / release / artifact drift, for `make status`. Informational: it
# reports and exits 0, even when everything disagrees. Deciding whether a drift
# matters is the caller's job, and the delivery skill's.
#
# This one is the repo's, not sealed: the contract cannot know what "published"
# means for a given profile. Here the artifact is a GitHub Release with both
# .tar.gz attached, so that is what it looks for.
#
#   ARGS=--no-registry   skip everything that needs the network
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
cd "$REPO"

NO_REGISTRY=0
[[ "${1:-}" == "--no-registry" ]] && NO_REGISTRY=1

VERSION="$(bash "$HERE/version.sh" get)"
BASELINE="$(bash "$HERE/version.sh" baseline 2>/dev/null || echo "-")"

say() { printf '  %-22s %s\n' "$1" "$2"; }

echo "Status — NiFi Monitoring for Splunk"
echo
say "local version" "$VERSION"
say "last release" "$BASELINE"

# The two apps ship on the same version and main.yml fails the build when they
# do not, so a drift here is worth seeing before anything else.
ta_version="$(python3 -c "import json;print(json.load(open('nifi_TA_monitoring/globalConfig.json'))['meta']['version'])" 2>/dev/null || echo "?")"
manifest_version="$(python3 -c "import json;print(json.load(open('nifi_TA_monitoring/package/app.manifest'))['info']['id']['version'])" 2>/dev/null || echo "?")"
if [[ "$ta_version" == "$VERSION" && "$manifest_version" == "$VERSION" ]]; then
    say "add-on derivations" "in step"
else
    say "add-on derivations" "DRIFT — globalConfig $ta_version, app.manifest $manifest_version"
    echo "                         run \`make version-sync\`"
fi

echo
echo "Working tree:"
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
dirty="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
say "branch" "$branch$([[ "$branch" == "main" ]] && echo '  — not a working branch')"
say "uncommitted" "$dirty file(s)"
if [[ "$BASELINE" != "-" ]]; then
    say "commits since $BASELINE" "$(git rev-list --count "$BASELINE"..HEAD 2>/dev/null || echo '?')"
fi

echo
echo "Packages:"
for app in nifi_monitoring nifi_TA_monitoring; do
    if [[ -f "$app-$VERSION.tar.gz" ]]; then
        say "$app" "built ($(du -h "$app-$VERSION.tar.gz" | cut -f1))"
    else
        say "$app" "not built — \`make package\`"
    fi
done

if (( NO_REGISTRY )); then
    echo
    echo "Release: skipped (--no-registry)"
    exit 0
fi

echo
echo "Release:"
if ! command -v gh >/dev/null 2>&1; then
    say "gh" "not installed; cannot check"
    exit 0
fi
if gh release view "$VERSION" >/dev/null 2>&1; then
    assets="$(gh release view "$VERSION" --json assets \
              --jq '[.assets[].name] | join(", ")' 2>/dev/null)"
    say "$VERSION" "published"
    say "assets" "${assets:-none attached}"
else
    say "$VERSION" "not released yet"
fi
