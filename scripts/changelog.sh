#!/usr/bin/env bash
# kudaw-delivery: v1.8.0
# The CHANGELOG.md: the versioned history of releases, and the source the GitHub Release
# notes are published from.
#
# Usage:
#   scripts/changelog.sh add <version>    Insert (or replace) the entry, then commit
#   scripts/changelog.sh get <version>    Print the entry body for <version>
#   scripts/changelog.sh has <version>    Exit 0 if an entry for <version> exists
#
# `add` reads an optional TITLE from the environment: TITLE="what shipped" ... add 0.12.0
#
# ONE CLASSIFIER: the entry body comes from release-notes.sh, and `release.sh` publishes
# what lands HERE rather than re-classifying the commits. Two generators of the same truth
# eventually disagree, and then nobody knows which one to believe.
#
# `add` is idempotent: re-running it for a version rewrites that entry in place, so a bump
# that gets amended does not leave two entries for the same version.
#
# `add` also COMMITS the manifest and the CHANGELOG together, because the contract makes
# that one action: a version that reaches a release without its entry is a hole nobody
# backfills. It commits those two paths only — anything else staged stays staged — and it
# does NOT push. Pushing belongs to the promotion, and to nothing else. NO_COMMIT=1 writes
# the file and stops, for a caller that wants to inspect before committing.

set -euo pipefail

# Every command in here operates on a manifest, so in a monorepo PKG= is required.
NEEDS_MANIFEST=1
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
cd "$PROJECT_ROOT"

# One CHANGELOG per shipped artifact: at the repo root for a single-artifact repo, and
# beside the package's manifest in a monorepo — the same place its consumers look.
if [[ -n "$PKG_NAME" ]]; then
    CHANGELOG="$(dirname "$MANIFEST")/CHANGELOG.md"
else
    CHANGELOG="$PROJECT_ROOT/CHANGELOG.md"
fi

# Where a new entry goes: right before the first `## ` heading, so entries stay
# newest-first and whatever preamble the file carries is kept verbatim. Computed, not
# assumed: hardcoding a header length breaks the splice the day someone edits the preamble.
header_lines() {
    local first
    first="$(grep -nE '^## ' "$CHANGELOG" 2>/dev/null | head -1 | cut -d: -f1 || true)"
    if [[ -n "$first" ]]; then printf '%s\n' "$((first - 1))"
    else wc -l < "$CHANGELOG"; fi
}

usage() {
    # The header block, from the line after the shebang to the first blank line. Line
    # numbers were what broke the moment a seal line was inserted above.
    sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | grep -v '^# kudaw-delivery:' | sed 's/^# \?//'
}

# The date of a release is the date its tag was created; an unreleased version is today.
entry_date() {
    local tag="v$1" d=""
    d="$(git log -1 --format=%as "$tag" 2>/dev/null || true)"
    [[ -z "$d" ]] && d="$(date +%F)"
    printf '%s\n' "$d"
}

# Line number of the `## <version>` heading, empty if absent. The `|| true` is load-
# bearing: no match makes grep exit 1, and under `pipefail` that would abort the caller's
# assignment instead of reading as "not there".
entry_line() {
    grep -nE "^## $1( |$)" "$CHANGELOG" 2>/dev/null | head -1 | cut -d: -f1 || true
}

cmd_has() {
    [[ -f "$CHANGELOG" ]] || return 1
    [[ -n "$(entry_line "$1")" ]]
}

cmd_get() {
    local version="$1" start end
    start="$(entry_line "$version")"
    if [[ -z "$start" ]]; then
        echo "Error: no CHANGELOG entry for $version" >&2
        return 1
    fi
    # From the line after the heading to the line before the next `## ` heading (or EOF).
    end="$(awk -v s="$start" 'NR>s && /^## / {print NR-1; exit}' "$CHANGELOG")"
    [[ -z "$end" ]] && end="$(wc -l < "$CHANGELOG")"
    sed -n "$((start + 1)),${end}p" "$CHANGELOG" \
        | sed -e '/./,$!d' \
        | awk 'BEGIN{blank=0} {if ($0=="") blank++; else blank=0; if (blank<2) print}'
}

