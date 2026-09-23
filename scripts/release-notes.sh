#!/usr/bin/env bash
# kudaw-delivery: v1.3.0
# Build categorised release notes from the Conventional Commits in a range.
#
# Usage:
#   scripts/release-notes.sh <version>     Notes for v<version>
#
# The notes go to stdout, ready for `gh release create --notes-file`.
#
# If the tag v<version> exists, the range is <previous tag>..v<version>. If it
# does not exist yet (preview, before tagging), the range is <last tag>..HEAD.
#
# This repo promotes by branch merges, not Pull Requests, so gh's
# --generate-notes only emits a compare link. Hence building the notes here.
#
# Resolving the start of the range takes two different answers, because release
# tags in this repo live on `main`:
#   * tag exists (we are on main's history) -> `git describe --tags --abbrev=0
#     <tag>^`, the nearest tag that is a real ANCESTOR. Taking the
#     highest-numbered tag instead breaks as soon as a release ships out of
#     order (a v0.10.2 hotfix cut after v0.11.0 was tagged).
#   * tag does not exist yet (preview from `develop`) -> ask
#     `version.sh baseline`, since main's tags are not ancestors of develop and
#     `git describe` would walk past them to a far older tag.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "Usage: scripts/release-notes.sh <version> [--preview]" >&2
    exit 2
fi
VERSION="${VERSION#v}"
TAG="v${VERSION}"

# --- resolve the range --------------------------------------------------------

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    HEAD_REF="$TAG"
    PREV="$(git describe --tags --abbrev=0 "${TAG}^" 2>/dev/null || true)"
else
    HEAD_REF="HEAD"
    PREV="$(bash "$PROJECT_ROOT/scripts/version.sh" baseline 2>/dev/null || true)"
fi

if [[ -n "$PREV" ]]; then RANGE="${PREV}..${HEAD_REF}"; else RANGE="$HEAD_REF"; fi

# --- collect and classify -----------------------------------------------------

declare -a BREAKING=() FEATURES=() SECURITY=() FIXES=() PERF=() \
           REFACTOR=() DOCS=() MAINT=() OTHER=()

# `- **scope**: description`, or `- description` when there is no scope.
entry() {
    local scope="$1" desc="$2"
    if [[ -n "$scope" ]]; then printf -- '- **%s**: %s\n' "$scope" "$desc"
    else printf -- '- %s\n' "$desc"; fi
}

while IFS= read -r sha; do
    [[ -z "$sha" ]] && continue
    subject="$(git log -1 --format=%s "$sha")"
    body="$(git log -1 --format=%b "$sha")"

    type="" scope="" bang="" desc="$subject"
    if [[ "$subject" =~ ^([a-zA-Z]+)(\(([^\)]*)\))?(!)?:[[:space:]]*(.*)$ ]]; then
        type="${BASH_REMATCH[1],,}"
        scope="${BASH_REMATCH[3]}"
        bang="${BASH_REMATCH[4]}"
        desc="${BASH_REMATCH[5]}"
    fi

    if [[ -n "$bang" ]] || grep -qiE '^BREAKING[ -]CHANGE:' <<< "$body"; then
        BREAKING+=("$(entry "$scope" "$desc")")
    elif [[ "$scope" == "security" ]]; then
        SECURITY+=("$(entry "" "$desc")")
    else
        case "$type" in
            feat)                   FEATURES+=("$(entry "$scope" "$desc")") ;;
            fix)                    FIXES+=("$(entry "$scope" "$desc")") ;;
            perf)                   PERF+=("$(entry "$scope" "$desc")") ;;
            refactor)               REFACTOR+=("$(entry "$scope" "$desc")") ;;
            docs)                   DOCS+=("$(entry "$scope" "$desc")") ;;
            chore|build|ci|test|style) MAINT+=("$type") ;;
            *)                      OTHER+=("$(entry "" "$subject")") ;;
        esac
    fi
done < <(git log --no-merges --format=%H "$RANGE" 2>/dev/null || true)

# --- emit ---------------------------------------------------------------------

section() {
    local heading="$1"; shift
    (( $# == 0 )) && return 0
    printf '## %s\n\n' "$heading"
    printf '%s\n' "$@"
    printf '\n'
}

section '⚠️ Breaking Changes' "${BREAKING[@]}"
section '✨ Features'          "${FEATURES[@]}"
section '🔒 Security'          "${SECURITY[@]}"
section '🐛 Fixes'             "${FIXES[@]}"
section '⚡ Performance'       "${PERF[@]}"
section '♻️ Refactors'         "${REFACTOR[@]}"
section '📝 Docs'              "${DOCS[@]}"

# Maintenance is noise in bulk: list it while short, collapse to per-type counts
# once it grows past what a reader will actually scan.
if (( ${#MAINT[@]} > 0 )); then
    printf '## 🔧 Maintenance\n\n'
    if (( ${#MAINT[@]} <= 8 )); then
        printf '%s\n' "${MAINT[@]}" | sort | uniq -c \
            | while read -r n t; do printf -- '- %s: %s commit(s)\n' "$t" "$n"; done
    else
        summary="$(printf '%s\n' "${MAINT[@]}" | sort | uniq -c \
                   | awk '{printf "%s%s: %s", sep, $2, $1; sep=", "}')"
        printf -- '- %s commits — %s\n' "${#MAINT[@]}" "$summary"
    fi
    printf '\n'
fi

section '📦 Other' "${OTHER[@]}"

if [[ -n "$PREV" ]]; then
    SLUG="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
    if [[ -z "$SLUG" ]]; then
        SLUG="$(git remote get-url origin 2>/dev/null \
                | sed -E 's#^.*[:/]([^/]+/[^/]+?)(\.git)?$#\1#' || true)"
    fi
    if [[ -n "$SLUG" ]]; then
        printf '**Full Changelog**: https://github.com/%s/compare/%s...%s\n' \
               "$SLUG" "$PREV" "$TAG"
    fi
fi
