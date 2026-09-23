#!/usr/bin/env bash
# The artifact slot of the app-splunk profile, for `make publish`.
#
# A Splunk app has no registry to push to: the artifact IS the pair of .tar.gz
# that `make release` attaches to the GitHub Release, and Splunkbase is a
# manual upload afterwards. So "publishing" here means producing them and
# putting them through the same gate CI applies -- and then stopping, because
# there is nowhere further to push without a human.
#
# That makes the dry run and the real thing do the same work; what differs is
# what they say at the end, and that the real one refuses a dirty tree. A
# package built from uncommitted changes is code that lives in no commit.
#
#   publish.sh --dry-run    preview: build, package, validate, report
#   publish.sh              the same, and leave the packages for `make release`
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
cd "$REPO"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

VERSION="$(bash "$HERE/version.sh" get)"
APPS=(nifi_monitoring nifi_TA_monitoring)

if (( ! DRY_RUN )); then
    if [[ -n "$(git status --porcelain)" ]]; then
        echo "publish: the tree is dirty. The packages are built from the working" >&2
        echo "         tree, so this would ship code that is in no commit." >&2
        exit 1
    fi
    if gh release view "$VERSION" >/dev/null 2>&1; then
        echo "publish: $VERSION is already released. To correct it, bump; do not" >&2
        echo "         replace a version that has shipped." >&2
        exit 1
    fi
fi

echo "==> packaging and validating $VERSION"
make --no-print-directory validate

echo
echo "Ready to attach to the release:"
for app in "${APPS[@]}"; do
    printf '  %-22s %s\n' "$app-$VERSION.tar.gz" \
        "$(du -h "$app-$VERSION.tar.gz" | cut -f1)"
done

echo
if (( DRY_RUN )); then
    echo "Dry run: nothing was published. DRY_RUN=0 to keep the packages for"
    echo "\`make release\`, which is what attaches them."
else
    echo "The packages are in place. Next: \`make verify\`, then promote and release."
    echo "Splunkbase is a manual upload of these same two files, after the release."
fi