cmd_add() {
    local version="$1"
    local title="${TITLE:-}"
    local date body heading tmp

    date="$(entry_date "$version")"
    heading="## $version — $date"
    [[ -n "$title" ]] && heading="$heading — $title"

    # The sections come out of release-notes.sh as `## ...`; inside an entry whose version
    # is already an `##`, they belong one level down.
    body="$(bash "$PROJECT_ROOT/scripts/release-notes.sh" "$version" | sed -E 's/^## /### /')"
    if [[ -z "$body" ]]; then
        echo "Error: release-notes.sh produced nothing for $version — no commits in range?" >&2
        return 1
    fi

    if [[ ! -f "$CHANGELOG" ]]; then
        local slug releases
        slug="$(repo_slug)"
        releases="https://github.com/${slug:-kudawdev}/releases"
        cat > "$CHANGELOG" <<HEAD
# Changelog

Historial de releases del $PRODUCT_LABEL. Las notas de cada GitHub Release se publican
desde este archivo; el formato de las secciones lo produce \`scripts/release-notes.sh\`.

Arranca en $version: las releases anteriores viven en los
[GitHub Releases]($releases). Para incorporar una,
\`scripts/changelog.sh add <version>\`.

HEAD
    fi

    tmp="$(mktemp)"

    local start end
    start="$(entry_line "$version")"
    if [[ -n "$start" ]]; then
        # Replace in place: keep everything before the heading and after the entry.
        end="$(awk -v s="$start" 'NR>s && /^## / {print NR-1; exit}' "$CHANGELOG")"
        [[ -z "$end" ]] && end="$(wc -l < "$CHANGELOG")"
        head -n "$((start - 1))" "$CHANGELOG" > "$tmp"
        { printf '%s\n\n%s\n\n' "$heading" "$body"; } >> "$tmp"
        tail -n +"$((end + 1))" "$CHANGELOG" >> "$tmp"
        echo "Rewrote the $version entry."
    else
        # New entry: newest first, right before the existing ones.
        local hl
        hl="$(header_lines)"
        head -n "$hl" "$CHANGELOG" > "$tmp"
        { printf '%s\n\n%s\n\n' "$heading" "$body"; } >> "$tmp"
        tail -n +"$((hl + 1))" "$CHANGELOG" >> "$tmp"
        echo "Added the $version entry."
    fi

    # Collapse the runs of blank lines the splicing can leave behind.
    awk 'BEGIN{blank=0} {if ($0=="") blank++; else blank=0; if (blank<2) print}' "$tmp" \
        > "$CHANGELOG"
    rm -f "$tmp"
    printf '%s\n' "${CHANGELOG#"$PROJECT_ROOT/"}"

    [[ -n "${NO_COMMIT:-}" ]] && return 0
    commit_entry "$version"
}

# Manifest + CHANGELOG in one commit. Scoped to those paths with `git commit -- ...`, so a
# caller who happens to have other work staged does not ship it by accident. Plus whatever
# POST_BUMP re-derived from the manifest, which `bump` recorded: a derived copy of the
# version left out of this commit is the inconsistency POST_BUMP exists to prevent.
commit_entry() {
    local version="$1" scope="" msg
    [[ -n "$PKG_NAME" ]] && scope="($PKG_NAME)"
    msg="chore${scope}: bump version to ${version} + changelog"

    local -a paths=("$MANIFEST_REL" "${CHANGELOG#"$PROJECT_ROOT/"}")
    local record derived
    record="$(post_bump_record)"
    if [[ -s "$record" ]]; then
        while IFS= read -r derived; do
            [[ -n "$(git status --porcelain -- "$derived")" ]] && paths+=("$derived")
        done < "$record"
    fi
    if [[ -z "$(git status --porcelain -- "${paths[@]}")" ]]; then
        echo "Nothing to commit: the manifest and the CHANGELOG are already committed."
        return 0
    fi
    git add -- "${paths[@]}"
    git commit -q -m "$msg" -- "${paths[@]}"
    rm -f "$record"
    echo "Committed: $msg"
    (( ${#paths[@]} > 2 )) && printf '  with what POST_BUMP re-derived: %s\n' "${paths[*]:2}"
    echo "Not pushed — the push belongs to the promotion."
}

main() {
    local cmd="${1:-}"; shift || true
    case "$cmd" in
        add) [[ $# -eq 1 ]] || { usage >&2; exit 2; }; cmd_add "${1#v}" ;;
        get) [[ $# -eq 1 ]] || { usage >&2; exit 2; }; cmd_get "${1#v}" ;;
        has) [[ $# -eq 1 ]] || { usage >&2; exit 2; }; cmd_has "${1#v}" ;;
        ""|-h|--help|help) usage ;;
        *) echo "Unknown command: $cmd" >&2; usage >&2; exit 2 ;;
    esac
}

main "$@"
