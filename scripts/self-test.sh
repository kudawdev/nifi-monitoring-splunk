#!/usr/bin/env bash
# kudaw-delivery: v1.3.0
# Level 2 of the contract's validation: do the deterministic targets do what they say?
#
# Usage:
#   scripts/self-test.sh
#
# Level 1 (contract-check) asserts that `make bump` exists. This asserts that it writes
# the version it claims and leaves the tree exactly as it found it. Read-only except for
# one bump that is undone and verified byte-for-byte.
#
# It refuses to run on a dirty manifest: it cannot promise to restore what it did not
# write.

set -euo pipefail

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"

# In a monorepo any package proves the round trip, so pick the first instead of making
# the caller choose. Re-sourced with PKG exported, so the version.sh calls below see it.
if [[ -z "$MANIFEST_REL" && -n "${PACKAGES:-}" ]]; then
    PKG="$(awk 'NF {print $1; exit}' <<< "$PACKAGES")"
    export PKG
    NEEDS_MANIFEST=1
    # shellcheck source=/dev/null
    source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
    echo "Monorepo: testing the round trip on '$PKG' (PKG= to pick another)."
fi
cd "$PROJECT_ROOT"

pass=0; fail=0
ok()   { printf '  ✓ %s\n' "$1"; pass=$((pass + 1)); }
bad()  { printf '  ✗ %s\n' "$1"; fail=$((fail + 1)); }

echo "Self-test — $PRODUCT_LABEL ($MANIFEST_FLAVOUR)"
echo

if [[ -n "$(git status --porcelain "$MANIFEST_REL")" ]]; then
    echo "Error: $MANIFEST_REL has uncommitted changes; refusing to touch it." >&2
    exit 2
fi

echo "Version:"
before="$(bash scripts/version.sh get)"
if [[ "$before" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    ok "get -> $before (MAJOR.MINOR.PATCH)"
else
    bad "get -> '$before' is not a SemVer triple"
fi

# The round trip: bump, confirm the write landed, put it back, confirm byte equality.
expected="$(awk -F. '{printf "%d.%d.%d", $1, $2, $3 + 1}' <<< "$before")"
bash scripts/version.sh bump patch >/dev/null
after="$(bash scripts/version.sh get)"
[[ "$after" == "$expected" ]] && ok "bump patch -> $expected" \
                              || bad "bump patch -> '$after', expected '$expected'"
bash scripts/version.sh set "$before" >/dev/null
[[ "$(bash scripts/version.sh get)" == "$before" ]] && ok "set restores $before" \
                                                    || bad "set did not restore $before"
if [[ -z "$(git status --porcelain "$MANIFEST_REL")" ]]; then
    ok "the manifest is byte-identical to where it started"
else
    bad "the round trip left $MANIFEST_REL modified — the writer is not reversible"
    git --no-pager diff -- "$MANIFEST_REL" >&2
fi

[[ "$(bash scripts/version.sh manifest)" == "$MANIFEST_REL" ]] \
    && ok "manifest -> $MANIFEST_REL" || bad "manifest does not report $MANIFEST_REL"

echo
echo "Baseline and classification:"
baseline="$(bash scripts/version.sh baseline 2>/dev/null || true)"
if [[ -n "$baseline" ]]; then
    ok "baseline -> $baseline"
else
    ok "baseline -> none (no release yet; valid for a repo that has not shipped)"
fi
level="$(bash scripts/version.sh suggest --level-only)"
case "$level" in
    none|patch|minor|major) ok "suggest --level-only -> $level" ;;
    *) bad "suggest --level-only -> '$level', not one of none/patch/minor/major" ;;
esac

echo
echo "Release notes:"
if bash scripts/release-notes.sh "$before" >/dev/null 2>&1; then
    ok "release-notes runs for $before"
else
    bad "release-notes failed for $before"
fi
if bash scripts/changelog.sh has "$before"; then
    ok "the CHANGELOG has an entry for $before"
else
    ok "no CHANGELOG entry for $before yet (expected before its \`changelog\` runs)"
fi

echo
echo "$pass passed, $fail failed."
(( fail == 0 ))
