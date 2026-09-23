#!/usr/bin/env bash
# kudaw-delivery: v1.3.0
# Everything that touches the project's version number, in one place.
#
# Usage:
#   scripts/version.sh get                       Print the current version
#   scripts/version.sh set <version>             Write an explicit version
#   scripts/version.sh bump <patch|minor|major>  Compute + write the next version
#   scripts/version.sh suggest [--level-only]    Suggest a bump level from the
#                                                Conventional Commits since the
#                                                last release
#   scripts/version.sh baseline                  Print the tag the "since last
#                                                release" range starts from
#   scripts/version.sh manifest                  Print the manifest path,
#                                                relative to the repo root
#
# `bump` and `set` only write the manifest — they never commit. The commit (and
# the decision of which level to apply) belongs to the caller.
#
# PARAMETERISATION POINT: none. What this repo contributes lives in `delivery.conf`
# and in scripts/manifest/<flavour>.sh. This file is identical in every repo.

set -euo pipefail

# Every command in here operates on a manifest, so in a monorepo PKG= is required.
NEEDS_MANIFEST=1
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"

# read_version / write_version come from the manifest flavour. The verification is here
# and not in the flavour: a flavour that forgot to re-read would report success on a
# write that silently did nothing.
set_version() {
    local new="$1" check
    write_version "$new"
    check="$(read_version)"
    if [[ "$check" != "$new" ]]; then
        echo "Error: wrote '$new' but manifest now reads '$check'" >&2
        return 1
    fi
}

# --- generic ------------------------------------------------------------------

# The baseline for "what changed since we last shipped".
#
# GitHub is the authority here, and `git describe` is NOT a valid substitute:
# release tags in this repo are created on `main`, on the merge commit produced
# by `promote prod`. Those commits never reach `develop`, so from `develop` the
# tags are not ancestors of HEAD and `git describe` walks straight past them to
# some far older tag. (Observed: v0.4.5 instead of v0.11.0.)
#
# A range like `$tag..HEAD` still works fine with a non-ancestor tag — it means
# "commits in HEAD that the tag does not have" — so only the tag *resolution*
# needs to come from gh.
#
# The offline fallback sorts by tag creation date, which is right for the normal
# sequential flow but can name a late out-of-order hotfix tag as "latest". When
# it is used, say so, so the caller can distrust the range.
last_release_tag() {
    local tag=""
    if command -v gh >/dev/null 2>&1; then
        tag="$(gh release view --json tagName -q .tagName 2>/dev/null || true)"
    fi
    if [[ -z "$tag" ]]; then
        tag="$(git -C "$PROJECT_ROOT" tag --sort=-creatordate | head -1 || true)"
        [[ -n "$tag" ]] && echo "Warning: gh unavailable; falling back to newest tag '$tag'" >&2
    fi
    printf '%s\n' "$tag"
}

compute_next() {
    local current="$1" level="$2"
    local major minor patch
    IFS='.' read -r major minor patch <<< "$current"
    if [[ ! "$major" =~ ^[0-9]+$ || ! "$minor" =~ ^[0-9]+$ || ! "$patch" =~ ^[0-9]+$ ]]; then
        echo "Error: '$current' is not a MAJOR.MINOR.PATCH version" >&2
        return 1
    fi
    case "$level" in
        major) printf '%d.0.0\n' "$((major + 1))" ;;
        minor) printf '%d.%d.0\n' "$major" "$((minor + 1))" ;;
        patch) printf '%d.%d.%d\n' "$major" "$minor" "$((patch + 1))" ;;
        *) echo "Error: level must be patch, minor or major (got '$level')" >&2; return 1 ;;
    esac
}

