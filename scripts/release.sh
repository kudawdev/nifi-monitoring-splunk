#!/usr/bin/env bash
# kudaw-delivery: v1.3.0
# Tag a released version and publish its GitHub Release.
#
# Usage:
#   scripts/release.sh <version>
#
# Run this AFTER `promote.sh prod` has put the code on main. The tag is created
# on origin/main explicitly rather than on HEAD, so it always points at the
# production commit no matter which branch you happen to be on — tagging HEAD
# from develop produces a tag that names a commit which never shipped.
#
# The tag is ANNOTATED: it carries its own author and date, and plain
# `git describe` finds it. Lightweight tags are not a substitute.

set -euo pipefail

# Needs the manifest: the tag prefix and the origin/main version check both come from it.
NEEDS_MANIFEST=1
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
cd "$PROJECT_ROOT"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "Usage: scripts/release.sh <version>" >&2
    exit 2
fi
VERSION="${VERSION#v}"

# The tag prefix comes from the config: `v` for a single-artifact repo, and per package in
# a monorepo, where one `v0.3.1` could mean any of seven things. A package configured with
# `-` ships without a tag at all — its registry is the record — and there is nothing here
# for this command to do.
if [[ "${TAG_PREFIX:-v}" == "-" ]]; then
    echo "Package '$PKG_NAME' ships without a git tag (registry is the record)."
    echo "Nothing to release here — 'make publish' and 'make verify' are its delivery."
    exit 0
fi
TAG="${TAG_PREFIX:-v}${VERSION}"

# --- preconditions ------------------------------------------------------------

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    echo "Error: tag $TAG already exists locally. A released version is a promise" >&2
    echo "       about one immutable commit — bump instead of retagging." >&2
    exit 1
fi

echo "Fetching origin..."
git fetch origin --quiet --tags

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    echo "Error: tag $TAG already exists on origin." >&2
    exit 1
fi

# The version being tagged has to be the version that is actually on main.
# Catches the common ordering mistake: releasing before promoting.
MANIFEST="$(bash "$PROJECT_ROOT/scripts/version.sh" manifest)"
if ! git show "origin/main:$MANIFEST" 2>/dev/null | grep -qF "\"$VERSION\""; then
    echo "Error: $MANIFEST on origin/main does not carry version $VERSION." >&2
    echo "       Promote to main first (make promote-prod), then release." >&2
    exit 1
fi

# --- tag ----------------------------------------------------------------------

echo "Creating annotated tag $TAG on origin/main..."
git tag -a "$TAG" -m "Release $TAG" origin/main
echo "Pushing tag..."
git push origin "$TAG"

# --- GitHub Release -----------------------------------------------------------

if ! command -v gh >/dev/null 2>&1; then
    echo "Warning: gh not found — tag pushed, but no GitHub Release created." >&2
    exit 0
fi

NOTES_FILE="$(mktemp -t release-notes-XXXXXX.md)"
trap 'rm -f "$NOTES_FILE"' EXIT

# The CHANGELOG entry is the source, not a re-classification of the commits. Two
# generators of the same truth eventually disagree, and then nobody knows which to
# believe. `changelog.sh add` is what produced that entry, from release-notes.sh, so the
# fallback below is for a version released before this repo adopted the changelog.
if bash "$PROJECT_ROOT/scripts/changelog.sh" has "$VERSION"; then
    echo "Reading the release notes from CHANGELOG.md..."
    bash "$PROJECT_ROOT/scripts/changelog.sh" get "$VERSION" > "$NOTES_FILE"
else
    echo "Warning: CHANGELOG.md has no entry for $VERSION — generating the notes from" >&2
    echo "         the commit range instead. Run 'make changelog' to record the entry." >&2
    bash "$PROJECT_ROOT/scripts/release-notes.sh" "$VERSION" > "$NOTES_FILE"
fi

# --- the artifact ---------------------------------------------------------------
#
# For a profile whose deliverable IS the release — a Splunk app, a plugin, anything a
# human downloads from the Releases page — notes without the artifact are a release in
# name only. RELEASE_ASSETS declares what to attach; `${VERSION}` expands, and a glob is
# allowed. Attached in the SAME call that creates the release, so the release never exists
# without it: a two-step upload leaves a window where the page is live and empty, and
# people find it exactly then.
ASSETS=()
if [[ -n "${RELEASE_ASSETS:-}" ]]; then
    for pattern in $RELEASE_ASSETS; do
        expanded="${pattern//\$\{VERSION\}/$VERSION}"
        mapfile -t matches < <(compgen -G "$expanded" || true)
        if (( ${#matches[@]} == 0 )); then
            echo "Error: RELEASE_ASSETS declares '$expanded' and nothing matches it." >&2
            echo "       Build the artifact first; a release whose deliverable is the" >&2
            echo "       artifact must not be published empty. The tag is already pushed," >&2
            echo "       so build and re-run, or delete the tag." >&2
            exit 1
        fi
        ASSETS+=("${matches[@]}")
    done
    echo "Attaching: ${ASSETS[*]}"
fi

echo "Creating GitHub Release..."
gh release create "$TAG" --title "$TAG" --notes-file "$NOTES_FILE" ${ASSETS[@]+"${ASSETS[@]}"}

echo
echo "Released $TAG"
gh release view "$TAG" --json url -q .url