# Classify the commits since the baseline and print a suggested level.
# Deterministic on purpose: the caller presents this and asks the user to
# confirm, but nobody has to re-derive the classification by hand.
cmd_suggest() {
    local level_only=0
    [[ "${1:-}" == "--level-only" ]] && level_only=1

    local current tag range
    current="$(read_version)"
    tag="$(last_release_tag)"
    if [[ -n "$tag" ]]; then range="${tag}..HEAD"; else range="HEAD"; fi

    local n_breaking=0 n_feat=0 n_fix=0 n_other=0
    local -a driving=()

    local sha subject body
    while IFS= read -r sha; do
        [[ -z "$sha" ]] && continue
        subject="$(git -C "$PROJECT_ROOT" log -1 --format=%s "$sha")"
        body="$(git -C "$PROJECT_ROOT" log -1 --format=%b "$sha")"
        if [[ "$subject" =~ ^[a-zA-Z]+(\([^\)]*\))?! ]] \
           || grep -qiE '^BREAKING[ -]CHANGE:' <<< "$body"; then
            n_breaking=$((n_breaking + 1)); driving+=("breaking: $subject")
        elif [[ "$subject" =~ ^feat(\([^\)]*\))?: ]]; then
            n_feat=$((n_feat + 1)); driving+=("feat:     $subject")
        elif [[ "$subject" =~ ^(fix|perf)(\([^\)]*\))?: ]]; then
            n_fix=$((n_fix + 1))
        else
            n_other=$((n_other + 1))
        fi
    done < <(git -C "$PROJECT_ROOT" log --no-merges --format=%H "$range" 2>/dev/null || true)

    local total=$((n_breaking + n_feat + n_fix + n_other))

    # Pre-1.0 rule: while the public API is unstable (0.y.z), SemVer does not
    # force a breaking change to 1.0.0 — convention is to ship it as a minor.
    local pre_1_0=0
    [[ "$current" == 0.* ]] && pre_1_0=1

    local level
    if (( total == 0 )); then
        level="none"
    elif (( n_breaking > 0 )); then
        if (( pre_1_0 )); then level="minor"; else level="major"; fi
    elif (( n_feat > 0 )); then
        level="minor"
    else
        level="patch"
    fi

    if (( level_only )); then
        printf '%s\n' "$level"
        return 0
    fi

    echo "Current version:  $current$( ((pre_1_0)) && echo '  (pre-1.0)')"
    echo "Baseline:         ${tag:-<no release found>}"
    echo "Commits:          $total  (breaking: $n_breaking, feat: $n_feat, fix/perf: $n_fix, other: $n_other)"
    if [[ "$level" == "none" ]]; then
        echo "Suggested level:  none — nothing shippable since $tag"
        return 0
    fi
    echo "Suggested level:  $level  ->  $current -> $(compute_next "$current" "$level")"
    if (( n_breaking > 0 && pre_1_0 )); then
        echo "Note:             breaking changes present, but pre-1.0 ships them as a minor."
        echo "                  'major' (-> 1.0.0) is never suggested automatically."
    fi
    if ((${#driving[@]})); then
        echo "Driving commits:"
        printf '  %s\n' "${driving[@]:0:8}"
        (( ${#driving[@]} > 8 )) && echo "  ... and $(( ${#driving[@]} - 8 )) more"
    fi
}

usage() {
    # The header block, from the line after the shebang to the first blank line. Line
    # numbers were what broke the moment a seal line was inserted above.
    sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | grep -v '^# kudaw-delivery:' | sed 's/^# \?//'
}

main() {
    local cmd="${1:-}"; shift || true
    case "$cmd" in
        get)     read_version ;;
        set)     [[ $# -eq 1 ]] || { usage >&2; exit 2; }
                 set_version "$1"; echo "Version set to $1" ;;
        bump)    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
                 local cur next
                 cur="$(read_version)"
                 next="$(compute_next "$cur" "$1")"
                 set_version "$next"
                 echo "$cur -> $next" ;;
        suggest)  cmd_suggest "${1:-}" ;;
        baseline) last_release_tag ;;
        manifest) printf '%s\n' "$MANIFEST_REL" ;;
        ""|-h|--help|help) usage ;;
        *)       echo "Unknown command: $cmd" >&2; usage >&2; exit 2 ;;
    esac
}

main "$@"
